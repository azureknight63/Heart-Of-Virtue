---
paths:
  - "ai/**"
  - "src/npc/_chat_llm.py"
  - "src/npc/_llm.py"
  - "src/npc/_chat_guard.py"
  - "tools/measure_llm_tokens.py"
  - "tests/integration/**"
---

# LLM and prompt rules

## Prompts are a metered resource
- Free tiers meter **tokens, not requests**, and count prompt + completion together: Groq ~6k/minute, OpenRouter 20 RPM + 50/day (1000 above $10 lifetime credit). Cerebras publishes ~1M/day in an 8k window but **a bare free account cannot reach it** — every call returns `402 payment_required` (`param: quota`) until billing is set up on the dashboard, for every model. Treat Cerebras as unconfigured until someone confirms otherwise.
- Aug 2026 measurement: the full live NPC chat suite is ~35s and 47 tests against Groq. It was ~180s against OpenRouter, so a provider swap changes what "run the live suite" costs you in wall time by 5×.
- `python tools/measure_llm_tokens.py [--outputs] [--dump]` drives the real prompt builders and prints per-call token cost. Re-run it after editing any prompt. Aug 2026: combat TA ~1,322 in / ~180 out, NPC chat round ~1,279 in / ~160 out; corpus averages 4.0 chars/token.
- System prompts and instruction tails are static and re-sent on **every** call, so prose there is paid for once per beat forever. Prefer terse field-per-line over explanatory paragraphs.
- The live NPC chat suite costs ~40 of OpenRouter's 50 free requests/day, so it realistically runs **once a day**. Check `X-RateLimit-Remaining` before starting one, and share live calls through module-scoped fixtures rather than per-test.

## Editing a prompt is a behaviour change
- Never edit a prompt on unit tests alone. Run the live A/B: baseline green → edit → same suites green (`HOV_LIVE_LLM=1 python -m pytest tests/integration/ -q`). Free models are flaky, so confirm any failure 3× on each side before believing it.
- Compression removes *restatement*, not rules. A pass that cut the TA HEAT band table as "redundant with the inline label" made the model answer `Rest` for a healthy player at heat 1.0 — nothing described the neutral band. Reproduced 3/3 trimmed, 0/3 restored. Keep every default-case clause.

## Provider gotchas (`ai/llm_client.py`)
- **The fallback chain hides a dead provider, and the live suite will not tell you.** Aug 2026: Groq and Cerebras were both configured with `default_model` slugs their vendors had retired. Every call 404'd, OpenRouter silently served all of them, and `test_npc_chat_live.py` reported **46/47 passing** while two of three providers served nothing. Green is not evidence a provider works — check *who answered* in the logs (`provider=<name> result_chars=`), or pin one with `HOV_LIVE_ONLY`.
- **`HOV_LIVE_ONLY=<provider>` runs the live suite against that provider alone** (`tests/integration/conftest.py`), blanking every other credential so nothing can fall through and mask a failure. Needed because the `live_env` fixture restores all of `_LIVE_KEYS` from `.env` unconditionally — a command-line `GROQ_API_KEY= pytest …` is silently refilled.
- **Three failures look identical from the call site; the status code is the whole diagnosis.** `401` = key wrong or revoked. `402` = account has no usable quota (billing). `404` = the *model* doesn't exist and the key is fine. Only 404 is fixed by editing config.
- **Vendors retire model slugs without warning** — Groq dropped every Llama between Aug 23 and Aug 26 2026, and gained a Qwen in the same window. `HOV_LIVE_LLM=1 pytest tests/integration/test_provider_catalogue.py` checks each `default_model` against the provider's live catalogue; it spends no LLM tokens (a catalogue is a plain GET) and takes ~2s. Run it when a provider stops answering, before touching anything else.
- **Two different 429s, two different meanings.** A per-minute limit is transient and the rotation loop absorbs it (2-minute bench, next candidate serves). The daily cap is not: `X-RateLimit-Remaining: 0` plus `"free-models-per-day"` in the body means every `:free` model *and* `openrouter/free` are dead until 00:00 UTC, because the bucket is per *account*. Never read a bare "429" as either — check the header.
- **`/api/v1/key` cannot see the free-tier request cap.** It reports dollar credit (`usage: 0, limit: null, is_free_tier: true`) and free models cost $0, so it reads clean with the 50/day fully spent. Response headers are the only signal — which is why saturation is recorded per call, not polled.
- **A pinned `MYNX_LLM_MODEL`/`NPC_CHAT_LLM_MODEL` bypasses ranking entirely** — `_get_openrouter_model` returns a pin verbatim, so the capability filter and reasoning-burden ordering never run. Check `.env` before blaming model selection.
- **Ranking filters on `supported_parameters`**: a model advertising neither `response_format` nor `structured_outputs` is dropped, since every caller here parses JSON. Untagged chain-of-thought ("Here's a thinking process:") cannot be stripped — `_strip_thinking_tokens` (`ai/llm_text.py`) only handles `<think>` tags — so capability filtering is the fix, not more stripping.
- `STABLE_FREE_FALLBACKS` are all retired slugs (404 on every one). `openrouter/free` is what actually catches a rotation.
- `_JSONTools` (in `ai/llm_text.py`, not `llm_client.py` -- it moved with the rest of the stateless text/JSON munging) parses with `object_pairs_hook=_keep_first_duplicate`. Models emit a good object then append a degenerate afterthought, and `json.loads` keeps the *last* duplicate — removing the hook silently empties `jean_options` with no warning.
- `reasoning: {"effort": "none"}` is rejected with HTTP 400 (`"Reasoning is mandatory for this endpoint"`) by part of the free catalogue. `"low"` is the safe floor; `exclude: true` only hides chain-of-thought, it does **not** save tokens. `_post_chat_completion` retries once with the block stripped.
- Reasoning tokens are billed as *completion* tokens and spend the same `max_tokens`. Budget ~4–5× the real answer, or a reasoning model returns empty and trips the `"empty after stripping thinking tokens"` warning.
