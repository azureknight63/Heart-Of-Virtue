"""Target-validation regression tests for ``ApiCombatAdapter``.

A combat command arrives from the client, so ``target_id`` is untrusted input.
The adapter publishes the legal target set for a move via
``_get_available_targets`` (alive, inside the move's effective ``mvrange``, and
friendly only when the move sets ``accepts_ally_target``) -- but both selection
entry points used to resolve the id against ``combat_list + combat_list_allies``
instead, each with its own copy of the lookup. A crafted ``select_target`` could
therefore land ``Disrupt`` (``mvrange=(0, 5)``, load-bearing per its docstring)
on an enemy 40 tiles away, or on a friendly NPC.

These tests use real ``Player``/``NPC``/``Move``/``ApiCombatAdapter`` objects but
no Flask app, session manager or universe, so they belong in the default tree
rather than ``tests/api/`` -- nothing here mutates the module-level item/merchant
registries that CLAUDE.md keeps full-app session tests out of the default run to
protect. (This mirrors ``tests/test_combat_adapter_coverage.py``.) The real
objects are the point: a mocked combatant answers every attribute the test asks
for, and would happily agree with a wrong ``mvrange`` or a missing
``accepts_ally_target``.
"""

from unittest.mock import patch

import pytest

import src.moves as moves
from src.npc import NPC
from src.api.serializers.combat import CombatantSerializer
from src.combatant import combatant_handle
from tests._combat_fixtures import (
    forced_roll,
    make_adapter,
    make_npc,
    make_player,
    place,
    repair_proximity,
)

#: Disrupt rolls ``random.randint(0, 100)`` in ``src.moves._utility`` against
#: its own ``preview_hit_chance``. Any assertion that a legal target actually
#: took damage must force the roll, or the test fails whenever the dice miss.
_ALWAYS_HITS = dict(value=0, module="src.moves._utility")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _build(move_cls=moves.Disrupt, ally_distance=3):
    """A real fight: two in-range enemies, one far enemy, one ally.

    Two enemies sit inside ``Disrupt``'s ``mvrange`` so the adapter genuinely
    enters ``target_selection`` (a single viable target auto-resolves instead).
    """
    player = make_player(
        weapon="Sword", strength=20, finesse=20, endurance=20, speed=20
    )
    move = move_cls(player)
    player.known_moves = [move]

    near = make_npc(NPC, name="NearEnemy", hp=100, maxhp=100)
    second = make_npc(NPC, name="SecondEnemy", hp=100, maxhp=100)
    far = make_npc(NPC, name="FarEnemy", hp=100, maxhp=100)
    ally = make_npc(NPC, name="Friendly", hp=100, maxhp=100)
    ally.friend = True

    adapter = make_adapter(player, enemies=[near, second, far], allies=[ally])

    place(player, 0, 0)
    place(near, 2, 0)
    place(second, 3, 0)
    place(far, 40, 0)
    place(ally, ally_distance, 0)
    repair_proximity([player, near, second, far, ally])

    return {
        "player": player,
        "adapter": adapter,
        "move": move,
        "near": near,
        "second": second,
        "far": far,
        "ally": ally,
    }


@pytest.fixture
def fight():
    return _build()


def _snapshot(adapter, fight):
    """The state that must survive a rejected target selection untouched."""
    return {
        "awaiting_input": adapter.awaiting_input,
        "input_type": adapter.input_type,
        "pending_move_index": adapter.pending_move_index,
        "options": [o["id"] for o in adapter.available_options],
        "hp": {c["key"]: c["obj"].hp for c in _combatants(fight)},
        "fatigue": fight["player"].fatigue,
        "beat": fight["player"].combat_beat,
    }


def _combatants(fight):
    return [
        {"key": key, "obj": fight[key]}
        for key in ("player", "near", "second", "far", "ally")
    ]


# ---------------------------------------------------------------------------
# The published option set is what makes a target legal
# ---------------------------------------------------------------------------


def test_published_options_exclude_out_of_range_enemy_and_ally(fight):
    """Sanity check on the option set the rejections are measured against."""
    options = fight["adapter"]._get_available_targets(fight["move"])
    names = {o["name"] for o in options}

    assert fight["move"].mvrange == (0, 5)
    assert names == {"NearEnemy", "SecondEnemy"}
    assert getattr(fight["move"], "accepts_ally_target", False) is False


