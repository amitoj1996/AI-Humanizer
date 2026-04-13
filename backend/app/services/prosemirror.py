"""Tiny ProseMirror JSON → plain text walker.

Used by detection / humanization paths that need plain text, and by the
TXT/MD export paths.  We deliberately don't pull in `prosemirror-py` —
the schema we use is small (paragraphs, headings, lists, blockquote, code,
hard breaks, marks) and the canonical JSON shape is stable across versions.

If we hit a node we don't recognise we just walk its `content` array, so
extending the editor's schema later doesn't silently lose text.
"""
from __future__ import annotations

import json
from typing import Any


def to_plain_text(content: str, *, format: str = "text") -> str:
    """Resolve a `Revision.content` string to plain text.

    `format == "text"` returns the string unchanged.
    `format == "prosemirror"` parses the JSON and walks the tree.
    Unknown formats fall back to returning the raw string.
    """
    if format != "prosemirror":
        return content
    try:
        doc = json.loads(content)
    except json.JSONDecodeError:
        # Stored content claims to be ProseMirror but isn't valid JSON —
        # surface what we have rather than crashing the request.
        return content
    return _walk(doc).rstrip("\n")


def _walk(node: Any) -> str:
    if not isinstance(node, dict):
        return ""
    type_ = node.get("type")
    if type_ == "text":
        return str(node.get("text") or "")
    if type_ == "hard_break" or type_ == "hardBreak":
        return "\n"

    parts = [_walk(child) for child in node.get("content") or []]
    inner = "".join(parts)

    # Block-level nodes get a trailing newline so paragraph + paragraph
    # round-trips with a sensible visual separator.
    block_types = {
        "doc",
        "paragraph",
        "heading",
        "blockquote",
        "code_block",
        "codeBlock",
        "bullet_list",
        "bulletList",
        "ordered_list",
        "orderedList",
        "list_item",
        "listItem",
        "horizontal_rule",
        "horizontalRule",
    }
    if type_ in block_types:
        return inner + "\n"
    return inner


def to_markdown(content: str, *, format: str = "text") -> str:
    """Slightly richer than plain text — emits `# heading`, `- list`, `> quote`,
    backtick-fenced code.  Used by the MD export path so users get something
    closer to what they typed.
    """
    if format != "prosemirror":
        return content
    try:
        doc = json.loads(content)
    except json.JSONDecodeError:
        return content
    return _walk_md(doc).rstrip("\n")


def _walk_md(node: Any, *, list_depth: int = 0, ordered: bool = False, ordered_index: int = 1) -> str:
    if not isinstance(node, dict):
        return ""
    type_ = node.get("type")

    if type_ == "text":
        text = str(node.get("text") or "")
        for mark in node.get("marks") or []:
            mtype = mark.get("type")
            if mtype == "bold" or mtype == "strong":
                text = f"**{text}**"
            elif mtype == "italic" or mtype == "em":
                text = f"*{text}*"
            elif mtype == "code":
                text = f"`{text}`"
            elif mtype == "link":
                href = (mark.get("attrs") or {}).get("href", "")
                text = f"[{text}]({href})"
        return text

    if type_ == "hard_break" or type_ == "hardBreak":
        return "\n"

    children = node.get("content") or []

    if type_ == "heading":
        level = (node.get("attrs") or {}).get("level", 1)
        inner = "".join(_walk_md(c) for c in children)
        return f"{'#' * level} {inner}\n\n"

    if type_ == "paragraph":
        inner = "".join(_walk_md(c) for c in children)
        return f"{inner}\n\n"

    if type_ == "blockquote":
        inner = "".join(_walk_md(c) for c in children)
        return "\n".join(f"> {line}" for line in inner.rstrip("\n").splitlines()) + "\n\n"

    if type_ in ("code_block", "codeBlock"):
        inner = "".join(_walk_md(c) for c in children)
        lang = (node.get("attrs") or {}).get("language", "")
        return f"```{lang}\n{inner}\n```\n\n"

    if type_ in ("bullet_list", "bulletList"):
        return "".join(_walk_md(c, list_depth=list_depth + 1, ordered=False) for c in children)

    if type_ in ("ordered_list", "orderedList"):
        return "".join(
            _walk_md(c, list_depth=list_depth + 1, ordered=True, ordered_index=i + 1)
            for i, c in enumerate(children)
        )

    if type_ in ("list_item", "listItem"):
        marker = f"{ordered_index}." if ordered else "-"
        indent = "  " * max(0, list_depth - 1)
        inner = "".join(_walk_md(c) for c in children).rstrip("\n")
        return f"{indent}{marker} {inner}\n"

    if type_ in ("horizontal_rule", "horizontalRule"):
        return "---\n\n"

    # Fallback for unknown nodes: walk children, no extra formatting.
    return "".join(_walk_md(c) for c in children)
