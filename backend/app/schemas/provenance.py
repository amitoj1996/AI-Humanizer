from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class SessionStartRequest(BaseModel):
    document_id: str


class SessionRead(BaseModel):
    id: str
    document_id: str
    started_at: int
    ended_at: Optional[int]
    genesis_hash: str
    final_hash: Optional[str]


class EventCreate(BaseModel):
    event_type: str
    timestamp: int
    payload: dict[str, Any] = Field(default_factory=dict)


class EventsAppendRequest(BaseModel):
    events: list[EventCreate]


class EventsAppendResponse(BaseModel):
    appended: int
    error: Optional[str] = None


class EventRead(BaseModel):
    id: str
    session_id: str
    sequence: int
    event_type: str
    timestamp: int
    payload: dict[str, Any]
    prev_hash: str
    self_hash: str


class VerificationResponse(BaseModel):
    valid: bool
    total_events: int
    broken_at: Optional[int] = None
    reason: Optional[str] = None
