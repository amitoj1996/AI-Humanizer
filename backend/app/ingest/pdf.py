"""PDF ingest via PyMuPDF4LLM — converts to clean layout-aware markdown.

Notes:
  - PyMuPDF4LLM preserves headings, lists, and tables as markdown.
  - For scanned PDFs (image-only) this returns near-empty text.  We detect
    that case heuristically and return a warning so the UI can surface it.
  - Marker (with Surya OCR) would solve scanned PDFs but adds ~2 GB of model
    weights — deferred until a user actually needs it.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pymupdf4llm


def parse(content: bytes) -> dict:
    # pymupdf4llm takes a path.  Write to temp, parse, unlink.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp.flush()
        tmp_path = Path(tmp.name)

    try:
        md = pymupdf4llm.to_markdown(str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)

    warnings: list[str] = []
    stripped = md.strip()
    # Rough scanned-PDF heuristic: very little text relative to file size
    if len(stripped) < max(200, len(content) // 20_000):
        warnings.append(
            "Very little text extracted — this PDF may be scanned. "
            "OCR ingest is not enabled in this build."
        )

    return {"text": md, "source_type": "pdf", "warnings": warnings}
