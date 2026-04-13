"""Passthrough ingest for plain text and markdown.

Decodes as UTF-8 with a latin-1 fallback; normalises line endings.
"""
from __future__ import annotations


def parse(content: bytes, source_type: str = "txt") -> dict:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1", errors="replace")

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    return {"text": text, "source_type": source_type, "warnings": []}
