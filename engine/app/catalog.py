"""iPlus model catalog v1 — routing_rules seed (researched & verified, 2026-06 snapshot).

This file holds the same data as iplus_seed_routing.sql in an in-memory form for the
local engine. The cloud tier loads the same structure from a PostgreSQL routing_rules table.
"""
from __future__ import annotations

# domain x intent taxonomy (intent_taxonomy)
INTENTS: dict[str, dict] = {
    # text
    "text.chat_writing":    {"domain": "text",   "requires_reasoning": False, "label": "Chat & writing"},
    "text.reasoning":       {"domain": "text",   "requires_reasoning": True,  "label": "Long-form reasoning & analysis"},
    "text.coding":          {"domain": "text",   "requires_reasoning": True,  "label": "Coding & debugging"},
    "text.translation":     {"domain": "text",   "requires_reasoning": False, "label": "Translation & localization"},
    "text.search_realtime": {"domain": "text",   "requires_reasoning": False, "label": "Search & realtime"},
    "text.agent":           {"domain": "text",   "requires_reasoning": True,  "label": "Agent (multi-step)"},
    # visual
    "visual.image_gen":     {"domain": "visual", "requires_reasoning": False, "label": "Image generation"},
    "visual.image_edit":    {"domain": "visual", "requires_reasoning": False, "label": "Image editing"},
    "visual.video":         {"domain": "visual", "requires_reasoning": False, "label": "Video generation & editing"},
    "visual.image_ocr":     {"domain": "visual", "requires_reasoning": True,  "label": "Image understanding (OCR)"},
    # audio
    "audio.tts":            {"domain": "audio",  "requires_reasoning": False, "label": "Text-to-speech (TTS)"},
    "audio.stt":            {"domain": "audio",  "requires_reasoning": False, "label": "Speech-to-text (STT)"},
    "audio.music":          {"domain": "audio",  "requires_reasoning": False, "label": "Music generation"},
}

# ai_models — provider/model_key, price (verified), terms_allow_resale (terms check result)
# cost: text = USD per 1M tokens (in, out) / others = unit price (see notes)
MODELS: dict[str, dict] = {
    "openai/gpt-5.5":                 {"cost": (5.00, 30.00), "resale": True,  "reasoning": True},
    "openai/gpt-5.5-nano":            {"cost": (0.20, 1.25),  "resale": True,  "reasoning": False},
    "anthropic/claude-opus-4-8":      {"cost": (5.00, 25.00), "resale": True,  "reasoning": True},
    "anthropic/claude-sonnet-4-6":    {"cost": (3.00, 15.00), "resale": True,  "reasoning": False},
    "anthropic/claude-haiku-4-5":     {"cost": (1.00, 5.00),  "resale": True,  "reasoning": False},
    "google/gemini-3.1-pro-preview":  {"cost": (2.00, 12.00), "resale": True,  "reasoning": True},
    "google/gemini-2.5-flash":        {"cost": (0.30, 2.50),  "resale": True,  "reasoning": False},
    "openai/gpt-image-2":             {"cost": (8.00, 30.00), "resale": True,  "reasoning": False},
    "openai/gpt-image-2-mini":        {"cost": (2.50, 8.00),  "resale": True,  "reasoning": False},
    "google/nano-banana-2":           {"cost": (0.0, 0.0),    "resale": True,  "reasoning": False},
    "google/veo-3":                   {"cost": (0.0, 0.0),    "resale": True,  "reasoning": False},
    "openai/sora-2":                  {"cost": (0.0, 0.0),    "resale": True,  "reasoning": False, "eol": "2026-09-24"},
    "kuaishou/kling":                 {"cost": (0.0, 0.0),    "resale": True,  "reasoning": False},
    # resale terms unverified -> conservatively false until legal review
    "elevenlabs/elevenlabs-tts":      {"cost": (0.0, 0.0),    "resale": False, "reasoning": False},
    "elevenlabs/elevenlabs-scribe-stt":{"cost": (0.0, 0.0),   "resale": False, "reasoning": False},
    "elevenlabs/elevenlabs-music":    {"cost": (0.0, 0.0),    "resale": False, "reasoning": False},  # resale prohibited (hard)
    "fishaudio/fish-s2-pro":          {"cost": (0.0, 0.0),    "resale": False, "reasoning": False},
    "fishaudio/fish-transcribe-1":    {"cost": (0.0, 0.0),    "resale": False, "reasoning": False},
    "openai/whisper":                 {"cost": (0.0, 0.0),    "resale": True,  "reasoning": False},
    "suno/suno":                      {"cost": (0.0, 0.0),    "resale": True,  "reasoning": False},
    # local models (Ollama) — default for the open-source free tier. cost 0, resale n/a.
    "ollama/llama3.1:8b":             {"cost": (0.0, 0.0),    "resale": True,  "reasoning": False, "local": True},
    "ollama/qwen2.5:7b":              {"cost": (0.0, 0.0),    "resale": True,  "reasoning": False, "local": True},
}

