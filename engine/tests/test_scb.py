"""SCB conversation threading — prior turns are replayed as message history."""
import json

import pytest
from fastapi.testclient import TestClient

from app import connectors
from app.main import app, STATE

_captured: dict = {}


@pytest.fixture(autouse=True)
def client(tmp_path, monkeypatch):
    STATE["db_path"] = str(tmp_path / "t.db")
    STATE["api_keys"] = {}
    _captured.clear()

    async def fake_stream(model, domain, messages, *, keys, system=None):
        _captured["messages"] = list(messages)
        yield "noted."

    monkeypatch.setattr(connectors, "stream_generate", fake_stream)
    with TestClient(app) as c:
        yield c


def _task_id(sse_text: str) -> int:
    for block in sse_text.split("\n\n"):
        if "event: routing" in block:
            data = "".join(l[6:] for l in block.split("\n") if l.startswith("data: "))
            return json.loads(data)["task_id"]
    raise AssertionError("no routing event")


def test_first_turn_creates_task_and_sends_only_current(client):
    r = client.post("/generate", json={"input": "hi there"})
    assert _task_id(r.text) is not None
    assert _captured["messages"] == [{"role": "user", "content": "hi there"}]


def test_second_turn_replays_prior_history(client):
    r1 = client.post("/generate", json={"input": "my name is Sam"})
    tid = _task_id(r1.text)

    client.post("/generate", json={"input": "what is my name?", "task_id": tid})
    msgs = _captured["messages"]

    assert msgs[0] == {"role": "user", "content": "my name is Sam"}
    assert msgs[1] == {"role": "assistant", "content": "noted."}
    assert msgs[-1] == {"role": "user", "content": "what is my name?"}


def test_turn_number_increments(client):
    r1 = client.post("/generate", json={"input": "one"})
    tid = _task_id(r1.text)
    r2 = client.post("/generate", json={"input": "two", "task_id": tid})
    block = next(b for b in r2.text.split("\n\n") if "event: routing" in b)
    data = json.loads("".join(l[6:] for l in block.split("\n") if l.startswith("data: ")))
    assert data["turn"] == 2
