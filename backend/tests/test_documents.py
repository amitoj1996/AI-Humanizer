"""CRUD + revision workflow tests for projects, documents, revisions."""


def test_create_and_list_projects(client):
    r = client.post("/api/projects", json={"name": "My Thesis"})
    assert r.status_code == 200
    project = r.json()
    assert project["name"] == "My Thesis"
    assert "id" in project
    assert project["created_at"] > 0

    r = client.get("/api/projects")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_project_not_found(client):
    r = client.get("/api/projects/nope")
    assert r.status_code == 404


def test_delete_project_cascades(client):
    p = client.post("/api/projects", json={"name": "X"}).json()
    d = client.post(
        "/api/documents",
        json={"project_id": p["id"], "title": "Doc 1", "initial_content": "hello world " * 20},
    ).json()

    assert client.delete(f"/api/projects/{p['id']}").status_code == 200
    assert client.get(f"/api/documents/{d['id']}").status_code == 404


def test_create_document_with_initial_content(client):
    p = client.post("/api/projects", json={"name": "P"}).json()
    r = client.post(
        "/api/documents",
        json={"project_id": p["id"], "title": "Essay", "initial_content": "first draft content"},
    )
    assert r.status_code == 200
    doc = r.json()
    assert doc["title"] == "Essay"
    assert doc["current_revision_id"] is not None

    # Initial content should be stored as revision #1
    revs = client.get(f"/api/documents/{doc['id']}/revisions").json()
    assert len(revs) == 1
    assert revs[0]["content"] == "first draft content"


def test_create_document_without_content(client):
    p = client.post("/api/projects", json={"name": "P"}).json()
    doc = client.post(
        "/api/documents", json={"project_id": p["id"], "title": "Blank"}
    ).json()
    assert doc["current_revision_id"] is None

    revs = client.get(f"/api/documents/{doc['id']}/revisions").json()
    assert revs == []


def test_save_revision_advances_head(client):
    p = client.post("/api/projects", json={"name": "P"}).json()
    doc = client.post(
        "/api/documents",
        json={"project_id": p["id"], "title": "Doc", "initial_content": "v1"},
    ).json()

    r = client.post(
        f"/api/documents/{doc['id']}/revisions",
        json={"content": "v2", "ai_score": 0.42},
    )
    assert r.status_code == 200
    new_rev = r.json()
    assert new_rev["content"] == "v2"
    assert new_rev["ai_score"] == 0.42

    refreshed = client.get(f"/api/documents/{doc['id']}").json()
    assert refreshed["current_revision_id"] == new_rev["id"]


def test_identical_content_dedupes(client):
    p = client.post("/api/projects", json={"name": "P"}).json()
    doc = client.post(
        "/api/documents",
        json={"project_id": p["id"], "title": "Doc", "initial_content": "same"},
    ).json()

    # Same content → should return existing head, not create new revision
    r = client.post(
        f"/api/documents/{doc['id']}/revisions", json={"content": "same"}
    )
    assert r.status_code == 200

    revs = client.get(f"/api/documents/{doc['id']}/revisions").json()
    assert len(revs) == 1  # still only one


def test_list_revisions_newest_first(client):
    p = client.post("/api/projects", json={"name": "P"}).json()
    doc = client.post(
        "/api/documents",
        json={"project_id": p["id"], "title": "Doc", "initial_content": "v1"},
    ).json()
    client.post(f"/api/documents/{doc['id']}/revisions", json={"content": "v2"})
    client.post(f"/api/documents/{doc['id']}/revisions", json={"content": "v3"})

    revs = client.get(f"/api/documents/{doc['id']}/revisions").json()
    assert [r["content"] for r in revs] == ["v3", "v2", "v1"]


def test_restore_revision_creates_new_head(client):
    p = client.post("/api/projects", json={"name": "P"}).json()
    doc = client.post(
        "/api/documents",
        json={"project_id": p["id"], "title": "Doc", "initial_content": "v1"},
    ).json()
    client.post(f"/api/documents/{doc['id']}/revisions", json={"content": "v2"})
    client.post(f"/api/documents/{doc['id']}/revisions", json={"content": "v3"})

    revs = client.get(f"/api/documents/{doc['id']}/revisions").json()
    v1_id = revs[-1]["id"]

    r = client.post(
        f"/api/documents/{doc['id']}/revisions/{v1_id}/restore"
    )
    assert r.status_code == 200
    restored = r.json()
    assert restored["content"] == "v1"
    assert "Restored from" in (restored.get("note") or "")

    # HEAD now points to the restored revision
    assert client.get(f"/api/documents/{doc['id']}").json()["current_revision_id"] == restored["id"]


def test_rename_document(client):
    p = client.post("/api/projects", json={"name": "P"}).json()
    doc = client.post(
        "/api/documents", json={"project_id": p["id"], "title": "Old"}
    ).json()

    r = client.patch(f"/api/documents/{doc['id']}", json={"title": "New"})
    assert r.status_code == 200
    assert r.json()["title"] == "New"


