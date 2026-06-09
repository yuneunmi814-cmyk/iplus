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


# Languages we recognize as a translation target (en + ko names). If a translation
# request names none of these, the target is the one high-leverage missing slot.
_LANGUAGES = {
    "english", "spanish", "french", "german", "italian", "portuguese", "dutch",
    "russian", "chinese", "mandarin", "cantonese", "japanese", "korean", "arabic",
    "hindi", "vietnamese", "thai", "indonesian", "turkish", "polish", "swedish",
    "greek", "hebrew", "latin",
    "영어", "스페인어", "프랑스어", "독일어", "이탈리아어", "포르투갈어", "러시아어",
    "중국어", "일본어", "한국어", "아랍어", "힌디어", "베트남어", "태국어", "라틴어",
}


def needs_clarification(intent: str, text: str) -> str | None:
    """Return ONE high-leverage question if a required slot is clearly missing,
    else None. Deliberately conservative — only asks when guessing would likely be
    wrong (the design's "ask the minimum" principle)."""
    if intent == "text.translation":
        t = text.lower()
        if not any(lang in t for lang in _LANGUAGES):
            return "Which language should I translate into?"
    return None
