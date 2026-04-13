import { create } from "zustand";

import { api } from "../lib/api";
import type { Document, Project, Revision } from "../lib/types";

type DocumentsState = {
  projects: Project[];
  documentsByProject: Record<string, Document[]>;
  currentProjectId: string | null;
  currentDocumentId: string | null;
  currentRevisions: Revision[];
  loadingProjects: boolean;

  // Actions
  loadProjects: () => Promise<void>;
  createProject: (name: string) => Promise<Project>;
  deleteProject: (id: string) => Promise<void>;
  selectProject: (id: string | null) => Promise<void>;

  loadDocuments: (projectId: string) => Promise<void>;
  createDocument: (title: string, initialContent?: string) => Promise<Document | null>;
  selectDocument: (id: string | null) => Promise<Document | null>;
  renameDocument: (id: string, title: string) => Promise<void>;
  deleteDocument: (id: string) => Promise<void>;

  loadRevisions: (docId: string) => Promise<void>;
  saveRevision: (docId: string, content: string, aiScore?: number, note?: string) => Promise<Revision>;
  restoreRevision: (docId: string, revId: string) => Promise<Revision>;
};

export const useDocumentsStore = create<DocumentsState>((set, get) => ({
  projects: [],
  documentsByProject: {},
  currentProjectId: null,
  currentDocumentId: null,
  currentRevisions: [],
  loadingProjects: false,

  loadProjects: async () => {
    set({ loadingProjects: true });
    try {
      const projects = await api.listProjects();
      set({ projects });
    } finally {
      set({ loadingProjects: false });
    }
  },

  createProject: async (name) => {
    const p = await api.createProject(name);
    set({ projects: [p, ...get().projects] });
    return p;
  },

  deleteProject: async (id) => {
    await api.deleteProject(id);
    const projects = get().projects.filter((p) => p.id !== id);
    const docsByProject = { ...get().documentsByProject };
    delete docsByProject[id];
    set({
      projects,
      documentsByProject: docsByProject,
      currentProjectId: get().currentProjectId === id ? null : get().currentProjectId,
      currentDocumentId: null,
    });
  },

  selectProject: async (id) => {
    set({ currentProjectId: id, currentDocumentId: null, currentRevisions: [] });
    if (id) await get().loadDocuments(id);
  },

  loadDocuments: async (projectId) => {
    const docs = await api.listDocuments(projectId);
    set({
      documentsByProject: { ...get().documentsByProject, [projectId]: docs },
    });
  },

  createDocument: async (title, initialContent) => {
    const projectId = get().currentProjectId;
    if (!projectId) return null;
    const doc = await api.createDocument({
      project_id: projectId,
      title,
      initial_content: initialContent,
    });
    set({
      documentsByProject: {
        ...get().documentsByProject,
        [projectId]: [doc, ...(get().documentsByProject[projectId] ?? [])],
      },
    });
    return doc;
  },

  selectDocument: async (id) => {
    set({ currentDocumentId: id, currentRevisions: [] });
    if (!id) return null;
    const doc = await api.getDocument(id);
    await get().loadRevisions(id);
    return doc;
  },

  renameDocument: async (id, title) => {
    const doc = await api.renameDocument(id, title);
    const projectId = doc.project_id;
    const existing = get().documentsByProject[projectId] ?? [];
    set({
      documentsByProject: {
        ...get().documentsByProject,
        [projectId]: existing.map((d) => (d.id === id ? doc : d)),
      },
    });
  },

  deleteDocument: async (id) => {
    await api.deleteDocument(id);
    const projectId = get().currentProjectId;
    if (!projectId) return;
    const existing = get().documentsByProject[projectId] ?? [];
    set({
      documentsByProject: {
        ...get().documentsByProject,
        [projectId]: existing.filter((d) => d.id !== id),
      },
      currentDocumentId: get().currentDocumentId === id ? null : get().currentDocumentId,
      currentRevisions: get().currentDocumentId === id ? [] : get().currentRevisions,
    });
  },

  loadRevisions: async (docId) => {
    const revs = await api.listRevisions(docId);
    set({ currentRevisions: revs });
  },

  saveRevision: async (docId, content, aiScore, note) => {
    const rev = await api.saveRevision(docId, {
      content,
      ai_score: aiScore,
      note,
    });
    await get().loadRevisions(docId);
    return rev;
  },

  restoreRevision: async (docId, revId) => {
    const rev = await api.restoreRevision(docId, revId);
    await get().loadRevisions(docId);
    return rev;
  },
}));
