"use client";

import { useEffect, useState } from "react";

import { recorder } from "../lib/provenance";
import { useAppStore } from "../store/app";
import { useDocumentsStore } from "../store/documents";
import { ImportButton } from "./ImportButton";

export function Sidebar() {
  const {
    projects,
    documentsByProject,
    currentProjectId,
    currentDocumentId,
    loadProjects,
    createProject,
    selectProject,
    deleteProject,
    createDocument,
    selectDocument,
    deleteDocument,
  } = useDocumentsStore();

  const { loadContent, clearResults } = useAppStore();
  const [creatingProject, setCreatingProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  // Hydration guard — Next.js SSRs client components, and Zustand state
  // only exists after mount, so any store-derived attribute renders
  // differently server-vs-client and React can't patch attributes.
  // Gating on `mounted` forces both to render the same initial output.
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    loadProjects();
  }, [loadProjects]);

  // Auto-select first project
  useEffect(() => {
    if (!currentProjectId && projects.length > 0) {
      selectProject(projects[0].id);
    }
  }, [projects, currentProjectId, selectProject]);

  const handleSelectDoc = async (docId: string) => {
    clearResults();
    await recorder.attachToDocument(docId);
    const doc = await selectDocument(docId);
    if (doc?.current_revision_id) {
      // Pull the current revision content into the editor.  ProseMirror
      // revisions hydrate the editor from JSON (preserves headings, marks,
      // lists); plain-text revisions come in as the raw string.
      const revs = useDocumentsStore.getState().currentRevisions;
      const currentRev = revs.find((r) => r.id === doc.current_revision_id);
      if (!currentRev) {
        loadContent("", null);
      } else if (currentRev.format === "prosemirror") {
        try {
          const json = JSON.parse(currentRev.content);
          // Plain-text projection is set to "" — the editor's onUpdate will
          // overwrite it with the hydrated text on the next render.
          loadContent("", json);
        } catch {
          // Stored format claims prosemirror but content isn't valid JSON.
          // Surface the raw string so the user can recover their content.
          loadContent(currentRev.content, null);
        }
      } else {
        loadContent(currentRev.content, null);
      }
    } else {
      loadContent("", null);
    }
  };

  const handleNewDoc = async () => {
    const title = window.prompt("Document title:");
    if (!title) return;
    const doc = await createDocument(title);
    if (doc) await handleSelectDoc(doc.id);
  };

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) {
      setCreatingProject(false);
      return;
    }
    const p = await createProject(newProjectName.trim());
    setNewProjectName("");
    setCreatingProject(false);
    await selectProject(p.id);
  };

  const docs = currentProjectId
    ? documentsByProject[currentProjectId] ?? []
    : [];

  return (
    <aside className="w-64 shrink-0 border-r border-zinc-800 bg-zinc-950 flex flex-col overflow-hidden">
      {/* Projects */}
      <div className="p-3 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
            Projects
          </span>
          <button
            onClick={() => setCreatingProject(true)}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            + New
          </button>
        </div>
        {creatingProject && (
          <input
            autoFocus
            value={newProjectName}
            onChange={(e) => setNewProjectName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleCreateProject();
              if (e.key === "Escape") {
                setCreatingProject(false);
                setNewProjectName("");
              }
            }}
            onBlur={handleCreateProject}
            placeholder="Project name"
            className="w-full text-sm bg-zinc-900 border border-zinc-700 rounded px-2 py-1 mb-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        )}
        <div className="space-y-0.5">
          {projects.length === 0 && !creatingProject && (
            <p className="text-xs text-zinc-600 py-1">No projects yet</p>
          )}
          {projects.map((p) => (
            <div
              key={p.id}
              className={`group flex items-center justify-between px-2 py-1 rounded text-sm cursor-pointer ${
                currentProjectId === p.id
                  ? "bg-blue-500/10 text-blue-400"
                  : "text-zinc-300 hover:bg-zinc-900"
              }`}
              onClick={() => selectProject(p.id)}
            >
              <span className="truncate">{p.name}</span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm(`Delete project "${p.name}" and all its documents?`)) {
                    deleteProject(p.id);
                  }
                }}
                className="opacity-0 group-hover:opacity-100 text-xs text-zinc-500 hover:text-red-400 transition-opacity"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Documents */}
      <div className="flex-1 overflow-y-auto p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
            Documents
          </span>
          <div className="flex items-center gap-3">
            <ImportButton />
            <button
              onClick={handleNewDoc}
              disabled={!mounted || !currentProjectId}
              className="text-xs text-blue-400 hover:text-blue-300 disabled:text-zinc-700 disabled:cursor-not-allowed"
            >
              + New
            </button>
          </div>
        </div>
        <div className="space-y-0.5">
          {docs.length === 0 && currentProjectId && (
            <p className="text-xs text-zinc-600 py-1">No documents yet</p>
          )}
          {!currentProjectId && (
            <p className="text-xs text-zinc-600 py-1">Select a project</p>
          )}
          {docs.map((d) => (
            <div
              key={d.id}
              className={`group flex items-center justify-between px-2 py-1 rounded text-sm cursor-pointer ${
                currentDocumentId === d.id
                  ? "bg-blue-500/10 text-blue-400"
                  : "text-zinc-300 hover:bg-zinc-900"
              }`}
              onClick={() => handleSelectDoc(d.id)}
            >
              <span className="truncate">{d.title}</span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm(`Delete "${d.title}"?`)) deleteDocument(d.id);
                }}
                className="opacity-0 group-hover:opacity-100 text-xs text-zinc-500 hover:text-red-400 transition-opacity"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
