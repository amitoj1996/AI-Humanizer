"use client";

import { recorder } from "../lib/provenance";
import type { Revision } from "../lib/types";
import { useAppStore } from "../store/app";
import { useDocumentsStore } from "../store/documents";

/** Hydrate `loadContent(text, json)` from a Revision, respecting its format. */
function contentFromRevision(rev: Revision): { text: string; json: { type: "doc"; content?: unknown[] } | null } {
  if (rev.format === "prosemirror") {
    try {
      return { text: "", json: JSON.parse(rev.content) };
    } catch {
      // Falls back to surfacing raw bytes so the user doesn't lose the row.
      return { text: rev.content, json: null };
    }
  }
  return { text: rev.content, json: null };
}

function formatTime(ms: number): string {
  const date = new Date(ms);
  const now = new Date();
  const diffMs = now.getTime() - ms;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return date.toLocaleDateString();
}

export function RevisionTimeline() {
  const { currentDocumentId, currentRevisions, restoreRevision } = useDocumentsStore();
  const { loadContent, clearResults } = useAppStore();

  if (!currentDocumentId || currentRevisions.length === 0) return null;

  const handleRestore = async (revId: string) => {
    if (!currentDocumentId) return;
    if (!confirm("Restore this revision? This creates a new revision with the old content.")) return;
    const restored = await restoreRevision(currentDocumentId, revId);
    const { text, json } = contentFromRevision(restored);
    loadContent(text, json);
    // Provenance: a restore appends a new revision with the old content;
    // it's a user-intent event, so include it in the writing history.
    recorder.revisionSaved(restored.id, restored.ai_score);
    clearResults();
  };

  const handlePreview = (rev: Revision) => {
    const { text, json } = contentFromRevision(rev);
    loadContent(text, json);
    clearResults();
  };

  return (
    <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-4 space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Revisions</h3>
        <span className="text-xs text-zinc-500">{currentRevisions.length} total</span>
      </div>
      <div className="space-y-1 max-h-60 overflow-y-auto">
        {currentRevisions.map((rev, i) => (
          <div
            key={rev.id}
            className="group flex items-center justify-between bg-zinc-800/30 rounded px-2 py-1.5"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 text-xs">
                <span className="text-zinc-400">#{currentRevisions.length - i}</span>
                <span className="text-zinc-500">{formatTime(rev.created_at)}</span>
                {rev.ai_score !== null && (
                  <span
                    className="font-mono"
                    style={{
                      color:
                        rev.ai_score > 0.65
                          ? "#f87171"
                          : rev.ai_score > 0.4
                          ? "#fbbf24"
                          : "#4ade80",
                    }}
                  >
                    {Math.round(rev.ai_score * 100)}% AI
                  </span>
                )}
                {rev.note && <span className="text-purple-400 italic">{rev.note}</span>}
              </div>
            </div>
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={() => handlePreview(rev)}
                className="text-xs text-blue-400 hover:text-blue-300 px-1"
              >
                View
              </button>
              <button
                onClick={() => handleRestore(rev.id)}
                className="text-xs text-emerald-400 hover:text-emerald-300 px-1"
              >
                Restore
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
