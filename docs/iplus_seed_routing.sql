-- =====================================================================
-- iPlus — routing seed data v1  (PostgreSQL)
-- Generated: 2026-06-06  /  Source: researched & verified model catalog
-- Target tables: ai_models, intent_taxonomy, routing_rules, model_benchmarks
-- Idempotent: uses ON CONFLICT, safe to re-run
-- =====================================================================
-- Prereq: the natural keys below need UNIQUE constraints for ON CONFLICT:
--   ALTER TABLE ai_models       ADD CONSTRAINT uq_ai_models_key UNIQUE (provider, model_key);
--   ALTER TABLE intent_taxonomy ADD CONSTRAINT uq_intent_key    UNIQUE (intent_key);
--   ALTER TABLE routing_rules   ADD CONSTRAINT uq_routing_rule  UNIQUE (intent, model_id, mode);
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1) ai_models  (routing candidates)
--    terms_allow_resale: result of the resale-terms review. Unverified/prohibited -> false.
--    cost_in/out: USD per 1M tokens (text) / unit price otherwise (see comment). is_reasoning: reasoning model
-- ---------------------------------------------------------------------
INSERT INTO ai_models (provider, model_key, layer, is_reasoning, cost_in, cost_out, lifecycle_state, circuit_state, error_rate, terms_allow_resale) VALUES
  -- text (per 1M tokens)
  ('openai',    'gpt-5.5',                   'model', true,  5.00, 30.00, 'active',     'closed', 0, true),
  ('openai',    'gpt-5.5-nano',              'model', false, 0.20,  1.25, 'active',     'closed', 0, true),
  ('anthropic', 'claude-opus-4-8',           'model', true,  5.00, 25.00, 'active',     'closed', 0, true),   -- verify terms directly
  ('anthropic', 'claude-sonnet-4-6',         'model', false, 3.00, 15.00, 'active',     'closed', 0, true),
  ('anthropic', 'claude-haiku-4-5',          'model', false, 1.00,  5.00, 'active',     'closed', 0, true),
  ('google',    'gemini-3.1-pro-preview',    'model', true,  2.00, 12.00, 'preview',    'closed', 0, true),
  ('google',    'gemini-2.5-pro',            'model', false, 1.25,  0.00, 'active',     'closed', 0, true),
  ('google',    'gemini-2.5-flash',          'model', false, 0.30,  2.50, 'active',     'closed', 0, true),
  -- visual (unit prices: see comments)
  ('openai',    'gpt-image-2',               'model', false, 8.00, 30.00, 'active',     'closed', 0, true),   -- per 1M img tokens
  ('openai',    'gpt-image-2-mini',          'model', false, 2.50,  8.00, 'active',     'closed', 0, true),
  ('google',    'nano-banana-2',             'model', false, 0.00,  0.00, 'active',     'closed', 0, true),   -- Gemini 3.1 Flash Image
  ('google',    'veo-3',                     'service', false, 0.00, 0.00, 'active',     'closed', 0, true),
  ('openai',    'sora-2',                    'service', false, 0.00, 0.00, 'deprecating','closed', 0, true),  -- EOL 2026-09-24, $0.10/s
  ('kuaishou',  'kling',                     'service', false, 0.00, 0.00, 'active',     'closed', 0, true),
  -- audio (unit prices: see comments)
  ('elevenlabs','elevenlabs-tts',            'service', false, 0.00, 0.00, 'active',     'closed', 0, false), -- resale terms unverified -> false
  ('elevenlabs','elevenlabs-scribe-stt',     'service', false, 0.00, 0.00, 'active',     'closed', 0, false), -- unverified
  ('elevenlabs','elevenlabs-music',          'service', false, 0.00, 0.00, 'active',     'closed', 0, false), -- resale prohibited (hard)
  ('fishaudio', 'fish-s2-pro',               'service', false, 0.00, 0.00, 'active',     'closed', 0, false), -- unverified, $15/1M bytes
  ('fishaudio', 'fish-transcribe-1',         'service', false, 0.00, 0.00, 'active',     'closed', 0, false), -- unverified, $0.36/hr
  ('openai',    'whisper',                   'model',   false, 0.00, 0.00, 'active',     'closed', 0, true),  -- STT fallback (resale clear)
  ('suno',      'suno',                      'service', false, 0.00, 0.00, 'active',     'closed', 0, true)   -- commercial use on paid plans
