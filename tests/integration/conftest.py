"""Shared setup for the live-LLM integration tests.

These modules are the only ones in the suite that make real network calls to an
LLM provider. Two things stand between them and a working provider:

1. ``tests/conftest.py`` pins ``MYNX_LLM_ENABLED=0`` and
   ``MYNX_LLM_PROVIDER=none`` process-wide so the default suite can never reach
   the network. That is correct for every other test and fatal for these -- a
   live module that reads those vars sees a disabled adapter and skips itself,
   which is how ``test_tactical_advisor_live.py`` came to be permanently
   inert.
2. ``.env`` holds the real provider config, but ``load_dotenv()`` does not
   override variables already present in the environment, so the pins above win
   even when a developer has everything configured.

``live_env`` resolves both for the duration of one module and then puts the
pinned values back, so nothing downstream inherits a live provider. The
opt-in gate is ``HOV_LIVE_LLM=1`` -- deliberately a separate variable from the
ones ``.env`` sets, so that merely having a working ``.env`` never causes the
default suite to start spending free-tier quota.
"""

import os
import warnings

import pytest

from tests.llm_doubles import PROVIDER_KEY_ENVS

# Provider configuration these tests need restored from .env. The credential
# half is derived from the provider registry (see tests/llm_doubles.py): a
# provider registered but missing from this tuple would be left blanked by
# tests/conftest.py for the whole live run, so the chain would quietly serve
# every call from a different provider than the one under test.
#
# The rule for the named half: a variable belongs here if some adapter under
# test *reads* it. Each adapter declares its own gate, provider and model
# (GenericLLMClient._{ENABLED,PROVIDER,MODEL}_ENV_VARS), and every one of those
# names has to be restored or the adapter runs the live suite on a different
# configuration than the deployment does. The COMBAT_ trio was the one that
# proved it: test_tactical_advisor_live.py builds a real CombatLLMAdapter,
# whose gate is ("COMBAT_LLM_ENABLED", "MYNX_LLM_ENABLED") -- first non-empty
# wins -- so a .env carrying COMBAT_LLM_ENABLED=0 made available() False,
# _make_client() return None, and all 21 tests skip. Restoring MYNX_LLM_ENABLED
# alone could not reach that gate.
_LIVE_KEYS = (
    "MYNX_LLM_ENABLED",
    "MYNX_LLM_PROVIDER",
    "MYNX_LLM_MODEL",
    "NPC_CHAT_LLM_ENABLED",
    "NPC_CHAT_LLM_PROVIDER",
    "NPC_CHAT_LLM_MODEL",
    "NPC_CHAT_LLM_TIMEOUT",
    "COMBAT_LLM_ENABLED",
    "COMBAT_LLM_PROVIDER",
    "COMBAT_LLM_MODEL",
    "OPENROUTER_SITE",
    "OPENROUTER_SITE_TITLE",
    "OLLAMA_BASE_URL",
) + PROVIDER_KEY_ENVS


def live_llm_enabled() -> bool:
    """True when the developer has explicitly opted into live provider calls."""
    return os.getenv("HOV_LIVE_LLM", "0") in ("1", "true", "True")


