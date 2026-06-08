"""API smoke tests via FastAPI TestClient (no network / no model calls)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app, STATE


@pytest.fixture(autouse=True)
def _memory_db(tmp_path):
    # a real file (not :memory:) so aiosqlite connections share the schema
    STATE["db_path"] = str(tmp_path / "test.db")
    STATE["api_keys"] = {}
    with TestClient(app) as client:  # triggers startup (init_db)
        yield client


def test_health(_memory_db):
    r = _memory_db.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_catalog(_memory_db):
    body = _memory_db.get("/catalog").json()
    assert len(body["intents"]) == 13
    assert body["modes"] == ["eco", "balanced", "quality"]
    assert len(body["resale_blocked"]) == 5


def test_classify_endpoint(_memory_db):
    r = _memory_db.post("/classify", json={"input": "debug this code"})
    assert r.json()["intent"] == "text.coding"


def test_tasks_routing_decision(_memory_db):
    r = _memory_db.post("/tasks", json={"input": "write a poem", "mode": "balanced"})
    body = r.json()
    assert body["classification"]["domain"] == "text"
    # no keys configured -> local fallback
    assert body["routing"]["model"] == "ollama/llama3.1:8b"


def test_config_sets_keys(_memory_db):
    r = _memory_db.post("/config", json={"openai": "sk-test"})
    assert r.json()["keys"] == ["openai"]
    # now routing should pick the cloud model
    body = _memory_db.post("/tasks", json={"input": "write a poem"}).json()
    assert body["routing"]["model"] == "openai/gpt-5.5"