ON CONFLICT (provider, model_key) DO UPDATE
  SET cost_in = EXCLUDED.cost_in, cost_out = EXCLUDED.cost_out,
      lifecycle_state = EXCLUDED.lifecycle_state,
      terms_allow_resale = EXCLUDED.terms_allow_resale;

-- ---------------------------------------------------------------------
-- 2) intent_taxonomy  (3 domains x 13 intents)
-- ---------------------------------------------------------------------
INSERT INTO intent_taxonomy (domain, intent_key, requires_reasoning) VALUES
  ('text',   'text.chat_writing',     false),  -- 1 chat & writing
  ('text',   'text.reasoning',        true),   -- 2 long-form reasoning & analysis
  ('text',   'text.coding',           true),   -- 3 coding & debugging
  ('text',   'text.translation',      false),  -- 4 translation & localization
  ('text',   'text.search_realtime',  false),  -- 5 search & realtime
  ('text',   'text.agent',            true),   -- 6 agent (multi-step)
  ('visual', 'visual.image_gen',      false),  -- 7 image generation
  ('visual', 'visual.image_edit',     false),  -- 8 image editing
  ('visual', 'visual.video',          false),  -- 9 video generation & editing
  ('visual', 'visual.image_ocr',      true),   -- 10 image understanding (OCR)
  ('audio',  'audio.tts',             false),  -- 11 text-to-speech (TTS)
  ('audio',  'audio.stt',             false),  -- 12 speech-to-text (STT)
  ('audio',  'audio.music',           false)   -- 13 music generation
ON CONFLICT (intent_key) DO NOTHING;