def test_delete_document(client):
    p = client.post("/api/projects", json={"name": "P"}).json()
    doc = client.post(
        "/api/documents",
        json={"project_id": p["id"], "title": "D", "initial_content": "hi"},
    ).json()

    assert client.delete(f"/api/documents/{doc['id']}").status_code == 200
    assert client.get(f"/api/documents/{doc['id']}").status_code == 404

    # Revisions are gone too
    assert client.get(f"/api/documents/{doc['id']}/revisions").status_code == 404


def test_create_document_invalid_project(client):
    r = client.post(
        "/api/documents", json={"project_id": "nonexistent", "title": "D"}
    )
    assert r.status_code == 404


def test_revision_format_defaults_to_text(client):
    """Backwards compat: clients that don't pass format get plain text."""
    p = client.post("/api/projects", json={"name": "P"}).json()
    doc = client.post(
        "/api/documents",
        json={"project_id": p["id"], "title": "D", "initial_content": "hello"},
    ).json()
    revs = client.get(f"/api/documents/{doc['id']}/revisions").json()
    assert revs[0]["format"] == "text"


def test_revision_prosemirror_roundtrip(client):
    """Save a ProseMirror JSON revision, read it back unchanged."""
    p = client.post("/api/projects", json={"name": "P"}).json()
    doc = client.post(
        "/api/documents", json={"project_id": p["id"], "title": "PM Doc"}
    ).json()

    pm_json = (
        '{"type":"doc","content":['
        '{"type":"heading","attrs":{"level":1},"content":[{"type":"text","text":"Title"}]},'
        '{"type":"paragraph","content":[{"type":"text","text":"Body line."}]}'
        "]}"
    )
    r = client.post(
        f"/api/documents/{doc['id']}/revisions",
        json={"content": pm_json, "format": "prosemirror"},
    )
    assert r.status_code == 200
    rev = r.json()
    assert rev["format"] == "prosemirror"
    assert rev["content"] == pm_json


def test_revision_format_part_of_dedup_key(client):
    """Same byte string but different format should NOT dedup — they
    represent semantically different documents (text vs structured)."""
    p = client.post("/api/projects", json={"name": "P"}).json()
    doc = client.post(
        "/api/documents", json={"project_id": p["id"], "title": "Dedup"}
    ).json()
    # Save a plain-text revision
    client.post(
        f"/api/documents/{doc['id']}/revisions",
        json={"content": "hello", "format": "text"},
    )
    # Save a "ProseMirror" revision whose content happens to equal "hello"
    # — different format, so it must NOT be deduped.
    client.post(
        f"/api/documents/{doc['id']}/revisions",
        json={"content": "hello", "format": "prosemirror"},
    )
    revs = client.get(f"/api/documents/{doc['id']}/revisions").json()
    assert len(revs) == 2


def test_restore_preserves_format(client):
    p = client.post("/api/projects", json={"name": "P"}).json()
    doc = client.post(
        "/api/documents", json={"project_id": p["id"], "title": "D"}
    ).json()
    pm = '{"type":"doc","content":[{"type":"paragraph","content":[{"type":"text","text":"hi"}]}]}'
    rev1 = client.post(
        f"/api/documents/{doc['id']}/revisions",
        json={"content": pm, "format": "prosemirror"},
    ).json()
    # Append a plain-text revision so HEAD is no longer rev1
    client.post(
        f"/api/documents/{doc['id']}/revisions",
        json={"content": "plain", "format": "text"},
    )
    # Restore rev1 — should come back as a NEW revision still in prosemirror format
    restored = client.post(
        f"/api/documents/{doc['id']}/revisions/{rev1['id']}/restore"
    ).json()
    assert restored["format"] == "prosemirror"
    assert restored["content"] == pm


def test_export_prosemirror_to_markdown(client):
    """Markdown export of a ProseMirror revision should preserve headings
    and bold marks, not just dump the JSON string."""
    p = client.post("/api/projects", json={"name": "P"}).json()
    doc = client.post(
        "/api/documents", json={"project_id": p["id"], "title": "MD Export"}
    ).json()
    pm = (
        '{"type":"doc","content":['
        '{"type":"heading","attrs":{"level":2},"content":[{"type":"text","text":"Section"}]},'
        '{"type":"paragraph","content":['
        '{"type":"text","text":"hello "},'
        '{"type":"text","text":"bold","marks":[{"type":"bold"}]},'
        '{"type":"text","text":" world"}'
        "]}]}"
    )
    client.post(
        f"/api/documents/{doc['id']}/revisions",
        json={"content": pm, "format": "prosemirror"},
    )
    r = client.get(f"/api/documents/{doc['id']}/export?format=md")
    assert r.status_code == 200
    body = r.text
    assert "## Section" in body
    assert "**bold**" in body


def test_list_documents_in_project(client):
    p = client.post("/api/projects", json={"name": "P"}).json()
    client.post("/api/documents", json={"project_id": p["id"], "title": "A"})
    client.post("/api/documents", json={"project_id": p["id"], "title": "B"})

    r = client.get(f"/api/projects/{p['id']}/documents")
    assert r.status_code == 200
    assert len(r.json()) == 2
