from pathlib import Path

from fastapi.testclient import TestClient

from app.api.chat_router import app
from app.database import get_db
from app.models.rpg_sessions import RpgSession, SourceDocument, StoryBeat, StoryEvent


client = TestClient(app)


def test_create_session_endpoint_accepts_form_data():
    response = client.post(
        "/story",
        data={
            "title": "Test Chronicle",
            "synopsis": "A short synopsis",
            "genre": "fantasy",
            "magic_rules_md": "No dragons",
            "context_token_limit": 2048,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Test Chronicle"
    assert payload["chunks_saved"] == 0
    assert payload["id"]


def test_create_session_endpoint_accepts_avatar_image():
    response = client.post(
        "/story",
        data={"title": "Image Chronicle", "synopsis": "A story with an image"},
        files={"avatar": ("avatar.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"]
    assert payload["avatar"].startswith("/data/images/")

    with get_db() as db:
        session = db.query(RpgSession).filter(RpgSession.id == payload["id"]).first()
        assert session is not None
        assert session.avatar.startswith("/data/images/")


def test_upload_document_endpoint_saves_pdf_and_returns_path(monkeypatch):
    monkeypatch.setattr("app.api.documents_router.process_document", lambda **kwargs: None)

    response = client.post(
        "/story/test-session/docs",
        files={"file": ("sample.pdf", b"%PDF-1.4\n%hello", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processing"
    assert payload["source_document_id"]
    assert payload["file_path"]

    saved_path = Path(payload["file_path"])
    assert saved_path.exists()


def test_chronicle_chat_includes_relevant_pdf_context(monkeypatch):
    created = client.post(
        "/story",
        data={"title": "PDF Chronicle", "synopsis": "Uses uploaded content"},
    )
    session_id = created.json()["id"]

    with get_db() as db:
        db.add(
            SourceDocument(
                session_id=session_id,
                filename="sample.pdf",
                status="ready",
                chunk_count=2,
                file_path="/tmp/sample.pdf",
            )
        )
        db.commit()

    captured = {}

    def fake_get_response(prompt):
        captured["prompt"] = prompt
        return "ok"

    monkeypatch.setattr("app.api.chronicle_router.get_response", fake_get_response)
    monkeypatch.setattr(
        "app.api.chronicle_router.query_chroma_for_lore",
        lambda session_id, query_text, n_results=5, category=None: [
            {"text": "The ancient map points to the ruins."},
            {"text": "The gate opens only at moonrise."},
        ],
    )

    response = client.post(
        f"/story/{session_id}/chat",
        json={"user_input": "What does the PDF say about the gate?"},
    )

    assert response.status_code == 200
    prompt = captured["prompt"]
    assert isinstance(prompt, list)
    assert any("Relevant PDF content" in message.get("content", "") for message in prompt if isinstance(message, dict))
    assert "The ancient map points to the ruins." in prompt[0]["content"]


def test_chronicle_chat_creates_story_beat_and_event(monkeypatch):
    created = client.post(
        "/story",
        data={"title": "Beat Chronicle", "synopsis": "A plot-driven adventure"},
    )
    session_id = created.json()["id"]

    monkeypatch.setattr("app.api.chronicle_router.get_response", lambda prompt: "The hero opens the ancient gate.")
    monkeypatch.setattr("app.api.chronicle_router.query_chroma_for_lore", lambda **kwargs: [])

    response = client.post(
        f"/story/{session_id}/chat",
        json={"user_input": "I try the gate"},
    )

    assert response.status_code == 200

    with get_db() as db:
        beats = db.query(StoryBeat).filter(StoryBeat.session_id == session_id).all()
        events = db.query(StoryEvent).filter(StoryEvent.session_id == session_id).all()

        assert len(beats) == 1
        assert beats[0].status == "completed"
        assert len(events) == 1
        assert "gate" in events[0].description.lower()
