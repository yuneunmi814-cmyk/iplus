"""SCB summarization — old turns fold into a summary; recent turns stay verbatim."""
import json

import pytest
from fastapi.testclient import TestClient

from app import connectors
from app.main import app, STATE, KEEP_RECENT_TURNS

_seen: dict = {}


@pytest.fixture(autouse=True)
def client(tmp_path, monkeypatch):
    STATE["db_path"] = str(tmp_path / "t.db")
    STATE["api_keys"] = {}
    _seen.clear()

    async def fake_stream(model, domain, messages, *, keys, system=None):
        _seen["messages"] = list(messages)
        _seen["system"] = system
        yield "reply."

    async def fake_complete(model, domain, messages, *, keys, system=None):
        # stand in for the summarizer model call
        return "SUMMARY: user mentioned a secret code ZEBRA-7."

    monkeypatch.setattr(connectors, "stream_generate", fake_stream)
    monkeypatch.setattr(connectors, "complete", fake_complete)
    with TestClient(app) as c:
        yield c


def _routing(text: str) -> dict:
    block = next(b for b in text.split("\n\n") if "event: routing" in b)
    return json.loads("".join(l[6:] for l in block.split("\n") if l.startswith("data: ")))


def test_short_conversation_not_summarized(client):
    r = client.post("/generate", json={"input": "hello"})
    tid = _routing(r.text)["task_id"]
    r2 = client.post("/generate", json={"input": "again", "task_id": tid})
    assert _routing(r2.text)["summarized_turns"] == 0
    assert "summary" not in (_seen["system"] or "").lower()


def test_long_conversation_summarizes_old_turns(client):
    r = client.post("/generate", json={"input": "turn 0"})
    tid = _routing(r.text)["task_id"]
    # drive enough turns to exceed the recent window
    last = None
    for i in range(1, KEEP_RECENT_TURNS + 3):
        last = client.post("/generate", json={"input": f"turn {i}", "task_id": tid})

    routing = _routing(last.text)
    assert routing["summarized_turns"] >= 1
    # the rolling summary is injected into the system prompt
    assert "SUMMARY" in _seen["system"]
    # only recent turns are replayed verbatim (not the whole history)
    user_msgs = [m for m in _seen["messages"] if m["role"] == "user"]
    assert len(user_msgs) <= KEEP_RECENT_TURNS + 1  # recent turns + current
    assert not any(m["content"] == "turn 0" for m in _seen["messages"])  # turn 0 folded away
