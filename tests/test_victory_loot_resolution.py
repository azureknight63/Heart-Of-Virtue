"""Regression tests for issues #610 and #621 — what a won fight hands over.

#610 (below) bounded the offer to the names the fight recorded. #621 is the
other half: a name is not an identity. ``TestADropIsTheObjectTheFightSpawned``
covers it.

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

import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.api.combat_adapter import ApiCombatAdapter
from src.api.services.game_service import GameService
from src.combatant import index_by_handle, wire_handle
from src.items import Restorative
from src.npc import Slime


#: A loot-table entry with a 100% chance and a fixed quantity, so ``roll_loot``
#: is deterministic without patching ``random`` (``randomize_amount("1")`` is
#: plain ``int("1")``; the chance test is ``100 >= randint(0, 100)``).
_CERTAIN_LOOT = {"Restorative": {"chance": 100, "qty": 1}}

#: The same certainty for a NON-stackable drop: ``Shortsword`` has no ``count``,
#: so it spawns one object per unit and never merges with anything.
_CERTAIN_SWORD = {"Shortsword": {"chance": 100, "qty": 1}}


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
    ``won_fight(loot=...)`` — a different loot table for the dying enemy.
    ``won_fight(before_the_kill=fn)`` — ``fn(tile)`` runs with the fight tile
    as it was BEFORE the enemy died, for tests that need something already
    lying there when the drop lands (#621).
    """

    def _build(player_knows_the_room=True, loot=None, before_the_kill=None):
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

        if before_the_kill is not None:
            before_the_kill(fight_tile)

        # A real NPC dying over a real loot table: this both spawns the item
        # onto the tile and appends the ``combat_drops`` entry the loot dialog
        # reads. ``before_death`` rather than ``roll_loot`` because the whole
        # death sequence -- the roll, the inventory scatter and the stacking
        # pass that follows them -- is what decides which objects exist to be
        # collected (#621).
        slime = Slime()
        slime.loot = dict(_CERTAIN_LOOT if loot is None else loot)
        slime.current_room = fight_tile
        slime.player_ref = jean
        slime.before_death()

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
    # By identity, not ``in`` (which compares with ``==``): an equal twin
    # already on the floor must not hide the object that just landed.
    before = {id(i) for i in tile.items_here}
    tile.spawn_item(item_type, amt=amt)
    return [i for i in tile.items_here if id(i) not in before]


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


def _units(items, name):
    """How many units of ``name`` sit in ``items``, counting stack sizes."""
    return sum(int(getattr(i, "count", 1) or 1) for i in items if i.name == name)


