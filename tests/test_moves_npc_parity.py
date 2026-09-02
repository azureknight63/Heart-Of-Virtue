"""NPC-side parity with the player damage path's hardening.

Two gaps this file pins:

* ``_npc.py`` read ``target.protection`` raw at ~9 sites while every player
  path reads through the sanitising ``target_protection`` — so a degraded
  protection (None, a string, NaN on a crafted save) crashed the NPC's turn
  mid-beat while the player's identical swing degraded gracefully.
* ``Player`` learned to strip the adapter's ``_pending_animation`` channel
  from its pickled state (it holds ``outcome_target`` — a LIVE combatant —
  and drags the enemy's whole object graph into every mid-combat save), but
  NPCs pickle through the ``Combatant`` base with no such strip, and a
  mid-wind-up NPC carries exactly the same channel.
"""

import pathlib
import pickle
import sys
from unittest.mock import MagicMock, patch

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.moves._npc import GorranClub, NpcAttack  # noqa: E402
from src.npc import NPC  # noqa: E402


def _npc(name="Biter", damage=40):
    npc = NPC(
        name=name, description="a test enemy", damage=damage, aggro=50,
        exp_award=1,
    )
    npc.friend = False
    npc.combat_range = (0, 10)
    return npc


def _engage(attacker, target, distance=2):
    attacker.target = target
    attacker.combat_proximity = {target: distance}
    attacker.combat_list = [target]
    target.combat_proximity = {attacker: distance}
    target.combat_list = [attacker]


class TestDegradedProtectionDoesNotCrashTheNpcTurn:
    """The player path sanitises protection through ``target_protection``;
    the NPC path must degrade the same way rather than raising mid-beat."""

    @pytest.mark.parametrize("protection", [None, "rusty", float("nan")])
    def test_npc_attack_survives_a_degraded_target_protection(self, protection):
        attacker = _npc()
        target = _npc(name="Victim")
        target.hp = target.maxhp = 1000
        _engage(attacker, target)
        target.protection = protection

        move = NpcAttack(attacker)
        move.target = target
        move.evaluate()
        before = target.hp
        with patch("random.randint", return_value=0), patch(
            "random.uniform", return_value=1.0
        ), patch("src.functions.check_parry", return_value=False):
            move.execute(attacker)
        # Degraded protection reads as 0: the swing lands for full power.
        assert target.hp < before

    @pytest.mark.parametrize("protection", [None, "rusty", float("nan")])
    def test_gorran_club_survives_a_degraded_target_protection(self, protection):
        attacker = _npc(name="Gorran")
        target = _npc(name="Victim")
        target.hp = target.maxhp = 1000
        _engage(attacker, target)
        target.protection = protection

        move = GorranClub(attacker)
        move.target = target
        move.evaluate()
        before = target.hp
        with patch("random.randint", return_value=0), patch(
            "random.uniform", return_value=1.5
        ), patch("src.functions.check_parry", return_value=False):
            move.execute(attacker)
        assert target.hp < before


class TestNpcFlatDamageHelper:
    """Differential: the extracted flat line must be bit-identical to the
    five copies it replaces, for every well-formed input."""

    def test_matches_the_legacy_line_over_a_wide_grid(self):
        from src.moves._npc import _npc_flat_damage

        powers = [0.0, 0.5, 1.0, 3.7, 12.0, 47.99, 100.0, 512.25]
        protections = [0, 1, 3, 7, 12, 28, 60, 250]
        mismatches = []
        for power in powers:
            for protection in protections:
                target = MagicMock()
                target.protection = protection
                legacy = power - protection
                if legacy <= 0:
                    legacy = 0
                got = _npc_flat_damage(power, target)
                if got != legacy:
                    mismatches.append((power, protection, got, legacy))
        assert not mismatches, mismatches[:5]

    def test_degraded_protection_reads_as_zero(self):
        from src.moves._npc import _npc_flat_damage

        for junk in (None, "rusty", float("nan"), float("inf"), True):
            target = MagicMock()
            target.protection = junk
            assert _npc_flat_damage(10.0, target) == 10.0, junk


class TestPendingAnimationNeverPickles:
    """``_pending_animation`` holds ``outcome_target`` — a live combatant —
    and is transient adapter state the next session rebuilds. Player already
    strips it; a mid-wind-up NPC must too, via the shared Combatant base."""

    def test_npc_getstate_strips_the_channel(self):
        npc = _npc()
        npc._pending_animation = {
            "outcome": "hit",
            "outcome_target": MagicMock(name="live enemy"),
        }
        state = npc.__getstate__()
        assert "_pending_animation" not in state

    def test_npc_pickle_round_trip_drops_the_channel(self):
        npc = _npc()
        victim = _npc(name="Victim")
        npc._pending_animation = {"outcome": "hit", "outcome_target": victim}
        revived = pickle.loads(pickle.dumps(npc))
        assert not hasattr(revived, "_pending_animation")
        assert revived.name == npc.name

    def test_player_override_still_composes(self):
        from src.player import Player

        player = Player()
        player._pending_animation = {"outcome": "hit", "outcome_target": None}
        state = player.__getstate__()
        assert "_pending_animation" not in state
        # The Player-specific exclusions still apply on top of the base's.
        player._combat_adapter = MagicMock()
        assert "_combat_adapter" not in player.__getstate__()

    def test_base_class_strips_reach_player_through_delegation(self, monkeypatch):
        """Player.__getstate__ must delegate to Combatant.__getstate__ rather
        than carry its own copy of the base strip: a new base-class exclusion
        has to reach Player structurally, not by someone remembering to keep
        two pop() lists in agreement."""
        from src.combatant import Combatant
        from src.player import Player

        original = Combatant.__getstate__

        def stripping(self):
            state = original(self)
            state.pop("_sentinel_transient", None)
            return state

        monkeypatch.setattr(Combatant, "__getstate__", stripping)
        player = Player()
        player._sentinel_transient = object()
        assert "_sentinel_transient" not in player.__getstate__()


class TestNpcEvaluateSurvivesADegradedSpeed:
    """Every hostile evaluate() computes ``int(50 / self.user.speed)`` for
    prep and recoil. The player path floors the divisor at 1
    (standard_evaluate_attack); the NPC copies did not, so a zero or NaN
    speed off a crafted save raised ZeroDivisionError/ValueError mid-beat."""

    @pytest.mark.parametrize("speed", [0, float("nan"), float("inf")])
    def test_npc_move_evaluate_floors_the_speed_divisor(self, speed):
        from src.moves._npc import BatBite, SpiderBite, VenomClaw

        for move_cls in (NpcAttack, GorranClub, VenomClaw, SpiderBite, BatBite):
            user = MagicMock()
            user.damage = 10
            user.speed = speed
            user.endurance = 10
            user.combat_range = (0, 5)
            move = move_cls.__new__(move_cls)
            move.user = user
            move.stage_beat = [1, 1, 1, 1]
            move.custom_mvrange = False
            move.mvrange = (0, 5)
            move.evaluate()
            assert move.stage_beat[0] >= 1, (move_cls.__name__, speed)
            assert move.stage_beat[2] >= 0, (move_cls.__name__, speed)
