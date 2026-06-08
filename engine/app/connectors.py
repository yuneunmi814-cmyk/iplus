"""Connector layer — actually call the chosen model and stream tokens.

Each provider exposes an async generator yielding text chunks. The local tier
defaults to Ollama (no key); BYO keys enable OpenAI / Anthropic / Google.

`messages` is the conversation so far: a list of {"role": "user"|"assistant",
"content": str}, oldest first, ending with the current user turn. Because the
history is model-agnostic, the conversation survives a model switch (the SCB idea).
Non-text modalities (image/audio/video) are not wired yet and yield a notice.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

OLLAMA_URL = "http://127.0.0.1:11434"
TEXT_DOMAIN = "text"

Messages = list[dict]


class ConnectorError(Exception):
    pass


def _with_system(messages: Messages, system: str | None) -> Messages:
    return ([{"role": "system", "content": system}] if system else []) + messages


async def _ollama(model_key: str, messages: Messages, system: str | None) -> AsyncIterator[str]:
    payload = {"model": model_key, "messages": _with_system(messages, system), "stream": True}
    async with httpx.AsyncClient(timeout=None) as client:
        try:
            async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as r:
                if r.status_code != 200:
                    raise ConnectorError(
                        f"Ollama returned {r.status_code}. Is it running? Try `ollama serve` "
                        f"and `ollama pull {model_key}`."
                    )
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    chunk = obj.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if obj.get("done"):
                        break
        except httpx.ConnectError as e:
            raise ConnectorError(
                "Cannot reach Ollama at localhost:11434. Install it from https://ollama.com "
                "and run `ollama serve`."
            ) from e


async def _openai(model_key: str, messages: Messages, system: str | None, key: str) -> AsyncIterator[str]:
    payload = {"model": model_key, "messages": _with_system(messages, system), "stream": True}
    headers = {"Authorization": f"Bearer {key}"}
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", "https://api.openai.com/v1/chat/completions",
                                 json=payload, headers=headers) as r:
            if r.status_code != 200:
                raise ConnectorError(f"OpenAI returned {r.status_code}: {await r.aread()!r}")
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
                if delta:
                    yield delta


async def _anthropic(model_key: str, messages: Messages, system: str | None, key: str) -> AsyncIterator[str]:
    # Anthropic takes system separately and only user/assistant in messages.
    payload = {
        "model": model_key,
        "max_tokens": 4096,
        "stream": True,
        "messages": [m for m in messages if m["role"] != "system"],
    }
    if system:
        payload["system"] = system
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", "https://api.anthropic.com/v1/messages",
                                 json=payload, headers=headers) as r:
            if r.status_code != 200:
                raise ConnectorError(f"Anthropic returned {r.status_code}: {await r.aread()!r}")
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                evt = json.loads(line[6:])
                if evt.get("type") == "content_block_delta":
                    text = evt.get("delta", {}).get("text")
                    if text:
                        yield text


async def _gemini(model_key: str, messages: Messages, system: str | None, key: str) -> AsyncIterator[str]:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model_key}:streamGenerateContent?alt=sse&key={key}")
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user",
         "parts": [{"text": m["content"]}]}
        for m in messages if m["role"] != "system"
    ]
    payload: dict = {"contents": contents}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", url, json=payload) as r:
            if r.status_code != 200:
                raise ConnectorError(f"Gemini returned {r.status_code}: {await r.aread()!r}")
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                obj = json.loads(line[6:])
                for cand in obj.get("candidates", []):
                    for part in cand.get("content", {}).get("parts", []):
                        if part.get("text"):
                            yield part["text"]


async def stream_generate(model: str, domain: str, messages: Messages, *,
                          keys: dict[str, str], system: str | None = None) -> AsyncIterator[str]:
    """Dispatch to the right provider and stream text chunks.

    `model` is "provider/model_key". `messages` is the full conversation. `keys`
    maps provider -> api key.
    """
    if domain != TEXT_DOMAIN:
        yield (f"[iPlus] Generation for '{domain}' isn't wired yet — routing chose "
               f"{model}. Text generation works today (local Ollama or your own keys).")
        return

    provider, _, model_key = model.partition("/")
    if provider == "ollama":
        gen = _ollama(model_key, messages, system)
    elif provider == "openai":
        gen = _openai(model_key, messages, system, keys["openai"])
    elif provider == "anthropic":
        gen = _anthropic(model_key, messages, system, keys["anthropic"])
    elif provider == "google":
        gen = _gemini(model_key, messages, system, keys["google"])
    else:
        yield f"[iPlus] No connector for provider '{provider}'."
        return

    async for chunk in gen:
        yield chunk
