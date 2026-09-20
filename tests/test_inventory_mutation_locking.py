"""Regression tests for issue #641 — concurrent inventory/floor mutations.

Production runs gunicorn with ``--worker-class eventlet -w 1``: one process
serves many greenlets concurrently for the SAME session, so two requests
against one ``Player`` object can interleave at any yield point.

A prior diagnosis of this issue (a stale worktree branched before PR #645)
found no lock anywhere in ``game_service.py`` and concluded every mutation
entry point was unprotected. That diagnosis does not hold on this branch:
PR #645 already added ``_LOOT_PHASE_LOCK`` around ``collect_combat_loot``'s
critical section, and #621's tolerance patches
(``functions.remove_by_identity``, ``Item._leave_floor``) already reorder a
floor ``take`` to remove the item from the floor BEFORE appending it to the
inventory, and make a second concurrent removal of the same object a no-op.
Racing a floor ``take`` against ``collect_combat_loot`` the way the stale
fix's test did (pausing ``player.inventory.append`` on its first call)
**passes** against this branch's pre-fix code -- see
``TestTakeViaInteractVsCollect`` below, kept as a passing regression guard
documenting that this specific pairing was already safe.

The still-open gap on this branch is the other seven entry points
(``equip_item``, ``unequip_item``, ``drop_item``, ``shop_buy``,
``shop_sell``, ``shop_buyback``, and the take-via-interact/take-from-
container path through ``_dispatch_interaction``), none of which held any
lock before this fix. ``TestShopBuyRace`` demonstrates the still-open gap
concretely: ``shop_buy`` checks the player's gold and then, in a separate
step, spends it and hands over the item -- a classic TOCTOU. Two concurrent
buys, each affordable alone but not both together, can both pass the gold
check before either debits it, so the player receives a SECOND item for
free. This has nothing to do with the #621 floor/loot tolerance patches;
it is a plain unguarded check-then-act race, and it still reproduces on
this branch's pre-fix code.
"""

import threading

import pytest

from src.api.services.game_service import GameService, _player_mutation_lock
from src.combatant import wire_handle
from src.items import Restorative
from src.inventory_utils import get_gold
from tests._gs_fixtures import live_shop, live_world


@pytest.fixture
def gs():
    return GameService()


def _units(inventory, name):
    """How many objects named ``name`` sit in ``inventory`` — a plain count,
    not a hand-maintained list, so a duplicate entry cannot be miscounted."""
    return sum(1 for item in inventory if getattr(item, "name", None) == name)


class _WeaklyReferenceable:
    """A plain, weakly-referenceable stand-in for a player identity.

    Bare ``object()`` instances cannot hold a weak reference, which
    ``WeakKeyDictionary`` requires -- a real ``Player`` can, so this only
    matters for isolating the lock-selection helper from a full world build.
    """


class TestPlayerMutationLock:
    """The lock-selection helper itself, independent of any call site."""

    def test_same_player_shares_one_lock_across_calls(self):
        player = _WeaklyReferenceable()
        assert _player_mutation_lock(player) is _player_mutation_lock(player)

    def test_different_players_get_different_locks(self):
        lock_a = _player_mutation_lock(_WeaklyReferenceable())
        lock_b = _player_mutation_lock(_WeaklyReferenceable())
        assert lock_a is not lock_b


