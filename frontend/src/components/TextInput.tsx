"use client";

import { useRef } from "react";

import { useProvenanceCapture } from "../lib/useProvenanceCapture";
import { useAppStore } from "../store/app";

export function TextInput() {
  const { text, setText } = useAppStore();
  const wordCount = text.trim().split(/\s+/).filter(Boolean).length;
  const ref = useRef<HTMLTextAreaElement>(null);

  useProvenanceCapture(ref);

  return (
    <div className="relative">
      <textarea
        ref={ref}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste your text here..."
        rows={14}
        className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm leading-relaxed placeholder:text-zinc-600 resize-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50"
      />
      <span className="absolute bottom-3 right-3 text-xs text-zinc-600">
        {wordCount} words
      </span>
    </div>
  );
}
