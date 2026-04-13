"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "../lib/api";
import { recorder } from "../lib/provenance";
import type { ProvenanceReport as Report } from "../lib/types";
import { useDocumentsStore } from "../store/documents";
import { ReplayTimeline } from "./ReplayTimeline";

type Tab = "summary" | "replay";

function formatTime(ms: number): string {
  return new Date(ms).toLocaleString();
}

function formatDuration(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function eventColor(type: string): string {
  if (type.startsWith("ai_")) return "text-purple-400";
  if (type === "pasted" || type === "imported") return "text-amber-400";
  if (type === "typed") return "text-emerald-400";
  if (type === "detection_run") return "text-blue-400";
  if (type === "revision_saved") return "text-zinc-400";
  if (type === "deleted") return "text-red-400";
  return "text-zinc-500";
}

export function ProvenanceReport() {
  const { currentDocumentId } = useDocumentsStore();
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("summary");
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!currentDocumentId) return;
    setLoading(true);
    try {
      // Flush any unsent events before building the report
      await recorder.flush();
      const r = await api.getReport(currentDocumentId);
      setReport(r);
    } finally {
      setLoading(false);
    }
  }, [currentDocumentId]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  if (!currentDocumentId) return null;

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-xs px-3 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700"
      >
        Writing Report
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-6"
          onClick={() => setOpen(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col"
          >
            <div className="px-6 py-4 border-b border-zinc-800">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">Writing Process Report</h2>
                  <p className="text-xs text-zinc-500">
                    Tamper-evident local record · SHA-256 chain
                  </p>
                </div>
                <button
                  onClick={() => setOpen(false)}
                  className="text-zinc-500 hover:text-zinc-300 text-lg"
                >
                  ✕
                </button>
              </div>
              {/* Tabs */}
              <div className="flex gap-1 mt-3">
                {(
                  [
                    ["summary", "Summary"],
                    ["replay", "Authoring Replay"],
                  ] as [Tab, string][]
                ).map(([id, label]) => (
                  <button
                    key={id}
                    onClick={() => setTab(id)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                      tab === id
                        ? "bg-zinc-800 text-white"
                        : "text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {tab === "replay" && <ReplayTimeline />}
              {tab === "summary" && loading && (
                <p className="text-sm text-zinc-500">Loading…</p>
              )}
              {tab === "summary" && !loading && report && (
                <>
                  {/* Chain integrity */}
                  <div
                    className={`rounded-lg px-4 py-3 flex items-start gap-3 ${
                      report.integrity.valid
                        ? "bg-emerald-500/10 border border-emerald-500/30"
                        : "bg-red-500/10 border border-red-500/30"
                    }`}
                  >
                    <span className="text-xl">
                      {report.integrity.valid ? "✓" : "⚠"}
                    </span>
                    <div>
                      <p className="text-sm font-medium">
                        {report.integrity.valid
                          ? "Chain verified"
                          : "Chain broken"}
                      </p>
                      <p className="text-xs text-zinc-400">
                        {report.integrity.sessions_verified} session(s),{" "}
                        {report.total_events} event(s) · SHA-256 hash chain
                        {report.integrity.valid ? " intact" : " has been tampered with"}
                      </p>
                    </div>
                  </div>

                  {/* Authorship breakdown */}
                  <div>
                    <h3 className="text-sm font-semibold mb-2">Authorship</h3>
                    <div className="grid grid-cols-3 gap-3">
                      <AuthorshipCard
                        label="Typed"
                        chars={report.authorship.typed_chars}
                        pct={report.authorship.typed_pct}
                        color="bg-emerald-500"
                      />
                      <AuthorshipCard
                        label="Pasted"
                        chars={report.authorship.pasted_chars}
                        pct={report.authorship.pasted_pct}
                        color="bg-amber-500"
                      />
                      <AuthorshipCard
                        label="AI-assisted"
                        chars={report.authorship.ai_assisted_chars}
                        pct={report.authorship.ai_assisted_pct}
                        color="bg-purple-500"
                      />
                    </div>
                  </div>

                  {/* Sessions */}
                  <div>
                    <h3 className="text-sm font-semibold mb-2">Sessions</h3>
                    <div className="space-y-1">
                      {report.sessions.map((s) => {
                        const ended = s.ended_at ?? Date.now();
                        return (
                          <div
                            key={s.session_id}
                            className="text-xs bg-zinc-800/40 rounded px-3 py-2 flex items-center justify-between"
                          >
                            <div>
                              <div className="text-zinc-300">
                                {formatTime(s.started_at)} ·{" "}
                                {formatDuration(ended - s.started_at)}{" "}
                                {s.ended_at ? "" : "(active)"}
                              </div>
                              <div className="text-zinc-500 font-mono">
                                {s.events} events · hash {s.final_hash?.slice(0, 12) ?? "—"}
                              </div>
                            </div>
                            <span
                              className={
                                s.valid ? "text-emerald-400" : "text-red-400"
                              }
                            >
                              {s.valid ? "✓" : "✗"}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Timeline */}
                  <div>
                    <h3 className="text-sm font-semibold mb-2">Timeline</h3>
                    <div className="space-y-0.5 max-h-80 overflow-y-auto">
                      {report.timeline.map((e, i) => (
                        <div
                          key={i}
                          className="text-xs flex items-start gap-3 px-2 py-1 hover:bg-zinc-800/40 rounded"
                        >
                          <span className="text-zinc-600 font-mono w-20 shrink-0">
                            {new Date(e.timestamp).toLocaleTimeString()}
                          </span>
                          <span
                            className={`font-mono w-32 shrink-0 ${eventColor(e.event_type)}`}
                          >
                            {e.event_type}
                          </span>
                          <span className="text-zinc-400 flex-1">{e.summary}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Export */}
                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-zinc-800">
                    <button
                      onClick={() => {
                        const blob = new Blob(
                          [JSON.stringify(report, null, 2)],
                          { type: "application/json" },
                        );
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `${report.document_title}-provenance.json`;
                        a.click();
                        URL.revokeObjectURL(url);
                      }}
                      className="text-xs px-3 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700"
                    >
                      Download JSON
                    </button>
                  </div>
                </>
              )}
              {tab === "summary" && !loading && !report && (
                <p className="text-sm text-zinc-500">No activity recorded yet.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function AuthorshipCard({
  label,
  chars,
  pct,
  color,
}: {
  label: string;
  chars: number;
  pct: number;
  color: string;
}) {
  return (
    <div className="bg-zinc-800/50 rounded-lg p-3">
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-zinc-400">{label}</span>
        <span className="text-xs font-mono text-zinc-500">{chars} chars</span>
      </div>
      <div className="text-2xl font-bold mt-1">{pct}%</div>
      <div className="h-1.5 bg-zinc-900 rounded-full overflow-hidden mt-2">
        <div
          className={`h-full ${color}`}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
    </div>
  );
}
