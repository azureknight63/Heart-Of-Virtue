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


class TestGetShopStateRestockRace:
    """A genuine, still-open race found in a follow-up /review pass on this
    same branch: ``get_shop_state`` (``GET /api/shop/state``, hit whenever a
    client opens or polls a shop) is not covered by ``_player_mutation_lock``
    at all -- unlike ``shop_buy``/``shop_sell``/``shop_buyback`` a few lines
    above it in this same file, which this PR did lock.

    Two symptoms share one cause (the whole method runs unlocked):

    1. A check-then-act TOCTOU on `_reset_stock_state`/`update_goods`: "if
       the shop's non-gold stock is empty, restock it" reads `merchant.
       inventory`, then unconditionally regenerates it. Two concurrent shop
       opens (two tabs, or a client retry racing the original request) can
       both see empty stock and both restock -- `_reset_stock_state` clears
       `merchant.inventory` a second time mid-generation, discarding the
       first call's in-flight work and double-consuming the unique-item
       registry.
    2. `Merchant._collect_player_merchandise` (src/npc/_shop.py) mutates
       `player.inventory` with no lock either -- the same list a concurrent
       take/drop/equip/shop call is mutating under the lock this PR added.

    This test demonstrates (1), the more universally reachable of the two
    (no merchandise item needed -- just two overlapping shop-state reads on
    a shop that hasn't been stocked yet).
    """

    def test_two_concurrent_shop_state_reads_do_not_both_restock(self, gs):
        player, _game_map, merchant = live_shop(stock=None)
        merchant_id = wire_handle(merchant)

        entered = threading.Event()
        release = threading.Event()
        paused = {"done": False}
        call_count = {"n": 0}

        # Patch the whole restock op rather than driving the real
        # always_stock/random-fill machinery (which needs a wired-up
        # `current_room` this fixture doesn't set up): a marker item makes
        # "did this run more than once" directly observable without needing
        # real item spawning, and it still exercises the exact check-then-act
        # shape under test -- `get_shop_state`'s own `non_gold` emptiness
        # check, calling this real attribute, under real concurrency.
        class _RestockMarker:
            name = "RestockMarker"

        def paused_update_goods(self):
            call_count["n"] += 1
            if not paused["done"]:
                paused["done"] = True
                entered.set()
                # Paused BEFORE the marker lands, not after: the real race
                # is in the `non_gold` check each caller makes for itself,
                # which happens before update_goods runs at all -- pausing
                # here (stock still empty) is what lets a second, unlocked
                # caller's own check also see empty and also decide to
                # restock, the same shape TestShopBuyRace uses for gold.
                # Bounded: a lock bug should hang the *fix*, not the suite.
                release.wait(timeout=5)
            self.inventory.append(_RestockMarker())

        original_update_goods = type(merchant).update_goods
        type(merchant).update_goods = paused_update_goods
        try:
            results = {}
            errors = []

            def do_get_state(key):
                try:
                    results[key] = gs.get_shop_state(player, merchant_id)
                except Exception as exc:  # pragma: no cover - failure path
                    errors.append((key, exc))

            first = threading.Thread(target=do_get_state, args=("first",))
            first.start()
            assert entered.wait(timeout=5), (
                "the first get_shop_state call never reached the paused restock"
            )

            second = threading.Thread(target=do_get_state, args=("second",))
            second.start()
            # Bounded wait, not a sleep-and-hope: give an UNLOCKED second call
            # (the pre-fix behaviour) generous room to run its own restock to
            # completion while the first sits paused. A LOCKED second call
            # (post-fix) just blocks harmlessly on the lock the first holds;
            # this join returning with the thread still alive is the
            # expected, correct outcome in that case.
            second.join(timeout=0.5)

            release.set()
            first.join(timeout=5)
            assert not first.is_alive(), "the first call thread never resumed"
            second.join(timeout=5)
            assert not second.is_alive(), "the second call thread never returned"
        finally:
            type(merchant).update_goods = original_update_goods

        assert errors == [], f"a mutation raised under contention: {errors}"
        assert results.get("first") is not None and results.get("second") is not None

        # The empty-stock check should only ever trigger one real restock —
        # a second concurrent read of an already-stocked shop must see that
        # and skip its own, exactly like the check-then-act guard is meant
        # to work when it isn't racing itself.
        assert call_count["n"] == 1, (
            f"update_goods ran {call_count['n']} times for one restock "
            "decision — two concurrent shop-state reads both saw empty stock "
            "and both regenerated it"
        )


