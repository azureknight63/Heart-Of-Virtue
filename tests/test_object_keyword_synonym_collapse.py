"""Issue #615: an object's button row collapses keywords that mean the same call.

The shipped Ferry Landing authors ``enter, go, leave, exit, ferry, landing``.
``ferry`` and ``landing`` are the placement's own name words and resolve to
``enter`` itself (``Passageway.instance_keyword_aliases``), so the INTERACT
panel rendered ENTER / FERRY / LANDING -- three buttons, one call.

Maintainer decision: collapse in the serializer, not by trimming map JSON.
``resolve_interaction`` is the single authority on what a keyword calls, so the
serializer groups a placement's keywords by the handler they resolve to and
ships one verb per group. A keyword that resolves to nothing is kept as-is --
the API refuses it in fiction, or (on a passageway) crosses on the target's
type, as it did before.

Synonyms written as one-line delegator METHODS were invisible to this grouping
until #626 turned them into class-level aliases (``go = leave = exit = enter``);
``tests/test_object_synonym_aliases.py`` keeps them that way.
"""

import pytest

from src.api.serializers.object_serializer import ObjectSerializer
from src.api.services.game_service import GameService
from src.objects import Object, resolve_interaction
from tests._ferry_fixtures import build_ferry_world, interact_with


class _Lamp(Object):
    """A plain object whose ``peer`` is a class-declared alias of ``look``."""

    KEYWORD_METHOD_ALIASES = {"peer": "look", "gaze": "look"}

    def __init__(self, keywords, action_aliases=()):
        super().__init__(name="Lamp", description="A lamp.")
        self.keywords = list(keywords)
        self.action_aliases = list(action_aliases)

    def look(self, player):
        return None

    def light(self, player):
        return None


class _Hatch(Object):
    """A lockable object whose ``pry`` means ``open`` and ``pick`` means ``unlock``."""

    KEYWORD_METHOD_ALIASES = {"pry": "open", "pick": "unlock"}

    def __init__(self, keywords, locked, state="closed"):
        super().__init__(name="Hatch", description="A hatch.")
        self.keywords = list(keywords)
        self.locked = locked
        self.state = state

    def open(self, player):
        return None

    def unlock(self, player):
        return None


def _wire_keywords(obj):
    return ObjectSerializer.serialize(obj)["keywords"]


@pytest.fixture
def ferry():
    _player, _game_map, ferry = build_ferry_world(with_tile_events=False)
    return ferry


def test_the_ferrys_name_words_collapse_into_enter(ferry):
    # Precondition: the reported shape is still the shipped one.
    assert "ferry" in ferry.keywords and "landing" in ferry.keywords
    # go/leave/exit are class-level aliases of enter since #626, so they fold
    # into ENTER too (the client also hides them as action_aliases).
    assert _wire_keywords(ferry) == ["enter"]


def test_the_engine_keeps_every_authored_keyword(ferry):
    """The collapse is a presentation of the list, never a mutation of it --
    the API's advertised-verb check reads the engine's own ``keywords``."""
    before = list(ferry.keywords)
    ObjectSerializer.serialize(ferry)
    assert ferry.keywords == before


def test_every_shipped_ferry_verb_is_still_reachable_by_a_rendered_one(ferry):
    """Every authored verb's call is still one button away, and every button
    passes the step-through gate the API applies to a passageway."""
    wire = _wire_keywords(ferry)
    wire_handlers = [resolve_interaction(ferry, k) for k in wire]
    for keyword in ferry.keywords:
        handler = resolve_interaction(ferry, keyword)
        assert handler is None or any(handler == h for h in wire_handlers), keyword
    for keyword in wire:
        assert ferry.accepts_step_through(resolve_interaction(ferry, keyword), keyword)


def test_the_primary_is_the_first_authored_keyword_of_its_group():
    assert _wire_keywords(_Lamp(["peer", "light", "look", "gaze"])) == ["peer", "light"]
    assert _wire_keywords(_Lamp(["look", "peer"])) == ["look"]


def test_the_primary_skips_a_keyword_the_client_hides_as_an_alias():
    """The client drops ``action_aliases`` from the row. Choosing one of those
    as a group's primary would leave the group with no button at all."""
    lamp = _Lamp(["peer", "look"], action_aliases=["peer"])
    assert _wire_keywords(lamp) == ["look"]


def test_a_group_made_only_of_aliases_keeps_its_first():
    lamp = _Lamp(["peer", "gaze"], action_aliases=["peer", "gaze"])
    assert _wire_keywords(lamp) == ["peer"]


def test_keywords_that_resolve_to_nothing_are_kept():
    lamp = _Lamp(["frobnicate", "look", "peer", "wiggle"])
    assert _wire_keywords(lamp) == ["frobnicate", "look", "wiggle"]


def test_the_collapse_runs_after_the_state_rewrite_so_open_is_not_doubled():
    # Closed and unlocked: the rewrite appends "open", which is ``pry``'s call.
    assert _wire_keywords(_Hatch(["pry"], locked=False)) == ["pry"]
    # Locked: the rewrite drops open and appends "unlock", which is ``pick``'s.
    assert _wire_keywords(_Hatch(["pick", "open"], locked=True)) == ["pick"]
    # A plain lockable with no synonyms is untouched.
    assert _wire_keywords(_Hatch(["open"], locked=True)) == ["unlock"]


def test_a_dict_target_is_left_alone():
    payload = {"name": "Sign", "keywords": ["read", "look", "read"]}
    assert ObjectSerializer.serialize(payload)["keywords"] == ["read", "look", "read"]


def test_the_interaction_response_ships_the_collapsed_row_too(ferry):
    """``object_state.keywords`` patches the client's selected target after
    every interaction. Shipping the raw list there re-expanded the row the
    moment the player pressed ENTER and the ferry declined."""
    player = ferry.player
    result = interact_with(GameService(), player, ferry, "enter")
    assert "ferry" not in result["object_state"]["keywords"]
    assert result["object_state"]["keywords"] == _wire_keywords(ferry)
