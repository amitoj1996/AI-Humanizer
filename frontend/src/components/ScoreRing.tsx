"use client";

type Props = { score: number; label: string; size?: number };

export function ScoreRing({ score, label, size = 100 }: Props) {
  const pct = Math.round(score * 100);
  const r = (size - 10) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - score * circ;
  const color =
    score > 0.65 ? "#ef4444" : score > 0.4 ? "#f59e0b" : "#22c55e";

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#27272a" strokeWidth={6} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={6}
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-700"
        />
      </svg>
      <span className="text-2xl font-bold -mt-16" style={{ color }}>
        {pct}%
      </span>
      <span className="text-xs text-zinc-400 mt-4">{label}</span>
    </div>
  );
}
