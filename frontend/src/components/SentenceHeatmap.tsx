"use client";

import type { SentenceScore } from "../lib/types";

export function SentenceHeatmap({ sentences }: { sentences: SentenceScore[] }) {
  return (
    <div>
      <p className="text-xs text-zinc-500 font-medium mb-2">
        Per-Sentence Heatmap{" "}
        <span className="text-zinc-600">· {sentences.length} sentences</span>
      </p>
      {/* Cap height and scroll internally so long documents don't push
          the surrounding panel off-screen. 50vh matches the rest of the
          output components (ReplayTimeline, ProvenanceReport). */}
      <div className="space-y-1.5 max-h-[50vh] overflow-y-auto overscroll-contain pr-1">
        {sentences.map((s, i) => {
        const score = s.ai_score;
        const bg =
          score === null
            ? "bg-zinc-800/50"
            : score > 0.65
            ? "bg-red-500/15 border-red-500/30"
            : score > 0.4
            ? "bg-amber-500/15 border-amber-500/30"
            : "bg-green-500/15 border-green-500/30";
        const textColor =
          score === null
            ? "text-zinc-500"
            : score > 0.65
            ? "text-red-300"
            : score > 0.4
            ? "text-amber-300"
            : "text-green-300";

        return (
          <div
            key={i}
            className={`rounded-lg px-3 py-2 border border-transparent ${bg} flex items-start justify-between gap-3`}
          >
            <p className="text-sm text-zinc-300 leading-relaxed flex-1">{s.sentence}</p>
            <span className={`text-xs font-mono whitespace-nowrap mt-0.5 ${textColor}`}>
              {score !== null ? `${Math.round(score * 100)}% AI` : "—"}
            </span>
          </div>
        );
      })}
      </div>
    </div>
  );
}
