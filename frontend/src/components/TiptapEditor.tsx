"use client";

import Placeholder from "@tiptap/extension-placeholder";
import type { Content, JSONContent } from "@tiptap/react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useRef } from "react";

import { useTiptapProvenanceCapture } from "../lib/useTiptapProvenanceCapture";
import { useAppStore } from "../store/app";

/**
 * Tiptap-based prose editor.
 *
 * Two views of the document live in the store:
 *   - `text` (plain string) — what detect/humanize see, and what the
 *     revision content_hash dedup key is computed from.
 *   - `documentJson` (ProseMirror doc) — the canonical structured form,
 *     used for revision saves with `format: "prosemirror"` and for replay.
 *
 * On load (doc switch / restore), if the revision is `prosemirror` we
 * hydrate the editor from JSON; if `text` we fall back to the string.
 * Either way both projections in the store stay coherent.
 */

export function TiptapEditor() {
  const { text, documentJson, setText, setDocumentJson } = useAppStore();
  const containerRef = useRef<HTMLDivElement>(null);
  // Set to `true` while we're programmatically writing into the editor (doc
  // load, restore, post-humanize sync).  The provenance hook checks this
  // flag and skips recording, so we don't counterfeit "user typed the whole
  // doc" events on every doc switch.  Tiptap's own preventUpdate meta is
  // also checked as belt-and-braces.
  const programmaticUpdateRef = useRef(false);
  const wordCount = text.trim().split(/\s+/).filter(Boolean).length;

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        // Keep the schema small for v1 — we only need prose primitives.
        // Extensions we DO want: paragraph, headings, bold, italic, lists,
        // code, blockquote, horizontalRule.  StarterKit ships all of these.
      }),
      Placeholder.configure({ placeholder: "Paste your text here..." }),
    ],
    // Required for Next.js SSR — without this we get a hydration mismatch.
    immediatelyRender: false,
    // Prefer the structured doc when available; fall back to plain text
    // for legacy revisions or first-launch.
    content: (documentJson as Content | undefined) ?? text,
    onUpdate: ({ editor: e }) => {
      // Keep BOTH projections in sync.  Plain text drives detect/humanize,
      // the JSON drives revision saves and replay frames.
      const nextText = e.getText();
      const nextJson = e.getJSON();
      if (nextText !== text) setText(nextText);
      if (JSON.stringify(nextJson) !== JSON.stringify(documentJson)) {
        setDocumentJson(nextJson);
      }
    },
    editorProps: {
      attributes: {
        // Apply our existing textarea styling to the contenteditable.
        class:
          "min-h-[18rem] outline-none px-4 py-3 text-sm leading-relaxed prose prose-invert prose-zinc max-w-none",
        // Important for Playwright + accessibility — the placeholder + the
        // role mean queries like getByRole("textbox") continue to find
        // the editor.
        "aria-placeholder": "Paste your text here...",
        role: "textbox",
        "aria-multiline": "true",
      },
    },
  });

  useTiptapProvenanceCapture(editor, programmaticUpdateRef);

  // Programmatic content sync: when the store changes (doc switch / restore
  // / post-humanize), push the new content into the editor.  Prefer the
  // structured JSON when present (preserves headings/marks/lists across
  // restore); fall back to plain text for legacy revisions.
  useEffect(() => {
    if (!editor) return;
    const currentEditorText = editor.getText();
    const currentEditorJson = editor.getJSON();

    const targetIsJson = documentJson !== null;
    const needsUpdate = targetIsJson
      ? JSON.stringify(currentEditorJson) !== JSON.stringify(documentJson)
      : currentEditorText !== text;
    if (!needsUpdate) return;

    programmaticUpdateRef.current = true;
    try {
      // emitUpdate:false also sets `tr.setMeta('preventUpdate', true)` —
      // both the ref AND the meta are checked by the provenance hook.
      const payload: Content = targetIsJson ? (documentJson as JSONContent) : text;
      editor.commands.setContent(payload, { emitUpdate: false });
    } finally {
      queueMicrotask(() => {
        programmaticUpdateRef.current = false;
      });
    }
  }, [editor, text, documentJson]);

  // Tiptap docs: render null until the editor is initialised on the
  // client to avoid SSR hydration mismatches.
  if (!editor) {
    return (
      <div
        ref={containerRef}
        className="relative min-h-[18rem] bg-zinc-900 border border-zinc-800 rounded-xl"
      />
    );
  }

  return (
    <div
      ref={containerRef}
      className="relative bg-zinc-900 border border-zinc-800 rounded-xl focus-within:ring-2 focus-within:ring-blue-500/50 focus-within:border-blue-500/50"
    >
      <EditorContent editor={editor} />
      <span className="absolute bottom-3 right-3 text-xs text-zinc-600 pointer-events-none">
        {wordCount} words
      </span>
    </div>
  );
}
