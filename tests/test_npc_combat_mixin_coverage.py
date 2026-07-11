"""Coverage for src/npc/_combat.py — NPCCombatMixin (select_move, add_move,
reset_combat_moves, combat_engage). Targets the branches existing NPC/AI
tests don't reach: the ai_config ImportError guard, the "no weighted moves"
early return, the in-range-but-unaffordable rest fallback, the hard-fallback
rest after 20 failed random attempts, and the combat-debug-manager logging
block in select_move.
"""

from unittest.mock import MagicMock, patch

from src.npc import NPC
import src.moves as moves  # type: ignore


def _make_npc(**overrides):
    npc = NPC(
        name="TestFoe",
        description="A test foe",
        damage=10,
        aggro=True,
        exp_award=5,
        maxhp=50,
    )
    for key, value in overrides.items():
        setattr(npc, key, value)
    return npc


def test_select_move_ai_config_import_error_is_swallowed():
    npc = _make_npc()
    npc.add_move(moves.NpcAttack(npc), 1)
    npc.player_ref = MagicMock()
    npc.ai_config = None
    with patch("src.npc_ai_config.NPCAIConfig", side_effect=ImportError("boom")):
        npc.select_move()
    # ai_config stays None; select_move still picks something rather than crashing.
    assert npc.ai_config is None
    assert npc.current_move is not None


def test_select_move_returns_early_when_no_weighted_moves():
    npc = _make_npc()
    npc.known_moves = []
    npc.current_move = None
    result = npc.select_move()
    assert result is None
    assert npc.current_move is None


def test_select_move_rests_when_offensive_move_in_range_but_unaffordable():
    npc = _make_npc()
    attack = moves.NpcAttack(npc)
    attack.category = "Offensive"
    attack.fatigue_cost = 1000  # unaffordable
    npc.known_moves = [attack]
    npc.fatigue = 10
    npc.maxfatigue = 100
    npc.current_move = None
    with patch.object(attack, "viable", return_value=True):
        npc.select_move()
    assert type(npc.current_move).__name__ == "NpcRest"


def test_select_move_rests_when_out_of_range_and_no_advance_available():
    """Neither an in-range offensive move nor an Advance move exists ->
    force-rest (lines 87-92), distinct from the in-range-unaffordable path.

    refresh_moves() filters known_moves down to viable() ones, so an
    always-nonviable attack would drop out of available_moves entirely and
    trigger the earlier "no weighted moves" return instead — include a
    viable non-offensive, non-"Advance" move (Idle) to reach the branch
    under test.
    """
    npc = _make_npc()
    attack = moves.NpcAttack(npc)
    attack.category = "Offensive"
    attack.fatigue_cost = 1000  # unaffordable, and never viable (out of range)
    idle = moves.NpcIdle(npc)
    idle.category = "Misc"
    npc.known_moves = [attack, idle]
    npc.fatigue = 10
    npc.maxfatigue = 100
    npc.current_move = None
    with patch.object(attack, "viable", return_value=False), \
         patch.object(idle, "viable", return_value=True):
        npc.select_move()
    assert type(npc.current_move).__name__ == "NpcRest"


def test_select_move_hard_fallback_rests_after_max_attempts():
    npc = _make_npc()
    unaffordable = moves.NpcAttack(npc)
    unaffordable.category = "Offensive"
    unaffordable.fatigue_cost = 5
    unaffordable.weight = 1
    npc.known_moves = [unaffordable]
    npc.fatigue = 100
    npc.maxfatigue = 100
    npc.current_move = None
    # can_attack becomes True (fatigue covers cost, viable True) so the
    # rest-fallback-before-random-pick branch is skipped, but viable() is
    # patched False during the random-pick loop so every attempt fails,
    # exhausting max_attempts and hitting the hard fallback.
    call_count = {"n": 0}

    def _viable():
        call_count["n"] += 1
        # True the first time (satisfies can_attack), False afterwards
        # (forces every random pick attempt to fail).
        return call_count["n"] == 1

    with patch.object(unaffordable, "viable", side_effect=_viable):
        npc.select_move()
    assert type(npc.current_move).__name__ == "NpcRest"


def test_select_move_logs_debug_info_when_debug_manager_enabled():
    npc = _make_npc()
    attack = moves.NpcAttack(npc)
    attack.category = "Offensive"
    attack.fatigue_cost = 1
    attack.weight = 1
    npc.known_moves = [attack]
    npc.fatigue = 100
    npc.maxfatigue = 100
    npc.current_move = None

    player = MagicMock()
    npc.player_ref = player
    debug_manager = MagicMock()
    debug_manager.should_debug_ai_decisions.return_value = True
    player.combat_debug_manager = debug_manager

    ai_config = MagicMock()
    ai_config.get_weighted_move_bonus.return_value = 3
    ai_config.calculate_retreat_priority.return_value = 7
    npc.ai_config = ai_config

    with patch.object(attack, "viable", return_value=True):
        npc.select_move()

    assert npc.current_move is attack
    debug_manager.display_ai_debug_info.assert_called_once()
    args, kwargs = debug_manager.display_ai_debug_info.call_args
    assert args[0] is npc
    assert "Selected" in args[1]
    assert args[2]["ai_bonus"] == 3
    assert args[2]["retreat_priority"] == 7


def test_add_move_appends_and_sets_weight():
    npc = _make_npc()
    npc.known_moves = []
    move = moves.NpcAttack(npc)
    npc.add_move(move, weight=7)
    assert move in npc.known_moves
    assert move.weight == 7


def test_reset_combat_moves_zeroes_stage_and_beats():
    npc = _make_npc()
    move = moves.NpcAttack(npc)
    move.current_stage = 3
    move.beats_left = 5
    npc.known_moves = [move]
    npc.reset_combat_moves()
    assert move.current_stage == 0
    assert move.beats_left == 0


def test_combat_engage_adds_to_lists_and_proximity_with_allies():
    npc = _make_npc()
    player = MagicMock()
    player.combat_list = []
    player.combat_proximity = {}
    ally = MagicMock()
    ally.combat_proximity = {}
    player.combat_list_allies = [ally]

    npc.combat_engage(player)

    assert npc in player.combat_list
    assert npc in player.combat_proximity
    assert npc in ally.combat_proximity
    assert npc.in_combat is True


def test_combat_engage_without_allies():
    npc = _make_npc()
    player = MagicMock()
    player.combat_list = []
    player.combat_proximity = {}
    player.combat_list_allies = []

    npc.combat_engage(player)

    assert npc in player.combat_list
    assert npc.in_combat is True