def test_select_target_rejects_out_of_range_enemy(fight):
    adapter, far = fight["adapter"], fight["far"]
    adapter.process_command({"type": "select_move", "move_index": 0})
    assert adapter.input_type == "target_selection"

    result = adapter.process_command(
        {"type": "select_target", "target_id": CombatantSerializer.stream_id(far)}
    )

    assert "error" in result
    assert "not a valid target" in result["error"]
    assert far.hp == 100
    assert fight["move"].target is not far


def test_select_target_rejects_ally_for_move_without_ally_targeting(fight):
    adapter, ally = fight["adapter"], fight["ally"]
    adapter.process_command({"type": "select_move", "move_index": 0})

    result = adapter.process_command(
        {"type": "select_target", "target_id": CombatantSerializer.stream_id(ally)}
    )

    assert "error" in result
    assert ally.hp == 100
    assert fight["move"].target is not ally


def test_combined_selection_rejects_out_of_range_enemy(fight):
    adapter, far = fight["adapter"], fight["far"]

    result = adapter.process_command(
        {
            "type": "select_move_and_target",
            "move_name": "Disrupt",
            "target_id": CombatantSerializer.stream_id(far),
        }
    )

    assert "error" in result
    assert far.hp == 100
    assert adapter.player.current_move is None


def test_combined_selection_rejects_ally(fight):
    adapter, ally = fight["adapter"], fight["ally"]

    result = adapter.process_command(
        {
            "type": "select_move_and_target",
            "move_name": "Disrupt",
            "target_id": CombatantSerializer.stream_id(ally),
        }
    )

    assert "error" in result
    assert ally.hp == 100


# ---------------------------------------------------------------------------
# Rejection must not corrupt combat state
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["far", "ally"])
def test_rejected_target_leaves_combat_state_untouched(fight, bad):
    """No half-applied move, no stale awaiting_input/pending_move_index.

    After a rejection the client must be able to simply re-send a legal target:
    the adapter is still awaiting a target selection for the same pending move,
    with the same option set.
    """
    adapter = fight["adapter"]
    adapter.process_command({"type": "select_move", "move_index": 0})
    before = _snapshot(adapter, fight)

    prefix = "enemy" if bad == "far" else "ally"
    result = adapter.process_command(
        {"type": "select_target", "target_id": f"{prefix}_{combatant_handle(fight[bad])}"}
    )

    assert "error" in result
    assert _snapshot(adapter, fight) == before
    assert before["awaiting_input"] is True
    assert before["input_type"] == "target_selection"
    assert before["pending_move_index"] == 0


def test_client_can_retry_with_a_legal_target_after_rejection(fight):
    adapter, near, far = fight["adapter"], fight["near"], fight["far"]
    adapter.process_command({"type": "select_move", "move_index": 0})
    adapter.process_command(
        {"type": "select_target", "target_id": CombatantSerializer.stream_id(far)}
    )

    with forced_roll(**_ALWAYS_HITS):
        result = adapter.process_command(
            {"type": "select_target", "target_id": CombatantSerializer.stream_id(near)}
        )

    assert "error" not in result
    assert fight["move"].target is near
    assert near.hp < 100
    assert adapter.pending_move_index is None


# ---------------------------------------------------------------------------
# Legitimate flows must keep working
# ---------------------------------------------------------------------------


def test_valid_in_range_enemy_still_resolves(fight):
    adapter, near = fight["adapter"], fight["near"]
    adapter.process_command({"type": "select_move", "move_index": 0})

    with forced_roll(**_ALWAYS_HITS):
        result = adapter.process_command(
            {"type": "select_target", "target_id": CombatantSerializer.stream_id(near)}
        )

    assert "error" not in result
    assert fight["move"].target is near
    assert near.hp < 100


def test_ally_accepted_for_move_that_declares_accepts_ally_target():
    """``Advance`` closes distance on an ally deliberately (e.g. to heal)."""
    fight = _build(move_cls=moves.Advance)
    adapter, ally, move = fight["adapter"], fight["ally"], fight["move"]

    assert move.accepts_ally_target is True
    assert CombatantSerializer.stream_id(ally) in {
        o["id"] for o in adapter._get_available_targets(move)
    }

    result = adapter.process_command(
        {
            "type": "select_move_and_target",
            "move_name": "Advance",
            "target_id": CombatantSerializer.stream_id(ally),
        }
    )

    assert "error" not in result
    assert move.target is ally


