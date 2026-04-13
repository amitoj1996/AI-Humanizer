"""Plain-text and markdown export — both are just the raw document content.

Kept as a module so the API layer can dispatch by format name without special-
casing strings.
"""
from __future__ import annotations


def export_txt(text: str) -> bytes:
    return text.encode("utf-8")


def export_md(text: str) -> bytes:
    return text.encode("utf-8")
