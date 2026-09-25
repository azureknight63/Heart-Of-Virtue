"""Issue #690: the server kept accepting world/player mutations after a
combat defeat (Jean at 0 HP could still walk, search, interact, chat, shop,
and heal herself with a Restorative).

``GameService.is_player_dead`` existed but was consulted only by
``submit_event_input`` (routes/world.py), and even there only to annotate the
response after the fact -- nothing ever REFUSED an action because the player
was dead. There is no legitimate out-of-combat revival (``check_revive`` is
combat-pipeline only), so every mutating ``GameService`` method now runs
``_refused_if_dead`` before doing anything else.

Two guards, twin shape: ``_refused_mid_fight`` (in-combat) and
``_refused_if_dead`` (post-defeat). This file has two halves:

1. A structural check that derives the guarded-method table from the source
   itself (every method already calling ``_refused_mid_fight``, since that is
   this codebase's existing marker for "mutating, exploration-gated route")
   plus a small hand-kept list for methods with a bespoke response shape that
   has no such marker to grep for. A future mutator that copies the
   `_refused_mid_fight` pattern is caught automatically; one that doesn't
   copy any existing pattern still needs a human to add it to the hand-kept
   list -- exactly the situation #690 was.
2. Behavioural checks: hp <= 0 -> refused, hp > 0 -> unchanged (the death
   refusal is never returned).
"""

import ast
from pathlib import Path

import pytest

from src.api.services.game_service import GameService, _PLAYER_DEAD_MESSAGE
from tests._gs_fixtures import live_world

_GAME_SERVICE_PATH = (
    Path(__file__).resolve().parent.parent / "src" / "api" / "services" / "game_service.py"
)


def _method_call_names():
    """``{method_name: {bare-name call targets}}`` for every method (sync or
    async) defined directly on ``class GameService`` in the real source file."""
    tree = ast.parse(_GAME_SERVICE_PATH.read_text(encoding="utf-8"))
    calls_by_method = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "GameService":
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    calls = {
                        sub.func.id
                        for sub in ast.walk(item)
                        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                    }
                    calls_by_method[item.name] = calls
    return calls_by_method


#: Mutating GameService methods that return a bespoke ``{"error": ...}``
#: shape (no ``success`` key) instead of the shared ``_refused_mid_fight``
#: marker, so the AST derivation below cannot find them on its own. Hand-kept
#: on purpose -- see the module docstring. If you add a new mutating method
#: with its own response shape, add it here in the same commit.
MANUALLY_GUARDED_METHODS = frozenset(
    {
        "move_player",
        "trigger_tile_events",
        "equip_item",
        "unequip_item",
        "drop_item",
        "use_item",
        "start_combat",
        "collect_combat_loot",
        "save_game",
    }
)


def _auto_derived_guarded(calls_by_method):
    """Every method already calling the mid-fight marker."""
    return {
        name for name, calls in calls_by_method.items() if "_refused_mid_fight" in calls
    }


def _guarded_methods(calls_by_method):
    return _auto_derived_guarded(calls_by_method) | MANUALLY_GUARDED_METHODS


def test_guarded_method_table_is_derived_and_nonempty():
    """The table this test enforces is not hand-typed twice: it is (every
    method already calling the mid-fight marker) union (the small hand-kept
    bespoke-shape list). The DERIVED half must be non-empty on its own -- a
    renamed marker would otherwise empty it while the hand-kept half kept the
    union green -- and every name must resolve to a real GameService method."""
    calls_by_method = _method_call_names()
    auto_derived = _auto_derived_guarded(calls_by_method)
    assert auto_derived, (
        "no GameService method calls _refused_mid_fight any more -- the marker "
        "this derivation keys on was renamed or moved; update the derivation"
    )
    for name in _guarded_methods(calls_by_method):
        assert name in calls_by_method, f"{name!r} is not a GameService method"


