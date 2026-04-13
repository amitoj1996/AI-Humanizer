"use client";

export function SimilarityBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 85
      ? "text-green-400 bg-green-400/10"
      : pct >= 70
      ? "text-amber-400 bg-amber-400/10"
      : "text-red-400 bg-red-400/10";
  return (
    <span className={`text-xs font-medium px-2 py-1 rounded ${color}`}>
      {pct}% meaning preserved
    </span>
  );
}
