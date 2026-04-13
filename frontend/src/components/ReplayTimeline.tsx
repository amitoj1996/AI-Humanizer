"use client";

import { useEffect, useMemo, useState } from "react";

import { api } from "../lib/api";
import type { ReplayData, ReplaySnapshot } from "../lib/types";
import { useDocumentsStore } from "../store/documents";

function formatTime(ms: number): string {
  return new Date(ms).toLocaleString();
}

function kindLabel(kind: string): string {
  return kind
    .split("+")
    .map((k) =>
      k === "revision" ? "Revision" : k === "ai_rewrite" ? "AI Rewrite" : k,
    )
    .join(" + ");
}

function kindColor(kind: string): string {
  if (kind.includes("ai_rewrite")) return "bg-purple-500";
  return "bg-emerald-500";
}

type FetchState =
  | { status: "idle" }
  | { status: "ready"; documentId: string; data: ReplayData }
  | { status: "error"; documentId: string };

export function ReplayTimeline() {
  const { currentDocumentId } = useDocumentsStore();
  const [state, setState] = useState<FetchState>({ status: "idle" });
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!currentDocumentId) return;
    let cancelled = false;
    api
      .getReplay(currentDocumentId)
      .then((d) => {
        if (cancelled) return;
        setState({ status: "ready", documentId: currentDocumentId, data: d });
        setIndex(Math.max(0, d.snapshots.length - 1));
      })
      .catch(() => {
        if (!cancelled)
          setState({ status: "error", documentId: currentDocumentId });
      });
    return () => {
      cancelled = true;
    };
  }, [currentDocumentId]);

  // "Stale" = the fetched data is for a different doc than the one we now
  // have selected.  Treated as loading so the previous doc's content doesn't
  // briefly flash before the new fetch resolves.
  const isStale =
    state.status !== "idle" && state.documentId !== currentDocumentId;
  const data =
    state.status === "ready" && !isStale ? state.data : null;

  const snapshot: ReplaySnapshot | null = useMemo(() => {
    if (!data || data.snapshots.length === 0) return null;
    return data.snapshots[Math.min(index, data.snapshots.length - 1)];
  }, [data, index]);

  if (state.status === "idle" || isStale) {
    return <p className="text-sm text-zinc-500">Loading replay…</p>;
  }
  if (state.status === "error" || !data || data.snapshots.length === 0) {
    return (
      <p className="text-sm text-zinc-500">
        No replay snapshots yet — save a revision or run a humanize to populate
        the writing history.
      </p>
    );
  }

  const totalMs = data.totals.span_ms;
  const first = data.snapshots[0];
  const current = snapshot ?? first;
  const sessionDuration =
    totalMs < 60_000
      ? `${Math.round(totalMs / 1000)}s`
      : totalMs < 3_600_000
      ? `${Math.round(totalMs / 60_000)}m`
      : `${(totalMs / 3_600_000).toFixed(1)}h`;

  return (
    <div className="space-y-3">
      {/* Summary */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-zinc-500 font-medium">
          {data.snapshots.length} snapshots · {data.totals.revisions} revisions ·{" "}
          span {sessionDuration}
        </p>
        <span className="text-xs text-zinc-500">
          Frame {index + 1}/{data.snapshots.length}
        </span>
      </div>

      {/* Scrubber */}
      <input
        type="range"
        min={0}
        max={data.snapshots.length - 1}
        value={index}
        onChange={(e) => setIndex(parseInt(e.target.value, 10))}
        className="w-full accent-blue-500"
      />

      {/* Tick marks with event-type colours */}
      <div className="flex gap-px">
        {data.snapshots.map((s, i) => (
          <button
            key={`${s.source_id}-${i}`}
            onClick={() => setIndex(i)}
            title={`${kindLabel(s.kind)} — ${formatTime(s.timestamp)}`}
            className={`flex-1 h-2 rounded-sm transition-all ${
              kindColor(s.kind)
            } ${i === index ? "opacity-100 ring-1 ring-white" : "opacity-40 hover:opacity-70"}`}
          />
        ))}
      </div>

      {/* Current snapshot metadata */}
      <div className="bg-zinc-800/50 rounded-lg p-3 space-y-1 text-xs">
        <div className="flex items-center justify-between">
          <span className="font-medium text-zinc-300">
            {kindLabel(current.kind)}
          </span>
          <span className="text-zinc-500">{formatTime(current.timestamp)}</span>
        </div>
        <div className="text-zinc-500 flex gap-3 flex-wrap">
          <span>{current.chars.toLocaleString()} chars</span>
          {current.ai_score !== null && current.ai_score !== undefined && (
            <span>
              AI score:{" "}
              <span
                style={{
                  color:
                    current.ai_score > 0.65
                      ? "#f87171"
                      : current.ai_score > 0.4
                      ? "#fbbf24"
                      : "#4ade80",
                }}
              >
                {Math.round(current.ai_score * 100)}%
              </span>
            </span>
          )}
          {current.strength && (
            <span>
              {current.strength}/{current.tone}/{current.mode}
              {current.ai_score_before !== undefined &&
                current.ai_score_before !== null && (
                  <>
                    {" "}
                    ({Math.round(current.ai_score_before * 100)}% →{" "}
                    {Math.round((current.ai_score ?? 0) * 100)}%)
                  </>
                )}
            </span>
          )}
          {current.note && (
            <span className="text-purple-400 italic">{current.note}</span>
          )}
        </div>
      </div>

      {/* Reconstructed content viewer */}
      <div className="bg-zinc-800/30 rounded-lg p-4 max-h-80 overflow-y-auto">
        <pre className="text-xs text-zinc-300 whitespace-pre-wrap font-mono leading-relaxed">
          {current.content}
        </pre>
      </div>

      {/* Copy-to-editor */}
      <button
        onClick={() => navigator.clipboard.writeText(current.content)}
        className="text-xs text-blue-400 hover:text-blue-300"
      >
        Copy this version to clipboard
      </button>
    </div>
  );
}