# routing_rules — (intent, mode) -> priority-ordered model list (by fallback_order)
# index [0] is the primary. The cloud tier loads the same table from the DB.
ROUTING: dict[str, dict[str, list[str]]] = {
    "text.chat_writing": {
        "balanced": ["openai/gpt-5.5", "anthropic/claude-sonnet-4-6", "google/gemini-3.1-pro-preview"],
        "eco":      ["google/gemini-2.5-flash", "openai/gpt-5.5-nano"],
        "quality":  ["anthropic/claude-opus-4-8", "openai/gpt-5.5"],
    },
    "text.reasoning": {
        "balanced": ["anthropic/claude-opus-4-8", "openai/gpt-5.5", "google/gemini-3.1-pro-preview"],
        "eco":      ["google/gemini-3.1-pro-preview", "anthropic/claude-haiku-4-5"],
        "quality":  ["anthropic/claude-opus-4-8", "openai/gpt-5.5"],
    },
    "text.coding": {
        "balanced": ["anthropic/claude-opus-4-8", "openai/gpt-5.5", "anthropic/claude-sonnet-4-6"],
        "eco":      ["anthropic/claude-haiku-4-5", "google/gemini-2.5-flash"],
        "quality":  ["anthropic/claude-opus-4-8", "openai/gpt-5.5"],
    },
    "text.translation": {
        "balanced": ["google/gemini-3.1-pro-preview", "openai/gpt-5.5"],
        "eco":      ["google/gemini-2.5-flash"],
        "quality":  ["anthropic/claude-opus-4-8", "google/gemini-3.1-pro-preview"],
    },
    "text.search_realtime": {
        "balanced": ["openai/gpt-5.5", "google/gemini-3.1-pro-preview"],
        "eco":      ["google/gemini-2.5-flash"],
        "quality":  ["openai/gpt-5.5", "google/gemini-3.1-pro-preview"],
    },
    "text.agent": {
        "balanced": ["anthropic/claude-opus-4-8", "openai/gpt-5.5", "google/gemini-3.1-pro-preview"],
        "eco":      ["anthropic/claude-sonnet-4-6"],
        "quality":  ["anthropic/claude-opus-4-8", "openai/gpt-5.5"],
    },
    "visual.image_gen": {
        "balanced": ["openai/gpt-image-2", "google/nano-banana-2"],
        "eco":      ["openai/gpt-image-2-mini", "google/nano-banana-2"],
        "quality":  ["openai/gpt-image-2", "google/nano-banana-2"],
    },
    "visual.image_edit": {
        "balanced": ["google/nano-banana-2", "openai/gpt-image-2"],
        "eco":      ["google/nano-banana-2"],
        "quality":  ["openai/gpt-image-2", "google/nano-banana-2"],
    },
    "visual.video": {
        "balanced": ["google/veo-3", "kuaishou/kling", "openai/sora-2"],
        "eco":      ["kuaishou/kling"],
        "quality":  ["google/veo-3", "kuaishou/kling"],
    },
    "visual.image_ocr": {
        "balanced": ["google/gemini-3.1-pro-preview", "openai/gpt-5.5", "anthropic/claude-opus-4-8"],
        "eco":      ["google/gemini-2.5-flash"],
        "quality":  ["google/gemini-3.1-pro-preview", "openai/gpt-5.5"],
    },
    "audio.tts": {
        "balanced": ["elevenlabs/elevenlabs-tts", "fishaudio/fish-s2-pro"],
        "eco":      ["fishaudio/fish-s2-pro"],
        "quality":  ["elevenlabs/elevenlabs-tts"],
    },
    "audio.stt": {
        "balanced": ["elevenlabs/elevenlabs-scribe-stt", "openai/whisper", "fishaudio/fish-transcribe-1"],
        "eco":      ["openai/whisper"],
        "quality":  ["elevenlabs/elevenlabs-scribe-stt", "openai/whisper"],
    },
    "audio.music": {
        "balanced": ["suno/suno"],
        "eco":      ["suno/suno"],
        "quality":  ["suno/suno"],
    },
}

# Local (open-source) tier fallback models usable without any cloud key
LOCAL_FALLBACK: dict[str, str] = {
    "text": "ollama/llama3.1:8b",
}


def resale_blocked() -> list[str]:
    """Models blocked by resale terms (from a SaaS-resale standpoint)."""
    return [k for k, v in MODELS.items() if not v.get("resale", True)]
