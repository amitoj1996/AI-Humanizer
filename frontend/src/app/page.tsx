"use client";

import { useCallback, useEffect, useState } from "react";

const API = "";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
type Breakdown = {
  classifier: { ai_probability: number; human_probability: number };
  perplexity: { perplexity: number; burstiness: number; combined_ai_signal: number };
  linguistic: {
    sentence_length_cv: number;
    type_token_ratio: number;
    ai_marker_density: number;
    contraction_rate: number;
    ai_signal: number;
    details: { word_count: number; sentence_count: number; ai_markers_found: number };
  };
};

type DetectionResult = {
  ai_score: number;
  human_score: number;
  verdict: string;
  breakdown: Breakdown;
};

type SentenceScore = {
  sentence: string;
  ai_score: number | null;
  verdict: string;
  word_count: number;
};

type SentenceDetectionResult = {
  overall: DetectionResult;
  average_sentence_ai: number;
  sentences: SentenceScore[];
  total_sentences: number;
};

type SentenceDetail = {
  original: string;
  humanized: string;
  original_ai_score: number | null;
  best_ai_score: number | null;
  candidates_tested: number;
  skipped: boolean;
};

type HumanizeResult = {
  original: string;
  humanized: string;
  detection_before: DetectionResult;
  detection_after: DetectionResult;
  iterations?: { iteration: number; strength: string; ai_score: number; verdict: string }[];
  sentence_details?: SentenceDetail[];
  total_iterations?: number;
  total_sentences?: number;
  mode: string;
  similarity_score?: number;
};

type Strength = "light" | "medium" | "aggressive";
type Tone = "general" | "academic" | "casual" | "blog" | "professional";
type Mode = "full" | "sentence";