class TestADropIsTheObjectTheFightSpawned:
    """Issue #621: a name is not an identity.

    #610 bounded the offer to the names the fight recorded, and resolved those
    names against the tile newest-first. Newest-of-that-name is a guess, and it
    is wrong in every case where the fight's own object is no longer the newest
    one: something else of that name landed afterwards, the player picked the
    drop up by hand first, or the drop was merged into a pile that was already
    lying there. Each of those hands over an object the fight never dropped --
    at worst a hidden one the player never found.

    The offer therefore records ``wire_handle`` for every object a drop
    spawned, and the collect resolves those handles (``src/npc/_loot.py``,
    ``GameService._take_offered_drops``).
    """

    def test_something_dropped_afterwards_is_not_mistaken_for_the_loot(
        self, won_fight, game_service
    ):
        """Two Shortswords dropped; a third lands on the tile before Jean
        collects, so the fight's own pair is no longer the newest of its name.

        ``Tile.spawn_item`` returns only the first object it creates, so a drop
        of two is exactly the case an identity record is most likely to miss.
        """
        fight = won_fight(loot={"Shortsword": {"chance": 100, "qty": 2}})
        dropped = _named(fight.fight_tile.items_here, ["Shortsword"])
        assert len(dropped) == 2, "a non-stackable spawns one object per unit"
        (latecomer,) = _spawned(fight.fight_tile, "Shortsword")

        result = game_service.collect_combat_loot(fight.player, ["Shortsword"])

        assert result["collected"] == ["Shortsword", "Shortsword"]
        assert all(sword in fight.player.inventory for sword in dropped)
        assert latecomer in fight.fight_tile.items_here
        assert latecomer not in fight.player.inventory

    def test_taking_the_drop_by_hand_leaves_every_twin_alone(
        self, won_fight, game_service
    ):
        """Jean takes the dropped Shortsword with an ordinary ``take``, then
        collects. The fight's object is already in his pack, so there is
        nothing left for the offer to hand over -- and the hidden twin beside
        it, which he never found, is no substitute.

        ``Item.take`` is the engine method the API dispatches the ``take`` verb
        to (``GameService._call_interaction_handler``).
        """
        stash = []
        fight = won_fight(
            loot=_CERTAIN_SWORD,
            before_the_kill=lambda tile: stash.append(
                tile.spawn_item("Shortsword", hidden=True, hfactor=90)
            ),
        )
        (twin,) = stash
        (dropped,) = [
            i
            for i in _named(fight.fight_tile.items_here, ["Shortsword"])
            if i is not twin
        ]

        dropped.take(fight.player)
        result = game_service.collect_combat_loot(fight.player, ["Shortsword"])

        assert dropped in fight.player.inventory, "the ordinary take stands"
        assert twin in fight.fight_tile.items_here
        assert twin not in fight.player.inventory
        assert twin.hidden is True, "a hidden twin stays hidden"
        assert result["collected"] == []
        assert result["skipped"] == [{"name": "Shortsword", "reason": "not_found"}]

    def test_a_drop_beside_a_hidden_pile_hands_over_only_its_own_units(
        self, won_fight, game_service
    ):
        """A hidden stash of three Restoratives is already on the tile when the
        enemy drops one more.

        ``before_death`` used to stack the whole floor, which merged the drop
        into the first pile of its kind -- ignoring ``hidden`` -- so collecting
        the name emptied the stash too. The drop is one unit; one unit is what
        the fight may hand over.
        """
        stash = []
        fight = won_fight(
            before_the_kill=lambda tile: stash.append(
                tile.spawn_item("Restorative", amt=3, hidden=True, hfactor=90)
            ),
        )
        (pile,) = stash
        assert pile.count == 3 and pile.hidden is True
        dropped_units = sum(d["quantity"] for d in fight.player.combat_drops)
        assert dropped_units == 1, "the loot table rolled exactly one"

        result = game_service.collect_combat_loot(fight.player, ["Restorative"])

        assert result["collected"] == ["Restorative"]
        assert _units(fight.player.inventory, "Restorative") == dropped_units
        assert pile in fight.fight_tile.items_here, "the stash stays on the floor"
        assert pile.count == 3, "and keeps every unit it had"
        assert pile.hidden is True, "and stays hidden"

    def test_a_later_pickup_cannot_fold_the_drop_into_the_hidden_pile(
        self, won_fight, game_service
    ):
        """Every ordinary pickup restacks the floor it was taken from
        (``Item.take`` -> ``MapTile.stack_duplicate_items``), so keeping the
        death's own stacking pass off the hidden stash is not enough on its
        own: picking up anything at all on the fight's tile used to fold the
        visible drop into that stash, where it was neither collectable nor
        visible.
        """
        stash = []
        fight = won_fight(
            before_the_kill=lambda tile: stash.append(
                tile.spawn_item("Restorative", amt=3, hidden=True, hfactor=90)
            ),
        )
        (pile,) = stash
        (bait,) = _spawned(fight.fight_tile, "Antidote")

        bait.take(fight.player)  # any pickup at all restacks this floor
        result = game_service.collect_combat_loot(fight.player, ["Restorative"])

        assert result["collected"] == ["Restorative"]
        assert _units(fight.player.inventory, "Restorative") == 1
        assert pile in fight.fight_tile.items_here
        assert pile.count == 3
        assert pile.hidden is True

    def test_the_resolved_object_leaves_the_tile_not_an_equal_one(self):
        """Resolving by handle and then removing by equality is not identity.

        ``list.remove`` compares with ``==``. No ``Item`` defines ``__eq__``
        today, so this is a guard rather than a live bug — but the day one
        does, "remove the object we resolved" would quietly take the first
        equal twin instead, which is the whole defect back again through the
        other door. ``find_by_handle`` documents the same trap for
        ``list.index``.
        """

        class _Twin:
            """A pair that compares equal, as a stacked duplicate would."""

            name = "Twin"
            weight = 0.0

            def __eq__(self, other):
                return isinstance(other, _Twin)

            def __hash__(self):
                return hash("Twin")

        older, dropped = _Twin(), _Twin()
        tile = SimpleNamespace(items_here=[older, dropped])
        jean = SimpleNamespace(inventory=[], weight_tolerance=20.0)
        offered = {"Twin": [wire_handle(dropped)]}

        collected, skipped = GameService._take_offered_drops(
            jean, tile, ["Twin"], offered
        )

        assert (collected, skipped) == (["Twin"], [])
        # ``is``, never ``==``: the two compare equal, so an equality
        # assertion here would pass whichever object moved.
        assert len(tile.items_here) == 1 and tile.items_here[0] is older
        assert len(jean.inventory) == 1 and jean.inventory[0] is dropped

    def test_one_deaths_own_drops_still_merge_into_a_single_pile(
        self, make_world, grid_3x3
    ):
        """The stacking pass in ``before_death`` is narrowed, not deleted.

        It was added so that one death's several drops of a kind arrive as one
        pile rather than several (commit 2d0f625, "items dropped by enemies now
        stack immediately after NPC death"). That still holds; only merging
        into what was already lying there stops.
        """
        _jean, game_map = make_world(grid_3x3)
        tile = game_map[(0, 0)]
        slime = Slime()
        slime.loot = {}  # the inventory scatter is the path under test
        slime.current_room = tile
        slime.inventory = [Restorative(count=2), Restorative(count=3)]

        # drop_inventory rolls per unit for survival; 0.0 keeps every one.
        with patch("random.random", return_value=0.0):
            slime.before_death()

        piles = [i for i in tile.items_here if i.name == "Restorative"]
        assert len(piles) == 1, "two scattered rows, one pile"
        assert piles[0].count == 5
        assert piles[0].hidden is True, "scattered inventory is hidden, as before"


