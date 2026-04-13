import type {
  DetectionResult,
  Document,
  HumanizeRequest,
  HumanizeResult,
  ModelsResponse,
  Project,
  ProvenanceEvent,
  ProvenanceReport,
  ProvenanceSession,
  Revision,
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

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(res.statusText);
  return res.json() as Promise<T>;
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" });
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

  // ---- Documents ----
  listProjects: () => get<Project[]>("/api/projects"),
  createProject: (name: string) => post<Project>("/api/projects", { name }),
  deleteProject: (id: string) => del<{ ok: boolean }>(`/api/projects/${id}`),

  listDocuments: (projectId: string) =>
    get<Document[]>(`/api/projects/${projectId}/documents`),
  createDocument: (req: {
    project_id: string;
    title: string;
    initial_content?: string;
  }) => post<Document>("/api/documents", req),
  getDocument: (id: string) => get<Document>(`/api/documents/${id}`),
  renameDocument: (id: string, title: string) =>
    patch<Document>(`/api/documents/${id}`, { title }),
  deleteDocument: (id: string) => del<{ ok: boolean }>(`/api/documents/${id}`),

  listRevisions: (docId: string) =>
    get<Revision[]>(`/api/documents/${docId}/revisions`),
  saveRevision: (
    docId: string,
    req: { content: string; ai_score?: number; note?: string },
  ) => post<Revision>(`/api/documents/${docId}/revisions`, req),
  restoreRevision: (docId: string, revId: string) =>
    post<Revision>(
      `/api/documents/${docId}/revisions/${revId}/restore`,
      {},
    ),

  // ---- Provenance ----
  startSession: (documentId: string) =>
    post<ProvenanceSession>("/api/sessions", { document_id: documentId }),
  getActiveSession: (documentId: string) =>
    get<ProvenanceSession | null>(
      `/api/documents/${documentId}/active-session`,
    ),
  appendEvents: (sessionId: string, events: ProvenanceEvent[]) =>
    post<{ appended: number; error: string | null }>(
      `/api/sessions/${sessionId}/events`,
      { events },
    ),
  sealSession: (sessionId: string) =>
    post<ProvenanceSession>(`/api/sessions/${sessionId}/seal`, {}),
  getReport: (documentId: string) =>
    get<ProvenanceReport>(`/api/documents/${documentId}/provenance/report`),

  // ---- Import / Export ----
  importDocument: async (
    projectId: string,
    file: File,
  ): Promise<{
    document_id: string;
    title: string;
    source_type: string;
    char_count: number;
    warnings: string[];
  }> => {
    const form = new FormData();
    form.append("project_id", projectId);
    form.append("file", file);
    const res = await fetch(`${BASE}/api/documents/import`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      const payload = (await res.json().catch(() => ({}))) as {
        detail?: string;
      };
      throw new Error(payload.detail ?? res.statusText);
    }
    return res.json();
  },

  exportDocumentUrl: (documentId: string, format: "md" | "txt" | "docx") =>
    `${BASE}/api/documents/${documentId}/export?format=${format}`,
  exportProvenanceUrl: (documentId: string, format: "md" | "docx") =>
    `${BASE}/api/documents/${documentId}/provenance/export?format=${format}`,
};
