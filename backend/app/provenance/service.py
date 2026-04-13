"""Session lifecycle + event append + chain verification + report generation.

Session lifecycle:
  - `start_session(document_id)` creates a session with a random genesis hash.
  - `append_events(session_id, events)` computes hashes server-side and inserts.
    We do NOT trust client-provided hashes — the server is authoritative.
  - `seal_session(session_id)` records `final_hash` and sets `ended_at`.
    Sealed sessions reject further events.
"""
from __future__ import annotations

import json
import time
from typing import Optional

from sqlmodel import Session, select

from ..db.models import Document, ProvenanceEvent, ProvenanceSession
from . import chain

# Event types — keep in sync with the frontend recorder.
EVENT_TYPES = frozenset(
    {
        "session_start",
        "session_end",
        "typed",
        "pasted",
        "deleted",
        "imported",
        "ai_rewrite_requested",
        "ai_rewrite_applied",
        "ai_rewrite_rejected",
        "detection_run",
        "revision_saved",
        "manual_edit",
    }
)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
def start_session(session: Session, document_id: str) -> Optional[ProvenanceSession]:
    if not session.get(Document, document_id):
        return None
    ps = ProvenanceSession(
        document_id=document_id,
        genesis_hash=chain.genesis_hash(),
    )
    session.add(ps)
    session.commit()
    session.refresh(ps)
    return ps


def get_session(session: Session, session_id: str) -> Optional[ProvenanceSession]:
    return session.get(ProvenanceSession, session_id)


def get_active_session_for_document(
    session: Session, document_id: str
) -> Optional[ProvenanceSession]:
    return session.exec(
        select(ProvenanceSession)
        .where(ProvenanceSession.document_id == document_id)
        .where(ProvenanceSession.ended_at.is_(None))
        .order_by(ProvenanceSession.started_at.desc())
    ).first()


def seal_session(session: Session, session_id: str) -> Optional[ProvenanceSession]:
    ps = session.get(ProvenanceSession, session_id)
    if not ps or ps.ended_at is not None:
        return None

    last = _last_event(session, session_id)
    ps.final_hash = last.self_hash if last else ps.genesis_hash
    ps.ended_at = int(time.time() * 1000)
    session.add(ps)
    session.commit()
    session.refresh(ps)
    return ps


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
def append_events(
    session: Session, session_id: str, events: list[dict]
) -> tuple[int, Optional[str]]:
    """Compute chain server-side and insert events.

    Each event dict should contain: event_type, timestamp, payload (dict).
    Client-supplied prev_hash/self_hash are ignored — we re-compute.

    Returns (number_appended, error_message).  error_message is None on success.
    """
    ps = session.get(ProvenanceSession, session_id)
    if not ps:
        return 0, "Session not found"
    if ps.ended_at is not None:
        return 0, "Session is sealed"

    last = _last_event(session, session_id)
    prev_hash = last.self_hash if last else ps.genesis_hash
    next_seq = (last.sequence + 1) if last else 0

    inserted = 0
    for ev in events:
        event_type = ev.get("event_type")
        if event_type not in EVENT_TYPES:
            return inserted, f"Unknown event_type: {event_type!r}"

        payload_dict = ev.get("payload", {})
        if not isinstance(payload_dict, dict):
            return inserted, "payload must be an object"

        timestamp = int(ev.get("timestamp", time.time() * 1000))
        payload_json = chain.canonical_json(payload_dict)

        # Fields that go into the hash — keep stable!
        hash_fields = {
            "sequence": next_seq,
            "event_type": event_type,
            "timestamp": timestamp,
            "payload": payload_dict,  # hash the dict, not the json string
            "session_id": session_id,
        }
        self_hash = chain.compute_self_hash(prev_hash, hash_fields)

        record = ProvenanceEvent(
            session_id=session_id,
            document_id=ps.document_id,
            sequence=next_seq,
            event_type=event_type,
            timestamp=timestamp,
            payload=payload_json,
            prev_hash=prev_hash,
            self_hash=self_hash,
        )
        session.add(record)

        prev_hash = self_hash
        next_seq += 1
        inserted += 1

    session.commit()
    return inserted, None


def list_events(
    session: Session, session_id: str
) -> list[ProvenanceEvent]:
    return list(
        session.exec(
            select(ProvenanceEvent)
            .where(ProvenanceEvent.session_id == session_id)
            .order_by(ProvenanceEvent.sequence.asc())
        ).all()
    )


def list_events_for_document(
    session: Session, document_id: str
) -> list[ProvenanceEvent]:
    return list(
        session.exec(
            select(ProvenanceEvent)
            .where(ProvenanceEvent.document_id == document_id)
            .order_by(ProvenanceEvent.timestamp.asc())
        ).all()
    )


