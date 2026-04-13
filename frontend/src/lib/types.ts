// Shared types for the API. Keep in sync with backend Pydantic models.

export type Breakdown = {
  classifier: { ai_probability: number; human_probability: number };
  perplexity: {
    perplexity: number;
    burstiness: number;
    combined_ai_signal: number;
  };
  linguistic: {
    sentence_length_cv: number;
    type_token_ratio: number;
    ai_marker_density: number;
    contraction_rate: number;
    ai_signal: number;
    details: {
      word_count: number;
      sentence_count: number;
      ai_markers_found: number;
    };
  };
};

export type DetectionResult = {
  ai_score: number;
  human_score: number;
  verdict: string;
  breakdown: Breakdown;
};

export type SentenceScore = {
  sentence: string;
  ai_score: number | null;
  verdict: string;
  word_count: number;
};

export type SentenceDetectionResult = {
  overall: DetectionResult;
  average_sentence_ai: number;
  sentences: SentenceScore[];
  total_sentences: number;
};

export type SentenceDetail = {
  original: string;
  humanized: string;
  original_ai_score: number | null;
  best_ai_score: number | null;
  candidates_tested: number;
  skipped: boolean;
};

export type IterationLog = {
  iteration: number;
  strength: string;
  ai_score: number;
  verdict: string;
};

export type HumanizeResult = {
  original: string;
  humanized: string;
  detection_before: DetectionResult;
  detection_after: DetectionResult;
  iterations?: IterationLog[];
  sentence_details?: SentenceDetail[];
  total_iterations?: number;
  total_sentences?: number;
  mode: string;
  similarity_score?: number;
};

export type ModelsResponse = {
  ollama_available: boolean;
  models: string[];
};

export type Strength = "light" | "medium" | "aggressive";
export type Tone = "general" | "academic" | "casual" | "blog" | "professional";
export type Mode = "full" | "sentence";
export type DetectionMode = "overall" | "sentences";

export type HumanizeRequest = {
  text: string;
  strength: Strength;
  tone: Tone;
  mode: Mode;
  candidates_per_sentence?: number;
  max_iterations?: number;
  target_score?: number;
};