class TestTwoCollectsInFlight:
    """Two requests for one victory must not both be served the offer.

    The offer is withdrawn as soon as it is read, but under the threaded
    Socket.IO server a second collect can read it before the first clears it
    (#621). Both requests then believe they may take the same objects.
    """

    def test_only_one_of_two_concurrent_collects_is_served(
        self, won_fight, game_service
    ):
        """Forced interleave: the first collect is held inside the offer read
        while the second one runs at it.

        Not a probabilistic race hunt -- the pause makes the losing order the
        only order. With the read-and-withdraw serialized, the second request
        cannot reach the read at all until the first has finished with it.
        """
        fight = won_fight(loot=_CERTAIN_SWORD)
        offers_seen = []
        results = []
        first_is_reading = threading.Event()
        second_has_started = threading.Event()
        original = GameService._offered_drops.__func__

        def held_open(cls, player):
            offer = original(cls, player)
            offers_seen.append(dict(offer))
            if not first_is_reading.is_set():
                first_is_reading.set()
                # Hand the window to the second request, and hold it open long
                # enough for that request to reach the read it must not make.
                second_has_started.wait(2.0)
                time.sleep(0.1)
            return offer

        def collect():
            results.append(
                game_service.collect_combat_loot(fight.player, ["Shortsword"])
            )

        def second():
            assert first_is_reading.wait(2.0), "the first collect never read the offer"
            second_has_started.set()
            collect()

        with patch.object(GameService, "_offered_drops", classmethod(held_open)):
            threads = [
                threading.Thread(target=collect),
                threading.Thread(target=second),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(10)
            assert not any(t.is_alive() for t in threads), "a collect never returned"

        assert [bool(offer) for offer in offers_seen] == [True, False]
        assert sorted(r["collected"] for r in results) == [[], ["Shortsword"]]
        assert _units(fight.player.inventory, "Shortsword") == 1


class TestTheFightTileHoldsStillWhileTheVictoryIsOpen:
    """Issue #621's residual, decided 2026-09-19: floor merges on the fight's
    tile are frozen until the victory is resolved.

    ``MapTile.stack_duplicate_items`` keeps the OLDER pile and folds the newer
    into it, and it runs after every ordinary pickup and stack drop. With a
    visible pile of the drop's kind already lying there, one pickup folded the
    drop away (collect then answered ``not_found``: too little); with Jean's
    own units dropped there afterwards, they folded INTO the drop (collect
    handed them over as loot: too much). Freezing the tile closes both.
    """

    def _with_a_visible_pile(self, won_fight, count=3):
        stash = []
        fight = won_fight(
            before_the_kill=lambda tile: stash.append(
                tile.spawn_item("Restorative", amt=count)
            ),
        )
        (pile,) = stash
        assert pile.hidden is False and pile.count == count
        return fight, pile

    def test_a_pickup_cannot_fold_the_drop_into_an_older_visible_pile(
        self, won_fight, game_service
    ):
        """Too little: the residual as reported."""
        fight, pile = self._with_a_visible_pile(won_fight)
        (bait,) = _spawned(fight.fight_tile, "Antidote")

        bait.take(fight.player)  # any pickup restacks the floor it came from
        result = game_service.collect_combat_loot(fight.player, ["Restorative"])

        assert result["collected"] == ["Restorative"], result
        assert _units(fight.player.inventory, "Restorative") == 1
        assert pile in fight.fight_tile.items_here and pile.count == 3

    def test_jeans_own_units_cannot_fold_into_the_drop(
        self, won_fight, game_service
    ):
        """Too much: units Jean drops onto the fight tile after the kill land
        newer than the drop, so the drop was the pile they merged INTO."""
        fight = won_fight()
        carried = Restorative(count=3)
        fight.player.inventory.append(carried)

        carried.drop(fight.player, quantity=2)
        result = game_service.collect_combat_loot(fight.player, ["Restorative"])

        assert result["collected"] == ["Restorative"], result
        # One from the loot, one Jean kept in his pack; the two he put down
        # are still on the floor.
        assert _units(fight.player.inventory, "Restorative") == 2
        assert _units(fight.fight_tile.items_here, "Restorative") == 2

    def test_merging_resumes_once_the_victory_is_resolved(
        self, won_fight, game_service
    ):
        """The freeze is derived from the open victory, so resolving it is the
        release -- nothing stored has to be remembered to be cleared."""
        fight, pile = self._with_a_visible_pile(won_fight)
        game_service.collect_combat_loot(fight.player, [])  # skip: resolves
        loose = _spawned(fight.fight_tile, "Restorative")
        (bait,) = _spawned(fight.fight_tile, "Antidote")

        bait.take(fight.player)

        piles = [i for i in fight.fight_tile.items_here if i.name == "Restorative"]
        assert piles == [pile], "the floor restacks again after the victory"
        assert pile.count == 3 + 1 + sum(i.count for i in loose)

    def test_other_tiles_still_merge_while_the_victory_is_open(
        self, won_fight, game_service
    ):
        fight = won_fight()
        elsewhere = fight.game_map[(1, 0)]
        fight.player.current_room = elsewhere
        fight.player.location_x, fight.player.location_y = 1, 0
        first = _spawned(elsewhere, "Restorative")
        second = _spawned(elsewhere, "Restorative")
        (bait,) = _spawned(elsewhere, "Antidote")

        bait.take(fight.player)

        piles = [i for i in elsewhere.items_here if i.name == "Restorative"]
        assert len(piles) == 1 and piles[0] in first + second


class TestNoFloorPilesMoveMidFight:
    """Take and drop are refused while a fight is on (maintainer decision,
    2026-09-19): an enemy's drop is recorded at its death, and a pickup or
    stack drop on that floor before the victory could merge it away before
    the victory's freeze begins."""

    def _mid_fight(self, make_world, grid_3x3):
        jean, game_map = make_world(grid_3x3)
        tile = game_map[(0, 0)]
        jean.in_combat = True
        return jean, tile

    def test_taking_a_floor_item_is_refused(
        self, make_world, grid_3x3, game_service
    ):
        jean, tile = self._mid_fight(make_world, grid_3x3)
        (potion,) = _spawned(tile, "Restorative")

        result = game_service.interact_with_target(
            jean, wire_handle(potion), "take", session_data={}
        )

        assert result["success"] is False, result
        assert potion in tile.items_here and potion not in jean.inventory

    def test_dropping_an_item_is_refused(self, make_world, grid_3x3, game_service):
        jean, tile = self._mid_fight(make_world, grid_3x3)
        carried = Restorative(count=2)
        jean.inventory.append(carried)

        result = game_service.drop_item(jean, carried)

        assert "error" in result, result
        assert carried in jean.inventory and carried not in tile.items_here

    def test_both_are_allowed_once_the_fight_is_over(
        self, make_world, grid_3x3, game_service
    ):
        """Control: the refusal is the fight's, not the verb's."""
        jean, tile = self._mid_fight(make_world, grid_3x3)
        jean.in_combat = False
        (potion,) = _spawned(tile, "Antidote")

        taken = game_service.interact_with_target(
            jean, wire_handle(potion), "take", session_data={}
        )
        dropped = game_service.drop_item(jean, potion)

        assert taken["success"] is True, taken
        assert dropped.get("success") is True, dropped


def test_every_floor_merge_goes_through_the_frozen_gate():
    """``functions.restack_floor`` is where the #621 freeze is checked, so it
    must be the only caller of ``stack_duplicate_items`` in the engine. A new
    call site elsewhere would merge the fight tile's floor around the freeze.
    Derived by AST over the engine, not a hand-kept list of files."""
    import ast

    from tests._source_scan import src_trees

    callers = []
    for source in src_trees():
        parents = {}
        for node in ast.walk(source.tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(source.tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "stack_duplicate_items"
            ):
                owner = node
                while owner is not None and not isinstance(owner, ast.FunctionDef):
                    owner = parents.get(owner)
                callers.append((source.rel_posix, getattr(owner, "name", "<module>")))
    assert callers, "no stack_duplicate_items call found -- the scan is broken"
    assert callers == [("src/functions.py", "restack_floor")], callers


class TestTheCollectRequestIsBoundedAndExact:
    """Scrub findings on the collect path (#621 review)."""

    def test_an_oversized_request_is_refused_before_anything_moves(
        self, won_fight, game_service
    ):
        """The request is client-sized and walked under a process-wide lock,
        so a list longer than any fight's offer is refused up front."""
        fight = won_fight()
        names = [f"name{i}" for i in range(GameService._MAX_LOOT_REQUEST_NAMES + 1)]

        result = game_service.collect_combat_loot(fight.player, names)

        assert result["success"] is False, result
        assert fight.player.combat_drops, "a refused request withdraws nothing"

    def test_the_drop_itself_leaves_even_if_the_floor_shifts_mid_collect(self):
        """Collect looks the drop up, weighs it, then removes it. Take and drop
        do not hold the loot lock, so another request can land an object on
        the floor in between -- and a delete by the looked-up INDEX then took
        the neighbour instead, while the drop was handed over as well."""
        class _Thing:
            name = "Thing"
            weight = 0.0

        neighbour, dropped, latecomer = _Thing(), _Thing(), _Thing()
        tile = SimpleNamespace(items_here=[neighbour, dropped])
        jean = SimpleNamespace(inventory=[], weight_tolerance=20.0)
        offered = {"Thing": [wire_handle(dropped)]}
        real_lookup = index_by_handle

        def a_drop_lands_in_the_window(items, handle):
            found = real_lookup(items, handle)
            items.insert(0, latecomer)
            return found

        with patch("src.api.services.game_service.index_by_handle",
                   a_drop_lands_in_the_window):
            collected, _skipped = GameService._take_offered_drops(
                jean, tile, ["Thing"], offered
            )

        assert collected == ["Thing"]
        assert len(jean.inventory) == 1 and jean.inventory[0] is dropped
        assert not any(i is dropped for i in tile.items_here)
        assert any(i is neighbour for i in tile.items_here)
        assert any(i is latecomer for i in tile.items_here)

    @pytest.mark.parametrize("item_type,count", [("Shortsword", 1), ("Restorative", 2)])
    def test_a_take_that_lost_the_race_does_not_carry_the_item_twice(
        self, make_world, grid_3x3, item_type, count
    ):
        """A take resolved its target, then a collect (which holds the loot
        lock; take does not) moved that very object into the pack. The take
        appended it anyway -- the pack held one object twice, and could sell
        it twice. Pre-existing; the stack take-all path had it too."""
        jean, game_map = make_world(grid_3x3)
        tile = game_map[(0, 0)]
        (item,) = _spawned(tile, item_type, amt=count)
        tile.items_here.remove(item)       # the collect that won the race
        jean.inventory.append(item)

        item.take(jean)

        assert sum(1 for i in jean.inventory if i is item) == 1

