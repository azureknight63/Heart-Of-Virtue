"""Fuzz test for engine inventory/item operations (issue #297).

Drives tools/inventory_fuzzer.py, which applies long seeded random sequences of
gold transfers, stackable-item transfers, and equip/unequip swaps to a Player
and checks the inventory invariants after every step: no negative gold/count,
gold and item-count conservation across a transfer, consistent non-negative
weight, no dangling ``eq_weapon``, idempotent ``refresh_stat_bonuses``, and no
uncaught exception. Any finding fails the test.

Pure in-memory engine objects (no Flask session), so this lives under tests/.
The fuzzer module is loaded by file path, matching tests/test_save_fuzz.py.
"""

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _load_fuzzer():
    path = _ROOT / "tools" / "inventory_fuzzer.py"
    spec = importlib.util.spec_from_file_location("_inventory_fuzzer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fuzzer = _load_fuzzer()


@pytest.mark.parametrize("seed", [1, 1337, 42, 20240101])
def test_inventory_invariants_hold(seed):
    findings = fuzzer.run_fuzz(iterations=200, seed=seed)
    assert not findings, "\n".join(str(f) for f in findings[:40])


def test_transfer_gold_conserves_and_never_negative():
    """Over-transferring gold neither creates nor destroys it (issue #297)."""
    from src.items import Gold
    from src.inventory_utils import get_gold, transfer_gold

    a = [Gold(100)]
    b = [Gold(30)]
    total = get_gold(a) + get_gold(b)
    # Try to move more than 'a' holds — must clamp, not create gold.
    transfer_gold(a, b, 10_000)
    assert get_gold(a) >= 0 and get_gold(b) >= 0
    assert get_gold(a) + get_gold(b) == total
    # A negative amount is a no-op, not a reverse transfer that goes negative.
    transfer_gold(a, b, -50)
    assert get_gold(a) >= 0 and get_gold(b) >= 0
    assert get_gold(a) + get_gold(b) == total


def test_transfer_equipped_weapon_does_not_dangle_eq_weapon():
    """Transferring an equipped weapon out unequips it first (issue #297)."""
    from src.player import Player
    from src.items import Longsword
    from src.inventory_utils import transfer_item

    src = Player()
    dst = Player()
    sword = Longsword()
    src.inventory.append(sword)
    src.equip_item(item_object=sword)
    assert src.eq_weapon is sword

    transfer_item(src, dst, sword, 1)

    assert sword not in src.inventory
    assert src.eq_weapon is not sword          # no dangling reference
    assert src.eq_weapon is getattr(src, "fists", None)
    assert not getattr(sword, "isequipped", False)
