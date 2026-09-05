"""Canonical doubles and factories for the ``ai/llm_client.py`` test suite.

Why this module exists
----------------------
Five files grew their own copies of the same four things, and the copies had
drifted into shapes that could not be swapped for one another:

* ``_Resp`` existed three times with three attribute sets — one carried
  ``headers``, one carried ``json()``, one carried neither — so a test moved
  between files silently changed what the transport under test could read.
* ``_HeaderResp`` existed twice with **incompatible positional constructors**:
  ``_HeaderResp(429)`` meant a status in one file and ``_HeaderResp({...})``
  meant a headers dict in the other. Copying a line across files produced a
  passing test that recorded the wrong thing. :class:`Resp` ends that by having
  one signature, status first, with ``headers`` keyword-only in practice.
* Thirteen ``NpcChatLLMAdapter.__new__`` stand-in builders shared two names
  (``_adapter``/``_adapter_returning``) across three files under five distinct
  signatures. :func:`make_chat_adapter` is the one factory.
* The provider-credential blank list was spelled in five places with five
  different subsets, while ``ai.llm_client._OPENAI_COMPATIBLE_PROVIDERS`` is
  the actual source of truth. Adding a fourth provider and missing one site
  lets a unit test dial a live endpoint — the exact hazard ``tests/conftest.py``
  says its blanking exists to prevent. :data:`PROVIDER_KEY_ENVS` is derived, so
  a new provider is covered everywhere the moment it is registered.

This is a plain module, not a ``conftest.py``, so nothing here is auto-injected;
:func:`isolate_llm_class_state` is a fixture a module opts into by name (see its
docstring). Sibling harness for the NPC/chat mixin: ``tests/_npc_fixtures.py``.
"""

from typing import Any, Dict, Iterable, Mapping, Optional, Tuple, Type, TypeVar

from ai.llm_client import (
    _OPENAI_COMPATIBLE_PROVIDERS,
    GenericLLMClient,
    NpcChatLLMAdapter,
)

import pytest

import ai.llm_client as llm

__all__ = [
    "PROVIDER_KEY_ENVS",
    "PROVIDER_MODEL_ENVS",
    "CREDENTIAL_ENVS",
    "LLM_GATE_SUFFIXES",
    "LLM_SETTING_ENVS",
    "llm_gate_envs",
    "Resp",
    "make_chat_adapter",
    "make_generic_client",
    "isolate_llm_class_state",
    "child_env",
]


#: Every provider credential the fallback chain reads, derived from the
#: registry rather than transcribed. ``_provider_chain`` treats a *present* key
#: as dialable, so any test process that must not reach the network has to blank
#: all of these — see :func:`child_env` and ``tests/conftest.py``.
PROVIDER_KEY_ENVS = tuple(
    sorted(cfg["key_env"] for cfg in _OPENAI_COMPATIBLE_PROVIDERS.values())
)

#: The per-provider model pin, derived from the same registry. ``openrouter``
#: has no ``model_env`` (it rotates models itself), so this is shorter than
#: :data:`PROVIDER_KEY_ENVS` by construction rather than by omission. Blanking
#: one is safe: the read site is
#: ``os.getenv(model_env, "").strip() or cfg["default_model"]``, so an empty
#: value restores the registry default instead of emptying the model id.
PROVIDER_MODEL_ENVS = tuple(
    sorted(
        cfg["model_env"]
        for cfg in _OPENAI_COMPATIBLE_PROVIDERS.values()
        if cfg.get("model_env")
    )
)

#: :data:`PROVIDER_KEY_ENVS` plus the non-LLM credential that also rides in on
#: ``.env``. ``GITHUB_TOKEN`` is here because ``feedback.py``'s issue-filing
#: path has no TESTING guard by design, so a child process that inherits it
#: files real GitHub issues.
CREDENTIAL_ENVS = PROVIDER_KEY_ENVS + ("GITHUB_TOKEN",)


