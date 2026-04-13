"use client";

import { ModelSelector } from "./ModelSelector";

export function Header() {
  return (
    <header className="border-b border-zinc-800 px-6 py-4">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight">AI Humanizer</h1>
          <p className="text-xs text-zinc-500">
            Detect &amp; humanize AI text — 100% local, 100% private
          </p>
        </div>
        <ModelSelector />
      </div>
    </header>
  );
}
