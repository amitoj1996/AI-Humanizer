import type {
  DetectionResult,
  HumanizeRequest,
  HumanizeResult,
  ModelsResponse,
  SentenceDetectionResult,
} from "./types";

// Dev: `npm run dev` sets NEXT_PUBLIC_API_BASE=http://localhost:8000
// Prod/desktop: API served from same origin as the static frontend.
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const payload = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(payload.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(res.statusText);
  return res.json() as Promise<T>;
}

export const api = {
  detect: (text: string) => post<DetectionResult>("/api/detect", { text }),
  detectSentences: (text: string) =>
    post<SentenceDetectionResult>("/api/detect/sentences", { text }),
  humanize: (req: HumanizeRequest) =>
    post<HumanizeResult>("/api/humanize", req),
  listModels: () => get<ModelsResponse>("/api/models"),
  selectModel: (model: string) =>
    post<{ selected_model: string }>("/api/models/select", { model }),
};
