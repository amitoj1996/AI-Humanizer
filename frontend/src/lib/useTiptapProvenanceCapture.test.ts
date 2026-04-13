/**
 * Unit tests for the transaction-level provenance hook.
 *
 * These exercise the four behaviours the reviewer flagged in Phase 9:
 *   H1 — programmatic setContent must NOT contaminate the recorder
 *   H2 — undo/redo emits manual_edit, not typed/deleted
 *   M1 — replace-overwrite logs the FULL deletion size
 *   plus the burst-aggregation behaviour we kept from the textarea era.
 *
 * Strategy: spin up a real Tiptap editor in jsdom, render the React hook
 * via @testing-library/react, drive it with editor.commands and
 * editor.view.dispatch (the latter so we can attach the meta keys we
 * actually expect — e.g. tr.setMeta('paste', true)).
 */
import Placeholder from "@tiptap/extension-placeholder";
import { Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRef } from "react";

import { recorder } from "./provenance";
import { useTiptapProvenanceCapture } from "./useTiptapProvenanceCapture";

// ---------------------------------------------------------------------------
// Editor + recorder fixture
// ---------------------------------------------------------------------------
function makeEditor(): Editor {
  return new Editor({
    extensions: [StarterKit.configure({}), Placeholder.configure({ placeholder: "" })],
  });
}

let editor: Editor;
let typedSpy: ReturnType<typeof vi.spyOn>;
let pastedSpy: ReturnType<typeof vi.spyOn>;
let deletedSpy: ReturnType<typeof vi.spyOn>;
let manualEditSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  editor = makeEditor();
  typedSpy = vi.spyOn(recorder, "typed").mockImplementation(() => {});
  pastedSpy = vi.spyOn(recorder, "pasted").mockImplementation(() => {});
  deletedSpy = vi.spyOn(recorder, "deleted").mockImplementation(() => {});
  manualEditSpy = vi
    .spyOn(recorder, "manualEdit")
    .mockImplementation(() => {});
});

afterEach(() => {
  editor.destroy();
  vi.restoreAllMocks();
});

function attachHook(programmatic = false) {
  return renderHook(() => {
    const ref = useRef(programmatic);
    useTiptapProvenanceCapture(editor, ref);
    return ref;
  });
}

function flushBurstWindow() {
  // The hook aggregates typing into a 1s-idle burst.  Fast-forward the
  // burst timer so spies see the typed() call.
  vi.advanceTimersByTime(1_500);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe("useTiptapProvenanceCapture", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("M1: replace-overwrite logs the full deletion size separately from the insertion", () => {
    attachHook();
    // Seed 20 chars
    editor.commands.insertContent("a".repeat(20));
    flushBurstWindow();
    typedSpy.mockClear();

    // Select the whole 20 and replace with a fresh 20 chars
    editor.commands.selectAll();
    editor.commands.insertContent("b".repeat(20));
    flushBurstWindow();

    const totalDeleted = deletedSpy.mock.calls.reduce(
      (sum, args) => sum + (args[0] as number),
      0,
    );
    // ProseMirror's positional coordinate space counts paragraph
    // open/close tokens, so the recorded delete is slightly > text length.
    // The Phase 9 bug we're guarding against was recording ZERO deletes
    // here — anything in the [text-length, text-length+a-few] range proves
    // the fix.
    expect(totalDeleted).toBeGreaterThanOrEqual(20);
    expect(totalDeleted).toBeLessThan(30);
    const totalTyped = typedSpy.mock.calls.reduce(
      (sum, args) => sum + (args[0] as string).length,
      0,
    );
    expect(totalTyped).toBe(20);
  });

  it("burst aggregation: contiguous typing collapses into one typed event", () => {
    attachHook();
    editor.commands.insertContent("hello");
    editor.commands.insertContent(" world");
    flushBurstWindow();
    expect(typedSpy).toHaveBeenCalledTimes(1);
    expect(typedSpy).toHaveBeenCalledWith("hello world");
  });

  it("H2: undo/redo emits manual_edit, never typed or deleted", () => {
    attachHook();
    editor.commands.insertContent("hello world");
    flushBurstWindow();
    typedSpy.mockClear();
    pastedSpy.mockClear();
    deletedSpy.mockClear();
    manualEditSpy.mockClear();

    editor.commands.undo();
    flushBurstWindow();

    expect(typedSpy).not.toHaveBeenCalled();
    expect(pastedSpy).not.toHaveBeenCalled();
    expect(deletedSpy).not.toHaveBeenCalled();
    expect(manualEditSpy).toHaveBeenCalled();
    const arg = manualEditSpy.mock.calls[0][0] as Record<string, unknown>;
    expect(arg.source).toBe("history");
  });

  it("H1: programmatic setContent does not record any user-authorship events", () => {
    // Mount the hook with programmatic flag = true — simulates the
    // ref-based guard the TiptapEditor sets while pushing store→editor.
    const { result } = attachHook(true);
    // (sanity: the ref starts true, mirroring the component's flow)
    expect(result.current.current).toBe(true);

    editor.commands.setContent("loaded from disk", { emitUpdate: false });
    flushBurstWindow();

    expect(typedSpy).not.toHaveBeenCalled();
    expect(pastedSpy).not.toHaveBeenCalled();
    expect(deletedSpy).not.toHaveBeenCalled();
    expect(manualEditSpy).not.toHaveBeenCalled();
  });

  it("paste meta routes to recorder.pasted, not typed", () => {
    attachHook();
    // Dispatch a transaction that mimics ProseMirror's paste pipeline:
    // tr.replaceSelectionWith + setMeta('paste', true).
    const { state } = editor.view;
    const tr = state.tr.insertText("clip");
    tr.setMeta("paste", true);
    editor.view.dispatch(tr);
    flushBurstWindow();

    expect(pastedSpy).toHaveBeenCalledWith("clip", "external");
    expect(typedSpy).not.toHaveBeenCalled();
  });
});
