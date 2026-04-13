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

// ---- Documents ----
export type Project = {
  id: string;
  name: string;
  created_at: number;
  updated_at: number;
};

export type Document = {
  id: string;
  project_id: string;
  title: string;
  source_type: string;
  current_revision_id: string | null;
  created_at: number;
  updated_at: number;
};

export type Revision = {
  id: string;
  document_id: string;
  parent_id: string | null;
  content: string;
  content_hash: string;
  ai_score: number | null;
  note: string | null;
  created_at: number;
};

// ---- Provenance ----
export type ProvenanceEventType =
  | "session_start"
  | "session_end"
  | "typed"
  | "pasted"
  | "deleted"
  | "imported"
  | "ai_rewrite_requested"
  | "ai_rewrite_applied"
  | "ai_rewrite_rejected"
  | "detection_run"
  | "revision_saved"
  | "manual_edit";

export type ProvenanceEvent = {
  event_type: ProvenanceEventType;
  timestamp: number;
  payload: Record<string, unknown>;
};

export type ProvenanceSession = {
  id: string;
  document_id: string;
  started_at: number;
  ended_at: number | null;
  genesis_hash: string;
  final_hash: string | null;
};

export type ProvenanceReport = {
  document_id: string;
  document_title: string;
  sessions: {
    session_id: string;
    started_at: number;
    ended_at: number | null;
    valid: boolean;
    events: number;
    final_hash: string | null;
    genesis_hash: string;
    reason: string | null;
  }[];
  total_events: number;
  authorship: {
    typed_chars: number;
    pasted_chars: number;
    ai_assisted_chars: number;
    typed_pct: number;
    pasted_pct: number;
    ai_assisted_pct: number;
  };
  timeline: {
    timestamp: number;
    event_type: string;
    sequence: number;
    session_id: string;
    summary: string;
  }[];
  integrity: { valid: boolean; sessions_verified: number };
};
