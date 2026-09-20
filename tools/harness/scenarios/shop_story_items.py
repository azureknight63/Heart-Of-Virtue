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
from collections import Counter
from typing import List

import src.items as items_module

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


#: Issue #632, maintainer decision (2026-09-19): three items excluded by
#: authorial intent rather than by any measurable property -- they are
#: instantiable, worth 600/1/5 gold, carry no level sentinel and are neither
#: Key nor Book, so every derived assertion is blind to them.
#:
#: Defined HERE rather than in the test that pins them
#: (``tests/test_shop_stock_excludes_story_items.py``, which imports this)
#: only because of a dependency direction: that module imports pytest, and the
#: bug-hunt workflow installs ``requirements.txt``, which has no pytest. A tool
#: importing the test suite would take the harness down with it. The test still
#: owns the *assertion*; this module owns the *list*, and nothing re-types it.
MAINTAINER_EXCLUDED_CLASSES = (
    items_module.EnchantedGolemitePauldron,   # Luminous Grotto puzzle reward
    items_module.FabricariumRejectionShard,   # authored evidence, grondia.json
    items_module.GronditeMarkToken,           # found flavour, 3 Grondia maps
)

#: The same three by name.
MAINTAINER_EXCLUDED = frozenset(c.__name__ for c in MAINTAINER_EXCLUDED_CLASSES)

#: Story items named one by one as well as read off the ``stockable`` flag
#: (see ``_story_items_in``), so the name list keeps this discriminating on
#: unfixed code: with the fix reverted nothing carries ``stockable = False``,
#: and a flag-only sweep would find zero offenders and report success against
#: the very bug it exists to catch.
#:
#: Names are resolved against ``src.items`` below, so a rename is an
#: AttributeError at import rather than an entry that silently stops matching.
#: ``tests/test_shop_stock_excludes_story_items.py`` asserts this list agrees
#: with the classes actually carrying the flag, so the two cannot drift.
_NAMED_STORY_ITEMS = (
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
)

STORY_ITEM_NAMES = frozenset(
    getattr(items_module, name).__name__ for name in _NAMED_STORY_ITEMS
) | MAINTAINER_EXCLUDED


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


def _random_fill_count(merchant, containers) -> int:
    """How many stocked items came from ``_fill_remaining_stock``.

    Total inventory cannot answer this: ``update_goods()`` always appends a
    Gold pouch and always spawns every ``always_stock`` entry, so a merchant
    holds items even when the random fill selected nothing at all. Subtract
    exactly those guaranteed contributions -- one instance per always_stock
    entry, plus one Gold -- and whatever remains across the merchant and his
    containers is the fill pass. Counter subtraction drops negatives, so an
    always_stock entry that failed to spawn cannot push this below zero, and a
    fourth Restorative rolled by the fill pass still counts (only the three
    guaranteed ones are subtracted).

    Unique items are skipped: ``UniqueItemInjectionCondition`` injects those
    after the fill, and the fill pass cannot produce one (every class in
    ``items.unique_item_factories`` is excluded from its candidate pool).
    """
    guaranteed = Counter(
        (spec if isinstance(spec, type) else type(spec)).__name__
        for spec in (getattr(merchant, "always_stock", None) or [])
    )
    guaranteed["Gold"] += 1

    observed: Counter = Counter()
    for items in [getattr(merchant, "inventory", [])] + [
        getattr(ct, "inventory", []) for ct in containers
    ]:
        for item in items or []:
            if getattr(item, "unique", False):
                continue
            observed[type(item).__name__] += 1
    return sum((observed - guaranteed).values())


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
        # global random module. Seeding it len(SWEEP_SEEDS) times and walking
        # away would leave every scenario registered after this one running on
        # a deterministic stream they were never written for, masking or
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
        filled_per_seed: List[tuple] = []
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

            # Three destinations: the merchant, his containers, the floor. A
            # list of pairs, not a dict: container display names are not
            # unique, and two containers sharing one would collapse into a
            # single key, leaving the other silently unswept.
            surfaces = [
                ("merchant inventory", getattr(merchant, "inventory", [])),
                ("room floor", getattr(room, "items_here", [])),
            ]
            containers = list(iter_merchant_containers(room, merchant))
            for ct in containers:
                label = f"container '{getattr(ct, 'name', ct)}'"
                surfaces.append((label, getattr(ct, "inventory", [])))

            filled_per_seed.append((seed, _random_fill_count(merchant, containers)))

            for where, items in surfaces:
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

        # A restock whose random fill selected nothing would satisfy every
        # check above: sweeping an empty selection proves nothing about what
        # the selection excludes. TOTAL inventory is useless as that measure --
        # update_goods() unconditionally appends a Gold pouch and Jambo's
        # always_stock contributes three consumables, so "inventory is not
        # empty" holds on every seed whether or not _fill_remaining_stock
        # picked a single class. Only the fill portion is evidence.
        if restocks and not bugs:
            barren = [seed for seed, filled in filled_per_seed if filled == 0]
            if barren:
                bugs.append(self._bug(
                    title=(
                        f"#632 scenario is vacuous: the random fill selected "
                        f"nothing on {len(barren)} seed(s), e.g. {barren[0]}"
                    ),
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.LOGIC,
                    endpoint="(engine) JamboHealsU.update_goods", method="-",
                    expected="_fill_remaining_stock selects stock on every seed",
                    actual=(
                        f"0 randomly-filled items on seeds {barren[:5]} - those "
                        f"sweeps proved nothing"
                    ),
                ))

        return bugs
