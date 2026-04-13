/**
 * Provenance capture for a Tiptap / ProseMirror editor.
 *
 * Replaces the textarea-era hook (`useProvenanceCapture`).  ProseMirror
 * gives us typed semantic operations as transaction `Step`s, which is a
 * far cleaner signal than DOM `beforeinput` — IME, undo/redo, drag-drop,
 * and structural changes all surface as the same primitive.
 *
 * What this hook ignores (does NOT record):
 *   - Programmatic writes (setContent from doc-load, restore, post-humanize).
 *     Caller passes a ref flag we check synchronously inside the handler.
 *     Without this, every document switch counterfeits a "user typed the
 *     whole doc just now" event.
 *   - Undo/redo transactions.  Recorded as `manual_edit` annotations
 *     instead of `typed`/`deleted` so they don't inflate authorship counts.
 *   - Pure formatting changes (AddMark / RemoveMark).
 *
 * Step classification:
 *   ReplaceStep with size N inserted, M deleted → both `typed` (or
 *     `pasted`) for N AND `deleted` for M.  Logging the FULL deletion is
 *     correct for replace-overwrite (e.g. select-all then paste).  The
 *     previous net-difference logic under-counted deletions on common
 *     editing patterns.
 */
import type { RefObject } from "react";
import { useEffect } from "react";

import type { Editor } from "@tiptap/react";
import type { Transaction } from "@tiptap/pm/state";

import { recorder } from "./provenance";

const TYPE_BURST_IDLE_MS = 1_000;

export function useTiptapProvenanceCapture(
  editor: Editor | null,
  programmaticUpdateRef?: RefObject<boolean>,
): void {
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

      // ---- Filters: skip transactions that aren't authentic user authorship.
      // 1. Programmatic writes — the component sets a ref flag before calling
      //    setContent, clears after a microtask.  Without this we'd record
      //    "user typed the entire document" on every doc switch, restore, or
      //    post-humanize sync.
      if (programmaticUpdateRef?.current) return;
      // 2. Tiptap's own preventUpdate flag (set by emitUpdate: false) — same
      //    intent, belt-and-braces in case the ref window is narrowly missed.
      if (tr.getMeta("preventUpdate") === true) return;
      // 3. Anything that explicitly opts out of history / authorship logging.
      if (tr.getMeta("addToHistory") === false) return;

      const isPaste =
        tr.getMeta("paste") === true || tr.getMeta("uiEvent") === "paste";
      const isHistory =
        tr.getMeta("history$") !== undefined ||
        tr.getMeta("y-sync$") !== undefined; // Yjs collab if we ever add it

      let totalInserted = "";
      let totalDeletedSize = 0;

      for (const step of tr.steps) {
        const stepJson = step.toJSON() as {
          stepType: string;
          from?: number;
          to?: number;
        };
        if (
          stepJson.stepType !== "replace" &&
          stepJson.stepType !== "replaceAround"
        )
          continue;

        const sliceObj = (
          step as unknown as {
            slice?: {
              size: number;
              content: { textBetween: (a: number, b: number, sep?: string) => string };
            };
          }
        ).slice;
        const insertedText =
          sliceObj && sliceObj.size > 0
            ? sliceObj.content.textBetween(0, sliceObj.size, "\n")
            : "";
        const from = stepJson.from ?? 0;
        const to = stepJson.to ?? 0;
        const deletedSize = Math.max(0, to - from);

        totalInserted += insertedText;
        totalDeletedSize += deletedSize;
      }

      // History (undo/redo): the original typed/deleted events that produced
      // the prior state are already on the chain.  Re-issuing typed/deleted
      // here would double-count and weaken the integrity story.  Surface as
      // a `manual_edit` annotation so the report still shows the user took
      // an action.
      if (isHistory) {
        flushBurst();
        recorder.manualEdit({
          source: "history",
          inserted_chars: totalInserted.length,
          deleted_chars: totalDeletedSize,
        });
        return;
      }

      // Always log the full deletion size first if there was any.  This
      // covers select-and-replace patterns (paste-overwrite, type-overwrite)
      // accurately — the previous net-difference logic under-counted them.
      if (totalDeletedSize > 0) {
        flushBurst();
        recorder.deleted(totalDeletedSize);
      }

      if (isPaste && totalInserted) {
        flushBurst();
        recorder.pasted(totalInserted, "external");
        return;
      }

      if (totalInserted) {
        burstBuffer += totalInserted;
        if (burstTimer) clearTimeout(burstTimer);
        burstTimer = setTimeout(flushBurst, TYPE_BURST_IDLE_MS);
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
  }, [editor, programmaticUpdateRef]);
}