# ---------------------------------------------------------------------------
# The LLM environment vocabulary, owned here so both conftests derive from it
# ---------------------------------------------------------------------------
# tests/conftest.py BLANKS this set process-wide; tests/integration/conftest.py
# RESTORES it for the opt-in live suite. Those two halves have to describe the
# same set of names or the live suite runs a feature adapter that the default
# suite disabled and nobody re-enabled -- which is precisely how
# test_tactical_advisor_live.py came to skip all 21 of its tests while
# reporting success. Neither conftest can import the other (no
# ``tests/__init__.py``, so pytest imports the root conftest under the bare
# name ``conftest``), so the vocabulary lives in this plain module, which both
# already import.

#: The naming convention every feature LLM adapter's gate trio obeys:
#: ``<FEATURE>_LLM_ENABLED`` / ``_PROVIDER`` / ``_MODEL``, resolved by
#: ``GenericLLMClient._first_env`` with "first non-empty wins". Swept by suffix
#: rather than from a list of adapter classes so an adapter added tomorrow --
#: or one whose module is mid-refactor and does not currently import -- is
#: covered without anyone remembering to add it.
LLM_GATE_SUFFIXES = ("_LLM_ENABLED", "_LLM_PROVIDER", "_LLM_MODEL")


def llm_gate_envs(names: Iterable[str]) -> Tuple[str, ...]:
    """The gate-trio variables among ``names``, sorted and de-duplicated.

    ``names`` is normally ``os.environ`` (what is actually set in this process)
    or the keys of ``dotenv_values()`` (what ``.env`` can contribute). Both
    conftests call this rather than spelling a tuple, so the blanked set and
    the restored set cannot drift apart.
    """
    return tuple(sorted({n for n in names if n.endswith(LLM_GATE_SUFFIXES)}))


#: The LLM settings that do NOT follow the gate-trio convention, so nothing
#: derives them. Each is here because leaving it live changes what the default
#: suite tests:
#:
#: * ``OLLAMA_BASE_URL`` -- the one that actually reaches the network.
#:   ``_provider_chain`` appends ollama whenever it is set and
#:   ``_provider_available("ollama")`` reads nothing else, so a developer with
#:   a local Ollama gets unit tests dialling it. This is the "host" the
#:   blanking comment in tests/conftest.py always claimed to cover.
#: * ``NPC_CHAT_LLM_TIMEOUT`` -- feeds ``_turn_deadline``. A large ``.env``
#:   value spends the whole per-round budget on attempt 1, so the QC retry and
#:   the state-guard revision call never run and their tests pass for the
#:   wrong reason. Blanking is safe: ``_round_timeout`` wraps the ``float()``
#:   in ``except (TypeError, ValueError)``.
#: * ``NPC_CHAT_LLM_FALLBACK`` -- three-state. ``_remote_fallback_setting``
#:   reads a blank as "unset", which is the default this suite wants.
#: * ``LLM_LOG_RAW_BODIES`` -- transcribes whole provider bodies to the log.
#: * ``OPENROUTER_SITE`` / ``_SITE_TITLE`` -- ranking headers; both read as
#:   ``os.getenv(...).strip() or None``, so blank is exactly absent.
#: * :data:`PROVIDER_MODEL_ENVS` -- the "model" half of the same claim.
#:
#: Deliberately ABSENT: the five ``NPC_CHAT_TEMP_*`` overrides. They are read
#: as a bare ``float(os.getenv("NPC_CHAT_TEMP_NPC", "0.65"))`` with no
#: ``try``/``except`` (ai/llm_client.py, five call sites), and ``float("")``
#: raises -- so blanking them would turn a developer's ``.env`` override into a
#: crash rather than neutralising it, and pinning them to their defaults here
#: would be a sixth copy of five constants that live in the engine. They also
#: cannot reach the network on their own: they only set ``temperature`` on a
#: call the blanked chain never dials. Fix the read sites (give them
#: ``_round_timeout``'s ``except``) before adding them here.
LLM_SETTING_ENVS = (
    "LLM_LOG_RAW_BODIES",
    "NPC_CHAT_LLM_FALLBACK",
    "NPC_CHAT_LLM_TIMEOUT",
    "OLLAMA_BASE_URL",
    "OPENROUTER_SITE",
    "OPENROUTER_SITE_TITLE",
) + PROVIDER_MODEL_ENVS