def test_every_guarded_method_calls_the_death_guard():
    """A method that calls ``_refused_mid_fight`` (or is in the hand-kept
    list) must also call ``_refused_if_dead`` -- this is the check that
    catches a *future* mutator added without the #690 guard, automatically,
    for anything following the existing mid-fight pattern."""
    calls_by_method = _method_call_names()
    guarded = _guarded_methods(calls_by_method)
    missing = sorted(
        name
        for name in guarded
        if "_refused_if_dead" not in calls_by_method.get(name, set())
    )
    assert not missing, f"GameService methods missing the #690 death guard: {missing}"


#: The ways out of a defeat (#690): a dead player must still be able to spend
#: pending points, list and load a save. Guarding any of them would strand a
#: player on the death screen. (START OVER is SessionManager.start_new_game,
#: outside GameService; the API test covers it.)
RECOVERY_METHODS = frozenset({"allocate_level_up_points", "list_saves", "load_game"})


def test_recovery_methods_never_call_the_death_guard():
    """Positive pin, not absence from a table: each recovery method is a real
    GameService method (sync or async) and does not call ``_refused_if_dead``,
    so a future pass that "fixes" one by adding the guard fails here."""
    calls_by_method = _method_call_names()
    for name in RECOVERY_METHODS:
        assert name in calls_by_method, f"{name!r} is not a GameService method"
        assert "_refused_if_dead" not in calls_by_method[name], (
            f"{name} refuses a dead player -- that strands them on the death screen"
        )


# ---------------------------------------------------------------------------
# Behavioural: hp <= 0 -> refused, hp > 0 -> the guard never fires.
# ---------------------------------------------------------------------------


@pytest.fixture
def gs():
    return GameService()


@pytest.fixture
def world():
    return live_world()


def _refusal_values(result):
    """Every string value in a result dict, flattened, for a substring check."""
    if not isinstance(result, dict):
        return []
    return [v for v in result.values() if isinstance(v, str)]


#: (label, invocation). Each invocation takes ``(gs, player)`` and returns
#: whatever the real method returns. Args are deliberately nonsense (bogus
#: ids, no setup) -- the whole point of the guard running FIRST is that none
#: of that ever gets resolved when the player is dead.
_DICT_RETURNING_CASES = [
    ("move_player", lambda gs, p: gs.move_player(p, "north")),
    ("process_event_input", lambda gs, p: gs.process_event_input(
        p, "nope", "", {"pending_events": {}}
    )),
    ("pray", lambda gs, p: gs.pray(p)),
    ("search", lambda gs, p: gs.search(p)),
    ("interact_with_target", lambda gs, p: gs.interact_with_target(p, "nope", "take")),
    ("learn_skill", lambda gs, p: gs.learn_skill(p, "Slash", "Basic")),
    ("npc_chat_open", lambda gs, p: gs.npc_chat_open(p, "nope")),
    ("npc_chat_respond", lambda gs, p: gs.npc_chat_respond(p, "nope", "hi")),
    ("get_shop_state", lambda gs, p: gs.get_shop_state(p, "nope")),
    ("shop_buy", lambda gs, p: gs.shop_buy(p, "nope", "nope", 1)),
    ("shop_sell", lambda gs, p: gs.shop_sell(p, "nope", "nope", 1)),
    ("shop_buyback", lambda gs, p: gs.shop_buyback(p, "nope", "nope")),
    ("equip_item", lambda gs, p: gs.equip_item(p, object())),
    ("unequip_item", lambda gs, p: gs.unequip_item(p, object())),
    ("drop_item", lambda gs, p: gs.drop_item(p, object())),
    ("use_item", lambda gs, p: gs.use_item(p, object())),
    ("start_combat", lambda gs, p: gs.start_combat(p, "nope")),
    # Maintainer decision 2026-09-25: loot is not collected by a fallen Jean.
    ("collect_combat_loot", lambda gs, p: gs.collect_combat_loot(p, [])),
]