def _apply_single_provider_isolation():
    """Honour ``HOV_LIVE_ONLY=<provider>``: run against that provider alone.

    The ``.env`` restore above is deliberately unconditional -- it has to beat
    the default suite's ``MYNX_LLM_ENABLED=0`` safety pins. The side effect was
    that a command-line ``GROQ_API_KEY= pytest ...`` got silently refilled from
    ``.env``, so there was no way to ask "does this one provider actually
    work?".

    That mattered more than it sounds. The fallback chain is designed to hide a
    dead provider: when Groq and Cerebras were both configured with retired
    model slugs, every call 404'd, OpenRouter quietly served all of them, and
    the live suite reported 46/47 passing. Blanking the *other* providers'
    credentials removes the safety net for one run, so a broken provider fails
    where you can see it.

        HOV_LIVE_LLM=1 HOV_LIVE_ONLY=groq python -m pytest tests/integration/...

    Every key touched here is in ``_LIVE_KEYS``, so the fixture's own finally
    block restores it -- the blanking never outlives the module.
    """
    only = os.getenv("HOV_LIVE_ONLY", "").strip().lower()
    if not only:
        return

    from ai.llm_client import _OPENAI_COMPATIBLE_PROVIDERS

    if only not in _OPENAI_COMPATIBLE_PROVIDERS:
        raise pytest.UsageError(
            "HOV_LIVE_ONLY=%r is not a known provider (choose from: %s)"
            % (only, ", ".join(sorted(_OPENAI_COMPATIBLE_PROVIDERS)))
        )

    for name, provider_cfg in _OPENAI_COMPATIBLE_PROVIDERS.items():
        if name != only:
            os.environ[provider_cfg["key_env"]] = ""
    # _provider_chain appends ollama whenever OLLAMA_BASE_URL is set, so a
    # local Ollama would quietly serve the calls this run exists to expose.
    os.environ["OLLAMA_BASE_URL"] = ""

    # Each feature is pinned through its own first-choice variable, because
    # that is the only entry the base class counts as an explicit choice.
    # MYNX_LLM_PROVIDER is deliberately left alone: it is the inherited
    # fallback for both feature adapters, so writing it here would move both of
    # them at once and would also re-point the mynx pet, which no live module
    # under this directory drives.
    os.environ["NPC_CHAT_LLM_PROVIDER"] = only
    os.environ["COMBAT_LLM_PROVIDER"] = only

    # The honest caveat, and it is a real one rather than boilerplate:
    # NpcChatLLMAdapter overrides available() and _dispatch_chat to reach the
    # whole chain by name, so chat genuinely runs against `only`. Combat uses a
    # plain GenericLLMClient, which routes ollama and openrouter and nothing
    # else -- pinned to groq or cerebras it reports "Unknown provider" and
    # test_tactical_advisor_live.py skips all 21 tests. Pinning it anyway is
    # still the better of the two: with HOV_LIVE_ONLY=openrouter it makes
    # combat run on openrouter even when .env has pointed it somewhere cheap,
    # and for the two chain-only providers the module skipped either way (on a
    # blanked OPENROUTER_API_KEY instead). What was wrong was saying nothing.
    if only != "openrouter":
        warnings.warn(
            "HOV_LIVE_ONLY=%s isolates the NPC chat chain only. Combat goes "
            "through GenericLLMClient, which can route ollama and openrouter "
            "alone, so test_tactical_advisor_live.py will skip this run. Use "
            "HOV_LIVE_ONLY=openrouter, or no isolation at all, to exercise it."
            % only,
            stacklevel=2,
        )


@pytest.fixture(scope="module", autouse=True)
def live_env():
    """Give one module the real provider config, then undo it."""
    if not live_llm_enabled():
        yield
        return

    from dotenv import dotenv_values

    cfg = dotenv_values()
    saved = {k: os.environ.get(k) for k in _LIVE_KEYS}

    # Discovery and the failed-model penalties are class-level and process-wide.
    # Clear them on the way in so a prior module's failures do not poison this
    # run, and on the way out so the live cache never reaches the default suite.
    #
    # NpcChatLLMAdapter caches a configured singleton in _instances, which
    # reset_class_state does not touch. Production reaches the adapter through
    # get_instance()/prewarm() (src/npc/_chat_llm.py, src/api/routes/world.py),
    # so any test driving the mixin end-to-end populates it -- and without this
    # teardown that instance would outlive the fixture still holding a live
    # provider and a real API key.
    from ai.llm_client import GenericLLMClient, NpcChatLLMAdapter

    def _reset():
        GenericLLMClient.reset_class_state()
        with NpcChatLLMAdapter._instances_lock:
            NpcChatLLMAdapter._instances.clear()
            NpcChatLLMAdapter._prewarm_attempted = False

    # Everything from the first os.environ write onward sits inside the
    # try/finally: if the mutation loop or the entry _reset() raises, the
    # finally still restores the saved env, so a live-enabled configuration
    # (real API key included) can never leak into later test modules.
    try:
        for key in _LIVE_KEYS:
            value = cfg.get(key)
            if value:
                os.environ[key] = value
        _apply_single_provider_isolation()
        _reset()
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _reset()
