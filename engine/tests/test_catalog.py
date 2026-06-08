"""Catalog integrity — guards the seed data against drift."""
from app import catalog


def test_thirteen_intents():
    assert len(catalog.INTENTS) == 13


def test_every_routed_model_exists_in_catalog():
    for intent, modes in catalog.ROUTING.items():
        for mode, models in modes.items():
            for m in models:
                assert m in catalog.MODELS, f"{intent}/{mode}: unknown model {m}"


def test_every_intent_has_all_three_modes():
    for intent in catalog.INTENTS:
        assert intent in catalog.ROUTING, f"no routing rules for {intent}"
        for mode in ("eco", "balanced", "quality"):
            assert catalog.ROUTING[intent].get(mode), f"{intent} missing {mode} rules"


def test_routing_intents_are_known():
    for intent in catalog.ROUTING:
        assert intent in catalog.INTENTS, f"routing references unknown intent {intent}"


def test_resale_blocked_set():
    assert set(catalog.resale_blocked()) == {
        "elevenlabs/elevenlabs-tts",
        "elevenlabs/elevenlabs-scribe-stt",
        "elevenlabs/elevenlabs-music",
        "fishaudio/fish-s2-pro",
        "fishaudio/fish-transcribe-1",
    }


def test_elevenlabs_music_never_resellable():
    # hard blocker — must stay false until an Authorized Reseller agreement
    assert catalog.MODELS["elevenlabs/elevenlabs-music"]["resale"] is False


def test_text_models_priced_per_token():
    # cost tuple present for every model
    for key, meta in catalog.MODELS.items():
        assert isinstance(meta["cost"], tuple) and len(meta["cost"]) == 2, key
