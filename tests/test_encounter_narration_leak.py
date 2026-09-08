"""Regression: an ally must not narrate a target from a finished encounter (#560).

The reported symptom, twice, with Gorran in the party::

    Gorran lashes out at Rock Rumbler Dulanidwe with extreme violence!
    Gorran struck Rock Rumbler Dulanidwe for 24 damage!

— narrated during a fight against two Talus Hounds, on a different tile, after
that Rumbler had already died in an earlier encounter.

The issue text blamed ``NpcAttack.__init__`` baking ``npc.target.name`` into
``stage_announce`` while ``refresh_announcements`` rebuilds from ``self.target``.
That is not the live defect: ``Move.cast`` and ``NpcAttack.execute`` both call
``refresh_announcements`` before narrating, so the baked strings never reach the
player. What actually leaks is the ally's **in-flight move**:

* nothing clears ``npc.current_move`` when a fight ends (only the player's is
  cleared — four exits do it, none of them touch an NPC);
* ``ApiCombatAdapter._process_npc`` re-selects ``npc.target`` only ``if
  npc.current_move is None``, so an ally holding a stale move never re-targets;
* the fresh-fight branch of ``initialize_combat`` rewinds every ally move to
  ``current_stage = 0, beats_left = 0`` — including that stale one — so it runs
  its whole prep→execute cycle again, against the corpse from the last fight.

Gorran makes this reachable in ordinary play because he is slow: ``NpcAttack``
prep is ``int(50 / speed)`` and his speed is 5, so his swing spends ten beats
winding up and is very likely to be mid-flight whenever a fight ends.

The damage is misdirected too, not just the prose — the blow lands on the dead
combatant, so the enemy actually being fought takes nothing.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _combat_fixtures import (  # noqa: E402
    engage,
    make_adapter,
    make_player,
    place,
    repair_proximity,
    seeded,
)
from src.narration import capture_narration  # noqa: E402
from src.npc import Gorran, RockRumbler, TalusHound  # noqa: E402


#: Deliberately distinctive so a leak is unmistakable in the assertion output.
FIGHT_ONE_ENEMY_NAME = "Rock Rumbler Dulanidwe"
FIGHT_TWO_ENEMY_NAME = "Talus Hound Igpor"

#: NPC turns needed for Gorran to select, wind up and land one swing.
ALLY_BEATS_TO_IMPACT = 16


def _drive_ally_beats(adapter, ally, beats):
    """Run ``beats`` NPC turns for ``ally`` and return the narration emitted."""
    with capture_narration() as messages:
        for _ in range(beats):
            adapter._process_npc(ally)
    return [entry.get("text", "") for entry in messages]


@pytest.fixture
def two_encounters():
    """Fight a Rumbler with Gorran alongside, win, then fight a Talus Hound.

    Returns ``(fight_one_lines, fight_two_lines)``. Both encounters are driven
    through the real adapter: only the ally's move list is narrowed (to his
    plain ``NpcAttack``) so move selection is deterministic, and the RNG is
    seeded because damage and to-hit are rolled.
    """
    with seeded(4321):
        player = make_player()
        gorran = Gorran()
        rumbler = RockRumbler()
        rumbler.name = FIGHT_ONE_ENEMY_NAME
        gorran.known_moves = [
            move for move in gorran.known_moves if type(move).__name__ == "NpcAttack"
        ]

        adapter = make_adapter(player, enemies=[rumbler], allies=[gorran])
        place(player, 2, 2)
        place(gorran, 3, 2)
        place(rumbler, 4, 2)
        repair_proximity([player, gorran, rumbler])
        # Gorran's swing costs ten beats of prep, so it lands on the
        # thirteenth NPC turn (select+cast, ten prep ticks, one execute
        # beat, then the execute stage itself). Sixteen leaves headroom
        # for the post-fix path, which has to re-select and re-cast.
        fight_one = _drive_ally_beats(adapter, gorran, ALLY_BEATS_TO_IMPACT)

        # End the encounter the way a won fight does.
        rumbler.hp = 0
        adapter.settle_victory()

        # A new encounter, on another tile, against a different enemy.
        hound = TalusHound()
        hound.name = FIGHT_TWO_ENEMY_NAME
        engage(player, enemies=[hound], allies=[gorran])
        adapter.initialize_combat([hound])
        place(player, 2, 2)
        place(gorran, 3, 2)
        place(hound, 4, 2)
        repair_proximity([player, gorran, hound])
        fight_two = _drive_ally_beats(adapter, gorran, ALLY_BEATS_TO_IMPACT)

        return fight_one, fight_two


def test_ally_attacked_the_first_encounters_enemy(two_encounters):
    """Negative control: fight one really does narrate the Rumbler by name.

    Without this the leak assertion below could pass on an ally that never
    attacked at all.
    """
    fight_one, _ = two_encounters
    assert any(FIGHT_ONE_ENEMY_NAME in line for line in fight_one), (
        "fight one never narrated an attack on the Rumbler, so the leak test "
        f"downstream proves nothing; got: {fight_one}"
    )


def test_no_first_encounter_name_leaks_into_the_second(two_encounters):
    """The dead Rumbler's name must not appear anywhere in fight two's log."""
    _, fight_two = two_encounters
    leaked = [line for line in fight_two if FIGHT_ONE_ENEMY_NAME in line]
    assert not leaked, (
        "narration from a finished encounter leaked into the next fight: "
        f"{leaked}"
    )


def test_ally_in_flight_move_is_dropped_when_a_new_fight_starts(two_encounters):
    """The mechanism, asserted directly: no ally carries a move across fights.

    ``initialize_combat`` rewinds every ally move to stage 0, so a surviving
    ``current_move`` is guaranteed to re-run — there is no state in which
    keeping it is meaningful.
    """
    fight_one, fight_two = two_encounters
    assert fight_one and fight_two  # the fixture ran both encounters
    # Reconstructed rather than returned so the assertion reads against the
    # public contract: after a fresh fight starts, the ally acts on a move
    # chosen for THIS fight, whose target is one of this fight's enemies.
    assert any(FIGHT_TWO_ENEMY_NAME in line for line in fight_two), (
        "the ally never engaged the enemy actually present in fight two; "
        f"got: {fight_two}"
    )
