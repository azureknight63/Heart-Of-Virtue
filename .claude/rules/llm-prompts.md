---
paths:
  - "ai/**"
  - "src/npc/_chat_llm.py"
  - "src/npc/_llm.py"
  - "tools/measure_llm_tokens.py"
  - "tests/integration/**"
---

# LLM and prompt rules

## Prompts are a metered resource
- Free tiers meter **tokens, not requests**, and count prompt + completion together: Cerebras ~1M/day in an 8k window, Groq ~6k/minute, OpenRouter 20 RPM + 50/day (1000 above $10 lifetime credit).
- `python tools/measure_llm_tokens.py [--outputs] [--dump]` drives the real prompt builders and prints per-call token cost. Re-run it after editing any prompt. Aug 2026: combat TA ~1,322 in / ~180 out, NPC chat round ~1,279 in / ~160 out; corpus averages 4.0 chars/token.
- System prompts and instruction tails are static and re-sent on **every** call, so prose there is paid for once per beat forever. Prefer terse field-per-line over explanatory paragraphs.

## Editing a prompt is a behaviour change
- Never edit a prompt on unit tests alone. Run the live A/B: baseline green → edit → same suites green (`HOV_LIVE_LLM=1 python -m pytest tests/integration/ -q`). Free models are flaky, so confirm any failure 3× on each side before believing it.
- Compression removes *restatement*, not rules. A pass that cut the TA HEAT band table as "redundant with the inline label" made the model answer `Rest` for a healthy player at heat 1.0 — nothing described the neutral band. Reproduced 3/3 trimmed, 0/3 restored. Keep every default-case clause.

## Provider gotchas (`ai/llm_client.py`)
- **`_free_models_cache` fallback does not survive a quota wall.** OpenRouter's free limit is per *account*, globally — every `:free` model and `openrouter/free` share one bucket, so a 429 kills the whole candidate list at once.
- `reasoning: {"effort": "none"}` is rejected with HTTP 400 (`"Reasoning is mandatory for this endpoint"`) by part of the free catalogue. `"low"` is the safe floor; `exclude: true` only hides chain-of-thought, it does **not** save tokens. `_post_chat_completion` retries once with the block stripped.
- Reasoning tokens are billed as *completion* tokens and spend the same `max_tokens`. Budget ~4–5× the real answer, or a reasoning model returns empty and trips the `"empty after stripping thinking tokens"` warning.
