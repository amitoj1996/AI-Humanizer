"""SQLModel tables for projects, documents, and revisions.

Design notes:
  - Timestamps stored as unix millis (INTEGER) — fastest, timezone-agnostic,
    easiest to compare.
  - UUIDs stored as TEXT — readable in sqlite3 CLI, fine performance at our scale.
  - Revisions are append-only + linear.  `parent_id` is reserved for future
    branching support but we don't use it yet.
  - `Document.current_revision_id` points at the HEAD revision.  Always
    updated inside the same transaction as a new revision insert.
"""
from __future__ import annotations

import time
import uuid
from typing import Optional

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now_ms() -> int:
    return int(time.time() * 1000)


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    created_at: int = Field(default_factory=_now_ms, index=True)
    updated_at: int = Field(default_factory=_now_ms, index=True)


class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    title: str
    source_type: str = Field(default="blank")  # blank | pdf | docx | txt | md
    current_revision_id: Optional[str] = Field(default=None, index=True)
    created_at: int = Field(default_factory=_now_ms)
    updated_at: int = Field(default_factory=_now_ms, index=True)


class Revision(SQLModel, table=True):
    __tablename__ = "revisions"

    id: str = Field(default_factory=_uuid, primary_key=True)
    document_id: str = Field(foreign_key="documents.id", index=True)
    parent_id: Optional[str] = Field(default=None, foreign_key="revisions.id")
    content: str
    content_hash: str = Field(index=True)
    ai_score: Optional[float] = None
    note: Optional[str] = None
    created_at: int = Field(default_factory=_now_ms, index=True)


# ---------------------------------------------------------------------------
# Provenance — tamper-evident writing-process log
# ---------------------------------------------------------------------------
class ProvenanceSession(SQLModel, table=True):
    __tablename__ = "provenance_sessions"

    id: str = Field(default_factory=_uuid, primary_key=True)
    document_id: str = Field(foreign_key="documents.id", index=True)
    started_at: int = Field(default_factory=_now_ms)
    ended_at: Optional[int] = None  # null = still active
    genesis_hash: str  # 32 random bytes hex-encoded, seeds the chain
    final_hash: Optional[str] = None  # last event's self_hash after sealing


class ProvenanceEvent(SQLModel, table=True):
    __tablename__ = "provenance_events"

    id: str = Field(default_factory=_uuid, primary_key=True)
    session_id: str = Field(foreign_key="provenance_sessions.id", index=True)
    document_id: str = Field(index=True)
    sequence: int  # monotonic within a session, unique per session
    event_type: str
    timestamp: int
    payload: str  # canonical JSON blob
    prev_hash: str
    self_hash: str
