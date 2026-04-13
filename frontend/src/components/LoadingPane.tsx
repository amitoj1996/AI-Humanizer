"use client";

import { useAppStore } from "../store/app";

export function LoadingPane() {
  const { loading, mode } = useAppStore();

  if (!loading) return null;

  const message =
    loading === "detect"
      ? "Running detection models..."
      : mode === "sentence"
      ? "Humanizing sentence-by-sentence (this takes a minute)..."
      : "Rewriting with local LLM...";

  return (
    <div className="flex items-center justify-center h-64 bg-zinc-900 rounded-xl border border-zinc-800">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-sm text-zinc-400">{message}</span>
      </div>
    </div>
  );
}
