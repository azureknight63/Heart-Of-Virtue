"""Canonical NPC/chat test factories for the ``test_npc_*`` suite.

Why this module exists
----------------------
``tests/test_npc_chat_llm_tier4.py`` alone declared **129 near-identical inline
``class TestNPC(ConversationalNPCMixin)`` bodies** — one per test method — each
hand-setting whichever three or four attributes that particular method happened
to touch. The copies had drifted: some omitted ``_prohibited_patterns`` (so a
test could not reach the prohibited-phrase branch at all), some omitted
``_chat_world_facts`` (so the invented-proper-noun scan silently saw an empty
allow-list), and none of them was reusable from a sibling file.

:func:`chat_npc` builds one host object carrying the mixin's *whole* documented
attribute contract (see the module docstring of ``src/npc/_chat_llm.py``), with
overrides for the handful a given test cares about. Because it starts from the
full contract, a test that forgets an attribute gets a working object rather
than an ``AttributeError`` that then gets "fixed" by narrowing the test.

These are plain functions rather than ``@pytest.fixture`` definitions on
purpose: this file is not a ``conftest.py``, so fixtures declared here would not
be auto-discovered. Each test module wraps whichever factory it needs in a
one-line local fixture. **These should be promoted to ``tests/conftest.py``.**
"""

import re

from src.npc._chat_llm import ConversationalNPCMixin

__all__ = [
    "ChatHost",
    "chat_npc",
    "qc_npc",
    "prohibit",
    "StubAdapter",
    "ScriptedAdapter",
    "ready_npc",
    "wired_chat_npc",
]


class ChatHost(ConversationalNPCMixin):
    """Minimal host class for ``ConversationalNPCMixin``.

    Mirrors the attribute surface the mixin's docstring declares it expects from
    its host: ``name``/``charisma``/``wisdom``/``keywords``, plus the optional
    ``_chat_config_path``. Everything else the mixin owns is produced by
    ``_init_chat_attrs``.
    """

    def __init__(self, name="TestNPC", charisma=10, wisdom=10, keywords=None,
                 config_path=None, init=True):
        self.name = name
        self.charisma = charisma
        self.wisdom = wisdom
        self.keywords = [] if keywords is None else list(keywords)
        self._chat_config_path = config_path
        if init:
            self._init_chat_attrs()


def chat_npc(init=True, **overrides):
    """Build a mixin host, then apply ``overrides`` as plain attributes.

    Args:
        init: run ``_init_chat_attrs`` (the normal path). Pass ``False`` to test
            the pre-initialization state.
        **overrides: any attribute to set afterwards — ``name``, ``charisma``,
            ``wisdom``, ``keywords`` and ``config_path`` are routed into the
            constructor; everything else is set on the finished instance, which
            is how tests force states such as an exhausted ``loquacity_current``
            or a pre-seeded ``_chat_history``.
    """
    ctor_keys = ("name", "charisma", "wisdom", "keywords", "config_path")
    ctor = {k: overrides.pop(k) for k in ctor_keys if k in overrides}
    npc = ChatHost(init=init, **ctor)
    for key, value in overrides.items():
        setattr(npc, key, value)
    return npc


def qc_npc(allowed_proper_nouns=None, prohibited=(), name="TestNPC", **overrides):
    """A host wired for the ``_qc_npc_text`` pipeline specifically.

    ``_qc_npc_text`` reads exactly two pieces of instance state —
    ``_chat_world_facts["allowed_proper_nouns"]`` and ``_prohibited_patterns``
    — plus ``self.name`` (which is always allow-listed as a proper noun). This
    factory makes all three explicit at the call site so a test can never
    accidentally exercise the empty-allow-list path while claiming to test the
    populated one.

    ``**overrides`` passes straight through to :func:`chat_npc`, for callers
    that need one attribute beyond those three (``_chat_personality``, say)
    without forking the factory — which is exactly how the hand-rolled copies
    in ``test_npc_chat_qc_hardening.py`` started.
    """
    facts = {}
    if allowed_proper_nouns is not None:
        facts["allowed_proper_nouns"] = list(allowed_proper_nouns)
    return chat_npc(
        init=False,
        name=name,
        _chat_world_facts=facts,
        _prohibited_patterns=prohibit(*prohibited),
        **overrides,
    )


def prohibit(*phrases):
    """Compile ``phrases`` the way ``_init_chat_attrs`` compiles them."""
    return [re.compile(p, re.IGNORECASE) for p in phrases]


class StubAdapter:
    """A deterministic stand-in for the LLM adapter.

    Records every ``system`` prompt it is handed on ``self.prompts`` so a test
    can assert what was actually *sent* — the thing that matters and the thing a
    bare ``MagicMock`` return-value assertion never checks. ``turns`` is a list
    of responses (or exceptions to raise) served in order; the last one repeats
    once the list is exhausted.
    """

    def __init__(self, *turns):
        self.turns = list(turns)
        self.prompts = []
        self.calls = 0

    def _next(self):
        index = min(self.calls, len(self.turns) - 1)
        self.calls += 1
        turn = self.turns[index]
        if isinstance(turn, BaseException):
            raise turn
        return turn

    def generate_turn(self, system=None, is_opening=False, jean_text=None, **kwargs):
        self.prompts.append(system)
        return self._next()


