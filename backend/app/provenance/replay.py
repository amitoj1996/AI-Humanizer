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
from ..services import prosemirror as pm

# How close in time an `ai_rewrite_applied` and a `revision_saved` with
# identical content have to be for them to count as the same checkpoint.
# HumanizePanel.run() saves the auto-revision in the same async chain as
# the rewrite-applied event, so they're typically <100 ms apart in practice.
# Pick 5 s as a safe ceiling that won't merge user-driven checkpoints.
_DEDUP_WINDOW_MS = 5_000


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

    # 1. Every revision is a definite snapshot.  ProseMirror revisions are
    #    decoded to plain text via the same walker the export path uses, so
    #    the replay timeline shows readable prose instead of leaking raw
    #    JSON to the user.
    for rev in revisions:
        rev_format = getattr(rev, "format", "text")
        plain = pm.to_plain_text(rev.content, format=rev_format)
        snapshots.append(
            {
                "timestamp": rev.created_at,
                "kind": "revision",
                "source_id": rev.id,
                "content": plain,
                "format": rev_format,
                "ai_score": rev.ai_score,
                "note": rev.note,
                "chars": len(plain),
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
    # Narrow dedup: ONLY merge the specific "HumanizePanel auto-saves the
    # rewrite output as a revision" pattern (ai_rewrite immediately followed
    # by a revision with identical content).  Any other duplicate-content
    # case — re-saving the same text manually, restoring to identical
    # content, typing-then-deleting back to the same string — represents a
    # distinct user checkpoint and stays as its own frame.
    deduped: list[dict[str, Any]] = []
    for s in snapshots:
        prev = deduped[-1] if deduped else None
        is_rewrite_then_revision_dup = (
            prev is not None
            and prev["content"] == s["content"]
            and prev["kind"] == "ai_rewrite"
            and s["kind"] == "revision"
            and (s["timestamp"] - prev["timestamp"]) <= _DEDUP_WINDOW_MS
        )
        if is_rewrite_then_revision_dup:
            assert prev is not None
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
