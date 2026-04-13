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

type AppState = {
  // Input
  text: string;
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