class ScriptedAdapter:
    """The legacy two-method LLM adapter interface, with scripted output.

    ``ConversationalNPCMixin`` supports two adapter shapes: the combined
    ``generate_turn`` (see :class:`StubAdapter`) and this older pair of
    ``generate_npc_turn`` / ``generate_jean_options`` calls. Both are exercised
    in the suite because the mixin still falls back to this one.

    Every prompt it receives is recorded on ``self.prompts`` so a test can
    assert on what was *sent*, not merely on what a mock was told to return.
    """

    #: A Jean-options block that survives ``_qc_jean_options`` unchanged.
    VALID_OPTIONS = [
        {"text": "Tell me more.", "tone": "direct"},
        {"text": "I will remember that.", "tone": "guarded"},
        {"text": "Go on, then.", "tone": "open"},
    ]

    def __init__(self, npc_text="The road north is closed.", quality="neutral",
                 options=None, enabled=True, personality=None, **extra):
        self.enabled = enabled
        self.npc_text = npc_text
        self.quality = quality
        self.options = self.VALID_OPTIONS if options is None else options
        self.personality = personality
        self.extra = extra
        self.prompts = []
        self.jean_texts = []

    def generate_npc_turn(self, system, history, is_opening=False, jean_text=None):
        self.prompts.append(system)
        self.jean_texts.append(jean_text)
        turn = {"npc_text": self.npc_text, "conversation_quality": self.quality}
        turn.update(self.extra)
        return turn

    def generate_jean_options(self, name, voice, response, history, turn):
        return self.options

    def generate_personality(self, class_name):
        return self.personality


def ready_npc(adapter=None, **overrides):
    """A mixin host wired for a live ``chat_open``/``chat_respond`` round.

    Sets every attribute those two methods read, so a test only has to state
    the one it is actually varying. ``_init_chat_attrs`` is skipped because it
    reads the on-disk world-facts/character-config JSON; the attributes it
    would set are supplied here as fixed, inspectable values instead.
    """
    defaults = {
        "name": "TestNPC",
        "charisma": 10,
        "wisdom": 10,
        "keywords": ["chat"],
        "config_path": None,
        "_chat_char_config": None,
        "_chat_world_facts": {},
        "_chat_personality": {"given_name": "Ren"},
        "_chat_history": [],
        "_chat_npc_key": None,
        "_chat_fallback_idx": 0,
        "_prohibited_patterns": [],
        "loquacity_current": 50,
        "loquacity_max": 100,
        "loquacity_threshold": 20,
        "loquacity_recovery": 2,
    }
    defaults.update(overrides)
    defaults["_chat_adapter"] = ScriptedAdapter() if adapter is None else adapter
    return chat_npc(init=False, **defaults)


def wired_chat_npc(adapter, persist=False, **overrides):
    """A mixin host wired for a real ``chat_open``/``chat_respond`` round.

    Unlike :func:`ready_npc`, which only carries attributes, this also stubs the
    *methods* those two entry points call out to — loquacity computation, npc
    key/chapter lookup, personality generation, adapter selection — so a test
    can drive the whole chat path without a player, a save file, or a provider.

    ``persist=False`` (the default) also stubs the persistence read and write,
    which is what a test asserting on the returned turn wants. Pass
    ``persist=True`` to leave the real ``_load_history_from_persistence`` /
    ``_save_exchange_to_persistence`` in place, which is what a test asserting
    on *what got written* needs.

    This replaced three near-identical builders — two of which declared an inner
    class with the same name, ``WiredNPC``, in different files — that differed
    only in ``_chat_fallback_idx`` and ``loquacity_recovery`` being present in
    one copy and absent in another. Both are set here, because a host missing an
    attribute the mixin reads is the failure mode this whole module exists to
    stop.

    The stubs are set as plain instance attributes rather than class methods, so
    they take the caller's arguments *without* a ``self`` — attribute lookup on
    an instance does not bind.
    """
    defaults = {
        "name": "Mara",
        "_chat_world_facts": {"allowed_proper_nouns": ["Mara", "Jean"]},
        "_chat_char_config": None,
        "_chat_personality": {"given_name": "Mara", "voice": "terse"},
        "_chat_history": [],
        "_chat_npc_key": "mara",
        "_prohibited_patterns": [],
        "_chat_fallback_idx": 0,
        "growth_profile": None,
        "known_moves": [],
        "loquacity_current": 80,
        "loquacity_max": 100,
        "loquacity_threshold": 10,
        "loquacity_recovery": 2,
        "_compute_loquacity": lambda player: None,
        "_get_npc_key": lambda player: "mara",
        "_get_chapter": lambda player: "01",
        "_ensure_personality": lambda player: None,
        "_get_adapter": lambda: adapter,
    }
    if not persist:
        defaults["_load_history_from_persistence"] = lambda player: None
        defaults["_save_exchange_to_persistence"] = (
            lambda player, npc, jean, tick, chapter: None
        )
    defaults.update(overrides)
    return chat_npc(init=False, **defaults)
