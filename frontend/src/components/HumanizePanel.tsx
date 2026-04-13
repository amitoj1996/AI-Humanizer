"use client";

import { useCallback } from "react";

import { api } from "../lib/api";
import { recorder } from "../lib/provenance";
import type { Mode, Strength, Tone } from "../lib/types";
import { useAppStore } from "../store/app";
import { useDocumentsStore } from "../store/documents";
import { SimilarityBadge } from "./SimilarityBadge";

const STRENGTHS: Strength[] = ["light", "medium", "aggressive"];
const TONES: Tone[] = ["general", "academic", "casual", "blog", "professional"];

/** Left-column controls for the Humanize tab. */
export function HumanizeControls() {
  const {
    text,
    strength,
    tone,
    mode,
    loading,
    error,
    setStrength,
    setTone,
    setMode,
    setHumanizeResult,
    setLoading,
    setError,
    clearResults,
  } = useAppStore();

  const run = useCallback(async () => {
    if (text.trim().length < 50) {
      setError("Enter at least 50 characters");
      return;
    }
    clearResults();
    setLoading("humanize");
    recorder.aiRewriteRequested(strength, tone, mode);
    try {
      const res = await api.humanize({
        text,
        strength,
        tone,
        mode,
        candidates_per_sentence: 3,
      });
      setHumanizeResult(res);

      recorder.aiRewriteApplied({
        beforeText: text,
        afterText: res.humanized,
        strength,
        tone,
        mode,
        aiScoreBefore: res.detection_before.ai_score,
        aiScoreAfter: res.detection_after.ai_score,
      });

      // Auto-save humanized output as a new revision
      const docId = useDocumentsStore.getState().currentDocumentId;
      if (docId) {
        const rev = await useDocumentsStore
          .getState()
          .saveRevision(
            docId,
            res.humanized,
            res.detection_after.ai_score,
            `Humanized (${strength}/${tone}/${mode})`,
          );
        recorder.revisionSaved(rev.id, res.detection_after.ai_score);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Humanization failed");
    } finally {
      setLoading(null);
    }
  }, [text, strength, tone, mode, clearResults, setLoading, setHumanizeResult, setError]);

  return (
    <>
      {/* Strength */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-zinc-400 w-16">Strength</span>
        {STRENGTHS.map((s) => (
          <button
            key={s}
            onClick={() => setStrength(s)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
              strength === s
                ? "border-blue-500 bg-blue-500/10 text-blue-400"
                : "border-zinc-700 text-zinc-400 hover:border-zinc-600"
            }`}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {/* Tone */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm text-zinc-400 w-16">Tone</span>
        {TONES.map((t) => (
          <button
            key={t}
            onClick={() => setTone(t)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
              tone === t
                ? "border-purple-500 bg-purple-500/10 text-purple-400"
                : "border-zinc-700 text-zinc-400 hover:border-zinc-600"
            }`}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Mode */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-zinc-400 w-16">Mode</span>
        {(
          [
            ["sentence", "Sentence-Level (best)"],
            ["full", "Full-Text (faster)"],
          ] as [Mode, string][]
        ).map(([m, label]) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
              mode === m
                ? "border-emerald-500 bg-emerald-500/10 text-emerald-400"
                : "border-zinc-700 text-zinc-400 hover:border-zinc-600"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <button
        onClick={run}
        disabled={loading !== null}
        className="w-full py-3 rounded-xl font-medium text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed bg-blue-600 hover:bg-blue-500 text-white"
      >
        {loading === "humanize" ? "Humanizing..." : "Humanize Text"}
      </button>

      {error && (
        <p className="text-sm text-red-400 bg-red-400/10 rounded-lg px-4 py-2">{error}</p>
      )}
    </>
  );
}

/** Right-column results for the Humanize tab. */
export function HumanizeResults() {
  const { humanizeResult, loading } = useAppStore();

  if (loading || !humanizeResult) return null;

  return (
    <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-lg font-semibold">Humanized Text</h2>
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-500">
            {humanizeResult.mode === "sentence-level"
              ? `${humanizeResult.total_sentences} sentences`
              : `${humanizeResult.total_iterations} iteration(s)`}
          </span>
          {humanizeResult.similarity_score !== undefined && (
            <SimilarityBadge score={humanizeResult.similarity_score} />
          )}
        </div>
      </div>

      {/* Before/after */}
      <div className="grid grid-cols-2 gap-4">
        {(["before", "after"] as const).map((k) => {
          const d =
            k === "before" ? humanizeResult.detection_before : humanizeResult.detection_after;
          return (
            <div key={k} className="bg-zinc-800/50 rounded-lg p-4 text-center">
              <p className="text-xs text-zinc-500 mb-1">{k === "before" ? "Before" : "After"}</p>
              <p
                className="text-2xl font-bold"
                style={{
                  color:
                    d.ai_score > 0.65 ? "#ef4444" : d.ai_score > 0.4 ? "#f59e0b" : "#22c55e",
                }}
              >
                {Math.round(d.ai_score * 100)}%
              </p>
              <p className="text-xs text-zinc-500">{d.verdict}</p>
            </div>
          );
        })}
      </div>

      {/* Per-sentence details */}
      {humanizeResult.sentence_details && (
        <div className="space-y-1.5">
          <p className="text-xs text-zinc-500 font-medium">Per-Sentence Results</p>
          {humanizeResult.sentence_details
            .filter((d) => !d.skipped)
            .map((d, i) => (
              <div key={i} className="bg-zinc-800/30 rounded-lg px-3 py-2 space-y-1">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-xs text-zinc-500 line-through leading-relaxed flex-1">
                    {d.original}
                  </p>
                  <span className="text-xs font-mono text-red-400 whitespace-nowrap">
                    {d.original_ai_score !== null
                      ? `${Math.round(d.original_ai_score * 100)}%`
                      : "—"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm text-zinc-300 leading-relaxed flex-1">{d.humanized}</p>
                  <span className="text-xs font-mono text-green-400 whitespace-nowrap">
                    {d.best_ai_score !== null
                      ? `${Math.round(d.best_ai_score * 100)}%`
                      : "—"}
                  </span>
                </div>
              </div>
            ))}
        </div>
      )}

      {/* Iteration log */}
      {humanizeResult.iterations && humanizeResult.iterations.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-zinc-500 font-medium">Iteration log</p>
          {humanizeResult.iterations.map((it) => (
            <div
              key={it.iteration}
              className="flex items-center justify-between text-xs text-zinc-400 bg-zinc-800/30 rounded px-3 py-1.5"
            >
              <span>
                #{it.iteration} &middot; {it.strength}
              </span>
              <span className="font-mono">{Math.round(it.ai_score * 100)}% AI</span>
            </div>
          ))}
        </div>
      )}

      {/* Output */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs text-zinc-500 font-medium">Final Output</p>
          <button
            onClick={() => navigator.clipboard.writeText(humanizeResult.humanized)}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            Copy
          </button>
        </div>
        <div className="bg-zinc-800/50 rounded-lg p-4 text-sm leading-relaxed text-zinc-300 max-h-64 overflow-y-auto whitespace-pre-wrap">
          {humanizeResult.humanized}
        </div>
      </div>
    </div>
  );
}
