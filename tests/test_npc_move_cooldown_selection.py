"""NPC move selection must respect recoil/cooldown stages.

``Move.cast()`` unconditionally resets ``current_stage`` to 0 and ``beats_left``
to the prep count, so any selector that hands back a move still sitting in
recoil or cooldown erases that debt entirely.  Two paths reach that state:

* ``Move.advance``'s interrupt branch (``move.interrupted = True``) drops the
  move straight into stage 3 with ``stage_beat[3]`` beats left and clears
  ``user.current_move`` — the mechanism War Cry and the player's ``Disrupt``
  are both built on.  Disrupt's entire payoff is that a cancelled wind-up
  costs the enemy its cooldown, so a re-castable cooling move makes the cancel
  nearly free for the enemy.
* The ordinary end of a move: ``advance`` detaches ``user.current_move`` when
  the move enters stage 3, which is exactly when the NPC is invited to choose
  again.

These tests pin both, plus the fallback that keeps an NPC whose entire kit is
cooling from standing still.
"""

import random

import pytest

import src.moves as moves  # type: ignore
from src.combatant import (
    MOVE_STAGE_COOLDOWN,
    MOVE_STAGE_EXECUTE,
    MOVE_STAGE_PREP,
    MOVE_STAGE_RECOIL,
)
from src.narration import capture_narration
from src.npc import NPC, TalusHound
from src.player import Player


def _arena(npc):
    """Wire `npc` into a minimal one-on-one combat against a real Player."""
    player = Player()
    npc.target = player
    npc.player_ref = player
    npc.in_combat = True
    npc.combat_proximity = {player: 1}
    player.combat_proximity = {npc: 1}
    # Fatigue is deliberately bottomless: these tests are about cooldowns, and
    # the fatigue-driven rest fallback would otherwise mask the behaviour.
    npc.maxfatigue = 1000
    npc.fatigue = 1000
    npc.current_move = None
    return player


def _slam_npc():
    """An NPC whose only move is Seismic Slam (prep 4 / exec 1 / recoil 6 / cd 8)."""
    npc = NPC(
        name="Cooldown Foe",
        description="A test foe",
        damage=10,
        aggro=True,
        exp_award=5,
        maxhp=60,
    )
    npc.known_moves = []
    player = _arena(npc)
    slam = moves.SeismicSlam(npc)
    npc.add_move(slam, 10)
    return player, npc, slam


def _advance_one_beat(npc):
    """Tick every move the NPC owns, the way ApiCombatAdapter._process_npc does."""
    to_advance = list(npc.known_moves)
    if npc.current_move is not None and npc.current_move not in to_advance:
        to_advance.append(npc.current_move)
    for move in to_advance:
        move.advance(npc)


@pytest.fixture(autouse=True)
def _quiet():
    """Move casts and executes narrate; keep the suite output clean."""
    with capture_narration():
        yield


class TestInterruptedMovePaysItsCooldown:
    def test_interrupted_move_is_not_reselectable_until_cooldown_drains(self):
        _, npc, slam = _slam_npc()

        npc.select_move()
        assert npc.current_move is slam
        npc.current_move.cast()
        assert slam.current_stage == MOVE_STAGE_PREP

        # Exactly what Disrupt._reward_read / WarCry do to a winding move.
        slam.interrupted = True
        slam.advance(npc)

        assert slam.current_stage == MOVE_STAGE_COOLDOWN
        assert slam.beats_left == slam.stage_beat[3]
        assert npc.current_move is None

        # Offer the NPC a fresh choice on *every* beat the cooldown is
        # outstanding. It must never take the move it still owes for.
        beats_waited = 0
        while slam.current_stage == MOVE_STAGE_COOLDOWN and beats_waited < 50:
            npc.current_move = None
            npc.select_move()
            assert npc.current_move is not slam, (
                f"Seismic Slam re-selected after {beats_waited} beat(s) of an "
                f"{slam.stage_beat[3]}-beat cooldown"
            )
            _advance_one_beat(npc)
            beats_waited += 1

        assert beats_waited >= slam.stage_beat[3], (
            "cooldown ended early: waited "
            f"{beats_waited} beats for a {slam.stage_beat[3]}-beat cooldown"
        )

    def test_move_becomes_selectable_again_once_the_cooldown_has_drained(self):
        """The filter must not be a one-way door."""
        _, npc, slam = _slam_npc()

        npc.select_move()
        npc.current_move.cast()
        slam.interrupted = True
        slam.advance(npc)

        for _ in range(60):
            npc.current_move = None
            _advance_one_beat(npc)
            if slam.current_stage == MOVE_STAGE_PREP:
                break
        assert slam.current_stage == MOVE_STAGE_PREP

        npc.current_move = None
        npc.select_move()
        assert npc.current_move is slam

    def test_ordinary_cooldown_is_paid_too(self):
        """Not just interrupts: advance() detaches current_move on entering
        stage 3, which is precisely when the NPC gets to pick again."""
        _, npc, slam = _slam_npc()

        recast_while_cooling = False
        for _ in range(40):
            if npc.current_move is None:
                cooling = slam.current_stage == MOVE_STAGE_COOLDOWN
                npc.select_move()
                if npc.current_move is not None:
                    if cooling and npc.current_move is slam:
                        recast_while_cooling = True
                    npc.current_move.cast()
            _advance_one_beat(npc)

        assert not recast_while_cooling


