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


def _named(items, names):
    """The items in ``items`` whose engine name is one of ``names``."""
    return [i for i in items if i.name in names]


@pytest.fixture
def won_fight(make_world, grid_3x3):
    """Factory for a just-won fight, settled by the real adapter.

    ``won_fight()`` — Jean knows which room he is standing in, the normal case.
    ``won_fight(player_knows_the_room=False)`` — ``player.current_room`` is
    ``None`` throughout. No real fight ends that way (``check_for_combat``
    reads ``current_room`` and ``start_combat`` sets it); this drives the
    defensive coordinate fallback in ``GameService._loot_tile`` directly.
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
        assert _named(
            fight_tile.items_here, drop_names
        ), "the rolled loot must actually be on the tile"

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

        assert _named(
            fight.fight_tile.items_here, fight.drop_names
        ), "skipped loot stays on the tile"
        assert not getattr(fight.player, "combat_end_summary", None)
        assert "end_state" not in fight.adapter.get_combat_state()


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
        assert not _named(fight.fight_tile.items_here, fight.drop_names)
        assert _named(fight.player.inventory, fight.drop_names)

    def test_loot_is_collected_when_the_player_has_no_current_room(
        self, won_fight, game_service
    ):
        """The defensive fallback: with ``current_room`` and the adapter's
        snapshot of it both ``None``, the tile at the player's coordinates.

        No real fight ends this way — ``check_for_combat`` reads
        ``current_room`` and ``start_combat`` sets it — but a lookup that can
        find the drops should, and what it may hand out is bounded by
        ``combat_drops`` either way.
        """
        fight = won_fight(player_knows_the_room=False)

        result = game_service.collect_combat_loot(fight.player, fight.drop_names)

        assert result["success"] is True
        assert result["collected"] == fight.drop_names
        assert not _named(fight.fight_tile.items_here, fight.drop_names)


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
        assert _named(lost_fight.fight_tile.items_here, lost_fight.drop_names)

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


def _spawned(tile, item_type, amt=1):
    """Spawn ``amt`` of ``item_type`` on ``tile`` and return what landed.

    Returned rather than re-derived by name, so a test holds the exact objects
    it placed and the item's name comes from the engine, not from the test.
    """
    before = list(tile.items_here)
    tile.spawn_item(item_type, amt=amt)
    return [i for i in tile.items_here if i not in before]


class TestOnlyThisFightsDropsCanBeCollected:
    """The client names what to collect; the engine decides what may be taken.

    ``collect-loot`` takes the item names from the request, and the fix for
    Defect 2 made it look on the fight's tile rather than where Jean stands.
    Without a check against what the fight actually dropped, that turned the
    endpoint into a remote pickup: any item named in a request, lying on the
    last tile a fight was won on, from anywhere, for as long as the snapshot
    lasted. The offer is ``player.combat_drops`` — written only by a dying
    enemy and cleared when the victory resolves — so it is the authority here.
    """

    def test_an_item_the_fight_did_not_drop_is_left_on_the_tile(
        self, won_fight, game_service
    ):
        fight = won_fight()
        (bystander,) = _spawned(fight.fight_tile, "Antidote")
        assert bystander.name not in fight.drop_names

        result = game_service.collect_combat_loot(fight.player, [bystander.name])

        assert bystander in fight.fight_tile.items_here
        assert bystander not in fight.player.inventory
        assert result["collected"] == []
        assert result["skipped"] == [{"name": bystander.name, "reason": "not_offered"}]

    def test_a_replayed_collect_takes_nothing(self, won_fight, game_service):
        """Once the victory resolves there is nothing on offer, so a second
        request for the same names cannot empty the tile again."""
        fight = won_fight()
        game_service.collect_combat_loot(fight.player, fight.drop_names)
        (second,) = _spawned(fight.fight_tile, fight.drop_names[0])

        result = game_service.collect_combat_loot(fight.player, fight.drop_names)

        assert second in fight.fight_tile.items_here
        assert result["collected"] == []

    def test_with_no_fight_nothing_can_be_collected(
        self, make_world, grid_3x3, game_service
    ):
        """No fight, no drops: the endpoint must not double as a pickup that
        skips discovery, hidden-item searches and walking to the item."""
        jean, game_map = make_world(grid_3x3)
        (lying_here,) = _spawned(jean.current_room, "Restorative")
        assert not getattr(jean, "combat_drops", None)

        result = game_service.collect_combat_loot(jean, [lying_here.name])

        assert lying_here in jean.current_room.items_here
        assert result["collected"] == []

    def test_a_drop_takes_only_as_many_objects_as_it_recorded(
        self, won_fight, game_service
    ):
        """One Shortsword dropped; another was already lying on the tile.

        Non-stackable items spawn one object per unit, so the recorded quantity
        bounds how many objects this fight may hand over. Stackable drops merge
        into piles already on the floor and are not bounded here — splitting a
        pile by its recorded share is a separate change.
        """
        fight = won_fight()
        swords = _spawned(fight.fight_tile, "Shortsword", amt=2)
        assert len(swords) == 2, "a non-stackable spawns one object per unit"
        fight.player.combat_drops.append({"name": swords[0].name, "quantity": 1})

        game_service.collect_combat_loot(fight.player, [swords[0].name])

        taken = [s for s in swords if s in fight.player.inventory]
        assert len(taken) == 1


class TestTheOfferEndsWithTheVictory:
    """``combat_drops`` is only an offer while a won fight is unresolved.

    Flee and load clear the summary but used to leave the drops listed, and a
    defeat leaves them too, so the names a fight recorded stayed collectable —
    from whatever tile the player walked to next — long after that fight was
    over.
    """

    @pytest.mark.parametrize(
        "summary",
        [None, {"status": "defeat", "game_over": True}],
        ids=["summary cleared, drops still listed", "defeat"],
    )
    def test_drops_offer_nothing_without_an_unresolved_victory(
        self, won_fight, game_service, summary
    ):
        """Any path that ends the fight some other way than resolving the
        victory -- one that clears only the summary, or a defeat -- must not
        leave the recorded names collectable."""
        fight = won_fight()
        fight.player.combat_end_summary = summary
        assert fight.player.combat_drops, "precondition: the drops are still listed"

        result = game_service.collect_combat_loot(fight.player, fight.drop_names)

        assert result["collected"] == []
        assert _named(fight.fight_tile.items_here, fight.drop_names)

    def test_a_non_stackable_drop_is_the_one_taken_not_an_older_twin(
        self, won_fight, game_service
    ):
        """``spawn_item`` appends, so the fight's own object is the newest of
        its name on the tile; an older same-named one — perhaps a hidden item
        the player never found — is not the fight's to hand over."""
        fight = won_fight()
        (older,) = _spawned(fight.fight_tile, "Shortsword")
        (dropped,) = _spawned(fight.fight_tile, "Shortsword")
        fight.player.combat_drops.append({"name": dropped.name, "quantity": 1})

        game_service.collect_combat_loot(fight.player, [dropped.name])

        assert dropped in fight.player.inventory
        assert older in fight.fight_tile.items_here