class Resp:
    """A ``requests``-shaped response double for the chat transports.

    One class rather than the previous ``_Resp``/``_HeaderResp`` pair: the
    split bought nothing (``headers`` defaults to empty, which is what the
    header-less call sites wanted anyway) and cost a positional-argument
    collision between two files. ``status`` stays first because that is the
    ordering the larger set of call sites already used.
    """

    def __init__(
        self,
        status: int = 200,
        payload: Optional[Dict[str, Any]] = None,
        text: str = "",
        headers: Optional[Dict[str, str]] = None,
        json_error: Optional[BaseException] = None,
    ) -> None:
        self.status_code = status
        self._payload = payload or {
            "choices": [{"message": {"content": '{"npc_text": "Fine."}'}}]
        }
        self.text = text
        self.headers = headers or {}
        self._json_error = json_error

    def json(self) -> Dict[str, Any]:
        """The decoded body, or ``json_error`` raised.

        A real ``requests`` response raises out of ``.json()`` whenever the
        body is not JSON -- an HTML error page from a proxy, a truncated
        stream, an empty 200. Two production branches exist for exactly that
        and neither was reachable from this class until ``json_error`` was
        added: ``_ollama_chat``'s ``except Exception: data = None``, which then
        falls back to ``r.text``, and ``NpcChatLLMAdapter._call_llm``'s chain
        safety net, which must move to the next provider rather than let one
        malformed body abort the round. Both were covered only by ad-hoc
        ``MagicMock(json=Mock(side_effect=...))`` in a single file.

        Pass any exception instance: ``Resp(json_error=ValueError("no json"))``.
        ``requests`` raises its own ``JSONDecodeError`` in real life, but both
        call sites catch bare ``Exception``, so the type is not part of the
        contract under test and pinning it here would only couple the double to
        the ``requests`` version.
        """
        if self._json_error is not None:
            raise self._json_error
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("HTTP %s" % self.status_code)


#: Any ``GenericLLMClient`` subclass, so :func:`_build` returns the class it
#: was handed rather than the base class -- which is the whole reason the two
#: public factories below have distinct return types.
_ClientT = TypeVar("_ClientT", bound=GenericLLMClient)


def _build(
    cls: Type[_ClientT],
    provider: Optional[str],
    model: Optional[str],
    api_key: Optional[str],
    overrides: Mapping[str, Any],
) -> _ClientT:
    obj = cls.__new__(cls)
    obj.enabled = True
    if provider is not None:
        obj.provider = provider
        obj.model = model
    if api_key is not None:
        obj._openrouter_api_key = api_key
        obj._openrouter_site = ""
        obj._openrouter_site_title = ""
    for key, value in overrides.items():
        setattr(obj, key, value)
    return obj


def make_chat_adapter(
    provider: Optional[str] = "openrouter",
    model: Optional[str] = "m",
    api_key: Optional[str] = "or-key",
    **overrides: Any,
) -> NpcChatLLMAdapter:
    """An ``NpcChatLLMAdapter`` built without running ``__init__``.

    ``__init__`` reads the environment and can start provider discovery, so
    every test that wants to drive one method in isolation goes through
    ``__new__`` and sets attributes by hand. This is that, once.

    Args:
        provider: value for ``.provider``. ``None`` leaves ``.provider`` and
            ``.model`` unset entirely — the shape used by tests that replace
            ``_call_llm`` outright and never reach provider selection.
        model: value for ``.model``; ignored when ``provider`` is ``None``.
        api_key: value for ``._openrouter_api_key``, which is also what arms
            the OpenRouter leg of the fallback chain. Pass ``None`` to leave the
            three OpenRouter attributes unset, which is what a test asserting on
            an *unconfigured* chain needs.
        **overrides: any further attribute — ``base_url`` for ollama,
            ``_call_llm`` for a scripted transport, ``_available``, and so on.
    """
    return _build(NpcChatLLMAdapter, provider, model, api_key, overrides)


def make_generic_client(
    provider: Optional[str] = "openrouter",
    model: Optional[str] = "m",
    api_key: Optional[str] = "k",
    **overrides: Any,
) -> GenericLLMClient:
    """:func:`make_chat_adapter` for the ``GenericLLMClient`` base class.

    Separate from the adapter factory because the two classes are tested for
    different things: the base class owns the transports, the subclass owns the
    chat payload. A single factory returning either would make every call site
    state which one it meant anyway.
    """
    return _build(GenericLLMClient, provider, model, api_key, overrides)


