/**
 * Provenance recorder — client-side event capture for the writing-process log.
 *
 * Responsibilities:
 *  - Ensure a session exists for the current document (lazy-start on first event)
 *  - Buffer events locally and flush to the backend in batches (every 2s or
 *    when the queue hits 50 events)
 *  - Provide typed helpers for the high-level operations (typed, pasted,
 *    detection run, AI rewrite applied, etc.)
 *
 * Design trade-offs:
 *  - We let the server compute the hash chain.  The client never sends
 *    prev_hash / self_hash, which keeps the client logic simple and the
 *    chain tamper-evidence server-authoritative.
 *  - If the app closes mid-session we lose ≤ 2s of unsent events.  Acceptable
 *    for v1; revisit if users demand it.
 */
import { api } from "./api";
import type { ProvenanceEvent, ProvenanceEventType } from "./types";

const FLUSH_INTERVAL_MS = 2_000;
const FLUSH_THRESHOLD = 50;

class ProvenanceRecorder {
  private sessionId: string | null = null;
  private documentId: string | null = null;
  private queue: ProvenanceEvent[] = [];
  private flushTimer: ReturnType<typeof setInterval> | null = null;
  private flushing = false;
  private startingSession: Promise<string | null> | null = null;

  /** Exposed for the beforeunload handler, which needs to pick up the
   *  active session synchronously to send a beacon. */
  get currentSessionId(): string | null {
    return this.sessionId;
  }

  async attachToDocument(documentId: string): Promise<void> {
    if (this.documentId === documentId) return;
    // Seal the previous session before swapping — flushes pending events,
    // writes the final_hash, and marks the session as ended.  Leaves the
    // previous chain permanently verifiable.
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
    this.queue = [];
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

  async flush(): Promise<void> {
    if (this.flushing) return;
    if (this.queue.length === 0) return;

    const sessionId = await this.ensureSession();
    if (!sessionId) return;  // still no doc selected — keep queued

    const batch = this.queue.splice(0, this.queue.length);
    this.flushing = true;
    try {
      await api.appendEvents(sessionId, batch);
    } catch {
      // Put them back for the next attempt
      this.queue.unshift(...batch);
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

  async seal(): Promise<void> {
    await this.flush();
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

// Seal on window unload so closing the app / reloading the tab always ends
// the current session cleanly.  We use `sendBeacon` via a keepalive fetch
// to the seal endpoint — regular fetch() promises don't survive `beforeunload`.
if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", () => {
    const sessionId = recorder.currentSessionId;
    if (!sessionId) return;
    try {
      const url = `${
        process.env.NEXT_PUBLIC_API_BASE ?? ""
      }/api/sessions/${sessionId}/seal`;
      // Blob body so sendBeacon sends as POST with JSON content-type
      const blob = new Blob(["{}"], { type: "application/json" });
      navigator.sendBeacon(url, blob);
    } catch {
      // non-fatal
    }
  });
}
