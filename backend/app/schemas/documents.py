from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---- Projects ----
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class ProjectRead(BaseModel):
    id: str
    name: str
    created_at: int
    updated_at: int


# ---- Documents ----
class DocumentCreate(BaseModel):
    project_id: str
    title: str = Field(..., min_length=1, max_length=200)
    source_type: str = Field(default="blank")
    initial_content: Optional[str] = None
    initial_format: str = Field(default="text", pattern="^(text|prosemirror)$")


class DocumentRead(BaseModel):
    id: str
    project_id: str
    title: str
    source_type: str
    current_revision_id: Optional[str]
    created_at: int
    updated_at: int


class DocumentRename(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


# ---- Revisions ----
class RevisionCreate(BaseModel):
    content: str
    format: str = Field(default="text", pattern="^(text|prosemirror)$")
    ai_score: Optional[float] = None
    note: Optional[str] = None


class RevisionRead(BaseModel):
    id: str
    document_id: str
    parent_id: Optional[str]
    content: str
    format: str
    content_hash: str
    ai_score: Optional[float]
    note: Optional[str]
    created_at: int
