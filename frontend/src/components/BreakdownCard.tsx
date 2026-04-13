"use client";

import type { Breakdown } from "../lib/types";

export function BreakdownCard({ breakdown }: { breakdown: Breakdown }) {
  const rows = [
    {
      label: "RoBERTa Classifier",
      value: breakdown.classifier.ai_probability,
      desc: "Fine-tuned transformer model",
    },
    {
      label: "Perplexity Signal",
      value: breakdown.perplexity.combined_ai_signal,
      desc: `PPL: ${breakdown.perplexity.perplexity.toFixed(1)} | Burstiness: ${breakdown.perplexity.burstiness.toFixed(3)}`,
    },
    {
      label: "Linguistic Analysis",
      value: breakdown.linguistic.ai_signal,
      desc: `TTR: ${breakdown.linguistic.type_token_ratio.toFixed(3)} | CV: ${breakdown.linguistic.sentence_length_cv.toFixed(3)}`,
    },
  ];

  return (
    <div className="space-y-3">
      {rows.map((r) => (
        <div key={r.label}>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-zinc-300">{r.label}</span>
            <span className="font-mono text-zinc-400">{(r.value * 100).toFixed(1)}%</span>
          </div>
          <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${r.value * 100}%`,
                background: r.value > 0.65 ? "#ef4444" : r.value > 0.4 ? "#f59e0b" : "#22c55e",
              }}
            />
          </div>
          <p className="text-xs text-zinc-500 mt-0.5">{r.desc}</p>
        </div>
      ))}
      <div className="text-xs text-zinc-500 pt-1 border-t border-zinc-800">
        {breakdown.linguistic.details.word_count} words &middot;{" "}
        {breakdown.linguistic.details.sentence_count} sentences &middot;{" "}
        {breakdown.linguistic.details.ai_markers_found} AI markers
      </div>
    </div>
  );
}
