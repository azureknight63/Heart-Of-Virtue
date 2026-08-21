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

import pytest

# Provider configuration these tests need restored from .env.
_LIVE_KEYS = (
    "MYNX_LLM_ENABLED",
    "MYNX_LLM_PROVIDER",
    "MYNX_LLM_MODEL",
    "NPC_CHAT_LLM_ENABLED",
    "NPC_CHAT_LLM_PROVIDER",
    "NPC_CHAT_LLM_MODEL",
    "NPC_CHAT_LLM_TIMEOUT",
    "OPENROUTER_API_KEY",
    "OPENROUTER_SITE",
    "OPENROUTER_SITE_TITLE",
    "OLLAMA_BASE_URL",
)


def live_llm_enabled() -> bool:
    """True when the developer has explicitly opted into live provider calls."""
    return os.getenv("HOV_LIVE_LLM", "0") in ("1", "true", "True")


@pytest.fixture(scope="module", autouse=True)
def live_env():
    """Give one module the real provider config, then undo it."""
    if not live_llm_enabled():
        yield
        return

    from dotenv import dotenv_values

    cfg = dotenv_values()
    saved = {k: os.environ.get(k) for k in _LIVE_KEYS}
    for key in _LIVE_KEYS:
        value = cfg.get(key)
        if value:
            os.environ[key] = value

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

    _reset()
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _reset()
