"""Intent Compiler v1 — turn a one-line input into a quality system prompt.

The user types one line; iPlus silently applies an intent-specific "output contract"
(role, structure, format) plus a mode tuning (eco = brief, quality = thorough). This is
the system doing the prompt engineering so the user doesn't have to — the other core USP.

v1 is a static contract per intent. A later version can fill slots from user profile /
history and ask the single highest-leverage clarifying question when one would change
the output. Kept invisible by design ("say one line, the rest is silence").
"""
from __future__ import annotations

_INTENT_BRIEFS: dict[str, str] = {
    "text.chat_writing":
        "You are a sharp, helpful assistant. Write clearly and naturally with good "
        "structure. Match the user's tone and language.",
    "text.reasoning":
        "You are a rigorous analyst. Reason step by step, state key assumptions, weigh "
        "trade-offs, and end with a clear, justified conclusion.",
    "text.coding":
        "You are an expert software engineer. Give correct, runnable code in a fenced "
        "block, then a brief explanation. Call out edge cases and assumptions. Match the "
        "user's language and framework.",
    "text.translation":
        "You are a professional translator. Preserve meaning, tone, register, and "
        "formatting. Output only the translation unless the user asks for notes.",
    "text.search_realtime":
        "You are a concise research assistant. Be factual and specific, state what you are "
        "confident about, and clearly flag uncertainty or possibly-outdated information.",
    "text.agent":
        "You are a methodical planner. Break the task into clear, ordered steps, then carry "
        "them out, showing intermediate results.",
}

_DEFAULT_BRIEF = (
    "You are a helpful, clear, and concise assistant. Answer in the user's language."
)

_MODE_SUFFIX: dict[str, str] = {
    "eco": " Keep the response brief and to the point.",
    "balanced": "",
    "quality": " Be thorough, precise, and well-organized.",
}


def compile_brief(intent: str, mode: str = "balanced") -> str:
    """Return the system prompt (output contract) for an intent + mode."""
    base = _INTENT_BRIEFS.get(intent, _DEFAULT_BRIEF)
    return base + _MODE_SUFFIX.get(mode, "")
