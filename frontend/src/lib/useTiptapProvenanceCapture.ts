/**
 * Provenance capture for a Tiptap / ProseMirror editor.
 *
 * Replaces the textarea-era hook (`useProvenanceCapture`).  ProseMirror
 * gives us typed semantic operations as transaction `Step`s, which is a
 * far cleaner signal than DOM `beforeinput` — IME, undo/redo, drag-drop,
 * and structural changes all surface as the same primitive.
 *
 * Classification per step:
 *   ReplaceStep with non-empty slice + zero deletion  → typed (or pasted)
 *   ReplaceStep with empty slice + non-zero deletion  → deleted
 *   AddMarkStep / RemoveMarkStep                      → ignored (formatting)
 *
 * Paste vs type:  ProseMirror sets `tr.getMeta('paste')` for paste-origin
 * transactions (and `tr.getMeta('uiEvent') === 'paste'` in some versions).
 * We check both for compatibility.
 *
 * Burst aggregation: contiguous `typed` steps within 1 s of each other
 * collapse into a single `typed` event so we don't spam the chain with
 * one-event-per-keystroke.
 */
import { useEffect } from "react";

import type { Editor } from "@tiptap/react";
import type { Transaction } from "@tiptap/pm/state";

import { recorder } from "./provenance";

const TYPE_BURST_IDLE_MS = 1_000;

export function useTiptapProvenanceCapture(editor: Editor | null): void {
  useEffect(() => {
    if (!editor) return;

    let burstBuffer = "";
    let burstTimer: ReturnType<typeof setTimeout> | null = null;

    const flushBurst = () => {
      if (burstBuffer) {
        recorder.typed(burstBuffer);
        burstBuffer = "";
      }
      if (burstTimer) {
        clearTimeout(burstTimer);
        burstTimer = null;
      }
    };

    const handleTransaction = ({ transaction: tr }: { transaction: Transaction }) => {
      if (!tr.docChanged) return;

      const isPaste =
        tr.getMeta("paste") === true || tr.getMeta("uiEvent") === "paste";
      // History (undo/redo) generates structural transactions we don't want
      // to count as fresh user keystrokes — surface as manual_edit instead.
      const isHistory =
        tr.getMeta("history$") !== undefined ||
        tr.getMeta("addToHistory") === false;

      let totalInserted = "";
      let totalDeletedSize = 0;

      for (const step of tr.steps) {
        // ProseMirror Step is a base class; we care about ReplaceStep + ReplaceAroundStep
        const stepJson = step.toJSON() as {
          stepType: string;
          from?: number;
          to?: number;
          slice?: { content?: unknown[] };
        };
        if (
          stepJson.stepType !== "replace" &&
          stepJson.stepType !== "replaceAround"
        )
          continue;

        // Extract inserted text via the step's slice; deleted size from from/to.
        // We use the mapped ranges via `getMap()` for ReplaceStep; here we
        // rely on the slice's textBetween when content is present.
        const sliceObj = (step as unknown as { slice?: { size: number; content: { textBetween: (a: number, b: number, sep?: string) => string } } }).slice;
        const insertedText = sliceObj && sliceObj.size > 0
          ? sliceObj.content.textBetween(0, sliceObj.size, "\n")
          : "";
        const from = stepJson.from ?? 0;
        const to = stepJson.to ?? 0;
        const deletedSize = Math.max(0, to - from);

        totalInserted += insertedText;
        totalDeletedSize += deletedSize;
      }

      if (isHistory) {
        // Treat undo/redo as a manual edit annotation — gives us a
        // navigable marker without inflating typed/pasted counts.
        if (totalInserted || totalDeletedSize) {
          flushBurst();
          recorder.deleted(totalDeletedSize);
          if (totalInserted)
            recorder.typed(totalInserted); // counts as re-typed via undo
        }
        return;
      }

      if (isPaste && totalInserted) {
        flushBurst();
        recorder.pasted(totalInserted, "external");
        if (totalDeletedSize > totalInserted.length) {
          // selection-replace paste: count the net deletion
          recorder.deleted(totalDeletedSize - totalInserted.length);
        }
        return;
      }

      // Pure deletion (no insertion text)
      if (!totalInserted && totalDeletedSize > 0) {
        flushBurst();
        recorder.deleted(totalDeletedSize);
        return;
      }

      // Typed insertion (possibly with selection-replace which acts like
      // a quick-overwrite — we count both halves)
      if (totalInserted) {
        burstBuffer += totalInserted;
        if (burstTimer) clearTimeout(burstTimer);
        burstTimer = setTimeout(flushBurst, TYPE_BURST_IDLE_MS);

        if (totalDeletedSize > totalInserted.length) {
          flushBurst();
          recorder.deleted(totalDeletedSize - totalInserted.length);
        }
      }
    };

    const handleBlur = () => {
      flushBurst();
      void recorder.flush();
    };

    editor.on("transaction", handleTransaction);
    editor.on("blur", handleBlur);

    return () => {
      flushBurst();
      editor.off("transaction", handleTransaction);
      editor.off("blur", handleBlur);
    };
  }, [editor]);
}
