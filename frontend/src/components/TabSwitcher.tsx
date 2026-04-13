"use client";

import type { AppTab } from "../store/app";
import { useAppStore } from "../store/app";

const TABS: { id: AppTab; label: string }[] = [
  { id: "detect", label: "Detect AI" },
  { id: "humanize", label: "Humanize" },
];

export function TabSwitcher() {
  const { activeTab, setActiveTab, clearResults } = useAppStore();

  return (
    <div className="flex gap-1 mb-6 bg-zinc-900 rounded-lg p-1 w-fit">
      {TABS.map((t) => (
        <button
          key={t.id}
          onClick={() => {
            setActiveTab(t.id);
            clearResults();
          }}
          className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
            activeTab === t.id
              ? "bg-zinc-700 text-white"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
