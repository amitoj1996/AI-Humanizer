"use client";

import { useCallback } from "react";

import { api } from "../lib/api";
import { useAppStore } from "../store/app";
import { useDocumentsStore } from "../store/documents";
import { BreakdownCard } from "./BreakdownCard";
import { ScoreRing } from "./ScoreRing";
import { SentenceHeatmap } from "./SentenceHeatmap";
import { VerdictBadge } from "./VerdictBadge";

/** Left-column controls for the Detect tab. */
export function DetectControls() {
  const {
    text,
    detectionMode,
    loading,
    error,
    setDetectionMode,
    setDetection,
    setSentenceDetection,
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
    setLoading("detect");
    try {
      let aiScore: number | undefined;
      if (detectionMode === "sentences") {
        const result = await api.detectSentences(text);
        setSentenceDetection(result);
        aiScore = result.overall.ai_score;
      } else {
        const result = await api.detect(text);
        setDetection(result);
        aiScore = result.ai_score;
      }
      // Auto-save revision snapshot of current text with AI score attached
      const docId = useDocumentsStore.getState().currentDocumentId;
      if (docId && aiScore !== undefined) {
        await useDocumentsStore.getState().saveRevision(docId, text, aiScore, "After detection");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Detection failed");
    } finally {
      setLoading(null);
    }
  }, [
    text,
    detectionMode,
    clearResults,
    setLoading,
    setSentenceDetection,
    setDetection,
    setError,
  ]);

  return (
    <>
      <div className="flex items-center gap-3">
        <span className="text-sm text-zinc-400">Mode:</span>
        {(["sentences", "overall"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setDetectionMode(m)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
              detectionMode === m
                ? "border-blue-500 bg-blue-500/10 text-blue-400"
                : "border-zinc-700 text-zinc-400 hover:border-zinc-600"
            }`}
          >
            {m === "sentences" ? "Sentence Heatmap" : "Overall Score"}
          </button>
        ))}
      </div>

      <button
        onClick={run}
        disabled={loading !== null}
        className="w-full py-3 rounded-xl font-medium text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed bg-blue-600 hover:bg-blue-500 text-white"
      >
        {loading === "detect" ? "Analyzing..." : "Detect AI Content"}
      </button>

      {error && (
        <p className="text-sm text-red-400 bg-red-400/10 rounded-lg px-4 py-2">{error}</p>
      )}
    </>
  );
}

/** Right-column results for the Detect tab. */
export function DetectResults() {
  const { detection, sentenceDetection, loading } = useAppStore();

  if (loading) return null;

  if (detection) {
    return (
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Detection Result</h2>
          <VerdictBadge score={detection.ai_score} verdict={detection.verdict} />
        </div>
        <div className="flex justify-center gap-8">
          <ScoreRing score={detection.ai_score} label="AI Score" />
          <ScoreRing score={detection.human_score} label="Human Score" />
        </div>
        <BreakdownCard breakdown={detection.breakdown} />
      </div>
    );
  }

  if (sentenceDetection) {
    return (
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Sentence Analysis</h2>
          <VerdictBadge
            score={sentenceDetection.overall.ai_score}
            verdict={sentenceDetection.overall.verdict}
          />
        </div>
        <div className="flex justify-center gap-8">
          <ScoreRing score={sentenceDetection.overall.ai_score} label="Overall AI" />
          <ScoreRing
            score={sentenceDetection.average_sentence_ai}
            label="Avg Sentence AI"
          />
        </div>
        <SentenceHeatmap sentences={sentenceDetection.sentences} />
      </div>
    );
  }

  return null;
}
