"use client";

import { useState } from "react";

import { recorder } from "../lib/provenance";
import { useAppStore } from "../store/app";
import { useDocumentsStore } from "../store/documents";
import { ExportMenu } from "./ExportMenu";
import { ProvenanceReport } from "./ProvenanceReport";

export function DocumentHeader() {
  const {
    currentDocumentId,
    currentProjectId,
    documentsByProject,
    renameDocument,
    saveRevision,
  } = useDocumentsStore();
  const { text } = useAppStore();
  const [editingTitle, setEditingTitle] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");

  if (!currentDocumentId || !currentProjectId) return null;

  const doc = (documentsByProject[currentProjectId] ?? []).find(
    (d) => d.id === currentDocumentId,
  );
  if (!doc) return null;

  const handleRename = async () => {
    if (draftTitle.trim() && draftTitle !== doc.title) {
      await renameDocument(doc.id, draftTitle.trim());
    }
    setEditingTitle(false);
  };

  const handleSave = async () => {
    if (!text.trim()) return;
    const rev = await saveRevision(doc.id, text);
    // Provenance: record the manual save so the writing-process report
    // shows user-driven checkpoints, not just detect/humanize events.
    recorder.revisionSaved(rev.id, rev.ai_score);
  };

  return (
    <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
      {editingTitle ? (
        <input
          autoFocus
          value={draftTitle}
          onChange={(e) => setDraftTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleRename();
            if (e.key === "Escape") setEditingTitle(false);
          }}
          onBlur={handleRename}
          className="text-lg font-semibold bg-zinc-900 border border-zinc-700 rounded px-2 py-0.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      ) : (
        <h2
          className="text-lg font-semibold cursor-pointer hover:text-blue-400"
          onClick={() => {
            setDraftTitle(doc.title);
            setEditingTitle(true);
          }}
          title="Click to rename"
        >
          {doc.title}
        </h2>
      )}
      <div className="flex items-center gap-2">
        <ExportMenu />
        <ProvenanceReport />
        <button
          onClick={handleSave}
          disabled={!text.trim()}
          className="text-xs px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed"
        >
          Save Revision
        </button>
      </div>
    </div>
  );
}
