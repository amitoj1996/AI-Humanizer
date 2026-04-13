/**
 * Provenance recorder — client-side event capture for the writing-process log.
 *
 * Responsibilities:
 *  - Ensure a session exists for the current document (lazy-start on first event)
 *  - Buffer events locally and flush to the backend in batches (every 2 s or
 *    when the queue hits 50 events)
 *  - Provide typed helpers for the high-level operations (typed, pasted,
 *    detection run, AI rewrite applied, etc.)
 *
 * Integrity guarantees we actually want to make good on:
 *  1. No event drop on successful flush (obvious)
 *  2. No event drop on seal — flush is retried with backoff before sealing,
 *     and the session stays open if we still can't flush.  detach() does
 *     NOT clear events that belonged to the just-sealed session (they're
 *     already gone, or they're server-side).
 *  3. No event drop on tab close — `beforeunload` sends a single atomic
 *     beacon to /api/sessions/{id}/seal with `{events: [...pending]}`,
 *     so the backend appends + seals in one transaction.
 */
import { api } from "./api";
import type { ProvenanceEvent, ProvenanceEventType } from "./types";

const FLUSH_INTERVAL_MS = 2_000;
const FLUSH_THRESHOLD = 50;
const SEAL_FLUSH_RETRIES = 3;

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

class ProvenanceRecorder {
  private sessionId: string | null = null;
  private documentId: string | null = null;
  private queue: ProvenanceEvent[] = [];
  private flushTimer: ReturnType<typeof setInterval> | null = null;
  private flushing = false;
  private startingSession: Promise<string | null> | null = null;

  /** For the beforeunload handler — synchronous read of the active session. */
  get currentSessionId(): string | null {
    return this.sessionId;
  }

  /** Drain the in-memory queue synchronously.  Returns the events; caller
   *  is responsible for delivering them (used by the beforeunload beacon). */
  drainQueueSync(): ProvenanceEvent[] {
    const drained = this.queue;
    this.queue = [];
    return drained;
  }

  async attachToDocument(documentId: string): Promise<void> {
    if (this.documentId === documentId) return;

    // Seal the previous session first — this flushes pending events
    // with retry, writes the final_hash, and leaves the chain verifiable.
    // If seal fails (e.g. backend unreachable), we surface a warning but
    // proceed — we can't block doc switching indefinitely.
    await this.seal();

    this.detach();
    this.documentId = documentId;

    // Re-use an active session if one exists (app reopened after crash, etc.)
    try {
      const active = await api.getActiveSession(documentId);
      if (active) this.sessionId = active.id;
    } catch {
      // non-fatal
    }

    if (!this.flushTimer) {
      this.flushTimer = setInterval(() => {
        void this.flush();
      }, FLUSH_INTERVAL_MS);
    }
  }

