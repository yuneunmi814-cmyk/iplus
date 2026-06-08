"""iPlus local engine — FastAPI entry point.

Started as a Tauri sidecar:  iplus-engine --port 8787 --db <APPDATA>/iplus.db
Open-source tier: local SQLite + BYO keys / local models. The cloud tier ships separately.
"""
from __future__ import annotations

import argparse
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import __version__, catalog, db
from .router import classify, route

app = FastAPI(title="iPlus Engine", version=__version__)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Runtime state (injected from main)
STATE: dict = {"db_path": ":memory:", "keys": set()}


# ---- schema -------------------------------------------------------------
class TaskRequest(BaseModel):
    input: str
    mode: str = "balanced"
    workspace_id: int | None = None
    override_model: str | None = None
    local_only: bool = False


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


# ---- lifecycle ----------------------------------------------------------
@app.on_event("startup")
async def _startup() -> None:
    _parent_death_watchdog(STATE.get("parent_pid"))
    # BYO keys: detect available providers from env (Tauri store -> env injection)
    keys = set()
    if os.getenv("OPENAI_API_KEY"):    keys.add("openai")
    if os.getenv("ANTHROPIC_API_KEY"): keys.add("anthropic")
    if os.getenv("GOOGLE_API_KEY"):    keys.add("google")
    STATE["keys"] = keys
    await db.init_db(STATE["db_path"])


# ---- endpoints ----------------------------------------------------------
@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__, "keys": sorted(STATE["keys"])}


@app.get("/catalog")
async def get_catalog() -> dict:
    return {
        "intents": catalog.INTENTS,
        "modes": ["eco", "balanced", "quality"],
        "resale_blocked": catalog.resale_blocked(),
    }


@app.post("/classify")
async def do_classify(req: TaskRequest) -> dict:
    c = classify(req.input)
    return c.__dict__


@app.post("/tasks")
async def run_task(req: TaskRequest) -> dict:
    """One-line input -> classify -> mode-aware routing -> (model call stub) -> log."""
    c = classify(req.input)

    if req.override_model and req.override_model in catalog.MODELS:
        decision = route(c.intent, req.mode)
        chosen = req.override_model
        decision.model = chosen
    else:
        decision = route(
            c.intent, req.mode,
            allow_keys=STATE["keys"] or None,
            local_only=req.local_only,
        )
        chosen = decision.model

    # Real model calls happen in the connector layer (MVP: returns the decision only).
    output = ""
    run_id = await db.log_run(
        STATE["db_path"], task_id=None, model=chosen, mode=req.mode,
        input_text=req.input, output=output,
    )

    return {
        "run_id": run_id,
        "classification": c.__dict__,
        "routing": {
            "model": chosen,
            "fallbacks": decision.fallbacks,
            "mode": decision.mode,
            "cost_in_out": decision.cost_in_out,
            "resale_ok": decision.resale_ok,
            "local": decision.local_only,
            "note": decision.note,
        },
        "output": output,  # empty until the connector layer is wired
    }


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
