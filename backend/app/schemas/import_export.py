from __future__ import annotations

from pydantic import BaseModel


class ImportResult(BaseModel):
    document_id: str
    title: str
    source_type: str
    char_count: int
    warnings: list[str]