class TestOnlyAVictoryIsResolvedByTheLootCall:
    """``collect-loot`` resolves a won fight, and nothing else."""

    def test_a_defeat_summary_survives_a_stray_collect(
        self, won_fight, game_service
    ):
        """A LootDialog left open in a second tab, SKIPped after Jean died in the
        first, must not erase the defeat: it is what the DefeatDialog is built
        from, and defeat resolves only through load or start-over."""
        fight = won_fight()
        defeat = {"status": "defeat", "game_over": True}
        fight.player.combat_end_summary = defeat

        game_service.collect_combat_loot(fight.player, [])

        assert fight.player.combat_end_summary == defeat

    def test_a_collect_during_combat_is_refused_and_keeps_the_drops(
        self, won_fight, game_service
    ):
        """Mid-fight there is no victory to resolve; a request here would
        otherwise wipe the drops gathered so far and leave the summary empty."""
        fight = won_fight()
        fight.player.in_combat = True
        drops_before = list(fight.player.combat_drops)

        result = game_service.collect_combat_loot(fight.player, fight.drop_names)

        assert result["success"] is False
        assert result["error"]
        assert fight.player.combat_drops == drops_before
        assert _named(fight.fight_tile.items_here, fight.drop_names)


def test_each_requested_name_is_handled_once(won_fight, game_service):
    """The name list is client-sized. Answering every repeat rescanned the
    growing ``skipped`` list per name -- 25,000 names took seconds, and a 1 MiB
    body carries far more -- and a repeat can take nothing a first pass did
    not, so each distinct name is handled once."""
    fight = won_fight()
    gone = fight.drop_names[0]
    for item in _named(list(fight.fight_tile.items_here), [gone]):
        fight.fight_tile.items_here.remove(item)

    result = game_service.collect_combat_loot(
        fight.player, ["", "", gone, gone, ""]
    )

    assert result["skipped"] == [
        {"name": "", "reason": "not_offered"},
        {"name": gone, "reason": "not_found"},
    ]