@pytest.mark.parametrize("label,invoke", _DICT_RETURNING_CASES, ids=[c[0] for c in _DICT_RETURNING_CASES])
def test_dead_player_is_refused(gs, world, label, invoke):
    player, _game_map = world
    player.hp = 0
    result = invoke(gs, player)
    assert isinstance(result, dict), f"{label} did not return a dict: {result!r}"
    assert result.get("success") is False or "success" not in result
    assert _PLAYER_DEAD_MESSAGE in _refusal_values(result), (
        f"{label} did not carry the #690 death-refusal message: {result!r}"
    )


@pytest.mark.parametrize("label,invoke", _DICT_RETURNING_CASES, ids=[c[0] for c in _DICT_RETURNING_CASES])
def test_alive_player_is_never_death_refused(gs, world, label, invoke):
    """hp > 0 -> unchanged behaviour: whatever the method does next (a
    different validation error, since args are still nonsense), it must not
    be the #690 death refusal."""
    player, _game_map = world
    assert player.hp > 0, "live_world() should hand back a freshly-alive Player"
    result = invoke(gs, player)
    assert _PLAYER_DEAD_MESSAGE not in _refusal_values(result)


def test_dead_player_triggers_no_tile_events(gs, world):
    """trigger_tile_events (routes/world.py's POST /world/events) returns a
    list, not a dict, so it can't carry the shared refusal message -- but a
    dead player must still get an empty list back, same as the existing
    in-combat guard."""
    player, game_map = world
    player.hp = 0
    tile = game_map[(0, 0)]
    tile.events_here = [object()]  # would explode if actually processed
    assert gs.trigger_tile_events(player, tile, {}) == []


class _RecordingEvent:
    """Minimal tile event that records whether the pipeline processed it."""

    name = "RecordingEvent"
    needs_input = False
    repeat = False

    def __init__(self):
        self.checked = False
        self.player = None
        self.tile = None

    def check_conditions(self):
        self.checked = True


def test_alive_player_tile_events_not_short_circuited_by_death_guard(gs, world):
    # An empty tile returns [] whether or not the guard misfires, so queue an
    # event that records it ran: the live player's events must be processed.
    player, game_map = world
    assert player.hp > 0
    tile = game_map[(0, 0)]
    event = _RecordingEvent()
    tile.events_here = [event]
    gs.trigger_tile_events(player, tile, {})
    assert event.checked is True


def test_every_guarded_method_has_a_behavioural_refusal_case():
    """The structural table and the behavioural cases must not drift apart: a
    method the derivation now guards needs a case in _DICT_RETURNING_CASES
    that actually calls it at hp 0 (trigger_tile_events returns a list and
    has its own test)."""
    # trigger_tile_events returns a list and save_game is async with its own
    # contract; each has dedicated tests below.
    guarded = _guarded_methods(_method_call_names()) - {"trigger_tile_events", "save_game"}
    covered = {label for label, _ in _DICT_RETURNING_CASES}
    assert guarded, "premise: the derived table is empty"
    missing = sorted(guarded - covered)
    assert not missing, f"guarded but never exercised at hp 0: {missing}"


# ---------------------------------------------------------------------------
# save_game (async): maintainer decision 2026-09-25 -- a fallen Jean cannot
# write a named save over a good one. An AUTOSAVE is skipped silently instead
# (defeat is a combat transition, so autosave fires on the death screen and a
# refusal would toast "Autosave failed" there).
# ---------------------------------------------------------------------------


def test_a_manual_save_is_refused_while_dead(gs, world):
    import asyncio

    from src.api.services.game_service import SaveRefusedWhileDead

    player, _game_map = world
    player.hp = 0
    with pytest.raises(SaveRefusedWhileDead) as refused:
        asyncio.run(gs.save_game(player, "Fallen", "user-1"))
    assert str(refused.value) == _PLAYER_DEAD_MESSAGE


def test_an_autosave_is_skipped_silently_while_dead(gs, world):
    import asyncio

    player, _game_map = world
    player.hp = 0
    assert asyncio.run(gs.save_game(player, "auto", "user-1", is_autosave=True)) is None

