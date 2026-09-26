"""A status poll that settles a fight flee has already torn down must not crash.

``GameService.flee_combat`` ends by discarding the fight's state from the
player (``_discard_fight_state`` deletes ``combat_adapter_state``). A
``GET /api/combat/status`` poll that loses the race with flee still calls
``settle_defeat``/``settle_victory`` on the old adapter. They take their
already-settled early return and snapshot the terminal state, which reads the
adapter's per-fight properties (``combat_id`` and friends) from that deleted
dict. That raised ``AttributeError`` and turned the poll into a 500.
"""

import pytest

from src.api.combat_adapter import ApiCombatAdapter
from src.api.services.game_service import GameService
from src.npc import Slime
from tests._combat_fixtures import engage, make_npc, make_player


def fled_fight():
    player = make_player()
    slime = make_npc(Slime, name="Slime", hp=20, maxhp=20)
    engage(player, [slime])
    adapter = ApiCombatAdapter(player)
    player._combat_adapter = adapter
    adapter._stream_combat_result = lambda *a, **k: None
    adapter.initialize_combat([slime])
    slime.combat_proximity = {player: 100}
    result = GameService().flee_combat(player)
    assert result.get("success") is not False, result
    assert not hasattr(player, "combat_adapter_state")  # the teardown under test
    return adapter, player


@pytest.mark.parametrize("settle", ["settle_defeat", "settle_victory"])
def test_a_late_settle_returns_the_terminal_state(settle):
    adapter, player = fled_fight()
    state = getattr(adapter, settle)()
    assert isinstance(state, dict)
    assert state.get("combat_id") is None  # the fight it named is gone


def test_a_late_status_read_does_not_crash_or_resurrect_state():
    adapter, player = fled_fight()
    assert isinstance(adapter.get_combat_state(), dict)
    assert adapter.victory_deferred is False
    assert not hasattr(player, "combat_adapter_state")


def test_the_late_settle_does_not_resurrect_the_fight():
    adapter, player = fled_fight()
    adapter.settle_defeat()
    assert player.in_combat is False
    assert not hasattr(player, "combat_adapter_state")  # a read left nothing behind
    assert not getattr(player, "combat_end_summary", None)  # no game-over dialog for a flee