class TestRefreshMovesFilter:
    def test_refresh_moves_drops_aftermath_stages_only(self):
        _, npc, slam = _slam_npc()

        for stage in (MOVE_STAGE_PREP, MOVE_STAGE_EXECUTE):
            slam.current_stage = stage
            assert slam in npc.refresh_moves(), f"stage {stage} should stay selectable"

        for stage in (MOVE_STAGE_RECOIL, MOVE_STAGE_COOLDOWN):
            slam.current_stage = stage
            assert slam not in npc.refresh_moves(), f"stage {stage} should be filtered"

    def test_a_move_with_no_stage_attribute_is_treated_as_ready(self):
        """Test doubles built via __new__ never ran Move.__init__; a missing
        current_stage must not silently delete the move from selection."""
        _, npc, slam = _slam_npc()
        del slam.current_stage
        assert slam in npc.refresh_moves()


class TestFallbackWhenEverythingIsCooling:
    def test_npc_rests_rather_than_stalling_when_every_move_is_cooling(self):
        _, npc, slam = _slam_npc()
        slam.current_stage = MOVE_STAGE_COOLDOWN
        slam.beats_left = 5
        npc.current_move = None

        npc.select_move()

        assert npc.current_move is not None, "NPC froze instead of resting"
        assert type(npc.current_move).__name__ == "NpcRest"

    def test_rest_fallback_is_a_fresh_move_so_it_can_never_be_filtered(self):
        """The fallback must not be drawn from known_moves — otherwise the
        rest itself could be cooling and the NPC would stall anyway."""
        _, npc, slam = _slam_npc()
        slam.current_stage = MOVE_STAGE_COOLDOWN
        npc.current_move = None
        npc.select_move()
        assert npc.current_move not in npc.known_moves

    def test_npc_with_no_moves_at_all_still_no_ops(self):
        """Unchanged contract: nothing to wait out means nothing to do."""
        _, npc, _ = _slam_npc()
        npc.known_moves = []
        npc.current_move = None
        assert npc.select_move() is None
        assert npc.current_move is None


class TestTalusHoundOverride:
    """TalusHound overrides select_move and rebuilds the weighted bag itself."""

    def _hound(self):
        hound = TalusHound()
        player = _arena(hound)
        return player, hound

    def test_hound_never_selects_a_cooling_move(self):
        random.seed(1234)
        _, hound = self._hound()

        cooling = [m for m in hound.known_moves if m.name in ("Dodge", "Withdraw")]
        assert cooling, "expected the hound to know Dodge/Withdraw"
        for move in cooling:
            move.current_stage = MOVE_STAGE_COOLDOWN
            move.beats_left = 3

        for _ in range(200):
            hound.current_move = None
            hound.select_move()
            assert hound.current_move not in cooling

    def test_hound_rests_when_its_whole_kit_is_cooling(self):
        _, hound = self._hound()
        for move in hound.known_moves:
            move.current_stage = MOVE_STAGE_COOLDOWN
            move.beats_left = 4
        hound.current_move = None

        hound.select_move()

        assert hound.current_move is not None, "hound froze instead of resting"
        assert type(hound.current_move).__name__ == "NpcRest"

    def test_hound_still_acts_normally_with_a_ready_kit(self):
        random.seed(99)
        _, hound = self._hound()
        hound.current_move = None
        hound.select_move()
        assert hound.current_move is not None
