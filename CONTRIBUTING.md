# Contributing to iPlus

Thanks for your interest! iPlus is an open-core AI orchestration desktop app.
This repo is the **local tier** (Tauri shell + FastAPI routing engine).

## Repo layout
- `engine/` — Python FastAPI routing engine (the core). Start here.
- `engine/app/router.py` — L0–L3 intent classification + mode routing
- `engine/app/catalog.py` — model catalog seed (routing rules, resale terms)
- `engine/app/connectors.py` — streamed model calls (Ollama / OpenAI / Anthropic / Google)
- `frontend/` — Tauri 2 desktop shell + static UI
- `docs/` — routing seed SQL + screenshot

## Dev setup (engine, no Rust needed)
```bash
cd engine
python3.12 -m venv .venv && source .venv/bin/activate   # Python 3.12
pip install -r requirements-dev.txt
python -m app.main --port 8787 --db ./iplus.db          # run the engine
python -m pytest                                         # run the tests
```
The full desktop app build is described in the [README](README.md#build-from-source).

## Running tests
`python -m pytest` from `engine/`. CI runs the same on every PR (`.github/workflows/test.yml`).
Please add tests for new routing rules, intents, or connectors.

## Guidelines
- **Routing/catalog changes** must keep the catalog integrity tests green
  (`tests/test_catalog.py`) — every routed model must exist, every intent needs
  all three modes (eco/balanced/quality).
- **Resale terms are a hard gate.** A model with unverified or prohibited resale
  terms must stay `resale: False` (the routing gate filters it). Do not flip a
  model to `True` without a citation to the provider's terms.
- Keep the UI/code/comments **English-first**; classification keyword hints may be
  bilingual.
- Small, focused PRs with a clear description are easiest to review.

## Reporting issues
Open a GitHub issue with steps to reproduce, your OS, and (for the desktop app)
whether the `iplus-engine` sidecar reached `http://localhost:8787/health`.

By contributing you agree your contributions are licensed under the [MIT License](LICENSE).