def test_unknown_target_id_still_falls_back_to_auto_resolution():
    """An id naming nobody in the fight is not the exploit path.

    It resolves to no combatant at all, so ``_resolve_move_target`` treats it as
    "no explicit target given" exactly as before -- and auto-resolution only
    ever picks from the viable set. Pinned so the strictness added for real-but-
    illegal targets is not quietly widened into a behaviour change here (the
    repeat-last-move flow can carry a stale id).
    """
    fight = _build()
    # Only one enemy in range, so the no-target path auto-resolves.
    place(fight["second"], 40, 0)
    repair_proximity(
        [fight["player"], fight["near"], fight["second"], fight["far"], fight["ally"]]
    )
    adapter = fight["adapter"]

    result = adapter.process_command(
        {
            "type": "select_move_and_target",
            "move_name": "Disrupt",
            "target_id": "enemy_999999999",
        }
    )

    assert "error" not in result
    assert fight["move"].target is fight["near"]


def test_untargeted_move_never_consults_the_target_option_set():
    """A non-targeted move self-targets; validation must not touch it."""
    fight = _build()
    player, adapter = fight["player"], fight["adapter"]
    dodge = moves.Dodge(player)
    dodge.user = player
    player.known_moves = [dodge]
    assert dodge.targeted is False and dodge.viable() is True

    with patch.object(
        adapter,
        "_resolve_target_from_options",
        wraps=adapter._resolve_target_from_options,
    ) as validator:
        result = adapter.process_command(
            {
                "type": "select_move_and_target",
                "move_name": "Dodge",
                "target_id": CombatantSerializer.stream_id(fight['ally']),
            }
        )

    assert "error" not in result
    validator.assert_not_called()
    assert dodge.target is player


# ---------------------------------------------------------------------------
# Move readiness: the same preconditions on both entry points
# ---------------------------------------------------------------------------
#
# ``select_move_and_target`` is what the React client sends for essentially
# every combat action (LeftPanel.jsx, useCombatCoordinator.js), yet it carried
# no ``current_stage`` check -- only ``select_move`` did. Since ``cast()``
# unconditionally resets ``current_stage`` to 0, re-selecting a move that was
# still in recoil or cooldown erased the remainder of its cycle, making every
# move free to spam through the primary UI path. Both entry points now share
# ``_check_move_preconditions``.


def _cooling_dodge():
    """A fight whose only move is a Dodge stuck mid-cooldown."""
    fight = _build()
    player = fight["player"]
    dodge = moves.Dodge(player)
    dodge.user = player
    player.known_moves = [dodge]
    dodge.current_stage = 3  # cooldown
    dodge.beats_left = 2
    fight["move"] = dodge
    return fight


@pytest.mark.parametrize(
    "command",
    [
        {"type": "select_move", "move_index": 0},
        {"type": "select_move_and_target", "move_name": "Dodge"},
    ],
    ids=["select_move", "select_move_and_target"],
)
def test_cooling_move_is_rejected_by_both_entry_points(command):
    fight = _cooling_dodge()
    adapter, dodge, player = fight["adapter"], fight["move"], fight["player"]

    result = adapter.process_command(command)

    assert result.get("error") == "Move not ready yet"
    # The cooldown must survive the rejection -- cast() would have zeroed it.
    assert dodge.current_stage == 3
    assert dodge.beats_left == 2
    assert player.current_move is None
    # ... and the adapter is still cleanly awaiting a fresh move selection.
    assert adapter.awaiting_input is True
    assert adapter.input_type == "move_selection"
    assert adapter.pending_move_index is None


@pytest.mark.parametrize(
    "command",
    [
        {"type": "select_move", "move_index": 0},
        {"type": "select_move_and_target", "move_name": "Dodge"},
    ],
    ids=["select_move", "select_move_and_target"],
)
def test_ready_move_still_works_through_both_entry_points(command):
    fight = _cooling_dodge()
    adapter, dodge, player = fight["adapter"], fight["move"], fight["player"]
    dodge.current_stage = 0
    dodge.beats_left = 0
    assert dodge.viable() is True

    result = adapter.process_command(command)

    assert "error" not in result
    # Dodge resolves inside the beats this request processes, so current_move is
    # already cleared again by the time it returns; the log entry the adapter
    # writes when a move is accepted is the durable evidence it actually ran.
    assert any(
        "Dodge" in entry.get("message", "")
        for entry in getattr(player, "combat_log", [])
    )
