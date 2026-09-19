"""Issue #632: no story item may reach a merchant's stock, or his tent floor.

The rung-1 pool test in ``tests/test_shop_stock_excludes_story_items.py``
observes the *candidate pool*. The reported symptom was a second wedding band
lying on the tent floor, which is ``_place_item`` /
``_remove_placed_item_from_room`` territory — a different surface. This
scenario drives a real ``JamboHealsU`` through a real ``update_goods()`` on a
real universe and sweeps all three destinations stock can land in: the
merchant, his containers, and the room itself.

Seed 92 is the reporter's case: on unfixed code it stocks *two* wedding bands
in a single roll.
"""

import random
from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory

#: The reporter's seed — two JeanWeddingBands in one roll on unfixed code.
REPRO_SEED = 92

#: Seeds swept, repro seed first. ~5% of Jambo restocks stocked a story item
#: before the fix, so a single roll is a coin flip; a spread turns "probably
#: fine" into evidence. The repro seed is excluded from the range so it is not
#: rolled twice.
SWEEP_SEEDS = (REPRO_SEED,) + tuple(s for s in range(0, 120) if s != REPRO_SEED)


def _find_merchant(universe, class_name: str):
    """Return the first NPC of ``class_name`` in ``universe``, with its room.

    ``universe.map`` is only the map the player currently stands on, and Jambo
    lives on another one — so walk ``universe.maps``, which holds every map
    the universe loaded, and fall back to the current map.
    """
    from src.shop_conditions import iter_rooms

    sources = list(getattr(universe, "maps", None) or [])
    current = getattr(universe, "map", None)
    if current is not None:
        sources.append(current)
    for source in sources:
        for room in iter_rooms(source):
            for npc in getattr(room, "npcs_here", []) or []:
                if type(npc).__name__ == class_name:
                    return npc, room
    return None, None


#: Story items by NAME, not by reading the ``stockable`` flag.
#:
#: Reading the flag would make this scenario blind on unfixed code -- with the
#: fix reverted nothing carries ``stockable = False``, so the sweep would find
#: zero offenders and report success against the very bug it exists to catch.
#: Naming the classes keeps it a genuine before/after discriminator.
STORY_ITEM_NAMES = frozenset({
    "JeanWeddingBand",          # Jean's late wife's ring (#632)
    "ConclaveSignalStone",      # quest key
    "FabricariumCompactSeal",   # quest key
    "MineralFragment",          # Ch02 memory flash fires on possession
    "AzuriteGem",               # puzzle ingredient #1
    "AmberStone",               # puzzle ingredient #2
    "PaleGreyFragment",         # puzzle ingredient #3
    "Book",                     # bare placeholder + all lore documents below
    "CompactOfSilence",
    "DissentingRecord",
    "ElderWritOfCleansing",
    "HeartkeeperNote",
    "MerchantJournalFragment",
    "QualityReport117K",
    # Maintainer decision (#632, 2026-09-19): excluded by authorial intent
    # rather than by any measurable property.
    "EnchantedGolemitePauldron",  # Luminous Grotto puzzle reward
    "FabricariumRejectionShard",  # authored evidence object in grondia.json
    "GronditeMarkToken",          # found flavour, authored into 3 Grondia maps
})


def _story_items_in(items) -> List[str]:
    """Names of any story-item classes among ``items``.

    Matches on the class name and on the ``stockable`` flag, so a story item
    added later picks up coverage from the flag without editing this list.
    """
    found = []
    for i in items or []:
        cls = type(i)
        if cls.__name__ in STORY_ITEM_NAMES or not getattr(cls, "stockable", True):
            found.append(cls.__name__)
    return sorted(found)


class ShopStoryItemsScenario(Scenario):
    name = "shop_story_items"
    description = (
        "Restock a real merchant under fixed seeds; no story item may reach "
        "his inventory, his containers or the room floor (#632)."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs: List[BugReport] = []

        player = client._session_manager.get_player(client.session_id)
        universe = getattr(player, "universe", None)
        if universe is None:
            return [self._bug(
                title="#632 scenario could not reach the universe",
                severity=BugSeverity.MEDIUM,
                category=BugCategory.LOGIC,
                endpoint="(engine)", method="-",
                expected="player.universe is available",
                actual="player.universe is None",
            )]

        merchant, room = _find_merchant(universe, "JamboHealsU")
        if merchant is None:
            return [self._bug(
                title="#632 scenario could not find JamboHealsU",
                severity=BugSeverity.LOW,
                category=BugCategory.LOGIC,
                endpoint="(engine)", method="-",
                expected="A JamboHealsU merchant somewhere in the universe",
                actual="No JamboHealsU found in any room",
            )]

        from src.shop_conditions import iter_merchant_containers

        # The merchant restocks into the room it actually stands in; prefer
        # that over the room we happened to find it in, so the floor sweep
        # cannot end up watching the wrong tile.
        floor_room = getattr(merchant, "current_room", None) or room

        # bug_hunt runs every scenario sequentially in ONE process against the
        # global random module. Seeding it 121 times and walking away would
        # leave every scenario registered after this one running on a
        # deterministic stream they were never written for, masking or
        # manufacturing intermittent findings. Borrow the RNG, then give it
        # back exactly as found.
        rng_state = random.getstate()
        try:
            bugs.extend(self._sweep(merchant, floor_room, iter_merchant_containers))
        finally:
            random.setstate(rng_state)
        return bugs

    def _sweep(self, merchant, room, iter_merchant_containers) -> List[BugReport]:
        """Restock ``merchant`` once per seed and sweep every stock surface."""
        bugs: List[BugReport] = []
        restocks = 0
        for seed in SWEEP_SEEDS:
            random.seed(seed)
            try:
                merchant.update_goods()
            except Exception as exc:  # noqa: BLE001
                bugs.append(self._bug(
                    title=f"#632: update_goods() raised on seed {seed}",
                    severity=BugSeverity.HIGH,
                    category=BugCategory.CRASH,
                    endpoint="(engine) JamboHealsU.update_goods", method="-",
                    expected="Restock completes",
                    actual=f"{type(exc).__name__}: {exc}",
                ))
                break
            restocks += 1

            # Three destinations: the merchant, his containers, the floor.
            surfaces = {
                "merchant inventory": getattr(merchant, "inventory", []),
                "room floor": getattr(room, "items_here", []),
            }
            for ct in iter_merchant_containers(room, merchant):
                label = f"container '{getattr(ct, 'name', ct)}'"
                surfaces[label] = getattr(ct, "inventory", [])

            for where, items in surfaces.items():
                offenders = _story_items_in(items)
                if offenders:
                    bugs.append(self._bug(
                        title=(
                            f"#632: story item(s) {offenders} reached the "
                            f"{where} (seed {seed})"
                        ),
                        severity=BugSeverity.HIGH,
                        category=BugCategory.LOGIC,
                        endpoint="(engine) JamboHealsU.update_goods", method="-",
                        expected="No stockable=False class in merchant stock",
                        actual=f"{where} holds {offenders}",
                    ))
            if bugs:
                break

        # A restock that stocks nothing would satisfy every check above.
        if restocks and not bugs:
            stocked = len(getattr(merchant, "inventory", []) or [])
            if stocked == 0:
                bugs.append(self._bug(
                    title="#632 scenario is vacuous: merchant stocked nothing",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.LOGIC,
                    endpoint="(engine) JamboHealsU.update_goods", method="-",
                    expected="Merchant holds stock after update_goods()",
                    actual="Merchant inventory is empty - the sweep proved nothing",
                ))

        return bugs
