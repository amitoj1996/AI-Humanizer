"""Smoke tests — verify endpoints wire up correctly with mocked services."""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["models_loaded"] is True


def test_detect_ai_text(client):
    text = (
        "Moreover, it is important to note that artificial intelligence has fundamentally "
        "transformed the landscape of modern technology. Furthermore, the comprehensive "
        "implementation of these systems has facilitated unprecedented efficiency."
    )
    r = client.post("/api/detect", json={"text": text})
    assert r.status_code == 200
    body = r.json()
    assert body["ai_score"] > 0.5, "Text with AI markers should score high"
    assert "breakdown" in body


def test_detect_human_text(client):
    text = (
        "so i tried this place last night and honestly it was kind of mid. "
        "the food was fine but the service took forever. not going back tbh."
    )
    r = client.post("/api/detect", json={"text": text})
    assert r.status_code == 200
    body = r.json()
    assert body["ai_score"] < 0.5, "Casual text should score low"


def test_detect_requires_min_length(client):
    r = client.post("/api/detect", json={"text": "too short"})
    assert r.status_code == 422


def test_detect_sentences(client):
    text = (
        "Moreover, artificial intelligence has transformed technology. "
        "It has changed how we work and play every single day."
    )
    r = client.post("/api/detect/sentences", json={"text": text})
    assert r.status_code == 200
    body = r.json()
    assert "sentences" in body
    assert "overall" in body
    assert body["total_sentences"] >= 1


def test_humanize_reduces_ai_score(client):
    text = (
        "Moreover, it is important to note that artificial intelligence has fundamentally "
        "transformed the landscape of modern technology and facilitated unprecedented efficiency."
    )
    r = client.post(
        "/api/humanize",
        json={"text": text, "strength": "medium", "mode": "full"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["detection_after"]["ai_score"] < body["detection_before"]["ai_score"]
    assert body["humanized"] != text


def test_humanize_sentence_level(client):
    text = (
        "Moreover, it is important to note that artificial intelligence has fundamentally "
        "transformed the landscape of modern technology and facilitated unprecedented efficiency."
    )
    r = client.post(
        "/api/humanize",
        json={"text": text, "strength": "medium", "mode": "sentence"},
    )
    assert r.status_code == 200
    assert r.json()["mode"] == "sentence-level"


def test_humanize_validates_strength(client):
    r = client.post(
        "/api/humanize",
        json={"text": "a" * 100, "strength": "bogus"},
    )
    assert r.status_code == 422


def test_humanize_validates_tone(client):
    r = client.post(
        "/api/humanize",
        json={"text": "a" * 100, "tone": "bogus"},
    )
    assert r.status_code == 422


def test_list_models(client):
    r = client.get("/api/models")
    assert r.status_code == 200
    body = r.json()
    assert body["ollama_available"] is True
    assert "fake-model:latest" in body["models"]


def test_select_model(client):
    r = client.post("/api/models/select", json={"model": "test-model"})
    assert r.status_code == 200
    assert r.json()["selected_model"] == "test-model"


def test_list_tones(client):
    r = client.get("/api/tones")
    assert r.status_code == 200
    body = r.json()
    assert len(body["tones"]) == 5
    tone_ids = {t["id"] for t in body["tones"]}
    assert tone_ids == {"general", "academic", "casual", "blog", "professional"}
