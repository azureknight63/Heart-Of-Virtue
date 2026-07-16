#!/usr/bin/env python3
"""Inventory/item operation fuzzer for Heart of Virtue (issue #297).

Inventory is heavily mutated (loot, shops, equip swaps) and the equip/drop/use
logic is a prime spot for state-corruption bugs that random operation sequences
expose. This fuzzer applies long, seeded random sequences of operations to a
``Player`` (and a paired inventory) — gold transfers, stackable-item transfers,
and equip/unequip swaps — and checks the invariants after every step:

  * item ``count`` and gold ``amt`` are never negative;
  * total gold and total item count are **conserved** across a transfer (no
    duplication or loss);
  * ``weight_current`` stays consistent (non-negative; recompute is idempotent);
  * ``eq_weapon`` never dangles to an item removed from the inventory;
  * ``refresh_stat_bonuses`` is idempotent (repeated calls don't drift stats);
  * no operation raises an uncaught exception.

Mirrors ``tools/save_fuzzer.py`` (``Finding`` class, seeded RNG,
``run_fuzz(iterations, seed)``, ``main()``). Operates on pure in-memory engine
objects — no Flask app/session — so the companion CI test lives under ``tests/``.

Usage:
    python tools/inventory_fuzzer.py                 # 300 iterations, random seed
    python tools/inventory_fuzzer.py --iterations 3000 --seed 1337
"""

import os
import sys
import copy
import random
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.functions as functions  # noqa: E402
from src.player import Player  # noqa: E402
from src import items as items_mod  # noqa: E402
from src.inventory_utils import get_gold, transfer_gold, transfer_item  # noqa: E402

_WEAPONS = ["Rock", "Dagger", "Longsword"]
_ARMOR = ["LeatherArmor", "TatteredCloth"]
_STACKABLE = ["Restorative"]


class Finding:
    def __init__(self, seed, i, category, detail):
        self.seed, self.i, self.category, self.detail = seed, i, category, detail

    def __str__(self):
        return f"[seed={self.seed} iter={self.i} {self.category}] {self.detail}"


def _stat_vector(p):
    return tuple(getattr(p, a, None) for a in (
        "strength", "finesse", "speed", "endurance", "charisma",
        "intelligence", "maxhp", "maxfatigue", "weight_tolerance",
        "protection"))


def _make_player(rng):
    p = Player()
    # Seed the inventory with a random mix of equippables and stackables.
    for _ in range(rng.randint(1, 4)):
        cls = getattr(items_mod, rng.choice(_WEAPONS + _ARMOR))
        p.inventory.append(cls())
    for _ in range(rng.randint(0, 3)):
        cls = getattr(items_mod, rng.choice(_STACKABLE))
        it = cls()
        if hasattr(it, "count"):
            it.count = rng.randint(1, 20)
        p.inventory.append(it)
    p.inventory.append(items_mod.Gold(rng.randint(0, 5000)))
    if hasattr(p, "refresh_weight"):
        p.refresh_weight()
    return p


def _total_item_count(inv):
    total = 0
    for it in inv:
        if getattr(it, "name", None) == "Gold":
            continue
        total += getattr(it, "count", 1) if hasattr(it, "count") else 1
    return total


def _check_invariants(seed, i, label, player, other, findings):
    # Gold never negative.
    for inv, who in ((player.inventory, "player"), (other.inventory, "other")):
        for it in inv:
            if getattr(it, "name", None) == "Gold":
                if getattr(it, "amt", 0) < 0:
                    findings.append(Finding(seed, i, "negative-gold",
                                            f"{label}: {who} gold {it.amt}"))
            cnt = getattr(it, "count", None)
            if cnt is not None and isinstance(cnt, (int, float)) and cnt < 0:
                findings.append(Finding(seed, i, "negative-count",
                                        f"{label}: {who} {getattr(it,'name','?')} "
                                        f"count {cnt}"))
    # weight_current non-negative and idempotent under recompute.
    if hasattr(player, "refresh_weight"):
        before = getattr(player, "weight_current", 0)
        player.refresh_weight()
        after = getattr(player, "weight_current", 0)
        if after < 0:
            findings.append(Finding(seed, i, "negative-weight", f"{label}: {after}"))
        if abs(float(before) - float(after)) > 0.011:
            findings.append(Finding(seed, i, "weight-drift",
                                    f"{label}: {before} -> {after}"))
    # eq_weapon must be fists or an item actually in the inventory.
    eqw = getattr(player, "eq_weapon", None)
    fists = getattr(player, "fists", None)
    if eqw is not None and eqw is not fists and eqw not in player.inventory:
        findings.append(Finding(seed, i, "dangling-eq-weapon",
                                f"{label}: {getattr(eqw,'name','?')} not in inventory"))
    # refresh_stat_bonuses idempotent.
    functions.refresh_stat_bonuses(player)
    v1 = _stat_vector(player)
    functions.refresh_stat_bonuses(player)
    v2 = _stat_vector(player)
    if v1 != v2:
        findings.append(Finding(seed, i, "stat-bonus-not-idempotent",
                                f"{label}: {v1} != {v2}"))


