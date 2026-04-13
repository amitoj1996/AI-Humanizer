"""Provenance: session lifecycle, hash chain, tamper detection, report."""
from __future__ import annotations

import json


def _make_doc(client) -> str:
    p = client.post("/api/projects", json={"name": "Provenance Test"}).json()
    d = client.post(
        "/api/documents",
        json={"project_id": p["id"], "title": "Doc", "initial_content": "hi"},
    ).json()
    return d["id"]


def _start_session(client, doc_id: str) -> str:
    r = client.post("/api/sessions", json={"document_id": doc_id})
    assert r.status_code == 200
    return r.json()["id"]


def test_start_session(client):
    doc_id = _make_doc(client)
    r = client.post("/api/sessions", json={"document_id": doc_id})
    assert r.status_code == 200
    s = r.json()
    assert s["document_id"] == doc_id
    assert s["ended_at"] is None
    assert len(s["genesis_hash"]) == 64  # 32 bytes hex


def test_start_session_requires_document(client):
    r = client.post("/api/sessions", json={"document_id": "nonexistent"})
    assert r.status_code == 404


def test_append_events_builds_chain(client):
    doc_id = _make_doc(client)
    session_id = _start_session(client, doc_id)

    events = [
        {"event_type": "session_start", "timestamp": 1000, "payload": {"document_id": doc_id}},
        {"event_type": "typed", "timestamp": 2000, "payload": {"text": "hello", "char_count": 5}},
        {"event_type": "pasted", "timestamp": 3000, "payload": {"text": "world", "char_count": 5, "source": "external"}},
    ]
    r = client.post(f"/api/sessions/{session_id}/events", json={"events": events})
    assert r.status_code == 200
    assert r.json()["appended"] == 3

    # Chain should verify
    v = client.get(f"/api/sessions/{session_id}/verify").json()
    assert v["valid"] is True
    assert v["total_events"] == 3


def test_chain_sequence_monotonic(client):
    doc_id = _make_doc(client)
    session_id = _start_session(client, doc_id)
    client.post(
        f"/api/sessions/{session_id}/events",
        json={"events": [{"event_type": "typed", "timestamp": 1000, "payload": {}}]},
    )
    client.post(
        f"/api/sessions/{session_id}/events",
        json={"events": [{"event_type": "typed", "timestamp": 2000, "payload": {}}]},
    )

    events = client.get(f"/api/sessions/{session_id}/events").json()
    seqs = [e["sequence"] for e in events]
    assert seqs == sorted(seqs)
    assert seqs == list(range(len(seqs)))


def test_chain_links_correctly(client):
    """Every prev_hash equals the previous event's self_hash."""
    doc_id = _make_doc(client)
    session_id = _start_session(client, doc_id)
    client.post(
        f"/api/sessions/{session_id}/events",
        json={
            "events": [
                {"event_type": "typed", "timestamp": 1, "payload": {"a": 1}},
                {"event_type": "typed", "timestamp": 2, "payload": {"a": 2}},
                {"event_type": "typed", "timestamp": 3, "payload": {"a": 3}},
            ]
        },
    )
    events = client.get(f"/api/sessions/{session_id}/events").json()
    for i, e in enumerate(events):
        if i == 0:
            continue
        assert e["prev_hash"] == events[i - 1]["self_hash"]


def test_unknown_event_type_rejected(client):
    doc_id = _make_doc(client)
    session_id = _start_session(client, doc_id)
    r = client.post(
        f"/api/sessions/{session_id}/events",
        json={"events": [{"event_type": "bogus", "timestamp": 1, "payload": {}}]},
    )
    assert r.status_code == 400


