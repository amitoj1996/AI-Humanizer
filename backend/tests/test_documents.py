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


def test_list_documents_in_project(client):
    p = client.post("/api/projects", json={"name": "P"}).json()
    client.post("/api/documents", json={"project_id": p["id"], "title": "A"})
    client.post("/api/documents", json={"project_id": p["id"], "title": "B"})

    r = client.get(f"/api/projects/{p['id']}/documents")
    assert r.status_code == 200
    assert len(r.json()) == 2
