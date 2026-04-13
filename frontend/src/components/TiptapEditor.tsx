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
 * Plain text continues to round-trip through the app via `editor.getText()`,
 * so backend detection / humanize / revisions stay unchanged.  A future
 * commit can store ProseMirror JSON in revisions for richer replay.
 */

export function TiptapEditor() {
  const { text, setText } = useAppStore();
  const containerRef = useRef<HTMLDivElement>(null);
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
        // role mean queries like getByPlaceholder("Paste your text here...")
        // continue to find the editor.
        "aria-placeholder": "Paste your text here...",
        role: "textbox",
        "aria-multiline": "true",
      },
    },
  });

  useTiptapProvenanceCapture(editor);

  // Programmatic text updates from the store (e.g. document switch,
  // restore-revision, "setText after humanize") need to flow back into the
  // editor.  We compare current editor text to the store value and only
  // run setContent on a real divergence — otherwise we'd loop.
  useEffect(() => {
    if (!editor) return;
    if (editor.getText() === text) return;
    // `false` to skip emitting a `transaction` for this programmatic write —
    // a setText from the store is not a user authorship event.
    editor.commands.setContent(text, { emitUpdate: false });
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