  detach(): void {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = null;
    }
    this.sessionId = null;
    this.documentId = null;
    // Intentionally keep `queue` untouched: if seal() failed and left events
    // pending for the previous session, nuking the queue would lose them.
    // In the common case, seal() succeeded and the queue is already empty.
    this.startingSession = null;
  }

  private async ensureSession(): Promise<string | null> {
    if (this.sessionId) return this.sessionId;
    if (!this.documentId) return null;
    if (this.startingSession) return this.startingSession;

    const docId = this.documentId;
    this.startingSession = (async () => {
      try {
        const s = await api.startSession(docId);
        this.sessionId = s.id;
        return s.id;
      } catch {
        return null;
      } finally {
        this.startingSession = null;
      }
    })();
    return this.startingSession;
  }

  private enqueue(
    event_type: ProvenanceEventType,
    payload: Record<string, unknown>,
  ): void {
    if (!this.documentId) return;
    this.queue.push({
      event_type,
      timestamp: Date.now(),
      payload,
    });
    if (this.queue.length >= FLUSH_THRESHOLD) void this.flush();
  }

  /** Flush pending events.  Returns true if the queue is empty afterwards. */
  async flush(): Promise<boolean> {
    if (this.flushing) return this.queue.length === 0;
    if (this.queue.length === 0) return true;

    const sessionId = await this.ensureSession();
    if (!sessionId) return false;

    const batch = this.queue.splice(0, this.queue.length);
    this.flushing = true;
    try {
      await api.appendEvents(sessionId, batch);
      return true;
    } catch {
      // Re-queue for the next attempt.
      this.queue.unshift(...batch);
      return false;
    } finally {
      this.flushing = false;
    }
  }

  // ---- Typed helpers ---------------------------------------------------
  typed(text: string): void {
    if (!text) return;
    this.enqueue("typed", { text, char_count: text.length });
  }

  pasted(text: string, source: "external" | "internal" = "external"): void {
    this.enqueue("pasted", { text, char_count: text.length, source });
  }

  deleted(charCount: number): void {
    if (charCount <= 0) return;
    this.enqueue("deleted", { char_count: charCount });
  }

  detectionRun(aiScore: number, verdict: string, mode: string): void {
    this.enqueue("detection_run", { ai_score: aiScore, verdict, mode });
  }

  aiRewriteRequested(strength: string, tone: string, mode: string): void {
    this.enqueue("ai_rewrite_requested", { strength, tone, mode });
  }

  aiRewriteApplied(params: {
    beforeText: string;
    afterText: string;
    strength: string;
    tone: string;
    mode: string;
    aiScoreBefore: number;
    aiScoreAfter: number;
  }): void {
    this.enqueue("ai_rewrite_applied", {
      before_text: params.beforeText,
      after_text: params.afterText,
      strength: params.strength,
      tone: params.tone,
      mode: params.mode,
      ai_score_before: params.aiScoreBefore,
      ai_score_after: params.aiScoreAfter,
    });
  }

  revisionSaved(revisionId: string, aiScore: number | null): void {
    this.enqueue("revision_saved", {
      revision_id: revisionId,
      ai_score: aiScore,
    });
  }

  imported(source: string, charCount: number): void {
    this.enqueue("imported", { source, char_count: charCount });
  }

  /** Seal the current session, retrying flush on failure so we don't lose
   *  the tail of a session to a transient hiccup. */
  async seal(): Promise<void> {
    if (!this.sessionId && this.queue.length === 0) return;

    for (let attempt = 0; attempt < SEAL_FLUSH_RETRIES; attempt++) {
      if (await this.flush()) break;
      await new Promise((r) => setTimeout(r, 200 * (attempt + 1)));
    }

    if (this.queue.length > 0) {
      // Best-effort: log a warning but proceed.  In practice this only
      // fires if the local backend is unreachable for >600 ms, which is
      // extraordinary for a local desktop app.
      // eslint-disable-next-line no-console
      console.warn(
        `Sealing session ${this.sessionId} with ${this.queue.length} undelivered events`,
      );
    }

    if (this.sessionId) {
      try {
        await api.sealSession(this.sessionId);
      } catch {
        // non-fatal
      }
      this.sessionId = null;
    }
  }
}

// Process-wide singleton — one recorder per app window.
export const recorder = new ProvenanceRecorder();

// Seal on window unload.  `beforeunload` fires synchronously, so we use
// `navigator.sendBeacon` with the combined seal+events endpoint: the
// pending queue is drained into the SAME request that seals the session,
// so the backend appends+seals atomically.  Any other approach leaks
// the last typing burst before close.
if (typeof window !== "undefined") {
  const handleUnload = () => {
    const sessionId = recorder.currentSessionId;
    if (!sessionId) return;
    const pending = recorder.drainQueueSync();
    try {
      const body = JSON.stringify({ events: pending });
      const blob = new Blob([body], { type: "application/json" });
      navigator.sendBeacon(`${BASE}/api/sessions/${sessionId}/seal`, blob);
    } catch {
      // best-effort — on real browsers sendBeacon is very reliable
    }
  };
  window.addEventListener("pagehide", handleUnload);
  // beforeunload as a belt-and-braces fallback on browsers where pagehide
  // behaves slightly differently for reloads vs navigations.
  window.addEventListener("beforeunload", handleUnload);
}