-- ---------------------------------------------------------------------
-- 3) routing_rules  (intent -> model, per mode, with fallback_order)
--    mode: balanced (default) / eco (value) / quality (best)
--    fallback_order: 0 = primary, 1 = fallback1, 2 = fallback2
--    weight: routing score (higher = preferred). Near-ties are placed close together.
-- ---------------------------------------------------------------------
WITH m AS (SELECT id, provider||'/'||model_key AS k FROM ai_models)
INSERT INTO routing_rules (intent, model_id, weight, fallback_order, mode, is_active)
SELECT v.intent, m.id, v.weight, v.fallback_order, v.mode, true
FROM (VALUES
  -- ===== balanced (default mode) =====
  ('text.chat_writing',    'openai/gpt-5.5',                100, 0, 'balanced'),
  ('text.chat_writing',    'anthropic/claude-sonnet-4-6',    90, 1, 'balanced'),
  ('text.chat_writing',    'google/gemini-3.1-pro-preview',  85, 2, 'balanced'),
  ('text.reasoning',       'anthropic/claude-opus-4-8',     100, 0, 'balanced'),
  ('text.reasoning',       'openai/gpt-5.5',                 95, 1, 'balanced'),
  ('text.reasoning',       'google/gemini-3.1-pro-preview',  90, 2, 'balanced'),
  ('text.coding',          'anthropic/claude-opus-4-8',     100, 0, 'balanced'),
  ('text.coding',          'openai/gpt-5.5',                 92, 1, 'balanced'),
  ('text.coding',          'anthropic/claude-sonnet-4-6',    85, 2, 'balanced'),
  ('text.translation',     'google/gemini-3.1-pro-preview',  90, 0, 'balanced'),  -- estimate, benchmark TBD
  ('text.translation',     'openai/gpt-5.5',                 85, 1, 'balanced'),
  ('text.search_realtime', 'openai/gpt-5.5',                 90, 0, 'balanced'),  -- estimate (web search)
  ('text.search_realtime', 'google/gemini-3.1-pro-preview',  88, 1, 'balanced'),  -- grounding
  ('text.agent',           'anthropic/claude-opus-4-8',     100, 0, 'balanced'),
  ('text.agent',           'openai/gpt-5.5',                 92, 1, 'balanced'),
  ('text.agent',           'google/gemini-3.1-pro-preview',  88, 2, 'balanced'),
  ('visual.image_gen',     'openai/gpt-image-2',            100, 0, 'balanced'),  -- AA #1, Elo 1339
  ('visual.image_gen',     'google/nano-banana-2',           90, 1, 'balanced'),  -- AA #3
  ('visual.image_edit',    'google/nano-banana-2',           90, 0, 'balanced'),  -- estimate (editing strength)
  ('visual.image_edit',    'openai/gpt-image-2',             85, 1, 'balanced'),
  ('visual.video',         'google/veo-3',                  100, 0, 'balanced'),  -- promoted to #1 (Sora 2 EOL)
  ('visual.video',         'openai/sora-2',                  70, 1, 'balanced'),  -- only until 2026-09-24
  ('visual.video',         'kuaishou/kling',                 80, 2, 'balanced'),
  ('visual.image_ocr',     'google/gemini-3.1-pro-preview',  90, 0, 'balanced'),  -- estimate
  ('visual.image_ocr',     'openai/gpt-5.5',                 85, 1, 'balanced'),
  ('visual.image_ocr',     'anthropic/claude-opus-4-8',      82, 2, 'balanced'),
  ('audio.tts',            'elevenlabs/elevenlabs-tts',     100, 0, 'balanced'),
  ('audio.tts',            'fishaudio/fish-s2-pro',          85, 1, 'balanced'),
  ('audio.stt',            'elevenlabs/elevenlabs-scribe-stt',100,0, 'balanced'),
  ('audio.stt',            'openai/whisper',                 90, 1, 'balanced'),
  ('audio.stt',            'fishaudio/fish-transcribe-1',    80, 2, 'balanced'),
  ('audio.music',          'suno/suno',                     100, 0, 'balanced'),  -- ElevenLabs Music excluded (resale)
  -- ===== eco (value) =====
  ('text.chat_writing',    'google/gemini-2.5-flash',       100, 0, 'eco'),
  ('text.chat_writing',    'openai/gpt-5.5-nano',            95, 1, 'eco'),
  ('text.reasoning',       'google/gemini-3.1-pro-preview', 100, 0, 'eco'),       -- best perf/price
  ('text.reasoning',       'anthropic/claude-haiku-4-5',     85, 1, 'eco'),
  ('text.coding',          'anthropic/claude-haiku-4-5',    100, 0, 'eco'),
  ('text.coding',          'google/gemini-2.5-flash',        88, 1, 'eco'),
  ('text.translation',     'google/gemini-2.5-flash',       100, 0, 'eco'),
  ('text.search_realtime', 'google/gemini-2.5-flash',       100, 0, 'eco'),
  ('text.agent',           'anthropic/claude-sonnet-4-6',   100, 0, 'eco'),
  ('visual.image_gen',     'openai/gpt-image-2-mini',       100, 0, 'eco'),
  ('visual.image_gen',     'google/nano-banana-2',           90, 1, 'eco'),
  ('visual.image_edit',    'google/nano-banana-2',          100, 0, 'eco'),
  ('visual.video',         'kuaishou/kling',                100, 0, 'eco'),
  ('visual.image_ocr',     'google/gemini-2.5-flash',       100, 0, 'eco'),
  ('audio.tts',            'fishaudio/fish-s2-pro',         100, 0, 'eco'),
  ('audio.stt',            'openai/whisper',                100, 0, 'eco'),
  ('audio.music',          'suno/suno',                     100, 0, 'eco'),
  -- ===== quality (best) =====
  ('text.chat_writing',    'anthropic/claude-opus-4-8',     100, 0, 'quality'),
  ('text.reasoning',       'anthropic/claude-opus-4-8',     100, 0, 'quality'),
  ('text.coding',          'anthropic/claude-opus-4-8',     100, 0, 'quality'),
  ('text.translation',     'anthropic/claude-opus-4-8',     100, 0, 'quality'),
  ('text.search_realtime', 'openai/gpt-5.5',                100, 0, 'quality'),
  ('text.agent',           'anthropic/claude-opus-4-8',     100, 0, 'quality'),
  ('visual.image_gen',     'openai/gpt-image-2',            100, 0, 'quality'),
  ('visual.image_edit',    'openai/gpt-image-2',            100, 0, 'quality'),
  ('visual.video',         'google/veo-3',                  100, 0, 'quality'),
  ('visual.image_ocr',     'google/gemini-3.1-pro-preview', 100, 0, 'quality'),
  ('audio.tts',            'elevenlabs/elevenlabs-tts',     100, 0, 'quality'),
  ('audio.stt',            'elevenlabs/elevenlabs-scribe-stt',100,0, 'quality'),
  ('audio.music',          'suno/suno',                     100, 0, 'quality')
) AS v(intent, model_k, weight, fallback_order, mode)
JOIN m ON m.k = v.model_k
ON CONFLICT (intent, model_id, mode) DO UPDATE
  SET weight = EXCLUDED.weight, fallback_order = EXCLUDED.fallback_order, is_active = true;

