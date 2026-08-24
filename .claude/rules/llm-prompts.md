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
- The live NPC chat suite costs ~40 of OpenRouter's 50 free requests/day, so it realistically runs **once a day**. Check `X-RateLimit-Remaining` before starting one, and share live calls through module-scoped fixtures rather than per-test.

## Editing a prompt is a behaviour change
- Never edit a prompt on unit tests alone. Run the live A/B: baseline green → edit → same suites green (`HOV_LIVE_LLM=1 python -m pytest tests/integration/ -q`). Free models are flaky, so confirm any failure 3× on each side before believing it.
- Compression removes *restatement*, not rules. A pass that cut the TA HEAT band table as "redundant with the inline label" made the model answer `Rest` for a healthy player at heat 1.0 — nothing described the neutral band. Reproduced 3/3 trimmed, 0/3 restored. Keep every default-case clause.

## Provider gotchas (`ai/llm_client.py`)
- **Two different 429s, two different meanings.** A per-minute limit is transient and the rotation loop absorbs it (2-minute bench, next candidate serves). The daily cap is not: `X-RateLimit-Remaining: 0` plus `"free-models-per-day"` in the body means every `:free` model *and* `openrouter/free` are dead until 00:00 UTC, because the bucket is per *account*. Never read a bare "429" as either — check the header.
- **`/api/v1/key` cannot see the free-tier request cap.** It reports dollar credit (`usage: 0, limit: null, is_free_tier: true`) and free models cost $0, so it reads clean with the 50/day fully spent. Response headers are the only signal — which is why saturation is recorded per call, not polled.
- **A pinned `MYNX_LLM_MODEL`/`NPC_CHAT_LLM_MODEL` bypasses ranking entirely** — `_get_openrouter_model` returns a pin verbatim, so the capability filter and reasoning-burden ordering never run. Check `.env` before blaming model selection.
- **Ranking filters on `supported_parameters`**: a model advertising neither `response_format` nor `structured_outputs` is dropped, since every caller here parses JSON. Untagged chain-of-thought ("Here's a thinking process:") cannot be stripped — `_strip_thinking_tokens` only handles `<think>` tags — so capability filtering is the fix, not more stripping.
- `STABLE_FREE_FALLBACKS` are all retired slugs (404 on every one). `openrouter/free` is what actually catches a rotation.
- `_JSONTools` parses with `object_pairs_hook=_keep_first_duplicate`. Models emit a good object then append a degenerate afterthought, and `json.loads` keeps the *last* duplicate — removing the hook silently empties `jean_options` with no warning.
- `reasoning: {"effort": "none"}` is rejected with HTTP 400 (`"Reasoning is mandatory for this endpoint"`) by part of the free catalogue. `"low"` is the safe floor; `exclude: true` only hides chain-of-thought, it does **not** save tokens. `_post_chat_completion` retries once with the block stripped.
- Reasoning tokens are billed as *completion* tokens and spend the same `max_tokens`. Budget ~4–5× the real answer, or a reasoning model returns empty and trips the `"empty after stripping thinking tokens"` warning.