class TestShopBuyRace:
    """A genuine, still-open race: two concurrent ``shop_buy`` calls sharing
    a gold-sufficiency check that neither's own purchase has debited yet.
    """

    def _priced_shop(self, gold):
        """A merchant selling a Restorative (``value=100``, the class's fixed
        price -- ``get_effective_buy_modifier`` defaults to 1.0, so the shop
        price is that value unmodified) to a player funded with exactly
        ``gold``."""
        stock = Restorative(count=5, merchandise=True)
        player, _game_map, merchant = live_shop(stock=[stock], player_gold=gold)
        return player, merchant

    def test_two_concurrent_buys_of_an_affordable_one_do_not_both_succeed(
        self, gs
    ):
        player, merchant = self._priced_shop(gold=100)
        merchant_id = wire_handle(merchant)

        state = gs.get_shop_state(player, merchant_id)
        assert state["success"] is True, state.get("error")
        stock_entry = state["shop_state"]["stock"][0]
        assert stock_entry["price"] == 100
        item_id = stock_entry["id"]

        entered = threading.Event()
        release = threading.Event()
        paused = {"done": False}

        import src.inventory_utils as inventory_utils

        original_transfer_gold = inventory_utils.transfer_gold

        def paused_transfer_gold(from_inventory, to_inventory, amt):
            if not paused["done"]:
                paused["done"] = True
                entered.set()
                # Bounded: a lock bug should hang the *fix*, not the suite.
                release.wait(timeout=5)
            return original_transfer_gold(from_inventory, to_inventory, amt)

        inventory_utils.transfer_gold = paused_transfer_gold
        try:
            results = {}
            errors = []

            def do_buy(key):
                try:
                    results[key] = gs.shop_buy(player, merchant_id, item_id, 1)
                except Exception as exc:  # pragma: no cover - failure path
                    errors.append((key, exc))

            first = threading.Thread(target=do_buy, args=("first",))
            first.start()
            assert entered.wait(timeout=5), (
                "the first buy never reached the paused gold transfer"
            )

            second = threading.Thread(target=do_buy, args=("second",))
            second.start()
            # Bounded wait, not a sleep-and-hope: give an UNLOCKED second buy
            # (the pre-fix behaviour) generous room to run to completion
            # while the first sits paused -- its real work is arithmetic and
            # list operations, microseconds long, so 0.5s is a large margin.
            # A LOCKED second buy (post-fix) just blocks harmlessly on the
            # lock the first is holding; this join returning with the thread
            # still alive is the expected, correct outcome in that case.
            second.join(timeout=0.5)

            release.set()
            first.join(timeout=5)
            assert not first.is_alive(), "the first buy thread never resumed"
            second.join(timeout=5)
            assert not second.is_alive(), "the second buy thread never returned"
        finally:
            inventory_utils.transfer_gold = original_transfer_gold

        assert errors == [], f"a mutation raised under contention: {errors}"

        first_result = results.get("first")
        second_result = results.get("second")
        assert first_result is not None and second_result is not None

        first_ok = first_result.get("success") is True
        second_ok = second_result.get("success") is True

        # Exactly one of the two 100-gold purchases may succeed against a
        # 100-gold purse; both succeeding is the item-for-free duplication
        # bug, and both failing would mean the lock wrongly refused a
        # legitimately affordable purchase.
        assert first_ok != second_ok, (
            f"exactly one concurrent buy should have succeeded against a "
            f"single-purchase purse — first={first_result!r} "
            f"second={second_result!r}"
        )

        assert get_gold(player.inventory) == 0, (
            f"expected the full 100 gold spent exactly once, found "
            f"{get_gold(player.inventory)} gold left"
        )
        assert _units(player.inventory, "Restorative") == 1, (
            f"expected exactly one Restorative purchased, found "
            f"{_units(player.inventory, 'Restorative')} — a concurrent "
            "buy got the second one for free"
        )


class TestTakeViaInteractVsCollect:
    """Documents that this specific pairing (floor ``take`` vs.
    ``collect_combat_loot``) was already race-safe on this branch BEFORE
    this fix, thanks to PR #645's ``_LOOT_PHASE_LOCK`` (now folded into
    ``_player_mutation_lock``) and the #621 tolerance patches. Kept as a
    passing regression guard, not as evidence the whole surface was safe —
    ``TestShopBuyRace`` above is that evidence.
    """

    def test_take_and_collect_never_both_win_the_same_item(
        self, gs, make_weapon
    ):
        player, _game_map = live_world()
        dagger = make_weapon("Dagger")
        player.current_room.items_here.append(dagger)
        dagger_id = wire_handle(dagger)

        player.combat_end_summary = {"status": "victory"}
        player.combat_drops = [{"name": "Dagger", "quantity": 1}]

        entered = threading.Event()
        release = threading.Event()
        paused = {"done": False}
        real_inventory = player.inventory

        class _PausingList(list):
            def append(self, item):
                super().append(item)
                if not paused["done"]:
                    paused["done"] = True
                    entered.set()
                    release.wait(timeout=5)

        pausing_inventory = _PausingList(real_inventory)
        player.inventory = pausing_inventory

        results = {}
        errors = []

        def do_take():
            try:
                results["take"] = gs.interact_with_target(player, dagger_id, "take")
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(("take", exc))

        def do_collect():
            try:
                results["collect"] = gs.collect_combat_loot(player, ["Dagger"])
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(("collect", exc))

        take_thread = threading.Thread(target=do_take)
        take_thread.start()
        assert entered.wait(timeout=5), (
            "the take thread never reached the paused mutation point"
        )

        collect_thread = threading.Thread(target=do_collect)
        collect_thread.start()
        collect_thread.join(timeout=0.5)

        release.set()
        take_thread.join(timeout=5)
        assert not take_thread.is_alive(), "the take thread never resumed"
        collect_thread.join(timeout=5)
        assert not collect_thread.is_alive(), "collect_combat_loot never returned"

        assert errors == [], f"a mutation raised under contention: {errors}"
        assert _units(player.inventory, "Dagger") == 1
        assert dagger not in player.current_room.items_here

        # Whichever call lost the race must say so honestly rather than
        # silently reporting success over nothing.
        take_result = results.get("take")
        collect_result = results.get("collect")
        assert take_result is not None and collect_result is not None
        take_got_it = take_result.get("success") is True and dagger in player.inventory
        collect_got_it = "Dagger" in (collect_result.get("collected") or [])
        assert take_got_it != collect_got_it, (
            f"exactly one of take/collect should have won the dagger — "
            f"take={take_result!r} collect={collect_result!r}"
        )
