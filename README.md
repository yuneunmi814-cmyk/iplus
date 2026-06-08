<div align="center">

# iPlus

**Say what you want to do — iPlus picks the right AI for you.**

An open-core AI orchestration desktop app. You describe your intent in one line;
iPlus judges intent, cost, quality, and modality, then **auto-dispatches** the best
model. You never need to know model names (GPT, Claude, Gemini, Sora…).

[Features](#features) · [Install](#install) · [Build](#build-from-source) · [How it works](#architecture) · [Roadmap](#status)

</div>

---

## Why iPlus

Most AI tools make *you* do the hard part: pick the model, write the perfect prompt,
track the cost. iPlus absorbs that complexity. Poe says "you choose"; iPlus says "leave it to me."

**Hybrid open-core.** This repo (open source) is the **local tier**: the routing engine
runs on your machine, free, using local models (Ollama) or your own API keys (BYO).
A paid cloud tier adds managed keys, premium models, and team controls.

## Features
- **System picks the model, not you** — intent → model mapping, with eco / balanced / quality modes.
- **Cross-modality routing** — "turn this summary into an infographic" flows text → image in one step.
- **Resale-aware catalog** — provider terms are enforced as a hard gate (see [the routing seed](docs/iplus_seed_routing.sql)).
- **100% local option** — run entirely on Ollama with no cloud calls, no keys.
- **Privacy-first** — append-only local SQLite; your data stays on your machine in the local tier.

## Architecture
```
┌──────────── Tauri desktop shell (Rust) ────────────┐
│  dist/index.html   one-line input UI                │
│        │ HTTP localhost:8787                         │
│  iplus-engine (sidecar) ── FastAPI routing engine   │
│        ├─ L0–L3 intent classification               │
│        ├─ mode (eco/balanced/quality) model select  │
│        ├─ resale-terms gate                          │
│        └─ local SQLite (append-only run log)         │
│  Ollama localhost:11434  (local models, optional)   │
└─────────────────────────────────────────────────────┘
```

| Path | What |
|---|---|
| `engine/` | Python FastAPI routing engine (heart of the local tier) |
| `engine/app/catalog.py` | Model catalog v1 seed (researched & verified, 2026-06) |
| `engine/app/router.py` | L0–L3 classification + mode-based routing |
| `frontend/src-tauri/` | Tauri shell — sidecar lifecycle, updater, signing |
| `frontend/dist/` | Static one-line-input UI (no Node build needed) |
| `docs/` | Routing seed (`routing_rules`) SQL |

## Install
Grab the latest installer from [Releases](../../releases) (`.dmg` for macOS, `.msi`/`.exe` for Windows).
Unsigned builds: on macOS first launch, right-click → Open to bypass Gatekeeper.

> **Optional — local models:** install [Ollama](https://ollama.com) and `ollama pull llama3.1:8b`
> to run fully offline. Or add your own API keys (OpenAI / Anthropic / Google) in-app.

## Build from source

### Engine only (no Rust needed)
```bash
cd engine
python3.12 -m venv .venv && source .venv/bin/activate   # Python 3.12 (3.14 wheels not ready yet)
pip install -r requirements.txt
python -m app.main --port 8787 --db ./iplus.db
# then open ../frontend/dist/index.html  (or: curl localhost:8787/health)
```

### Full desktop app (Rust required)
```bash
# 0) install Rust once
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 1) bundle the engine into a single binary → externalBin
cd engine && ./build.sh

# 2) generate the updater signing key once → put the pubkey in tauri.conf.json
cd ../frontend && npm install
npx tauri signer generate -w ~/.tauri/iplus.key

# 3) build the desktop app (.dmg / .app / .msi)
npm run build
```

## Release (GitHub Releases, Meetily-style)
`git tag v0.1.0 && git push --tags` triggers `.github/workflows/release.yml`, which builds,
signs, generates `latest.json`, and uploads installers for all platforms. Clients then
auto-update via `tauri-plugin-updater`.

Required GitHub Secret: `TAURI_SIGNING_PRIVATE_KEY` (mandatory),
`APPLE_*` (macOS notarization, optional — otherwise an ad-hoc build).

## Local engine API
| Method | Path | Description |
|---|---|---|
| GET | `/health` | status, version, detected keys |
| GET | `/catalog` | intents, modes, resale-blocked models |
| POST | `/classify` | input → intent classification only |
| POST | `/tasks` | input → classify → routing decision (+ run log) |

## Status
- [x] Local engine: L0–L3 classification + mode routing + resale gate + SQLite log (verified)
- [x] **Tauri shell + sidecar + signed updater + CI** — `.dmg` (20 MB) built & run-verified
- [x] **Sidecar auto-start / cleanup** — engine spawns & health-checks inside the app; a
      watchdog self-terminates the engine if the shell is force-killed (no orphans)
- [x] **Connector layer** — real streamed model calls over SSE: local Ollama (no key) +
      BYO OpenAI / Anthropic / Google; in-app key settings (stored locally)
- [ ] SCB (context retention) + Intent Compiler (brief builder)
- [ ] Image / audio / video generation (text generation works today)
- [ ] Cloud tier (subscription · KMS · teams)

### macOS packaging gotchas found by actually running the app (a review can't catch these)
1. **Hardened runtime vs PyInstaller library validation** — an ad-hoc-signed app with hardened
   runtime refuses to `dlopen` the `Python.framework` PyInstaller extracts to `/tmp`
   ("different Team IDs"). Fix: add `com.apple.security.cs.disable-library-validation` to
   `entitlements.plist`.
2. **PyInstaller `--onefile` defeats a naive parent-death watchdog** — it's a 2-process
   [bootloader → Python] tree, so Python's parent is the bootloader, not the shell. Fix: the
   shell passes its own PID via `--parent-pid` and the engine checks it with `os.kill(pid, 0)`.
3. **Cold start ~8–15 s** — `--onefile` self-extracts to `/tmp` on each launch; keep the health
   timeout generous (30 s).

## Tech
React-ready static UI · Tauri 2 (Rust) · FastAPI · SQLite (local) · PyInstaller sidecar ·
Ollama. Routing weights cite public benchmarks (Artificial Analysis, LMArena, Chatbot Arena).

## License
MIT — see [LICENSE](LICENSE).