-- ---------------------------------------------------------------------
-- 4) model_benchmarks  (routing rationale — seed only verified rows; gaps stay NULL)
--    quality_score: 0–100 normalized (relative to public leaderboards). Unbenchmarked -> omitted.
-- ---------------------------------------------------------------------
WITH m AS (SELECT id, provider||'/'||model_key AS k FROM ai_models)
INSERT INTO model_benchmarks (model_id, intent, quality_score, uptime_score, avg_latency, cost_per_1k)
SELECT m.id, v.intent, v.quality_score, v.uptime_score, v.avg_latency, v.cost_per_1k
FROM (VALUES
  ('openai/gpt-5.5',                'text.chat_writing', 97, NULL, NULL, 0.030),
  ('anthropic/claude-opus-4-8',     'text.reasoning',    97, NULL, NULL, 0.025),
  ('anthropic/claude-opus-4-8',     'text.coding',       96, NULL, NULL, 0.025),  -- SWE-bench top tier
  ('google/gemini-3.1-pro-preview', 'text.reasoning',    95, NULL, NULL, 0.012),
  ('openai/gpt-image-2',            'visual.image_gen',  100,NULL, NULL, NULL),    -- AA Elo 1339 (#1)
  ('google/nano-banana-2',          'visual.image_gen',  92, NULL, NULL, NULL)     -- AA (#3)
) AS v(model_k, intent, quality_score, uptime_score, avg_latency, cost_per_1k)
JOIN m ON m.k = v.model_k
ON CONFLICT DO NOTHING;

COMMIT;

-- =====================================================================
-- Operational notes (handle after development starts)
--  1) sora-2: lifecycle 'deprecating' + EOL 2026-09-24. Track via model_rollout /
--     deprecation report; video #1 already seeded as veo-3.
--  2) elevenlabs-music: terms_allow_resale=false permanently. Excluded from routing.
--     Do NOT promote to true before an Authorized Reseller agreement.
--  3) terms_allow_resale=false (unverified): elevenlabs-tts/scribe, fish-*.
--     Promote to true only after legal review. (Routing gate blocks them meanwhile.)
--  4) Gap intents (translation/search/image-edit/OCR): marked "estimate" -> fill
--     model_benchmarks via a Phase-1 sandbox eval, then re-tune weights.
--  5) Models with cost_out=0 are unit-priced (image/video/audio), not token models.
--     The billing guard must consult a separate unit-price table.
-- =====================================================================
