import { create } from "zustand";

import type {
  DetectionMode,
  DetectionResult,
  HumanizeResult,
  Mode,
  SentenceDetectionResult,
  Strength,
  Tone,
} from "../lib/types";

export type AppTab = "detect" | "humanize";
export type LoadingKind = "detect" | "humanize" | null;

// ProseMirror JSON document.  We don't need to type the content nodes
// strictly here — Tiptap's JSONContent is the source of truth at the
// editor boundary and the rest of the app just round-trips this opaquely
// (via JSON.stringify for the revision save path).
export type ProseMirrorDoc = {
  type: "doc";
  content?: unknown[];
  attrs?: Record<string, unknown>;
  marks?: unknown[];
};

type AppState = {
  // Input
  text: string;                     // plain-text projection (detect/humanize)
  documentJson: ProseMirrorDoc | null; // canonical rich doc (revisions/replay)
  // UI controls
  activeTab: AppTab;
  strength: Strength;
  tone: Tone;
  mode: Mode;
  detectionMode: DetectionMode;
  preserveCitations: boolean;
  // Results
  detection: DetectionResult | null;
  sentenceDetection: SentenceDetectionResult | null;
  humanizeResult: HumanizeResult | null;
  // Loading/error
  loading: LoadingKind;
  error: string | null;
  // Models
  models: string[];
  selectedModel: string;
  ollamaAvailable: boolean | null;
  // Setters
  setText: (t: string) => void;
  setDocumentJson: (j: ProseMirrorDoc | null) => void;
  /** Replace both text + json atomically (used by doc load / restore). */
  loadContent: (text: string, json: ProseMirrorDoc | null) => void;
  setActiveTab: (t: AppTab) => void;
  setStrength: (s: Strength) => void;
  setTone: (t: Tone) => void;
  setMode: (m: Mode) => void;
  setDetectionMode: (d: DetectionMode) => void;
  setPreserveCitations: (p: boolean) => void;
  setDetection: (d: DetectionResult | null) => void;
  setSentenceDetection: (d: SentenceDetectionResult | null) => void;
  setHumanizeResult: (d: HumanizeResult | null) => void;
  setLoading: (l: LoadingKind) => void;
  setError: (e: string | null) => void;
  setModels: (m: string[]) => void;
  setSelectedModel: (m: string) => void;
  setOllamaAvailable: (a: boolean | null) => void;
  clearResults: () => void;
};

export const useAppStore = create<AppState>((set) => ({
  text: "",
  documentJson: null,
  activeTab: "detect",
  strength: "medium",
  tone: "general",
  mode: "sentence",
  detectionMode: "sentences",
  preserveCitations: true,
  detection: null,
  sentenceDetection: null,
  humanizeResult: null,
  loading: null,
  error: null,
  models: [],
  selectedModel: "",
  ollamaAvailable: null,
  setText: (text) => set({ text }),
  setDocumentJson: (documentJson) => set({ documentJson }),
  loadContent: (text, documentJson) => set({ text, documentJson }),
  setActiveTab: (activeTab) => set({ activeTab }),
  setStrength: (strength) => set({ strength }),
  setTone: (tone) => set({ tone }),
  setMode: (mode) => set({ mode }),
  setDetectionMode: (detectionMode) => set({ detectionMode }),
  setPreserveCitations: (preserveCitations) => set({ preserveCitations }),
  setDetection: (detection) => set({ detection }),
  setSentenceDetection: (sentenceDetection) => set({ sentenceDetection }),
  setHumanizeResult: (humanizeResult) => set({ humanizeResult }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  setModels: (models) => set({ models }),
  setSelectedModel: (selectedModel) => set({ selectedModel }),
  setOllamaAvailable: (ollamaAvailable) => set({ ollamaAvailable }),
  clearResults: () =>
    set({
      detection: null,
      sentenceDetection: null,
      humanizeResult: null,
      error: null,
    }),
}));