class TestUseItemRace:
    """A genuine, still-open race found by the /review skill's adversarial
    subagent pass on this same branch: ``use_item`` (``POST
    /inventory/use``, also the in-combat item-use route per
    ``.claude/rules/combat-engine.md``) delegates to ``item.use()`` with no
    ``_player_mutation_lock`` at all -- unlike the 9 other mutation entry
    points this PR locked.

    ``Restorative.use`` (``src/items.py``) is a plain check-then-act: read
    ``player.hp < player.maxhp``, apply the heal, THEN ``self.count -= 1``,
    THEN ``_user.inventory.remove(self)`` if exhausted -- with no lock and
    no upfront exhaustion guard. Two concurrent uses of a single-count
    Restorative (a double-click, a client retry, a second tab) can both
    pass the health check before either decrements, and when both reach the
    exhausted branch the second ``inventory.remove(self)`` raises an
    uncaught ``ValueError`` -- ``GameService.use_item`` catches nothing
    around ``item.use()`` -- surfacing as an unhandled exception on a
    double-submitted click rather than a clean, idempotent response.
    """

    def test_two_concurrent_uses_of_a_single_count_item_do_not_both_apply(self, gs):
        player, _game_map = live_world()
        player.hp = 50
        player.maxhp = 100
        restorative = Restorative(count=1)
        player.inventory = [restorative]

        entered = threading.Event()
        release = threading.Event()
        paused = {"done": False}

        import src.items as items_module

        original_narrate = items_module.narrate

        def paused_narrate(*args, **kwargs):
            # Fires right after the `player.hp < player.maxhp` check passes
            # but BEFORE `player.hp += amount` -- the real defect's window.
            # Filtered on message content so it doesn't pause on unrelated
            # narrate calls (e.g. the "already at full health" branch a
            # losing/retried call would hit post-fix).
            text = " ".join(str(a) for a in args)
            if not paused["done"] and "quaffs" in text.lower():
                paused["done"] = True
                entered.set()
                # Bounded: a lock bug should hang the *fix*, not the suite.
                release.wait(timeout=5)
            return original_narrate(*args, **kwargs)

        items_module.narrate = paused_narrate
        try:
            results = {}
            errors = []

            def do_use(key):
                try:
                    results[key] = gs.use_item(player, restorative)
                except Exception as exc:  # pragma: no cover - failure path
                    errors.append((key, exc))

            first = threading.Thread(target=do_use, args=("first",))
            first.start()
            assert entered.wait(timeout=5), (
                "the first use_item call never reached the paused heal message"
            )

            second = threading.Thread(target=do_use, args=("second",))
            second.start()
            # Bounded wait, not a sleep-and-hope: give an UNLOCKED second use
            # (the pre-fix behaviour) generous room to run to completion
            # while the first sits paused. A LOCKED second use (post-fix)
            # just blocks harmlessly on the lock the first holds; this join
            # returning with the thread still alive is the expected,
            # correct outcome in that case.
            second.join(timeout=0.5)

            release.set()
            first.join(timeout=5)
            assert not first.is_alive(), "the first use thread never resumed"
            second.join(timeout=5)
            assert not second.is_alive(), "the second use thread never returned"
        finally:
            items_module.narrate = original_narrate

        # The real defect: a concurrent second use hits an uncaught
        # ValueError from `inventory.remove(self)` on an already-removed
        # item, not a clean success/failure response.
        assert errors == [], (
            f"a concurrent use_item call raised instead of returning a clean "
            f"result: {errors}"
        )
        # Exactly one use should have actually consumed the item.
        assert restorative.count == 0
        assert _units(player.inventory, "Restorative") == 0