def _op_transfer_gold(rng, player, other):
    src, dst = (player, other) if rng.random() < 0.5 else (other, player)
    amt = rng.choice([rng.randint(-100, 100), rng.randint(0, 10 ** 7),
                      "not-int", None, -1, 0])
    before = get_gold(player.inventory) + get_gold(other.inventory)
    transfer_gold(src.inventory, dst.inventory, amt)
    after = get_gold(player.inventory) + get_gold(other.inventory)
    return ("transfer_gold", before, after)


def _op_transfer_item(rng, player, other):
    src, dst = (player, other) if rng.random() < 0.5 else (other, player)
    candidates = [it for it in src.inventory
                  if getattr(it, "name", None) != "Gold"]
    if not candidates:
        return None
    item = rng.choice(candidates)
    qty = rng.choice([1, rng.randint(-3, 30), 0, None])
    before = _total_item_count(player.inventory) + _total_item_count(other.inventory)
    transfer_item(src, dst, item, qty if qty is not None else 1)
    after = _total_item_count(player.inventory) + _total_item_count(other.inventory)
    return ("transfer_item", before, after)


def _op_equip(rng, player):
    equippable = [it for it in player.inventory
                  if hasattr(it, "isequipped") and getattr(it, "type", "") != "Consumable"]
    if equippable and rng.random() < 0.7:
        target = rng.choice(equippable)
        player.equip_item(item_object=target)
    else:
        # Unequip a random currently-equipped item.
        equipped = [it for it in player.inventory if getattr(it, "isequipped", False)]
        if equipped:
            player.unequip_item(item_object=rng.choice(equipped))
    return ("equip/unequip", None, None)


def run_fuzz(iterations=300, seed=None):
    if seed is None:
        seed = random.randrange(2 ** 32)
    rng = random.Random(seed)
    findings = []
    for i in range(iterations):
        try:
            player = _make_player(rng)
            other = _make_player(rng)
        except Exception as exc:  # noqa: BLE001
            findings.append(Finding(seed, i, "harness-error",
                                    f"setup: {type(exc).__name__}: {exc}"))
            continue
        for step in range(rng.randint(3, 12)):
            op = rng.randint(0, 2)
            try:
                if op == 0:
                    res = _op_transfer_gold(rng, player, other)
                elif op == 1:
                    res = _op_transfer_item(rng, player, other)
                else:
                    res = _op_equip(rng, player)
            except Exception as exc:  # noqa: BLE001 - any raise is a finding
                findings.append(Finding(seed, i, "crash",
                                        f"op{op} step{step}: "
                                        f"{type(exc).__name__}: {exc}"))
                continue
            # Conservation check for transfer ops.
            if res and res[1] is not None and res[1] != res[2]:
                findings.append(Finding(seed, i, "not-conserved",
                                        f"{res[0]}: {res[1]} -> {res[2]}"))
            _check_invariants(seed, i, f"after op{op} step{step}",
                              player, other, findings)
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=300)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args(argv)

    findings = run_fuzz(args.iterations, args.seed)
    if findings:
        print(f"FAIL: {len(findings)} invariant violation(s):")
        seen = set()
        for f in findings:
            key = (f.category, f.detail.split(":")[0])
            if key not in seen:
                seen.add(key)
                print("  " + str(f))
        return 1
    print(f"OK: {args.iterations} iterations, no invariant violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
