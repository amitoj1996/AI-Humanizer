"use client";

import { useEffect, useRef, useState } from "react";

import { api } from "../lib/api";
import { useDocumentsStore } from "../store/documents";

type ExportFormat = {
  kind: "document" | "provenance";
  format: "md" | "txt" | "docx";
  label: string;
};

const OPTIONS: ExportFormat[] = [
  { kind: "document", format: "md", label: "Document as Markdown" },
  { kind: "document", format: "txt", label: "Document as Plain Text" },
  { kind: "document", format: "docx", label: "Document as Word (.docx)" },
  { kind: "provenance", format: "md", label: "Process Report as Markdown" },
  { kind: "provenance", format: "docx", label: "Process Report as Word (.docx)" },
];

export function ExportMenu() {
  const { currentDocumentId } = useDocumentsStore();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handle = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [open]);

  if (!currentDocumentId) return null;

  const handleExport = (opt: ExportFormat) => {
    const url =
      opt.kind === "document"
        ? api.exportDocumentUrl(currentDocumentId, opt.format)
        : api.exportProvenanceUrl(currentDocumentId, opt.format as "md" | "docx");
    const a = document.createElement("a");
    a.href = url;
    a.rel = "noopener";
    a.click();
    setOpen(false);
  };

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="text-xs px-3 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700"
      >
        Export ▾
      </button>
      {open && (
        <div className="absolute right-0 mt-1 w-64 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl z-10 overflow-hidden">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500 px-3 pt-2 pb-1">
            Document
          </div>
          {OPTIONS.filter((o) => o.kind === "document").map((o) => (
            <button
              key={`${o.kind}-${o.format}`}
              onClick={() => handleExport(o)}
              className="w-full text-left text-xs px-3 py-1.5 text-zinc-300 hover:bg-zinc-800"
            >
              {o.label}
            </button>
          ))}
          <div className="text-[10px] uppercase tracking-wider text-zinc-500 px-3 pt-2 pb-1 border-t border-zinc-800 mt-1">
            Writing process
          </div>
          {OPTIONS.filter((o) => o.kind === "provenance").map((o) => (
            <button
              key={`${o.kind}-${o.format}`}
              onClick={() => handleExport(o)}
              className="w-full text-left text-xs px-3 py-1.5 text-zinc-300 hover:bg-zinc-800"
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
