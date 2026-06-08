"""Tests for L0-L3 classification and mode-aware routing (the core IP)."""
from app.router import classify, route


# ---- classification (bilingual) -----------------------------------------
def test_classify_coding_english():
    c = classify("debug this python error stack trace")
    assert c.intent == "text.coding"
    assert c.requires_reasoning is True


def test_classify_coding_korean():
    assert classify("이 코드 디버그").intent == "text.coding"


def test_classify_image_english_and_korean():
    assert classify("draw a cat image").domain == "visual"
    assert classify("고양이 이미지 그려줘").domain == "visual"


def test_classify_audio_music():
    assert classify("compose background music").intent == "audio.music"


def test_classify_defaults_to_chat_writing():
    c = classify("hello there, how are you")
    assert c.domain == "text"
    assert c.intent == "text.chat_writing"


# ---- mode-aware routing -------------------------------------------------
def test_quality_mode_prefers_opus_for_coding():
    assert route("text.coding", "quality").model == "anthropic/claude-opus-4-8"


def test_eco_mode_prefers_cheaper_model():
    # eco coding -> haiku (cheapest reasoning-capable in the eco list)
    assert route("text.coding", "eco").model == "anthropic/claude-haiku-4-5"


def test_invalid_mode_falls_back_to_balanced():
    assert route("text.coding", "nonsense").model == route("text.coding", "balanced").model


# ---- resale-terms gate (business-critical) ------------------------------
def test_tts_all_blocked_by_resale_returns_no_model():
    d = route("audio.tts", "balanced", require_resale=True)
    assert d.model is None
    assert "resale" in d.note


def test_stt_skips_blocked_and_picks_whisper():
    # elevenlabs + fish are resale-blocked; whisper is allowed
    assert route("audio.stt", "balanced", require_resale=True).model == "openai/whisper"


def test_resale_disabled_allows_blocked_model():
    assert route("audio.tts", "balanced", require_resale=False).model == "elevenlabs/elevenlabs-tts"


# ---- local fallback (open-source tier) ----------------------------------
def test_no_keys_falls_back_to_local_ollama():
    d = route("text.chat_writing", "balanced", allow_keys=set())
    assert d.model == "ollama/llama3.1:8b"
    assert d.local_only is True


def test_with_key_picks_cloud_model():
    d = route("text.chat_writing", "balanced", allow_keys={"openai"})
    assert d.model == "openai/gpt-5.5"
