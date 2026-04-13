"""DOCX ingest via python-docx.

Extracts paragraphs (preserving headings) plus table cell text.  Output is
plain markdown-ish: headings get `#` prefixes based on the Word heading style,
everything else is a blank-line-separated paragraph.

Trade-off: python-docx doesn't preserve nested lists, text-box content, or
drawings.  Pandoc would do better but requires a system binary.  For v1 we
optimise for zero-dependency import; Pandoc is a future enhancement.
"""
from __future__ import annotations

import io

from docx import Document


def parse(content: bytes) -> dict:
    doc = Document(io.BytesIO(content))

    parts: list[str] = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name or "").lower()
        if style.startswith("heading 1"):
            parts.append(f"# {text}")
        elif style.startswith("heading 2"):
            parts.append(f"## {text}")
        elif style.startswith("heading 3"):
            parts.append(f"### {text}")
        elif style.startswith("heading"):
            parts.append(f"#### {text}")
        else:
            parts.append(text)

    # Tables rendered as markdown tables
    for table in doc.tables:
        if not table.rows:
            continue
        rows = [
            ["".join(cell.text.splitlines()).strip() for cell in row.cells]
            for row in table.rows
        ]
        if not rows or not any(rows):
            continue
        width = max(len(r) for r in rows)
        header = rows[0] + [""] * (width - len(rows[0]))
        parts.append("| " + " | ".join(header) + " |")
        parts.append("| " + " | ".join(["---"] * width) + " |")
        for row in rows[1:]:
            padded = row + [""] * (width - len(row))
            parts.append("| " + " | ".join(padded) + " |")

    text = "\n\n".join(parts)

    return {"text": text, "source_type": "docx", "warnings": []}
