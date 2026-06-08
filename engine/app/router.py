"""L0–L3 layered intent classification + mode-aware model selection.

Design principle: "minimize LLM calls". Cheap rule layers (L0–L2) decide most cases;
only ambiguous ones escalate to L3 (an LLM hook, injected; defaults to a heuristic).

Keyword hints are bilingual (English-first + Korean) so the classifier works for a
global audience while still handling Korean input.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import catalog

Mode = str  # "eco" | "balanced" | "quality"
VALID_MODES = ("eco", "balanced", "quality")

# ---- L0: domain signals (cheapest layer) --------------------------------
_DOMAIN_HINTS: dict[str, list[str]] = {
    "visual": ["image", "picture", "photo", "draw", "poster", "infographic", "video",
               "clip", "ocr", "edit", "retouch",
               "이미지", "그림", "그려", "사진", "포스터", "인포그래픽", "영상", "동영상", "비디오", "편집", "보정"],
    "audio":  ["voice", "tts", "speak", "narration", "transcribe", "transcription", "stt",
               "music", "song", "compose", "bgm",
               "음성", "목소리", "읽어", "내레이션", "받아쓰", "전사", "음악", "노래", "작곡"],
    # text is the default
}

# ---- L1: intent signals (within a domain) -------------------------------
_INTENT_HINTS: dict[str, list[str]] = {
    "text.coding":          ["code", "coding", "debug", "bug", "function", "refactor", "python",
                             "javascript", "error", "stack trace", "implement", "compile",
                             "코드", "코딩", "디버그", "버그", "함수", "리팩터", "에러", "구현"],
    "text.reasoning":       ["analyze", "analysis", "reasoning", "paper", "strategy", "compare",
                             "pros and cons", "why", "rationale", "in-depth",
                             "분석", "추론", "논문", "전략", "비교", "장단점", "근거", "심층"],
    "text.translation":     ["translate", "translation", "localize", "localization", "into english",
                             "into korean", "번역", "영어로", "한국어로", "일본어로", "현지화"],
    "text.search_realtime": ["search", "latest", "realtime", "real-time", "today", "now", "news", "recent",
                             "검색", "최신", "실시간", "오늘", "지금", "뉴스", "최근"],
    "text.agent":           ["automatically", "step by step", "workflow", "multi-step", "agent", "schedule",
                             "자동으로", "단계별로", "워크플로우", "여러 단계", "에이전트", "예약", "실행해줘"],
    "visual.video":         ["video", "clip", "scene", "footage", "영상", "동영상", "비디오", "장면", "클립"],
    "visual.image_ocr":     ["ocr", "extract text", "recognize text", "scan", "read the table",
                             "추출", "텍스트 인식", "스캔", "표 추출"],
    "visual.image_edit":    ["edit", "retouch", "remove", "replace", "inpaint", "background removal", "compose",
                             "편집", "보정", "지워", "바꿔", "합성", "배경 제거"],
    "audio.stt":            ["transcribe", "transcription", "stt", "subtitle", "captions",
                             "받아쓰", "전사", "자막"],
    "audio.music":          ["music", "song", "compose", "bgm", "음악", "노래", "작곡"],
    "audio.tts":            ["voice", "tts", "speak", "narration", "read aloud",
                             "음성", "목소리", "읽어", "내레이션"],
}

_DEFAULT_INTENT = {"text": "text.chat_writing", "visual": "visual.image_gen", "audio": "audio.tts"}


@dataclass
class Classification:
    domain: str
    intent: str
    confidence: float
    level: str          # which layer decided (L0–L3)
    requires_reasoning: bool = False
    signals: list[str] = field(default_factory=list)


def _score(text: str, hints: list[str]) -> tuple[int, list[str]]:
    t = text.lower()
    hit = [h for h in hints if h.lower() in t]
    return len(hit), hit


def classify(text: str, llm_hook=None) -> Classification:
    """Decide intent via L0 -> L1 -> (L2) -> L3."""
    # L0: domain
    domain, dom_signals, best = "text", [], 0
    for d, hints in _DOMAIN_HINTS.items():
        n, hit = _score(text, hints)
        if n > best:
            domain, dom_signals, best = d, hit, n

    # L1: intent within domain
    intent, intent_signals, best_i = None, [], 0
    for ik, hints in _INTENT_HINTS.items():
        if catalog.INTENTS.get(ik, {}).get("domain") != domain:
            continue
        n, hit = _score(text, hints)
        if n > best_i:
            intent, intent_signals, best_i = ik, hit, n

    if intent is None:
        intent = _DEFAULT_INTENT[domain]
        level, confidence = "L0", 0.55 if best else 0.4
    else:
        level = "L1"
        confidence = min(0.95, 0.6 + 0.12 * best_i)

    # L3: escalate to an LLM only when low-confidence (the costly layer)
    if confidence < 0.5 and llm_hook is not None:
        guess = llm_hook(text, list(catalog.INTENTS.keys()))
        if guess in catalog.INTENTS:
            intent = guess
            domain = catalog.INTENTS[guess]["domain"]
            level, confidence = "L3", 0.8

    rr = catalog.INTENTS[intent]["requires_reasoning"]
    return Classification(domain, intent, round(confidence, 2), level, rr,
                          dom_signals + intent_signals)


@dataclass
class RouteDecision:
    intent: str
    mode: Mode
    model: str | None
    fallbacks: list[str]
    cost_in_out: tuple[float, float] | None
    resale_ok: bool
    local_only: bool
    note: str = ""


def route(intent: str, mode: Mode = "balanced", *, allow_keys: set[str] | None = None,
          require_resale: bool = True, local_only: bool = False) -> RouteDecision:
    """intent + mode -> model. Gates: resale terms, available keys, local-only."""
    if mode not in VALID_MODES:
        mode = "balanced"
    candidates = list(catalog.ROUTING.get(intent, {}).get(mode, []))
    if not candidates:  # no rule for this mode -> fall back to balanced
        candidates = list(catalog.ROUTING.get(intent, {}).get("balanced", []))

    notes = []
    filtered = []
    for m in candidates:
        meta = catalog.MODELS.get(m, {})
        if require_resale and not meta.get("resale", True):
            notes.append(f"{m} blocked by resale terms")
            continue
        if local_only and not meta.get("local", False):
            continue
        provider = m.split("/")[0]
        if allow_keys is not None and not meta.get("local", False) and provider not in allow_keys:
            notes.append(f"{m} no key")
            continue
        filtered.append(m)

    # Local tier: if every cloud candidate is blocked, fall back to a local model
    if not filtered:
        domain = intent.split(".")[0]
        lf = catalog.LOCAL_FALLBACK.get(domain)
        if lf:
            filtered = [lf]
            notes.append(f"local fallback {lf}")

    chosen = filtered[0] if filtered else None
    meta = catalog.MODELS.get(chosen, {}) if chosen else {}
    return RouteDecision(
        intent=intent, mode=mode, model=chosen,
        fallbacks=filtered[1:],
        cost_in_out=meta.get("cost"),
        resale_ok=meta.get("resale", True),
        local_only=meta.get("local", False),
        note="; ".join(notes),
    )