@pytest.fixture(autouse=True)
def isolate_llm_class_state(monkeypatch, tmp_path):
    """Reset the process-wide LLM class state around every test in a module.

    ``GenericLLMClient`` keeps discovery results, benched models, provider usage
    counters and the usage window on the *class*, so one test's failed model or
    spent quota is visible to every test that runs after it — including in
    another file, since the class outlives the module.

    Opt a module in with a module-level alias::

        from tests.llm_doubles import isolate_llm_class_state  # noqa: F401

    The alias makes the fixture module-scoped in effect (autouse applies only
    where the name is visible), which is why this is not in ``conftest.py``:
    the whole suite does not need a ``reset_class_state`` per test.

    This replaced four spellings of the same idea — two near-identical
    ``_reset_llm_class_state`` copies, one ``_isolate_class_state``, and ten
    hand-rolled ``setup_method``/``teardown_method`` pairs. The pairs are the
    worse form for exactly the reason seen in ``test_llm_provider_digest.py``:
    a class that adds one more piece of state to reset updates its own pair and
    nobody else's, so the classes drift apart silently. A fixture cannot drift,
    because there is only one.

    The disk model cache is redirected into ``tmp_path`` for the same reason —
    it is real, shared, and survives the process. The environment is pinned to a
    clean, provider-less baseline that individual tests override as needed; the
    credential names come from :data:`PROVIDER_KEY_ENVS`, so a newly registered
    provider is neutralised here without anyone remembering to add it.

    Those names are SET EMPTY rather than deleted, which is not a style choice.
    ``load_dotenv`` runs with ``override=False``, so it refills a key that is
    *absent* and leaves an assigned empty one alone — and ``load_project_env()``
    runs again at import of several ``src.api`` modules. A ``delenv`` here
    therefore held only until the test under it imported something from the API,
    at which point the repo's real ``GROQ_API_KEY``/``CEREBRAS_API_KEY``/
    ``OPENROUTER_API_KEY`` came straight back from ``.env`` and armed the
    fallback chain inside a unit test. Empty is what every consumer reads as
    unset anyway: ``_first_env()`` strips and skips it, ``_provider_chain``
    tests ``os.getenv(key_env, "").strip()``, and the enabled gate compares
    against ``("1", "true", "True")``. Same trap as the GITHUB_TOKEN incident,
    and the same fix as :func:`child_env` and ``tests/conftest.py``.
    """
    GenericLLMClient.reset_class_state()
    GenericLLMClient._nightly_refresh_started = False
    monkeypatch.setattr(llm, "_MODEL_CACHE_FILE", str(tmp_path / ".model_cache.json"))
    monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
    monkeypatch.setenv("MYNX_LLM_PROVIDER", "none")
    for key in PROVIDER_KEY_ENVS + (
        "MYNX_LLM_MODEL",
        "NPC_CHAT_LLM_ENABLED",
        "NPC_CHAT_LLM_PROVIDER",
        "NPC_CHAT_LLM_MODEL",
    ):
        monkeypatch.setenv(key, "")
    yield
    GenericLLMClient.reset_class_state()
    GenericLLMClient._nightly_refresh_started = False


def child_env(**overrides: str) -> Dict[str, str]:
    """A subprocess environment that inherits PATH etc. but no live credentials.

    ``os.environ.copy()`` alone hands the child everything ``python-dotenv``
    loaded from the repo's real ``.env`` — live provider API keys included —
    and none of ``tests/conftest.py``'s blanking, so a child that imports the
    API can make real paid LLM calls.

    The blanked keys are ASSIGNED an empty string rather than popped: dotenv
    runs with ``override=False``, which only skips keys already *present*, so a
    popped key is silently refilled from ``.env`` the moment the child imports
    anything that calls ``load_dotenv()``. (Same trap as the GITHUB_TOKEN
    incident.)
    """
    import os

    env = os.environ.copy()
    for key in CREDENTIAL_ENVS:
        env[key] = ""
    env["NPC_CHAT_LLM_ENABLED"] = "0"
    env["LOG_LEVEL"] = "WARNING"
    env.update(overrides)
    return env
