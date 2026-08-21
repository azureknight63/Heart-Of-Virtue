"""Lock in removal of the dead terminal combat loop.

The web client drives combat entirely through ApiCombatAdapter
(src/api/combat_adapter.py) + GameService; the blocking terminal combat() loop
(src/combat.py) and its terminal entry points (Player.attack, actions.Attack,
CombatEvent's terminal fallback) are dead. This suite guards their removal.
"""

import importlib
from types import SimpleNamespace

import pytest

from src.combat_event_config import CombatEventConfig
from src.events import CombatEvent
from src.player import Player


class _FakeTile:
    """Minimal tile that records spawn_npc calls (CombatEvent's only tile verb)."""

    def __init__(self):
        self.events_here = []
        self.spawned = []

    def spawn_npc(self, name):
        npc = SimpleNamespace(name=name, aggro=False, friend=False)
        self.spawned.append(npc)
        return npc


@pytest.fixture
def combat_event():
    tile = _FakeTile()
    player = SimpleNamespace(combat_list_allies=[])
    config = CombatEventConfig(
        enemy_list=[("Slime", 2)],
        ally_list=[("Gorran", 1)],
        scenario_type="pincer",
        grid_size_override=(9, 5),
        on_victory_text="The cavern falls silent.",
    )
    event = CombatEvent("Test Fight", player=player, tile=tile, config=config)
    tile.events_here.append(event)
    return event


def test_engine_combat_loop_is_gone():
    """src/combat.py (the blocking terminal combat() loop) is deleted.

    Asserted as an import failure rather than `try/except: return`, which
    passed either way — including if the module came back with the loop in it.
    """
    with pytest.raises(ModuleNotFoundError, match=r"src\.combat"):
        importlib.import_module("src.combat")


def test_no_engine_module_still_exposes_a_terminal_combat_loop():
    """Belt and braces: no surviving engine module re-exports combat()/
    _evaluate_combat_events, which is how the loop would sneak back."""
    for name in ("src.combatant", "src.api.combat_adapter", "src.events"):
        module = importlib.import_module(name)
        assert not callable(getattr(module, "combat", None)), name
        assert not hasattr(module, "_evaluate_combat_events"), name


def test_player_has_no_terminal_attack():
    # The terminal explore-mode attack (which launched combat()) is removed;
    # web combat starts via GameService.start_combat / the Attack *move*.
    assert not hasattr(Player, "attack")


def test_actions_has_no_attack_action():
    actions = importlib.import_module("src.actions")
    assert not hasattr(actions, "Attack")


def test_combat_start_spawns_roster_and_stashes_overrides(combat_event):
    """The single supported input path builds the fight for ApiCombatAdapter."""
    result = combat_event.process(user_input="combat_start")

    assert result == {"combat_ready": True}

    tile = combat_event.tile
    player = combat_event.player
    assert [n.name for n in tile.spawned] == ["Slime", "Slime", "Gorran"]
    # Enemies aggro; the temp ally does not, and is flagged for post-fight cleanup.
    assert [n.aggro for n in tile.spawned] == [True, True, False]
    gorran = tile.spawned[-1]
    assert gorran.friend is True
    assert gorran.event_temp_ally is True
    assert player.combat_list_allies == [gorran]

    # Scenario/grid/victory overrides are handed to the adapter via the player.
    assert player._pending_scenario_type == "pincer"
    assert player._pending_grid_size_override == (9, 5)
    assert player._pending_victory_narrative == "The cavern falls silent."

    # Non-repeating event consumes itself.
    assert combat_event.completed is True
    assert combat_event.needs_input is False
    assert combat_event not in tile.events_here


@pytest.mark.parametrize("bad_input", [None, "", "fight", "1", "attack"])
def test_non_combat_start_input_is_an_inert_no_op(combat_event, bad_input):
    """There is no terminal fallback: anything but combat_start does nothing."""
    result = combat_event.process(user_input=bad_input)

    assert result == {"combat_ready": False}
    assert combat_event.tile.spawned == []
    assert combat_event.player.combat_list_allies == []
    assert not hasattr(combat_event.player, "_pending_scenario_type")
    # The event stays armed so the web client can still answer it properly.
    assert combat_event.completed is False
    assert combat_event in combat_event.tile.events_here


def test_combat_start_is_the_only_offered_option():
    event = CombatEvent("Solo", player=SimpleNamespace(), tile=_FakeTile(),
                        config=CombatEventConfig())
    assert event.needs_input is True
    assert [opt["value"] for opt in event.input_options] == ["combat_start"]