/* ------------------------------------------------------------------ */
/*  Score ring                                                         */
/* ------------------------------------------------------------------ */
function ScoreRing({ score, label, size = 100 }: { score: number; label: string; size?: number }) {
  const pct = Math.round(score * 100);
  const r = (size - 10) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - score * circ;
  const color = score > 0.65 ? "#ef4444" : score > 0.4 ? "#f59e0b" : "#22c55e";

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#27272a" strokeWidth={6} />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={6}
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          className="transition-all duration-700"
        />
      </svg>
      <span className="text-2xl font-bold -mt-16" style={{ color }}>{pct}%</span>
      <span className="text-xs text-zinc-400 mt-4">{label}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Breakdown bars                                                     */
/* ------------------------------------------------------------------ */
function BreakdownCard({ breakdown }: { breakdown: Breakdown }) {
  const rows = [
    { label: "RoBERTa Classifier", value: breakdown.classifier.ai_probability, desc: "Fine-tuned transformer model" },
    { label: "Perplexity Signal", value: breakdown.perplexity.combined_ai_signal, desc: `PPL: ${breakdown.perplexity.perplexity.toFixed(1)} | Burstiness: ${breakdown.perplexity.burstiness.toFixed(3)}` },
    { label: "Linguistic Analysis", value: breakdown.linguistic.ai_signal, desc: `TTR: ${breakdown.linguistic.type_token_ratio.toFixed(3)} | CV: ${breakdown.linguistic.sentence_length_cv.toFixed(3)}` },
  ];

  return (
    <div className="space-y-3">
      {rows.map((r) => (
        <div key={r.label}>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-zinc-300">{r.label}</span>
            <span className="font-mono text-zinc-400">{(r.value * 100).toFixed(1)}%</span>
          </div>
          <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${r.value * 100}%`, background: r.value > 0.65 ? "#ef4444" : r.value > 0.4 ? "#f59e0b" : "#22c55e" }}
            />
          </div>
          <p className="text-xs text-zinc-500 mt-0.5">{r.desc}</p>
        </div>
      ))}
      <div className="text-xs text-zinc-500 pt-1 border-t border-zinc-800">
        {breakdown.linguistic.details.word_count} words &middot; {breakdown.linguistic.details.sentence_count} sentences &middot; {breakdown.linguistic.details.ai_markers_found} AI markers
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Sentence heatmap                                                   */
/* ------------------------------------------------------------------ */
function SentenceHeatmap({ sentences }: { sentences: SentenceScore[] }) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs text-zinc-500 font-medium mb-2">Per-Sentence Heatmap</p>
      {sentences.map((s, i) => {
        const score = s.ai_score;
        const bg =
          score === null
            ? "bg-zinc-800/50"
            : score > 0.65
            ? "bg-red-500/15 border-red-500/30"
            : score > 0.4
            ? "bg-amber-500/15 border-amber-500/30"
            : "bg-green-500/15 border-green-500/30";
        const textColor =
          score === null ? "text-zinc-500" : score > 0.65 ? "text-red-300" : score > 0.4 ? "text-amber-300" : "text-green-300";

        return (
          <div key={i} className={`rounded-lg px-3 py-2 border border-transparent ${bg} flex items-start justify-between gap-3`}>
            <p className="text-sm text-zinc-300 leading-relaxed flex-1">{s.sentence}</p>
            <span className={`text-xs font-mono whitespace-nowrap mt-0.5 ${textColor}`}>
              {score !== null ? `${Math.round(score * 100)}% AI` : "—"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Similarity badge                                                   */
/* ------------------------------------------------------------------ */
function SimilarityBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 85 ? "text-green-400 bg-green-400/10" : pct >= 70 ? "text-amber-400 bg-amber-400/10" : "text-red-400 bg-red-400/10";
  return (
    <span className={`text-xs font-medium px-2 py-1 rounded ${color}`}>
      {pct}% meaning preserved
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Main page                                                          */
/* ------------------------------------------------------------------ */
export default function Home() {
  const [text, setText] = useState("");
  const [strength, setStrength] = useState<Strength>("medium");
  const [tone, setTone] = useState<Tone>("general");
  const [mode, setMode] = useState<Mode>("sentence");
  const [detection, setDetection] = useState<DetectionResult | null>(null);
  const [sentenceDetection, setSentenceDetection] = useState<SentenceDetectionResult | null>(null);
  const [humanizeResult, setHumanizeResult] = useState<HumanizeResult | null>(null);
  const [loading, setLoading] = useState<"detect" | "humanize" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [ollamaAvailable, setOllamaAvailable] = useState<boolean | null>(null);
  const [activeTab, setActiveTab] = useState<"detect" | "humanize">("detect");
  const [detectionMode, setDetectionMode] = useState<"overall" | "sentences">("sentences");

  useEffect(() => {
    fetch(`${API}/api/models`)
      .then((r) => r.json())
      .then((d) => {
        setOllamaAvailable(d.ollama_available);
        setModels(d.models || []);
        if (d.models?.length) setSelectedModel(d.models[0]);
      })
      .catch(() => setOllamaAvailable(false));
  }, []);

  const clearResults = () => { setDetection(null); setSentenceDetection(null); setHumanizeResult(null); setError(null); };

  const detect = useCallback(async () => {
    if (text.trim().length < 50) { setError("Enter at least 50 characters"); return; }
    clearResults();
    setLoading("detect");
    try {
      if (detectionMode === "sentences") {
        const res = await fetch(`${API}/api/detect/sentences`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
        if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
        setSentenceDetection(await res.json());
      } else {
        const res = await fetch(`${API}/api/detect`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
        if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
        setDetection(await res.json());
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Detection failed");
    } finally { setLoading(null); }
  }, [text, detectionMode]);

  const humanize = useCallback(async () => {
    if (text.trim().length < 50) { setError("Enter at least 50 characters"); return; }
    clearResults();
    setLoading("humanize");
    try {
      const res = await fetch(`${API}/api/humanize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, strength, tone, mode, candidates_per_sentence: 3 }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
      setHumanizeResult(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Humanization failed");
    } finally { setLoading(null); }
  }, [text, strength, tone, mode]);

  const selectModel = useCallback(async (model: string) => {
    setSelectedModel(model);
    await fetch(`${API}/api/models/select`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model }) });
  }, []);

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <header className="border-b border-zinc-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight">AI Humanizer</h1>
            <p className="text-xs text-zinc-500">Detect &amp; humanize AI text — 100% local, 100% private</p>
          </div>
          <div className="flex items-center gap-3">
            {ollamaAvailable === false && (
              <span className="text-xs text-red-400 bg-red-400/10 px-2 py-1 rounded">Ollama offline</span>
            )}
            {models.length > 0 && (
              <select value={selectedModel} onChange={(e) => selectModel(e.target.value)} className="text-sm bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-zinc-300">
                {models.map((m) => (<option key={m} value={m}>{m}</option>))}
              </select>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-8">
        {/* Tab switcher */}
        <div className="flex gap-1 mb-6 bg-zinc-900 rounded-lg p-1 w-fit">
          <button onClick={() => { setActiveTab("detect"); clearResults(); }} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === "detect" ? "bg-zinc-700 text-white" : "text-zinc-400 hover:text-zinc-200"}`}>
            Detect AI
          </button>
          <button onClick={() => { setActiveTab("humanize"); clearResults(); }} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === "humanize" ? "bg-zinc-700 text-white" : "text-zinc-400 hover:text-zinc-200"}`}>
            Humanize
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* ---- Input panel ---- */}
          <div className="space-y-4">
            <div className="relative">
              <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste your text here..." rows={14}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm leading-relaxed placeholder:text-zinc-600 resize-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50" />
              <span className="absolute bottom-3 right-3 text-xs text-zinc-600">{text.trim().split(/\s+/).filter(Boolean).length} words</span>
            </div>

            {/* Detection options */}
            {activeTab === "detect" && (
              <div className="flex items-center gap-3">
                <span className="text-sm text-zinc-400">Mode:</span>
                {(["sentences", "overall"] as const).map((m) => (
                  <button key={m} onClick={() => setDetectionMode(m)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${detectionMode === m ? "border-blue-500 bg-blue-500/10 text-blue-400" : "border-zinc-700 text-zinc-400 hover:border-zinc-600"}`}>
                    {m === "sentences" ? "Sentence Heatmap" : "Overall Score"}
                  </button>
                ))}
              </div>
            )}

            {/* Humanize options */}
            {activeTab === "humanize" && (
              <div className="space-y-3">
                {/* Strength */}
                <div className="flex items-center gap-3">
                  <span className="text-sm text-zinc-400 w-16">Strength</span>
                  {(["light", "medium", "aggressive"] as const).map((s) => (
                    <button key={s} onClick={() => setStrength(s)}
                      className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${strength === s ? "border-blue-500 bg-blue-500/10 text-blue-400" : "border-zinc-700 text-zinc-400 hover:border-zinc-600"}`}>
                      {s.charAt(0).toUpperCase() + s.slice(1)}
                    </button>
                  ))}
                </div>

                {/* Tone */}
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm text-zinc-400 w-16">Tone</span>
                  {(["general", "academic", "casual", "blog", "professional"] as const).map((t) => (
                    <button key={t} onClick={() => setTone(t)}
                      className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${tone === t ? "border-purple-500 bg-purple-500/10 text-purple-400" : "border-zinc-700 text-zinc-400 hover:border-zinc-600"}`}>
                      {t.charAt(0).toUpperCase() + t.slice(1)}
                    </button>
                  ))}
                </div>

                {/* Mode */}
                <div className="flex items-center gap-3">
                  <span className="text-sm text-zinc-400 w-16">Mode</span>
                  <button onClick={() => setMode("sentence")}
                    className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${mode === "sentence" ? "border-emerald-500 bg-emerald-500/10 text-emerald-400" : "border-zinc-700 text-zinc-400 hover:border-zinc-600"}`}>
                    Sentence-Level (best)
                  </button>
                  <button onClick={() => setMode("full")}
                    className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${mode === "full" ? "border-emerald-500 bg-emerald-500/10 text-emerald-400" : "border-zinc-700 text-zinc-400 hover:border-zinc-600"}`}>
                    Full-Text (faster)
                  </button>
                </div>
              </div>
            )}

            <button onClick={activeTab === "detect" ? detect : humanize} disabled={loading !== null}
              className="w-full py-3 rounded-xl font-medium text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed bg-blue-600 hover:bg-blue-500 text-white">
              {loading ? (loading === "detect" ? "Analyzing..." : "Humanizing...") : activeTab === "detect" ? "Detect AI Content" : "Humanize Text"}
            </button>

            {error && <p className="text-sm text-red-400 bg-red-400/10 rounded-lg px-4 py-2">{error}</p>}
          </div>

          {/* ---- Results panel ---- */}
          <div className="space-y-4">
            {/* Loading */}
            {loading && (
              <div className="flex items-center justify-center h-64 bg-zinc-900 rounded-xl border border-zinc-800">
                <div className="flex flex-col items-center gap-3">
                  <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm text-zinc-400">
                    {loading === "detect" ? "Running detection models..." : mode === "sentence" ? "Humanizing sentence-by-sentence (this takes a minute)..." : "Rewriting with local LLM..."}
                  </span>
                </div>
              </div>
            )}

            {/* Overall detection result */}
            {detection && !loading && (
              <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-6 space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">Detection Result</h2>
                  <span className={`text-sm font-medium px-3 py-1 rounded-full ${detection.ai_score > 0.65 ? "bg-red-500/10 text-red-400" : detection.ai_score > 0.4 ? "bg-amber-500/10 text-amber-400" : "bg-green-500/10 text-green-400"}`}>
                    {detection.verdict}
                  </span>
                </div>
                <div className="flex justify-center gap-8">
                  <ScoreRing score={detection.ai_score} label="AI Score" />
                  <ScoreRing score={detection.human_score} label="Human Score" />
                </div>
                <BreakdownCard breakdown={detection.breakdown} />
              </div>
            )}

            {/* Sentence-level detection */}
            {sentenceDetection && !loading && (
              <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-6 space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">Sentence Analysis</h2>
                  <span className={`text-sm font-medium px-3 py-1 rounded-full ${sentenceDetection.overall.ai_score > 0.65 ? "bg-red-500/10 text-red-400" : sentenceDetection.overall.ai_score > 0.4 ? "bg-amber-500/10 text-amber-400" : "bg-green-500/10 text-green-400"}`}>
                    {sentenceDetection.overall.verdict}
                  </span>
                </div>
                <div className="flex justify-center gap-8">
                  <ScoreRing score={sentenceDetection.overall.ai_score} label="Overall AI" />
                  <ScoreRing score={sentenceDetection.average_sentence_ai} label="Avg Sentence AI" />
                </div>
                <SentenceHeatmap sentences={sentenceDetection.sentences} />
              </div>
            )}

            {/* Humanize result */}
            {humanizeResult && !loading && (
              <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-6 space-y-6">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <h2 className="text-lg font-semibold">Humanized Text</h2>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-zinc-500">
                      {humanizeResult.mode === "sentence-level" ? `${humanizeResult.total_sentences} sentences` : `${humanizeResult.total_iterations} iteration(s)`}
                    </span>
                    {humanizeResult.similarity_score !== undefined && (
                      <SimilarityBadge score={humanizeResult.similarity_score} />
                    )}
                  </div>
                </div>

                {/* Before / After scores */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-zinc-800/50 rounded-lg p-4 text-center">
                    <p className="text-xs text-zinc-500 mb-1">Before</p>
                    <p className="text-2xl font-bold" style={{ color: humanizeResult.detection_before.ai_score > 0.65 ? "#ef4444" : humanizeResult.detection_before.ai_score > 0.4 ? "#f59e0b" : "#22c55e" }}>
                      {Math.round(humanizeResult.detection_before.ai_score * 100)}%
                    </p>
                    <p className="text-xs text-zinc-500">{humanizeResult.detection_before.verdict}</p>
                  </div>
                  <div className="bg-zinc-800/50 rounded-lg p-4 text-center">
                    <p className="text-xs text-zinc-500 mb-1">After</p>
                    <p className="text-2xl font-bold" style={{ color: humanizeResult.detection_after.ai_score > 0.65 ? "#ef4444" : humanizeResult.detection_after.ai_score > 0.4 ? "#f59e0b" : "#22c55e" }}>
                      {Math.round(humanizeResult.detection_after.ai_score * 100)}%
                    </p>
                    <p className="text-xs text-zinc-500">{humanizeResult.detection_after.verdict}</p>
                  </div>
                </div>

                {/* Sentence-level details */}
                {humanizeResult.sentence_details && (
                  <div className="space-y-1.5">
                    <p className="text-xs text-zinc-500 font-medium">Per-Sentence Results</p>
                    {humanizeResult.sentence_details.filter((d) => !d.skipped).map((d, i) => (
                      <div key={i} className="bg-zinc-800/30 rounded-lg px-3 py-2 space-y-1">
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-xs text-zinc-500 line-through leading-relaxed flex-1">{d.original}</p>
                          <span className="text-xs font-mono text-red-400 whitespace-nowrap">
                            {d.original_ai_score !== null ? `${Math.round(d.original_ai_score * 100)}%` : "—"}
                          </span>
                        </div>
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-sm text-zinc-300 leading-relaxed flex-1">{d.humanized}</p>
                          <span className="text-xs font-mono text-green-400 whitespace-nowrap">
                            {d.best_ai_score !== null ? `${Math.round(d.best_ai_score * 100)}%` : "—"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Full-text iteration log */}
                {humanizeResult.iterations && humanizeResult.iterations.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-xs text-zinc-500 font-medium">Iteration log</p>
                    {humanizeResult.iterations.map((it) => (
                      <div key={it.iteration} className="flex items-center justify-between text-xs text-zinc-400 bg-zinc-800/30 rounded px-3 py-1.5">
                        <span>#{it.iteration} &middot; {it.strength}</span>
                        <span className="font-mono">{Math.round(it.ai_score * 100)}% AI</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Output text */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs text-zinc-500 font-medium">Final Output</p>
                    <button onClick={() => navigator.clipboard.writeText(humanizeResult.humanized)} className="text-xs text-blue-400 hover:text-blue-300">Copy</button>
                  </div>
                  <div className="bg-zinc-800/50 rounded-lg p-4 text-sm leading-relaxed text-zinc-300 max-h-64 overflow-y-auto whitespace-pre-wrap">
                    {humanizeResult.humanized}
                  </div>
                </div>
              </div>
            )}

            {/* Empty state */}
            {!detection && !sentenceDetection && !humanizeResult && !loading && (
              <div className="flex items-center justify-center h-64 bg-zinc-900 rounded-xl border border-zinc-800 border-dashed">
                <p className="text-sm text-zinc-600">Results will appear here</p>
              </div>
            )}
          </div>
        </div>
      </main>

      <footer className="border-t border-zinc-800 px-6 py-3">
        <p className="text-center text-xs text-zinc-600">
          Runs 100% locally &middot; RoBERTa + Qwen 3.5 detection &middot; Sentence-level adversarial humanization &middot; Ollama LLM rewriting
        </p>
      </footer>
    </div>
  );
}
