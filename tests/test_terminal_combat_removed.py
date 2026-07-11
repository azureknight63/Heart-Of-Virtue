"""Lock in removal of the dead terminal combat loop.

The web client drives combat entirely through ApiCombatAdapter
(src/api/combat_adapter.py) + GameService; the blocking terminal combat() loop
(src/combat.py) and its terminal entry points (Player.attack, actions.Attack,
CombatEvent's terminal fallback) are dead. This suite guards their removal.
"""

import importlib

from src.player import Player


def test_engine_combat_loop_is_gone():
    # The engine module's terminal combat() loop and its helper must be gone
    # (src/combat.py is deleted, so ModuleNotFoundError is the expected path).
    try:
        module = importlib.import_module("src.combat")
    except ModuleNotFoundError:
        return
    assert not callable(getattr(module, "combat", None))
    assert not hasattr(module, "_evaluate_combat_events")


def test_player_has_no_terminal_attack():
    # The terminal explore-mode attack (which launched combat()) is removed;
    # web combat starts via GameService.start_combat / the Attack *move*.
    assert not hasattr(Player, "attack")


def test_actions_has_no_attack_action():
    actions = importlib.import_module("src.actions")
    assert not hasattr(actions, "Attack")


def test_combat_event_has_no_terminal_fallback():
    """CombatEvent.process must not import/run the terminal combat() loop."""
    import inspect
    from src.events import CombatEvent

    src = inspect.getsource(CombatEvent.process)
    assert "import combat" not in src
    assert "combat(" not in src.replace("combat_", "")
