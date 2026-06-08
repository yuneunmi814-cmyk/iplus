"""iPlus local engine — FastAPI entry point.

Started as a Tauri sidecar:  iplus-engine --port 8787 --db <APPDATA>/iplus.db
Open-source tier: local SQLite + BYO keys / local models. The cloud tier ships separately.
"""
from __future__ import annotations

import argparse
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import __version__, catalog, connectors, db
from .router import classify, route

app = FastAPI(title="iPlus Engine", version=__version__)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Runtime state (injected from main)
STATE: dict = {"db_path": ":memory:", "api_keys": {}}


# ---- schema -------------------------------------------------------------
class TaskRequest(BaseModel):
    input: str
    mode: str = "balanced"
    task_id: int | None = None  # continue an existing conversation (SCB)
    workspace_id: int | None = None
    override_model: str | None = None
    local_only: bool = False


class KeysRequest(BaseModel):
    openai: str | None = None
    anthropic: str | None = None
    google: str | None = None


# ---- watchdog -----------------------------------------------------------
def _parent_death_watchdog(parent_pid: int | None) -> None:
    """Self-terminate if the Tauri shell dies (orphan prevention).

    PyInstaller --onefile is a 2-process [bootloader -> Python] tree, so watching
    getppid() only sees the bootloader and misses the shell's death. Instead we take
    the shell PID directly and probe it with os.kill(pid, 0). ProcessLookupError =
    the shell is gone -> exit.
    """
    import os
    import threading
    import time

    if not parent_pid or parent_pid <= 1:
        return  # standalone (dev) run: no watchdog needed

    def loop() -> None:
        while True:
            time.sleep(2)
            try:
                os.kill(parent_pid, 0)  # no signal sent, existence check only
            except ProcessLookupError:
                os._exit(0)  # shell is gone
            except PermissionError:
                pass  # alive but not permitted -> fine

    threading.Thread(target=loop, daemon=True).start()


def _route_for(req: TaskRequest):
    c = classify(req.input)
    if req.override_model and req.override_model in catalog.MODELS:
        decision = route(c.intent, req.mode)
        decision.model = req.override_model
    else:
        decision = route(
            c.intent, req.mode,
            allow_keys=set(STATE["api_keys"]),  # empty set -> cloud filtered -> local fallback
            local_only=req.local_only,
        )
    return c, decision


# ---- lifecycle ----------------------------------------------------------
@app.on_event("startup")
async def _startup() -> None:
    _parent_death_watchdog(STATE.get("parent_pid"))
    # BYO keys: seed from env (Tauri/UI can also set them at runtime via /config)
    for prov, env in (("openai", "OPENAI_API_KEY"),
                      ("anthropic", "ANTHROPIC_API_KEY"),
                      ("google", "GOOGLE_API_KEY")):
        v = os.getenv(env)
        if v:
            STATE["api_keys"][prov] = v
    await db.init_db(STATE["db_path"])


# ---- endpoints ----------------------------------------------------------
@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__, "keys": sorted(STATE["api_keys"])}


@app.get("/catalog")
async def get_catalog() -> dict:
    return {
        "intents": catalog.INTENTS,
        "modes": ["eco", "balanced", "quality"],
        "resale_blocked": catalog.resale_blocked(),
    }


@app.post("/config")
async def set_keys(req: KeysRequest) -> dict:
    """Set BYO API keys at runtime (the UI persists them locally and posts on load)."""
    for prov in ("openai", "anthropic", "google"):
        val = getattr(req, prov)
        if val:
            STATE["api_keys"][prov] = val
        elif val == "":  # explicit clear
            STATE["api_keys"].pop(prov, None)
    return {"keys": sorted(STATE["api_keys"])}


@app.post("/classify")
async def do_classify(req: TaskRequest) -> dict:
    return classify(req.input).__dict__


@app.post("/tasks")
async def run_task(req: TaskRequest) -> dict:
    """One-line input -> classify -> mode-aware routing decision (no generation)."""
    c, decision = _route_for(req)
    run_id = await db.log_run(
        STATE["db_path"], task_id=None, model=decision.model, mode=req.mode,
        input_text=req.input, output="",
    )
    return {
        "run_id": run_id,
        "classification": c.__dict__,
        "routing": {
            "model": decision.model, "fallbacks": decision.fallbacks, "mode": decision.mode,
            "cost_in_out": decision.cost_in_out, "resale_ok": decision.resale_ok,
            "local": decision.local_only, "note": decision.note,
        },
    }


@app.post("/generate")
async def generate(req: TaskRequest) -> StreamingResponse:
    """Classify -> route -> call the model and stream tokens back as SSE.

    Continues a conversation when task_id is given: prior turns are replayed as
    message history (the SCB idea — context survives even a model switch).
    Events:  routing (json, includes task_id) -> token* (text) -> error? -> done
    """
    c, decision = _route_for(req)

    # conversation thread: reuse the task or start a new one
    task_id = req.task_id or await db.create_task(
        STATE["db_path"], domain=c.domain, intent=c.intent
    )
    history = await db.get_history(STATE["db_path"], task_id) if req.task_id else []
    messages: list[dict] = []
    for user_in, assistant_out in history:
        messages.append({"role": "user", "content": user_in})
        messages.append({"role": "assistant", "content": assistant_out})
    messages.append({"role": "user", "content": req.input})

    async def sse():
        import json as _json
        yield ("event: routing\ndata: " + _json.dumps({
            "task_id": task_id, "turn": len(history) + 1,
            "classification": c.__dict__,
            "model": decision.model, "fallbacks": decision.fallbacks,
            "mode": decision.mode, "cost_in_out": decision.cost_in_out,
            "local": decision.local_only, "note": decision.note,
        }) + "\n\n")

        if not decision.model:
            yield "event: error\ndata: No eligible model. Add an API key or run Ollama.\n\n"
            yield "event: done\ndata: {}\n\n"
            return

        acc: list[str] = []
        try:
            async for chunk in connectors.stream_generate(
                decision.model, c.domain, messages, keys=STATE["api_keys"]
            ):
                acc.append(chunk)
                yield "event: token\ndata: " + _json.dumps(chunk) + "\n\n"
        except connectors.ConnectorError as e:
            yield "event: error\ndata: " + _json.dumps(str(e)) + "\n\n"
        finally:
            await db.log_run(
                STATE["db_path"], task_id=task_id, model=decision.model, mode=req.mode,
                input_text=req.input, output="".join(acc),
            )
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--db", default=os.getenv("IPLUS_DB", "iplus.db"))
    ap.add_argument("--parent-pid", type=int,
                    default=int(os.getenv("IPLUS_PARENT_PID", "0")) or None)
    args = ap.parse_args()
    STATE["db_path"] = args.db
    STATE["parent_pid"] = args.parent_pid

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
