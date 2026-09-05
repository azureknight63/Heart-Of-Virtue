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

That migration is **complete**. Every inline body that could be expressed as
a factory call is one; the handful that remain are exceptions that state
their own reason on the line above the ``class`` statement, and all of them
pin a state the factory cannot reach *because* it is a complete host --
a missing ``keywords``, a missing ``_chat_config_path``, or a class whose
``__name__`` is itself the thing under assertion (``_get_npc_key`` derives
the key from ``type(self).__name__``, so a shared host class has nothing to
vary). Adding a body without such a reason is the regression.

To re-derive rather than trust this paragraph::

    grep -rn "(ConversationalNPCMixin)" tests/

That is the honest command: counting ``class TestNPC`` alone misses the two
named ``CustomNomad`` and the two in ``tests/integration/``. As of this
writing it finds five subclasses in the default-collected suite (four in
``test_npc_chat_llm_tier4.py``, one file-local builder in
``test_npc_chat_llm_review.py``), two in the opt-in live suite, and
:class:`ChatHost` below.

:func:`chat_npc` builds one host object carrying the mixin's *whole* documented
attribute contract (see the module docstring of ``src/npc/_chat_llm.py``), with
overrides for the handful a given test cares about. Because it starts from the
full contract, a test that forgets an attribute gets a working object rather
than an ``AttributeError`` that then gets "fixed" by narrowing the test.
:func:`chat_player` and :func:`make_turn` do the same for the other two halves
of a chat round: the player handed to ``chat_open``, and the turn payload an
adapter hands back.

Why these stay plain functions, and stay here
---------------------------------------------
This file is not a ``conftest.py``, so nothing in it is auto-discovered; a test
module imports what it needs by name. Earlier revisions carried a standing note
saying these should be promoted into ``tests/conftest.py``. They should not, and
the note is retired rather than acted on — but the reason it used to give was
backwards, so here is the real one.

pytest resolves a fixture from the most specific scope outward: a definition in
the test module itself wins, then a ``conftest.py`` in the same directory, then
each parent ``conftest.py``. A root-conftest fixture therefore **cannot** shadow
a file-local one; the file-local definition always wins. (``tests/conftest.py``
states this correctly on its own ``game_service`` fixture.)

The hazard runs the other way, and it is quieter. ``tests/conftest.py`` is the
*root* conftest, so a fixture added there is visible to every test in the suite
— 10,675 of them at last count, the great majority with nothing to do with
NPCs. A name as generic as ``chat_player`` or ``make_turn`` would then be
silently *inherited* by any file that forgot to define its own: the test does
not fail, it passes, against an object its author never chose and cannot see
from the file they are reading. That is the same class of papercut as the
broken ``flask_app``/``flask_client``/``app_with_session`` fixtures deleted
from the root conftest, which handed an ``AttributeError`` out of a file
nobody had opened.

