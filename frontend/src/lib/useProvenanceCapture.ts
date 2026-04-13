/**
 * Hook that attaches provenance capture to a textarea.
 *
 * Uses `beforeinput` + `InputEvent.inputType` to distinguish typed vs pasted
 * vs deleted content (MDN: the standard way in modern browsers).
 *
 * Typing is aggregated into "bursts" separated by >1s of idleness to avoid
 * one event per keystroke.  Pastes and large deletions flush immediately.
 */
import { useEffect } from "react";

import { recorder } from "./provenance";

const TYPE_BURST_IDLE_MS = 1_000;

type TextareaRef = React.RefObject<HTMLTextAreaElement | null>;

export function useProvenanceCapture(ref: TextareaRef): void {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

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

    const handleBeforeInput = (e: Event) => {
      const ev = e as InputEvent;
      const data = ev.data ?? "";

      switch (ev.inputType) {
        case "insertText":
        case "insertCompositionText":
        case "insertLineBreak":
        case "insertParagraph": {
          const chunk = data || (ev.inputType === "insertLineBreak" || ev.inputType === "insertParagraph" ? "\n" : "");
          if (chunk) {
            burstBuffer += chunk;
            if (burstTimer) clearTimeout(burstTimer);
            burstTimer = setTimeout(flushBurst, TYPE_BURST_IDLE_MS);
          }
          break;
        }
        case "insertFromPaste": {
          flushBurst();
          // The DataTransfer-style payload isn't on InputEvent for paste;
          // the separate `paste` handler below captures the real text.
          break;
        }
        case "deleteContentBackward":
        case "deleteContentForward":
        case "deleteWordBackward":
        case "deleteWordForward":
        case "deleteByCut":
        case "deleteByDrag": {
          flushBurst();
          const selLen = el.selectionEnd - el.selectionStart;
          const count = selLen > 0 ? selLen : 1;
          recorder.deleted(count);
          break;
        }
        default:
          break;
      }
    };

    const handlePaste = (e: ClipboardEvent) => {
      const pasted = e.clipboardData?.getData("text") ?? "";
      if (pasted) {
        flushBurst();
        recorder.pasted(pasted, "external");
      }
    };

    const handleBlur = () => {
      flushBurst();
      void recorder.flush();
    };

    el.addEventListener("beforeinput", handleBeforeInput);
    el.addEventListener("paste", handlePaste);
    el.addEventListener("blur", handleBlur);

    return () => {
      flushBurst();
      el.removeEventListener("beforeinput", handleBeforeInput);
      el.removeEventListener("paste", handlePaste);
      el.removeEventListener("blur", handleBlur);
    };
  }, [ref]);
}
