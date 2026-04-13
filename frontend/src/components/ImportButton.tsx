"use client";

import { useRef, useState } from "react";

import { api } from "../lib/api";
import { recorder } from "../lib/provenance";
import { useAppStore } from "../store/app";
import { useDocumentsStore } from "../store/documents";

export function ImportButton() {
  const { currentProjectId, loadDocuments, selectDocument } = useDocumentsStore();
  const { setText, clearResults, setError } = useAppStore();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const handleFile = async (file: File) => {
    if (!currentProjectId) return;
    setUploading(true);
    clearResults();
    try {
      const result = await api.importDocument(currentProjectId, file);
      await loadDocuments(currentProjectId);
      await recorder.attachToDocument(result.document_id);
      recorder.imported(result.source_type, result.char_count);

      await selectDocument(result.document_id);
      const currentRev = useDocumentsStore
        .getState()
        .currentRevisions.find((r) => r.id);  // pull newest (first in list)
      if (currentRev) setText(currentRev.content);

      if (result.warnings.length) {
        setError(result.warnings.join(" "));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setUploading(false);
    }
  };

  if (!currentProjectId) return null;

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept=".pdf,.docx,.md,.markdown,.txt"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void handleFile(file);
          e.target.value = "";
        }}
      />
      <button
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        className="text-xs text-blue-400 hover:text-blue-300 disabled:text-zinc-700 disabled:cursor-not-allowed"
      >
        {uploading ? "Importing…" : "+ Import"}
      </button>
    </>
  );
}