The import line these factories cost is the price of that isolation, and it is
also documentation: it says on the face of the test file where its objects come
from. If they ever do warrant fixture form, the right home is a
``conftest.py`` under an ``npc``-scoped test directory, not the root.
"""

import re
from typing import Any, Dict, Iterable, List, Optional, Pattern, Sequence

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
    "ChatPlayer",
    "chat_player",
    "make_turn",
]


class ChatPlayer:
    """The player side of the mixin's contract: ``universe`` and ``reputation``.

    Those two, plus the optional ``npc_chat_histories``, are the *only* things
    ``src/npc/_chat_llm.py`` ever reads off a player. See :func:`chat_player`
    for why this is a double rather than a real ``Player``.
    """

    def __init__(
        self, universe: Any = None, reputation: Optional[Dict[str, Any]] = None
    ) -> None:
        self.universe = universe
        self.reputation: Dict[str, Any] = {} if reputation is None else reputation


def chat_player(persist: bool = False, **overrides: Any) -> ChatPlayer:
    """Build the player object a chat test hands to ``chat_open``/``chat_respond``.

    ``player = chat_player()`` is the ordinary case. Nothing else is needed:
    ``universe = None`` makes ``_story()`` return an empty dict, which is what a
    test not asserting on story state wants.

    Args:
        persist: also give the player an empty ``npc_chat_histories`` dict, for
            a test driving the real persistence path
            (``wired_chat_npc(adapter, persist=True)``). The mixin creates the
            attribute itself when it is missing, so this is not required — it is
            for tests that want to *read* the dict afterwards without depending
            on that creation having happened.
        **overrides: ``universe`` and ``reputation`` are routed into the
            constructor; every other keyword is set on the finished
            instance. The routing is not cosmetic: ``ChatPlayer.__init__``
            normalises ``reputation=None`` to ``{}``, and setting the
            attribute afterwards instead skips that -- so
            ``chat_player(reputation=None)`` used to hand back a player
            whose ``reputation`` was ``None``, which is the
            AttributeError-shaped trap this module exists to prevent.
            Same reason :func:`chat_npc` routes its own constructor
            keywords rather than setattr-ing them.

    A double rather than a real ``src.player.Player`` on purpose, and this is
    the one place in the NPC suite where that is the right call: ``reputation``
    and ``npc_chat_histories`` are attributes a fresh ``Player`` does not have
    at all (CLAUDE.md lists both), so the mixin's own code creates them on
    first write. A real ``Player`` would therefore test the creation path and
    nothing else, while costing a full engine construction per test.

    This replaces four hand-rolled copies that had already collided on names:
    ``_Player`` existed in two files with identical bodies, ``_EndToEndPlayer``
    was a third copy under a third name, and ``_PersistPlayer`` was the same
    thing plus ``npc_chat_histories`` -- which is the ``persist=True`` argument.
    """
    ctor_keys = ("universe", "reputation")
    ctor = {k: overrides.pop(k) for k in ctor_keys if k in overrides}
    player = ChatPlayer(**ctor)
    if persist:
        player.npc_chat_histories = {}
    for key, value in overrides.items():
        setattr(player, key, value)
    return player


def make_turn(npc_text: str, **overrides: Any) -> Dict[str, Any]:
    """One structured turn payload, as an adapter's ``generate_turn`` returns it.

    ``make_turn("The road north is closed.")``, or
    ``make_turn("...", reputation_delta=3, jean_options=[...])``.

    The six keys are the shape ``_qc_npc_text`` and the loquacity/reputation
    bookkeeping read, and each default is the value that leaves that field's
    behaviour to the engine: empty flavor, ``"neutral"`` quality, no reputation
    movement, no options. A test therefore states only the field it is varying,
    which is also the field the assertion is about -- the whole dict spelled
    out inline buries that one field among five constants.

    ``loquacity_delta`` defaults to ``None`` because ``None`` is a *sentinel*
    here, not an absent number. ``_apply_loquacity_delta`` reads it as "the
    model did not signal a cost" and falls through to the quality-based
    ``_LOQUACITY_DRAIN`` table (``positive`` 3, ``neutral`` 8, ``negative`` 15,
    ``offensive`` 30, keyed on the ``conversation_quality`` in this same dict).
    Any non-``None`` value suppresses that whole branch, so a factory that
    supplied one would route every one of its call sites away from the
    production path while calling the default inert -- and would silently
    decouple ``conversation_quality`` from the cost it is supposed to drive.
    Pass an explicit number only when the *signalled* delta is what the test is
    about.

    Deliberately not validated against a schema: several tests exist precisely
    to feed this pipeline a ``reputation_delta`` of ``"not-a-number"`` or
    ``999999`` and watch it clamp, so every override passes through untouched.
    """
    turn: Dict[str, Any] = {
        "npc_text": npc_text,
        "npc_flavor": "",
        "conversation_quality": "neutral",
        "reputation_delta": 0,
        "loquacity_delta": None,
        "jean_options": [],
    }
    turn.update(overrides)
    return turn


class ChatHost(ConversationalNPCMixin):
    """Minimal host class for ``ConversationalNPCMixin``.

    Mirrors the attribute surface the mixin's docstring declares it expects from
    its host: ``name``/``charisma``/``wisdom``/``keywords``, plus the optional
    ``_chat_config_path``. Everything else the mixin owns is produced by
    ``_init_chat_attrs``.
    """

    def __init__(self, name: str = "TestNPC", charisma: int = 10,
                 wisdom: int = 10, keywords: Optional[Iterable[str]] = None,
                 config_path: Optional[str] = None, init: bool = True) -> None:
        self.name = name
        self.charisma = charisma
        self.wisdom = wisdom
        self.keywords = [] if keywords is None else list(keywords)
        self._chat_config_path = config_path
        if init:
            self._init_chat_attrs()


def chat_npc(init: bool = True, **overrides: Any) -> ChatHost:
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


def qc_npc(allowed_proper_nouns: Optional[Iterable[str]] = None,
           prohibited: Sequence[str] = (), name: str = "TestNPC",
           **overrides: Any) -> ChatHost:
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
    facts: Dict[str, Any] = {}
    if allowed_proper_nouns is not None:
        facts["allowed_proper_nouns"] = list(allowed_proper_nouns)
    return chat_npc(
        init=False,
        name=name,
        _chat_world_facts=facts,
        _prohibited_patterns=prohibit(*prohibited),
        **overrides,
    )


def prohibit(*phrases: str) -> List[Pattern[str]]:
    """Compile ``phrases`` the way ``_init_chat_attrs`` compiles them."""
    return [re.compile(p, re.IGNORECASE) for p in phrases]


#: "no scripted raw payload" -- distinct from a scripted ``None``, which
#: is itself one of the malformed shapes the mixin has to survive.
_UNSET = object()


class StubAdapter:
    """A deterministic stand-in for the LLM adapter.

    Records every ``system`` prompt it is handed on ``self.prompts`` so a test
    can assert what was actually *sent* — the thing that matters and the thing a
    bare ``MagicMock`` return-value assertion never checks. ``turns`` is a list
    of responses (or exceptions to raise) served in order; the last one repeats
    once the list is exhausted.
    """

    def __init__(self, *turns: Any, enabled: bool = True) -> None:
        # `enabled` is not decoration: `_prepare_turn_context` reads it to
        # decide whether an adapter counts as available at all, so without it
        # the mixin raises AttributeError before this stub is ever called.
        self.enabled = enabled
        self.turns: List[Any] = list(turns)
        self.prompts: List[Any] = []
        self.history: Any = None
        self.calls = 0

    def _next(self) -> Any:
        index = min(self.calls, len(self.turns) - 1)
        self.calls += 1
        turn = self.turns[index]
        if isinstance(turn, BaseException):
            raise turn
        return turn

    def generate_turn(self, system: Any = None, history: Any = None,
                      is_opening: bool = False,
                      jean_text: Optional[str] = None, **kwargs: Any) -> Any:
        """Match the mixin's call shape exactly.

        ``history`` is second and positional because that is how
        ``_generate_turn`` calls it (``src/npc/_chat_llm.py``):
        ``method(system, self._chat_history, is_opening=True)``. Omitting it
        bound the history list to ``is_opening``, so the keyword arrived twice
        and raised ``TypeError`` -- into ``_generate_turn``'s bare ``except``,
        which then silently ran the FALLBACK path. Every test using this stub
        passed while asserting on a turn the stub never produced: ``calls`` 0,
        ``prompts`` empty, turn ``None``. A double that cannot be reached is
        worse than no double, because the suite stays green either way.
        """
        self.prompts.append(system)
        self.history = history
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
    VALID_OPTIONS: List[Dict[str, str]] = [
        {"text": "Tell me more.", "tone": "direct"},
        {"text": "I will remember that.", "tone": "guarded"},
        {"text": "Go on, then.", "tone": "open"},
    ]

    def __init__(self, npc_text: str = "The road north is closed.",
                 quality: str = "neutral",
                 options: Optional[List[Dict[str, str]]] = None,
                 enabled: bool = True,
                 personality: Optional[Dict[str, Any]] = None,
                 raw: Any = _UNSET,
                 error: Optional[BaseException] = None,
                 **extra: Any) -> None:
        self.enabled = enabled
        self.npc_text = npc_text
        self.quality = quality
        self.options = self.VALID_OPTIONS if options is None else options
        self.personality = personality
        #: Return this instead of a built turn -- for the malformed-payload
        #: cases (``None``, ``[]``, a bare string) the mixin must survive.
        self.raw = raw
        #: Raise this instead of returning -- for the adapter-blew-up path.
        self.error = error
        self.extra = extra
        self.prompts: List[Any] = []
        self.jean_texts: List[Optional[str]] = []

    def generate_npc_turn(self, system: Any, history: Any,
                          is_opening: bool = False,
                          jean_text: Optional[str] = None) -> Dict[str, Any]:
        self.prompts.append(system)
        self.jean_texts.append(jean_text)
        # `raw` and `error` exist so the malformed-payload and raising-adapter
        # cases need no local class of their own. Checked before the turn is
        # built, because both are about the adapter never returning a
        # well-formed one.
        if self.error is not None:
            raise self.error
        if self.raw is not _UNSET:
            return self.raw
        turn: Dict[str, Any] = {
            "npc_text": self.npc_text,
            "conversation_quality": self.quality,
        }
        turn.update(self.extra)
        return turn

    def generate_jean_options(self, name: str, voice: Any, response: Any,
                              history: Any, turn: Any) -> List[Dict[str, str]]:
        return self.options

    def generate_personality(self, class_name: str) -> Optional[Dict[str, Any]]:
        return self.personality


def ready_npc(adapter: Any = None, **overrides: Any) -> ChatHost:
    """A mixin host wired for a live ``chat_open``/``chat_respond`` round.

    Sets every attribute those two methods read, so a test only has to state
    the one it is actually varying. ``_init_chat_attrs`` is skipped because it
    reads the on-disk world-facts/character-config JSON; the attributes it
    would set are supplied here as fixed, inspectable values instead.
    """
    defaults: Dict[str, Any] = {
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


def wired_chat_npc(adapter: Any, persist: bool = False,
                   **overrides: Any) -> ChatHost:
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
    defaults: Dict[str, Any] = {
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
