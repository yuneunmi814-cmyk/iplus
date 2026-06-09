"""Intent Compiler v1 — output-contract system prompts."""
import pytest
from fastapi.testclient import TestClient

from app import brief, connectors
from app.main import app, STATE

_cap: dict = {}


def test_coding_brief_is_engineer():
    s = brief.compile_brief("text.coding", "balanced")
    assert "engineer" in s.lower()
    assert "code" in s.lower()


def test_translation_brief_is_translator():
    assert "translat" in brief.compile_brief("text.translation").lower()


def test_unknown_intent_uses_default():
    assert brief.compile_brief("audio.tts") == brief._DEFAULT_BRIEF


def test_mode_suffix_changes_verbosity():
    eco = brief.compile_brief("text.reasoning", "eco")
    quality = brief.compile_brief("text.reasoning", "quality")
    assert "brief" in eco.lower()
    assert "thorough" in quality.lower()
    assert eco != quality


# ---- the compiled brief reaches the connector as the system prompt ------
@pytest.fixture
def client(tmp_path, monkeypatch):
    STATE["db_path"] = str(tmp_path / "t.db")
    STATE["api_keys"] = {}
    _cap.clear()

    async def fake_stream(model, domain, messages, *, keys, system=None):
        _cap["system"] = system
        yield "ok."

    monkeypatch.setattr(connectors, "stream_generate", fake_stream)
    with TestClient(app) as c:
        yield c


def test_generate_applies_brief(client):
    client.post("/generate", json={"input": "fix this bug in my code", "mode": "quality"})
    assert _cap["system"] == brief.compile_brief("text.coding", "quality")


# ---- clarifying question (Intent Compiler v2) ---------------------------
def test_needs_clarification_translation_missing_target():
    assert brief.needs_clarification("text.translation", "translate this sentence")


def test_needs_clarification_translation_with_target():
    assert brief.needs_clarification("text.translation", "translate this into Korean") is None


def test_needs_clarification_non_translation():
    assert brief.needs_clarification("text.coding", "write a function") is None


def test_generate_asks_when_target_missing(client):
    r = client.post("/generate", json={"input": "translate good morning"})
    assert "event: clarify" in r.text
    assert "Which language" in r.text
    assert "event: token" not in r.text  # did not generate


def test_generate_proceeds_when_target_present(client):
    r = client.post("/generate", json={"input": "translate good morning into French"})
    assert "event: clarify" not in r.text
    assert "event: routing" in r.text


def test_clarify_skipped_inside_a_thread(client):
    r = client.post("/generate", json={"input": "translate good morning", "task_id": 999})
    assert "event: clarify" not in r.text  # never re-ask mid-conversation
