"""Authoring replay — reconstruct the document state at each meaningful
point in a writing session from the provenance event stream + revision
history.

Pragmatic v1 approach:
  - Every committed revision IS a known snapshot (we have the full text).
  - Every `ai_rewrite_applied` event stashes `after_text` in its payload,
    which is also a known snapshot.
  - Typed / pasted / deleted events become annotations on the timeline
    but not navigable states — their exact resulting content isn't stored
    (we don't track cursor position), so reconstructing them precisely
    would require re-running the editor state machine.
  - Imported events carry the import source + char count.

That gives users a scrubbable history at the granularity that actually
matters: every save and every AI rewrite is a known, verifiable snapshot.
Intermediate keystrokes are logged (and counted in the authorship
breakdown) but not navigable.

Schema kept deliberately loose so we can add sub-revision replay later
without breaking the API.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlmodel import Session, select

from ..db.models import Document, ProvenanceEvent, Revision


def build_replay(session: Session, document_id: str) -> dict:
    """Aggregate revisions + provenance events into a scrubbable timeline."""
    doc = session.get(Document, document_id)
    if not doc:
        return {}

    revisions = list(
        session.exec(
            select(Revision)
            .where(Revision.document_id == document_id)
            .order_by(Revision.created_at.asc())
        ).all()
    )
    events = list(
        session.exec(
            select(ProvenanceEvent)
            .where(ProvenanceEvent.document_id == document_id)
            .order_by(ProvenanceEvent.timestamp.asc())
        ).all()
    )

    snapshots: list[dict[str, Any]] = []

    # 1. Every revision is a definite snapshot.
    for rev in revisions:
        snapshots.append(
            {
                "timestamp": rev.created_at,
                "kind": "revision",
                "source_id": rev.id,
                "content": rev.content,
                "ai_score": rev.ai_score,
                "note": rev.note,
                "chars": len(rev.content),
            }
        )

    # 2. AI rewrites carry the after_text in their payload.
    for ev in events:
        if ev.event_type == "ai_rewrite_applied":
            payload = json.loads(ev.payload)
            after = payload.get("after_text") or ""
            snapshots.append(
                {
                    "timestamp": ev.timestamp,
                    "kind": "ai_rewrite",
                    "source_id": ev.id,
                    "content": after,
                    "ai_score": payload.get("ai_score_after"),
                    "strength": payload.get("strength"),
                    "tone": payload.get("tone"),
                    "mode": payload.get("mode"),
                    "ai_score_before": payload.get("ai_score_before"),
                    "chars": len(after),
                }
            )

    snapshots.sort(key=lambda s: s["timestamp"])
    # Dedup consecutive snapshots with identical content (revision-saved
    # immediately after an ai_rewrite typically produces a dup).
    deduped: list[dict[str, Any]] = []
    for s in snapshots:
        if deduped and deduped[-1]["content"] == s["content"]:
            # Merge metadata so we don't lose the "this was both a rewrite
            # and a saved revision" story.
            prev = deduped[-1]
            prev["kind"] = f"{prev['kind']}+{s['kind']}"
            prev.setdefault("merged_source_ids", [prev["source_id"]]).append(
                s["source_id"]
            )
            continue
        deduped.append(s)

    # 3. Build the full annotation list — non-snapshot events that appear
    # on the timeline but don't have navigable content.
    annotations: list[dict[str, Any]] = []
    for ev in events:
        if ev.event_type in ("ai_rewrite_applied",):
            continue  # already a snapshot
        payload = json.loads(ev.payload)
        annotations.append(
            {
                "timestamp": ev.timestamp,
                "event_type": ev.event_type,
                "payload": payload,
                "sequence": ev.sequence,
                "session_id": ev.session_id,
            }
        )

    return {
        "document_id": document_id,
        "document_title": doc.title,
        "snapshots": deduped,
        "annotations": annotations,
        "totals": {
            "snapshots": len(deduped),
            "events": len(events),
            "revisions": len(revisions),
            "span_ms": (deduped[-1]["timestamp"] - deduped[0]["timestamp"])
            if deduped
            else 0,
        },
    }


def snapshot_at(
    session: Session, document_id: str, timestamp: int
) -> Optional[dict]:
    """Return the nearest snapshot at-or-before `timestamp`, or None."""
    replay = build_replay(session, document_id)
    if not replay:
        return None
    best = None
    for s in replay["snapshots"]:
        if s["timestamp"] > timestamp:
            break
        best = s
    return best