def test_sealed_session_rejects_events(client):
    doc_id = _make_doc(client)
    session_id = _start_session(client, doc_id)
    client.post(
        f"/api/sessions/{session_id}/events",
        json={"events": [{"event_type": "typed", "timestamp": 1, "payload": {}}]},
    )
    sealed = client.post(f"/api/sessions/{session_id}/seal").json()
    assert sealed["ended_at"] is not None
    assert sealed["final_hash"] is not None

    r = client.post(
        f"/api/sessions/{session_id}/events",
        json={"events": [{"event_type": "typed", "timestamp": 2, "payload": {}}]},
    )
    assert r.status_code == 400


def test_tampered_final_hash_is_caught(client):
    """Post-seal: if someone flips final_hash in the DB, verify must fail
    even though the event chain itself is still internally consistent."""
    from app.db.connection import get_engine
    from app.db.models import ProvenanceSession
    from sqlmodel import Session

    doc_id = _make_doc(client)
    session_id = _start_session(client, doc_id)
    client.post(
        f"/api/sessions/{session_id}/events",
        json={"events": [{"event_type": "typed", "timestamp": 1, "payload": {}}]},
    )
    client.post(f"/api/sessions/{session_id}/seal")

    # Before tamper: verification passes
    before = client.get(f"/api/sessions/{session_id}/verify").json()
    assert before["valid"] is True

    # Flip the stored final_hash directly in the DB (simulating tamper that
    # leaves the event chain untouched but swaps the sealed terminal hash).
    engine = get_engine()
    with Session(engine) as s:
        ps = s.get(ProvenanceSession, session_id)
        assert ps is not None
        ps.final_hash = "0" * 64
        s.add(ps)
        s.commit()

    after = client.get(f"/api/sessions/{session_id}/verify").json()
    assert after["valid"] is False
    assert "final_hash" in (after["reason"] or "")


def test_tamper_detection(client):
    """If someone edits a payload in the DB, verification must fail."""
    from app.db.connection import get_engine
    from app.db.models import ProvenanceEvent
    from sqlmodel import Session, select

    doc_id = _make_doc(client)
    session_id = _start_session(client, doc_id)
    client.post(
        f"/api/sessions/{session_id}/events",
        json={
            "events": [
                {"event_type": "typed", "timestamp": 1, "payload": {"text": "original"}},
                {"event_type": "typed", "timestamp": 2, "payload": {"text": "also original"}},
            ]
        },
    )

    # Tamper with event 0's payload directly in the DB
    engine = get_engine()
    with Session(engine) as s:
        target = s.exec(
            select(ProvenanceEvent)
            .where(ProvenanceEvent.session_id == session_id)
            .where(ProvenanceEvent.sequence == 0)
        ).first()
        # Note: we change payload but don't update self_hash, so chain must fail
        target.payload = json.dumps({"text": "TAMPERED"})
        s.add(target)
        s.commit()

    v = client.get(f"/api/sessions/{session_id}/verify").json()
    assert v["valid"] is False
    assert v["broken_at"] == 0


def test_report_aggregates_authorship(client):
    doc_id = _make_doc(client)
    session_id = _start_session(client, doc_id)
    client.post(
        f"/api/sessions/{session_id}/events",
        json={
            "events": [
                {"event_type": "typed", "timestamp": 1, "payload": {"text": "hello world", "char_count": 11}},
                {"event_type": "pasted", "timestamp": 2, "payload": {"text": "xyz", "char_count": 3, "source": "external"}},
                {"event_type": "ai_rewrite_applied", "timestamp": 3, "payload": {
                    "after_text": "rewritten",
                    "strength": "medium",
                    "tone": "casual",
                    "ai_score_before": 0.8,
                    "ai_score_after": 0.2,
                }},
            ]
        },
    )

    r = client.get(f"/api/documents/{doc_id}/provenance/report")
    assert r.status_code == 200
    report = r.json()
    assert report["authorship"]["typed_chars"] == 11
    assert report["authorship"]["pasted_chars"] == 3
    assert report["authorship"]["ai_assisted_chars"] == 9  # len("rewritten")
    assert report["integrity"]["valid"] is True
    assert len(report["timeline"]) == 3


