"use client";

export function VerdictBadge({ score, verdict }: { score: number; verdict: string }) {
  const cls =
    score > 0.65
      ? "bg-red-500/10 text-red-400"
      : score > 0.4
      ? "bg-amber-500/10 text-amber-400"
      : "bg-green-500/10 text-green-400";
  return (
    <span className={`text-sm font-medium px-3 py-1 rounded-full ${cls}`}>
      {verdict}
    </span>
  );
}