def _last_event(session: Session, session_id: str) -> Optional[ProvenanceEvent]:
    return session.exec(
        select(ProvenanceEvent)
        .where(ProvenanceEvent.session_id == session_id)
        .order_by(ProvenanceEvent.sequence.desc())
    ).first()


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def verify_session_chain(
    session: Session, session_id: str
) -> chain.VerificationResult:
    ps = session.get(ProvenanceSession, session_id)
    if not ps:
        return chain.VerificationResult(
            valid=False, total_events=0, reason="Session not found"
        )
    events = list_events(session, session_id)
    dicts = [
        {
            "sequence": e.sequence,
            "event_type": e.event_type,
            "timestamp": e.timestamp,
            "payload": json.loads(e.payload),
            "session_id": e.session_id,
            "prev_hash": e.prev_hash,
            "self_hash": e.self_hash,
        }
        for e in events
    ]
    return chain.verify_chain(ps.genesis_hash, dicts)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def build_report(session: Session, document_id: str) -> dict:
    """Aggregate all sessions for a document into a writing-process report."""
    doc = session.get(Document, document_id)
    if not doc:
        return {}

    sessions = list(
        session.exec(
            select(ProvenanceSession)
            .where(ProvenanceSession.document_id == document_id)
            .order_by(ProvenanceSession.started_at.asc())
        ).all()
    )
    events = list_events_for_document(session, document_id)

    # Authorship counts — very approximate (don't account for delete+retype).
    typed_chars = 0
    pasted_chars = 0
    ai_assisted_chars = 0

    timeline = []
    for e in events:
        payload = json.loads(e.payload)
        ts = e.timestamp
        if e.event_type == "typed":
            typed_chars += int(payload.get("char_count") or len(payload.get("text") or ""))
        elif e.event_type == "pasted":
            pasted_chars += int(payload.get("char_count") or len(payload.get("text") or ""))
        elif e.event_type == "ai_rewrite_applied":
            after_len = len(payload.get("after_text") or "")
            ai_assisted_chars += after_len

        timeline.append(
            {
                "timestamp": ts,
                "event_type": e.event_type,
                "sequence": e.sequence,
                "session_id": e.session_id,
                "summary": _summarise(e.event_type, payload),
            }
        )

    total = typed_chars + pasted_chars + ai_assisted_chars
    authorship = {
        "typed_chars": typed_chars,
        "pasted_chars": pasted_chars,
        "ai_assisted_chars": ai_assisted_chars,
        "typed_pct": _pct(typed_chars, total),
        "pasted_pct": _pct(pasted_chars, total),
        "ai_assisted_pct": _pct(ai_assisted_chars, total),
    }

    # Verify every session's chain
    chain_results = []
    for ps in sessions:
        result = verify_session_chain(session, ps.id)
        chain_results.append(
            {
                "session_id": ps.id,
                "started_at": ps.started_at,
                "ended_at": ps.ended_at,
                "valid": result.valid,
                "events": result.total_events,
                "final_hash": ps.final_hash,
                "genesis_hash": ps.genesis_hash,
                "reason": result.reason,
            }
        )

    overall_valid = all(r["valid"] for r in chain_results)

    return {
        "document_id": document_id,
        "document_title": doc.title,
        "sessions": chain_results,
        "total_events": len(events),
        "authorship": authorship,
        "timeline": timeline,
        "integrity": {
            "valid": overall_valid,
            "sessions_verified": len(chain_results),
        },
    }


def _summarise(event_type: str, payload: dict) -> str:
    if event_type == "typed":
        return f"Typed ~{payload.get('char_count', len(payload.get('text', '')))} chars"
    if event_type == "pasted":
        src = payload.get("source", "clipboard")
        return f"Pasted {payload.get('char_count', len(payload.get('text', '')))} chars from {src}"
    if event_type == "deleted":
        return f"Deleted {payload.get('char_count', 0)} chars"
    if event_type == "ai_rewrite_applied":
        before = payload.get("ai_score_before")
        after = payload.get("ai_score_after")
        return (
            f"AI rewrite applied ({payload.get('strength', '?')}/{payload.get('tone', '?')}): "
            f"{_pct_fmt(before)} → {_pct_fmt(after)} AI"
        )
    if event_type == "detection_run":
        return f"Detection run: {_pct_fmt(payload.get('ai_score'))} AI"
    if event_type == "revision_saved":
        return f"Revision saved ({payload.get('revision_id', '?')[:8]})"
    if event_type == "session_start":
        return "Session started"
    if event_type == "session_end":
        return "Session sealed"
    if event_type == "imported":
        return f"Imported {payload.get('char_count', 0)} chars from {payload.get('source', '?')}"
    return event_type


def _pct(a: int, total: int) -> float:
    return round(100.0 * a / total, 1) if total else 0.0


def _pct_fmt(score: Optional[float]) -> str:
    return f"{round(score * 100)}%" if score is not None else "—"