def test_delete_document_cascades_through_provenance(client):
    """Regression: deleting a document with provenance sessions must not
    fail on FK constraint errors."""
    doc_id = _make_doc(client)
    session_id = _start_session(client, doc_id)
    client.post(
        f"/api/sessions/{session_id}/events",
        json={"events": [{"event_type": "typed", "timestamp": 1, "payload": {}}]},
    )

    assert client.delete(f"/api/documents/{doc_id}").status_code == 200
    assert client.get(f"/api/documents/{doc_id}").status_code == 404


def test_delete_project_cascades_through_provenance(client):
    """Same regression, via the project-level delete."""
    p = client.post("/api/projects", json={"name": "P"}).json()
    doc = client.post(
        "/api/documents",
        json={"project_id": p["id"], "title": "D", "initial_content": "hi"},
    ).json()
    s = client.post("/api/sessions", json={"document_id": doc["id"]}).json()
    client.post(
        f"/api/sessions/{s['id']}/events",
        json={"events": [{"event_type": "typed", "timestamp": 1, "payload": {}}]},
    )

    assert client.delete(f"/api/projects/{p['id']}").status_code == 200


def test_seal_with_pending_events_appends_atomically(client):
    """The /seal endpoint accepts optional events in the body — used by the
    frontend's beforeunload beacon so the tail of a session isn't lost on
    tab close.  Append happens FIRST, then the seal."""
    doc_id = _make_doc(client)
    session_id = _start_session(client, doc_id)

    # Some earlier events already delivered
    client.post(
        f"/api/sessions/{session_id}/events",
        json={"events": [{"event_type": "typed", "timestamp": 1, "payload": {"text": "early"}}]},
    )

    # Now the user closes the tab — beforeunload sends a seal request with
    # the pending queue included.  Both should land on the chain.
    r = client.post(
        f"/api/sessions/{session_id}/seal",
        json={
            "events": [
                {"event_type": "typed", "timestamp": 2, "payload": {"text": "last burst"}},
                {"event_type": "typed", "timestamp": 3, "payload": {"text": "final keystrokes"}},
            ]
        },
    )
    assert r.status_code == 200
    sealed = r.json()
    assert sealed["ended_at"] is not None
    assert sealed["final_hash"] is not None

    # Both pre-seal and seal-payload events are on the chain
    events = client.get(f"/api/sessions/{session_id}/events").json()
    assert len(events) == 3
    assert [e["payload"]["text"] for e in events] == [
        "early",
        "last burst",
        "final keystrokes",
    ]

    # And the chain verifies cleanly (including the terminal-hash check)
    v = client.get(f"/api/sessions/{session_id}/verify").json()
    assert v["valid"] is True


def test_seal_without_body_still_works(client):
    """Backwards-compat: seal with no body (the existing doc-switch path)."""
    doc_id = _make_doc(client)
    session_id = _start_session(client, doc_id)
    r = client.post(f"/api/sessions/{session_id}/seal")
    assert r.status_code == 200
    assert r.json()["ended_at"] is not None


