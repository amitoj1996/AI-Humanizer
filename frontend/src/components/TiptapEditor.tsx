"use client";

import Placeholder from "@tiptap/extension-placeholder";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useRef } from "react";

import { useTiptapProvenanceCapture } from "../lib/useTiptapProvenanceCapture";
import { useAppStore } from "../store/app";

/**
 * Tiptap-based prose editor.  Replaces the textarea — gives us:
 *   - Real document model (ProseMirror) instead of a blob of characters
 *   - Typed transactions for fine-grained provenance capture
 *   - Future hooks for headings / lists / inline marks without rebuilding
 *
 * KNOWN INTERIM LIMITATION (data loss): plain text round-trips through
 * the rest of the app via `editor.getText()`.  Marks (bold/italic/code),
 * heading levels, list structure, and blockquotes are STRIPPED on
 * save / detect / humanize / document switch.  Migrating `Revision.content`
 * to ProseMirror JSON (with a `format` column for backwards compat) is
 * the next phase; for now the rich editor is a UX upgrade only, not a
 * structural-content one.
 */

export function TiptapEditor() {
  const { text, setText } = useAppStore();
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
    content: text,
    onUpdate: ({ editor: e }) => {
      // Sync plain text to the store so the rest of the app
      // (detect/humanize/save) keeps working unchanged.
      const next = e.getText();
      if (next !== text) setText(next);
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

  // Programmatic text updates from the store (doc switch, restore-revision,
  // setText after humanize) need to flow back into the editor.  We compare
  // current editor text to the store value to break the loop, then mark
  // the transaction as programmatic so the provenance hook skips it.
  useEffect(() => {
    if (!editor) return;
    if (editor.getText() === text) return;
    programmaticUpdateRef.current = true;
    try {
      // emitUpdate:false sets `tr.setMeta('preventUpdate', true)` which the
      // hook also checks — two independent reasons to skip recording.
      editor.commands.setContent(text, { emitUpdate: false });
    } finally {
      // Clear after the transaction has flushed.  Using queueMicrotask
      // (rather than setTimeout(0)) means we re-arm before any animation
      // frame, so subsequent user keystrokes are recorded correctly.
      queueMicrotask(() => {
        programmaticUpdateRef.current = false;
      });
    }
  }, [editor, text]);

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
