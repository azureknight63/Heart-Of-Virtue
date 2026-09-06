"""
Catalogue guard: every provider default must be a model the provider serves.

    HOV_LIVE_LLM=1 python -m pytest tests/integration/test_provider_catalogue.py -v

This exists because of a silent, total failure. Groq and Cerebras were
configured with `default_model` values (`llama-3.3-70b-versatile`,
`llama-3.3-70b`) that both providers had since retired. Every call to either
returned 404, the chain fell through to OpenRouter, and the live NPC chat
suite reported 46/47 passing -- while two of the three providers were serving
nothing at all. Fallthrough is the feature that hid the bug.

Unlike the rest of tests/integration/, these tests spend no LLM tokens: a
model catalogue is a plain authenticated GET. That makes this cheap enough to
run whenever a provider is added or a default is changed, and it fails loudly
the next time a vendor retires a model out from under us.

Status codes worth telling apart when this fails (all three look like "the
provider is broken" from the call site):
    401 -- the API key is wrong or revoked
    402 -- the account has no usable quota (billing not set up)
    404 -- the *model* does not exist; the key is fine
"""

import os

import pytest

from ai.llm_client import _OPENAI_COMPATIBLE_PROVIDERS


# Opt-in gate. Duplicated from conftest for the reason given in
# test_npc_chat_live.py: tests/integration has no __init__.py, so a relative
# import fails at collection.
def _live_llm_enabled() -> bool:
    return os.getenv("HOV_LIVE_LLM", "0") in ("1", "true", "True")


pytestmark = pytest.mark.skipif(
    not _live_llm_enabled(),
    reason="set HOV_LIVE_LLM=1 to run live provider catalogue checks",
)

# Providers carrying a default_model. OpenRouter is excluded by construction:
# it picks a model per call from its own ranked catalogue, so it has no single
# default to verify (see the comment on _OPENAI_COMPATIBLE_PROVIDERS).
_WITH_DEFAULTS = sorted(
    name for name, cfg in _OPENAI_COMPATIBLE_PROVIDERS.items() if cfg.get("default_model")
)


def _catalogue_url(chat_url):
    """Every provider here is OpenAI-compatible: /chat/completions -> /models."""
    return chat_url.replace("/chat/completions", "/models")


def _effective_model(cfg):
    """The slug calls will actually carry.

    `_call_openai_compatible` prefers the `model_env` override, and this repo's
    own `.env` sets both `GROQ_MODEL` and `CEREBRAS_MODEL` — so checking only
    `default_model` would pass while every real call 404'd on a retired slug
    pinned in the environment. Returns (slug, source) for the failure message.
    """
    override = os.getenv(cfg["model_env"], "").strip()
    if override:
        return override, cfg["model_env"]
    return cfg["default_model"], "default_model"


@pytest.mark.parametrize("provider", _WITH_DEFAULTS)
def test_configured_model_is_in_the_provider_catalogue(provider):
    import requests

    cfg = _OPENAI_COMPATIBLE_PROVIDERS[provider]
    key = os.getenv(cfg["key_env"], "").strip()
    if not key:
        pytest.skip("%s not configured (%s unset)" % (provider, cfg["key_env"]))

    response = requests.get(
        _catalogue_url(cfg["url"]),
        headers={"Authorization": "Bearer %s" % key},
        timeout=20,
    )
    # 401/402 are account problems, not model problems: the credential is
    # wrong or the account has no quota (Cerebras answers every request this
    # way until billing is set up). Neither tells us anything about whether
    # the configured slug exists, so skip rather than report a false verdict.
    if response.status_code in (401, 402):
        pytest.skip(
            "%s cannot be queried: %s %s"
            % (provider, response.status_code, response.text[:120])
        )
    assert response.status_code == 200, "%s catalogue lookup failed: %s %s" % (
        provider,
        response.status_code,
        response.text[:200],
    )

    model, source = _effective_model(cfg)
    served = {entry.get("id") for entry in response.json().get("data", [])}
    assert model in served, (
        "%s %s is %r, which is not in its catalogue -- every call will 404 and "
        "fall through to the next provider. Currently served: %s"
        % (provider, source, model, ", ".join(sorted(served)) or "(none)")
    )
