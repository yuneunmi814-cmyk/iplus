# Contributing to iPlus

First off — **thank you**. iPlus gets better every time someone teaches it a new
language, a sharper prompt, or a better model choice. This guide is built so your
**first PR can land in an afternoon**.

Why it's a pleasant project to hack on:

- **You can run everything locally, for free.** The engine talks to [Ollama](https://ollama.com) — no API key, no cloud bill to test your change.
- **Fast feedback.** 41 tests run in well under a second; CI mirrors them on every PR.
- **Small, readable core.** The routing engine is plain Python (~a few hundred lines). No framework spelunking.
- **No contribution is too small.** Typos, docs, a single keyword, one test — all welcome.

---

## 1 · Get set up (~5 minutes)

```bash
git clone https://github.com/yuneunmi814-cmyk/iplus.git
cd iplus/engine
python3.12 -m venv .venv && source .venv/bin/activate    # Python 3.12 (not 3.13/3.14)
pip install -r requirements-dev.txt
python -m pytest                                          # 41 passing — you're ready
```

Want to see it actually answer? Install [Ollama](https://ollama.com), `ollama pull llama3.1:8b`,
then `python -m app.main` and open `frontend/dist/index.html`. Full details in the
[README Quickstart](README.md#quickstart-5-minutes).

## 2 · The map

| File | What lives here |
|---|---|
| `engine/app/router.py` | L0–L3 intent classification + mode routing (the keyword hints) |
| `engine/app/catalog.py` | Model catalog: models, prices, **resale terms**, routing rules |
| `engine/app/brief.py` | Intent Compiler: output-contract prompts + the clarifying question |
| `engine/app/connectors.py` | Streamed model calls (Ollama / OpenAI / Anthropic / Google) |
| `engine/app/main.py` | FastAPI endpoints + SCB conversation/summary logic |
| `engine/tests/` | The test suite that guards all of the above |
| `frontend/dist/index.html` | The one-file UI (no build step) |
| `frontend/src-tauri/` | Tauri desktop shell, updater, packaging |

---

## 3 · Good first PRs (pick one, copy the recipe)

Each recipe lists **the file**, **the change**, and **the test that proves it works**.

### 🌍 Teach iPlus your language
Make iPlus understand requests written in your language.
- **File:** `engine/app/router.py` → add words to `_DOMAIN_HINTS` / `_INTENT_HINTS` (they're bilingual lists).
- **Verify:** add a case to `engine/tests/test_router.py`, e.g. `assert classify("<your-language request>").intent == "text.coding"`.

### 🈯 Add a translation-target language
So "translate this into Swahili" stops asking which language.
- **File:** `engine/app/brief.py` → add the language to `_LANGUAGES`.
- **Verify:** `assert brief.needs_clarification("text.translation", "translate hi into swahili") is None`.

### ✍️ Sharpen an output contract
Improve the system prompt iPlus applies for an intent (coding, reasoning, …).
- **File:** `engine/app/brief.py` → `_INTENT_BRIEFS`.
- **Verify:** run a before/after with Ollama and paste the diff in your PR.

### 🧩 Add a model to the catalog
- **File:** `engine/app/catalog.py` → add to `MODELS` **and** wire it into `ROUTING` for the relevant intents/modes.
- **Guardrails (the tests enforce these):**
  - every model in `ROUTING` must exist in `MODELS`;
  - every intent needs `eco` / `balanced` / `quality` lists;
  - **resale terms** — see §4. New audio/video models default to `resale: False`.
- **Verify:** `python -m pytest tests/test_catalog.py`.

### 🔌 Add a model provider (connector)
- **File:** `engine/app/connectors.py` → add an `async def _yourprovider(...)` generator and a branch in `stream_generate`.
- **Verify:** a unit test that mocks the HTTP response shape (see how `test_scb.py` monkeypatches the connector).

### 🧪 Add a test / 📝 fix docs
Find an untested path or a confusing sentence. These are real, appreciated PRs.

> No good-first-issue grabs you? **Open an issue** describing what you'd like to add — we'll help scope it.

---

## 4 · Principles (what keeps quality high)

These are short and non-negotiable; they're also what the reviewers check first.

1. **Verify by running, not just reading.** The trickiest bugs here only show up at runtime
   (sidecar packaging, streaming, model output). If you change behavior, run it — and say so in the PR.
2. **Resale terms are a hard gate.** iPlus resells model output to users, so a model may only be
   routable if its provider terms allow it. Keep unverified/prohibited models at `resale: False`.
   **Do not flip a model to `True` without a link to the provider's terms** in your PR.
3. **Keep the catalog honest.** `tests/test_catalog.py` must stay green — no dangling models, no
   intent missing a mode.
4. **English-first, but bilingual where it helps.** UI, code, and comments in English; classification
   keyword hints may include other languages (that's how iPlus understands the world).
5. **Small, focused PRs.** One idea per PR is far easier (and faster) to merge than a big mixed one.

## 5 · Pull request checklist

- [ ] `python -m pytest` passes (from `engine/`)
- [ ] Added/updated a test for the behavior you changed
- [ ] Resale terms unchanged, or a provider-terms link is included
- [ ] PR description says **what** changed and **why** (and how you verified, if behavior changed)
- [ ] One focused change

Open the PR against `main`. CI runs the tests automatically. Reviews aim to be quick and
friendly — expect a first response within a couple of days, and ping if it goes quiet.

## 6 · Reporting bugs & ideas

Open a [GitHub issue](https://github.com/yuneunmi814-cmyk/iplus/issues). For bugs, include:
your OS, what you did, what you expected, and — for the desktop app — whether the engine
answered at `http://localhost:8787/health`. Ideas and questions are equally welcome.

## 7 · Conduct & license

Be kind and assume good intent — see the [Code of Conduct](CODE_OF_CONDUCT.md). We want
this to be a friendly place to learn and build.
By contributing, you agree your work is licensed under the project's [MIT License](LICENSE).

Happy hacking 🚀
