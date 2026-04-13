"use client";

import { useAppStore } from "../store/app";

export function EmptyState() {
  const { detection, sentenceDetection, humanizeResult, loading } = useAppStore();

  if (detection || sentenceDetection || humanizeResult || loading) return null;

  return (
    <div className="flex items-center justify-center h-64 bg-zinc-900 rounded-xl border border-zinc-800 border-dashed">
      <p className="text-sm text-zinc-600">Results will appear here</p>
    </div>
  );
}
