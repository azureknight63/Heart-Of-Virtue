"""Regression tests for issue #610 — the victory that never resolves.

Defect 1
    ``player.combat_end_summary`` is written by
    ``ApiCombatAdapter._handle_victory`` and was never cleared when the player
    resolved the victory. ``get_combat_state`` re-emits it on every poll while
    ``in_combat`` is False, so the only thing suppressing a repeat of the
    VICTORY dialog was the client's in-memory ``lastEndStateId`` — which a page
    reload resets by design (issue #116). The dialog therefore came back on
    every reload, and ``GamePage`` pins the Combat screen while it is pending.

Defect 2
    ``GameService.collect_combat_loot`` looked for the drops on
    ``player.current_room`` — not the tile the fight ended on, and ``None`` for
    a player who has not moved since the session began. Either way it then
    wiped ``combat_drops`` and reported ``success: True``, so the loot flow
    could never deliver those items again and nothing said where they went.

Everything here runs on real engine objects: a real ``Player``, a real
``Universe``/``MapTile`` graph, a real ``Slime`` rolling its own loot table
(which is what both spawns the item on the tile and records ``combat_drops``),
and the real ``ApiCombatAdapter`` settling the victory. Expectations are read
back out of engine state rather than restating the implementation.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.api.combat_adapter import ApiCombatAdapter
from src.npc import Slime


#: A loot-table entry with a 100% chance and a fixed quantity, so ``roll_loot``
#: is deterministic without patching ``random`` (``randomize_amount("1")`` is
#: plain ``int("1")``; the chance test is ``100 >= randint(0, 100)``).
_CERTAIN_LOOT = {"Restorative": {"chance": 100, "qty": 1}}


@pytest.fixture
def won_fight(make_world, grid_3x3):
    """Factory for a just-won fight, settled by the real adapter.

    ``won_fight()`` — Jean knows which room he is standing in, the normal case.
    ``won_fight(player_knows_the_room=False)`` — ``player.current_room`` is
    ``None`` throughout, which is what a fight started by a starting-tile event
    on a fresh session looks like: session creation never assigns
    ``current_room`` (``src/player/__init__.py`` initialises it to ``None``).
    """

    def _build(player_knows_the_room=True):
        jean, game_map = make_world(grid_3x3)
        fight_tile = game_map[(0, 0)]

        jean.known_moves = []
        jean.combat_log = []
        jean.last_move_summary = ""
        jean.combat_beat = 1
        jean.combat_list = []
        jean.combat_list_allies = [jean]
        jean.combat_proximity = {}
        jean.combat_exp = {}
        jean.combat_drops = []
        jean.in_combat = True
        with patch("src.api.combat_adapter.CombatStrategist"):
            jean._combat_adapter = ApiCombatAdapter(jean)

        # A real NPC rolling a real loot table: this both spawns the item onto
        # the tile and appends the ``combat_drops`` entry the loot dialog reads.
        slime = Slime()
        slime.loot = dict(_CERTAIN_LOOT)
        slime.current_room = fight_tile
        slime.player_ref = jean
        slime.roll_loot()

        drop_names = sorted({d["name"] for d in jean.combat_drops})
        assert drop_names, "fixture must produce at least one drop"
        assert [
            i for i in fight_tile.items_here if i.name in drop_names
        ], "the rolled loot must actually be on the tile"

        jean.current_room = fight_tile if player_knows_the_room else None
        jean._combat_adapter._handle_victory()

        return SimpleNamespace(
            player=jean,
            game_map=game_map,
            fight_tile=fight_tile,
            adapter=jean._combat_adapter,
            drop_names=drop_names,
        )

    return _build


class TestResolvingAVictoryClearsTheEndSummary:
    """Collecting (or skipping) the loot is the victory's resolve signal.

    Until it arrives, ``get_combat_state`` must keep emitting ``end_state`` —
    that is what lets a player who reloads mid-dialog still see the result
    (issue #116). Once it arrives, the summary must be gone, or the same
    ``end_state`` is served forever and every reload re-opens the dialog.
    """

    def test_end_state_is_emitted_until_the_victory_is_resolved(self, won_fight):
        fight = won_fight()

        state = fight.adapter.get_combat_state()

        assert state["combat_active"] is False
        assert state["end_state"]["status"] == "victory"
        assert [d["name"] for d in state["end_state"]["items_dropped"]] == (
            fight.drop_names
        )

    def test_collecting_the_loot_stops_the_end_state_being_re_emitted(
        self, won_fight, game_service
    ):
        fight = won_fight()
        assert "end_state" in fight.adapter.get_combat_state()

        result = game_service.collect_combat_loot(fight.player, fight.drop_names)

        assert result["collected"] == fight.drop_names
        assert not getattr(fight.player, "combat_end_summary", None)
        assert "end_state" not in fight.adapter.get_combat_state()

    def test_skipping_the_loot_also_resolves_the_victory(
        self, won_fight, game_service
    ):
        """SKIP leaves the items on the floor but still ends the victory.

        ``GamePage.handleSkipLoot`` posts an empty selection; that request is
        the only resolve signal the no-loot and skip paths have.
        """
        fight = won_fight()

        game_service.collect_combat_loot(fight.player, [])

        assert [
            i for i in fight.fight_tile.items_here if i.name in fight.drop_names
        ], "skipped loot stays on the tile"
        assert not getattr(fight.player, "combat_end_summary", None)
        assert "end_state" not in fight.adapter.get_combat_state()


def _drops_on(tile, names):
    return [i for i in tile.items_here if i.name in names]


class TestLootIsCollectedFromTheTileTheFightEndedOn:
    """The drops lie where the fight was fought, wherever Jean is now."""

    def test_loot_is_collected_after_the_player_has_moved_on(
        self, won_fight, game_service
    ):
        fight = won_fight()
        moved = game_service.move_player(fight.player, "east")
        assert "error" not in moved, moved
        assert fight.player.current_room is not fight.fight_tile

        result = game_service.collect_combat_loot(fight.player, fight.drop_names)

        assert result["success"] is True
        assert result["collected"] == fight.drop_names
        assert not _drops_on(fight.fight_tile, fight.drop_names)
        assert _drops_on(
            SimpleNamespace(items_here=fight.player.inventory), fight.drop_names
        )

    def test_loot_is_collected_when_the_player_has_no_current_room(
        self, won_fight, game_service
    ):
        """A fight on the spawn tile of a fresh session.

        Session creation never assigns ``current_room``, so both it and the
        adapter's victory-time snapshot of it are ``None``. Every path that
        relocates the player also assigns ``current_room``, so while it is
        still ``None`` the player's coordinates are the tile they spawned on —
        which is where they fought.
        """
        fight = won_fight(player_knows_the_room=False)

        result = game_service.collect_combat_loot(fight.player, fight.drop_names)

        assert result["success"] is True
        assert result["collected"] == fight.drop_names
        assert not _drops_on(fight.fight_tile, fight.drop_names)


class TestAnUnresolvableTileNeverCostsTheLoot:
    """If the fight's tile cannot be found, say so and keep the loot flow alive.

    No real path reaches this once the adapter snapshot, ``current_room`` and
    the player's coordinates are all consulted; it is contrived here by giving
    the player coordinates that address no tile. What it pins is the contract:
    a failed lookup is an error, never a silent success that throws the drops
    away.
    """

    @pytest.fixture
    def lost_fight(self, won_fight):
        fight = won_fight(player_knows_the_room=False)
        fight.player.location_x, fight.player.location_y = 99, 99
        return fight

    def test_collecting_is_an_error_that_keeps_the_drops(
        self, lost_fight, game_service
    ):
        drops_before = list(lost_fight.player.combat_drops)

        result = game_service.collect_combat_loot(
            lost_fight.player, lost_fight.drop_names
        )

        assert result["success"] is False
        assert result["error"]
        assert lost_fight.player.combat_drops == drops_before
        assert _drops_on(lost_fight.fight_tile, lost_fight.drop_names)

    def test_a_failed_collect_does_not_resolve_the_victory(
        self, lost_fight, game_service
    ):
        """The player must still be able to retry, or skip."""
        game_service.collect_combat_loot(lost_fight.player, lost_fight.drop_names)

        assert lost_fight.player.combat_end_summary
        assert "end_state" in lost_fight.adapter.get_combat_state()

    def test_skipping_needs_no_tile(self, lost_fight, game_service):
        """An empty selection picks nothing up, so it can always resolve."""
        result = game_service.collect_combat_loot(lost_fight.player, [])

        assert result == {"success": True, "collected": [], "skipped": []}
        assert "end_state" not in lost_fight.adapter.get_combat_state()