def test_replay_builds_snapshots_from_revisions_and_rewrites(client):
    """Replay turns each revision AND each ai_rewrite_applied event into a
    navigable snapshot, sorted by timestamp."""
    # Build a doc with initial content, then an AI rewrite, then another save
    p = client.post("/api/projects", json={"name": "P"}).json()
    doc = client.post(
        "/api/documents",
        json={"project_id": p["id"], "title": "Replay Test", "initial_content": "draft v1"},
    ).json()
    doc_id = doc["id"]

    # Start a session, emit a rewrite event, save another revision
    s = client.post("/api/sessions", json={"document_id": doc_id}).json()
    client.post(
        f"/api/sessions/{s['id']}/events",
        json={
            "events": [
                {"event_type": "typed", "timestamp": 100, "payload": {"text": "hi", "char_count": 2}},
                {"event_type": "ai_rewrite_applied", "timestamp": 200, "payload": {
                    "before_text": "draft v1",
                    "after_text": "polished draft",
                    "strength": "medium",
                    "tone": "general",
                    "mode": "full",
                    "ai_score_before": 0.8,
                    "ai_score_after": 0.2,
                }},
            ]
        },
    )
    client.post(
        f"/api/documents/{doc_id}/revisions",
        json={"content": "hand-edited final", "ai_score": 0.15},
    )

    r = client.get(f"/api/documents/{doc_id}/provenance/replay")
    assert r.status_code == 200
    result = r.json()

    # The replay should have snapshots (ordered by timestamp), plus the
    # non-snapshot events (typed) as annotations.
    snapshots = result["snapshots"]
    contents = [s["content"] for s in snapshots]
    # Initial revision, rewrite output, final revision — all three distinct
    assert "draft v1" in contents
    assert "polished draft" in contents
    assert "hand-edited final" in contents

    # Rewrite snapshot carries the strength/tone metadata
    rewrite = next(s for s in snapshots if s["content"] == "polished draft")
    assert rewrite["strength"] == "medium"
    assert rewrite["ai_score_before"] == 0.8
    assert rewrite["ai_score"] == 0.2

    # typed event lands in annotations, not snapshots
    annot_types = {a["event_type"] for a in result["annotations"]}
    assert "typed" in annot_types

    # Totals
    assert result["totals"]["revisions"] >= 2
    assert result["totals"]["snapshots"] >= 2


def test_replay_dedupes_identical_adjacent_content(client):
    """After an ai_rewrite_applied, HumanizePanel saves the same text as a
    revision too.  The replay should collapse those into one snapshot with
    merged metadata rather than show the user a duplicate frame."""
    import time

    p = client.post("/api/projects", json={"name": "P"}).json()
    doc = client.post(
        "/api/documents",
        json={"project_id": p["id"], "title": "Dedup Test", "initial_content": "original"},
    ).json()
    doc_id = doc["id"]
    s = client.post("/api/sessions", json={"document_id": doc_id}).json()

    # Use a timestamp AFTER the initial revision's created_at (which is
    # now_ms() at create_document time), otherwise sort order puts the
    # rewrite before the initial revision and no dedup chance exists.
    future_ts = int(time.time() * 1000) + 10_000

    client.post(
        f"/api/sessions/{s['id']}/events",
        json={
            "events": [{
                "event_type": "ai_rewrite_applied",
                "timestamp": future_ts,
                "payload": {
                    "before_text": "original",
                    "after_text": "polished",
                    "strength": "medium",
                    "tone": "general",
                    "mode": "full",
                    "ai_score_before": 0.8,
                    "ai_score_after": 0.2,
                },
            }]
        },
    )
    # Immediately save a revision with the same post-rewrite content
    client.post(
        f"/api/documents/{doc_id}/revisions",
        json={"content": "polished", "ai_score": 0.2},
    )

    r = client.get(f"/api/documents/{doc_id}/provenance/replay").json()
    polished = [s for s in r["snapshots"] if s["content"] == "polished"]
    # Only one snapshot for "polished" — the revision merged into the rewrite
    assert len(polished) == 1, f"Expected merged dedup, got {len(polished)} frames"
    assert "+" in polished[0]["kind"]  # combined kind label


def test_replay_requires_document(client):
    r = client.get("/api/documents/nonexistent/provenance/replay")
    assert r.status_code == 404


def test_get_active_session(client):
    doc_id = _make_doc(client)
    # No active session yet
    assert client.get(f"/api/documents/{doc_id}/active-session").json() is None

    # After starting one, it should come back
    session_id = _start_session(client, doc_id)
    active = client.get(f"/api/documents/{doc_id}/active-session").json()
    assert active["id"] == session_id

    # After sealing, no active session
    client.post(f"/api/sessions/{session_id}/seal")
    assert client.get(f"/api/documents/{doc_id}/active-session").json() is None
