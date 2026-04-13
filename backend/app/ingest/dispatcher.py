"""Dispatches imports to the right parser based on file extension.

Return shape: dict with
  - text: str (plain text or markdown — depends on source type)
  - source_type: 'pdf' | 'docx' | 'md' | 'txt'
  - warnings: list[str] (e.g. 'low text density — likely scanned PDF')
"""
from __future__ import annotations

from pathlib import Path

from . import docx as docx_ingest
from . import pdf as pdf_ingest
from . import text as text_ingest

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".md", ".markdown", ".txt"}


class UnsupportedFileError(ValueError):
    pass


def parse_file(filename: str, content: bytes) -> dict:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return pdf_ingest.parse(content)
    if ext == ".docx":
        return docx_ingest.parse(content)
    if ext in {".md", ".markdown"}:
        return text_ingest.parse(content, source_type="md")
    if ext == ".txt":
        return text_ingest.parse(content, source_type="txt")
    raise UnsupportedFileError(
        f"Unsupported file type {ext!r}. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
    )
