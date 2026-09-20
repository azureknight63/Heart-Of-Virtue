"""Issue #632: story items must never roll into random merchant stock.

Every assertion here but one derives its expectation from an authority
*outside* ``src/npc/_shop.py`` — the type system, the item's own economics,
its instantiability, ``loot_tables``' level sentinel, or Jean's authored
starting kit. No *exclusion* assertion below reads ``disallowed_classes`` or
the ``stockable`` flag: a test that hand-lists what the code hand-lists only
proves the list was copied correctly, not that the right things are excluded.
(``test_the_harness_scenarios_story_item_names_track_the_stockable_flags`` does
read the flag, deliberately and for a different job: it is not judging what
should be excluded, it is holding the harness scenario's hand-written copy of
the list to the original so the two cannot drift.)

The exception is ``test_maintainer_excluded_items_are_not_stockable``, which
pins three items excluded by authorial intent alone. No measurable property
separates them from ordinary stock, so there is nothing to derive from; it is
labelled a maintainer decision rather than dressed up as an invariant.

KNOWN GAP -- exclusion is opt-in. ``Item.stockable`` defaults to True, so a
story item is only kept out of stock if someone remembers to flag it. The
derived assertions below catch a *new* story item only when it happens to be a
Key, a Book, worth nothing, or marked ``level = 99``. A future non-zero-value
story ``Special`` -- the ``GronditeMarkToken`` shape -- is stockable by default
and NO assertion in this file would notice. That shape needs a deliberate flag
plus a line in the harness scenario's ``MAINTAINER_EXCLUDED_CLASSES``; nothing
here covers it automatically.
"""

import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import src.items as items_module  # noqa: E402
from src.items import Book, Key  # noqa: E402
from src.npc._shop import MerchantShopMixin  # noqa: E402


class _PoolRecorder:
    """An availability shop-condition that records the restock candidate pool.

    ``_fill_remaining_stock`` hands every registered availability condition the
    freshly built ``weight_map`` so it can scale weights. Its keys *are* the
    candidate pool, so borrowing that documented extension point observes the
    real pool produced by the real code path without reimplementing the
    enumeration (which would mean copying the very list under test).
    """

    def __init__(self):
        self.pool: set[type] = set()

    def adjust_restock_weights(self, weight_map):
        self.pool.update(weight_map.keys())


class _FakeRoom:
    def __init__(self):
        self.objects = []
        self.objects_here = []
        self.items_here = []
        self.universe = None

    def spawn_item(self, item_type, amt=1, hidden=False, hfactor=0, merchandise=False):
        """Mirror ``Room.spawn_item``: build with a bare ``cls()``, then set
        ``merchandise`` by attribute.

        Production (``src/tiles.py``, ``_new_instance``) does exactly this.
        Passing ``merchandise=`` to the constructor instead would raise
        TypeError for every item whose ``__init__`` takes no arguments --
        which is most story items -- silently making them unspawnable here
        and hiding them from any test that measures what actually gets
        stocked.
        """
        cls = getattr(items_module, item_type, None)
        if cls is None:
            return None
        item = cls()
        if hasattr(item, 'merchandise'):
            item.merchandise = merchandise
        if not hasattr(item, 'base_value'):
            setattr(item, 'base_value', getattr(item, 'value', 1))
        return item


class _MockMerchant(MerchantShopMixin):
    def __init__(self):
        self.name = "PoolProbe"
        self.inventory = []
        self.stock_count = 1
        self.always_stock = None
        self.specialties = []
        self.enchantment_rate = 0.0
        self.base_gold = 300
        self.shop_conditions = {"value": [], "availability": [], "unique": []}
        self.shop = None
        self.current_room = _FakeRoom()


@pytest.fixture(scope="module")
def pool():
    """The real restock candidate pool, captured from the real roller."""
    recorder = _PoolRecorder()
    merchant = _MockMerchant()
    merchant.shop_conditions["availability"].append(recorder)
    merchant._fill_remaining_stock([])
    return recorder.pool


@pytest.fixture(scope="module")
def pool_names(pool):
    return {cls.__name__ for cls in pool}


def _try_build(cls):
    """Instantiate ``cls`` the way the roller does, or return None.

    An abstract base in the pool is its own defect, owned by
    ``test_every_stockable_class_can_actually_be_instantiated``. Swallowing it
    here keeps the economics and level-sentinel assertions failing on *their*
    subject instead of crashing on someone else's.
    """
    try:
        return cls()
    except Exception:  # noqa: BLE001
        return None


# ── Guard: every assertion below is vacuously true of an empty pool ──────────

def test_the_pool_is_not_empty_and_still_holds_ordinary_trade_goods(pool, pool_names):
    """Mandatory non-emptiness guard.

    Every exclusion assertion in this file passes trivially if the pool
    collapses, so a scan that matched nothing would approve of everything.
    This pins the floor and names one representative of each merchandise
    family that a merchant must still be able to stock.

    The floor is 60 against a real pool of 68, i.e. 8 classes of headroom:
    flagging a 9th class ``stockable = False`` fails this test on purpose, so
    that a steady drip of exclusions has to be re-argued rather than waved
    through one commit at a time. Raise the floor deliberately (and say why)
    if the pool itself grows.
    """
    assert len(pool) >= 60, f"stock pool collapsed to {len(pool)}"
    for cls_name in (
        "Longsword",      # weapon
        "Restorative",    # consumable
        "IronHelm",       # protective gear
        "GoldRing",       # accessory
        "WoodenArrow",    # ammunition
        "Crystals",       # Commodity trade good — exists to be sold
    ):
        assert cls_name in pool_names, f"{cls_name} vanished from merchant stock"


# ── Authority: the type system (issubclass, not identity) ───────────────────

def test_no_quest_key_is_stockable(pool):
    """Keys open authored locks. A purchasable duplicate trivialises the lock.

    ``Key`` itself is excluded by identity today; this asserts over the whole
    subtree, which is where the real quest keys live.
    """
    offenders = sorted(c.__name__ for c in pool if issubclass(c, Key))
    assert offenders == []


def test_no_lore_document_is_stockable(pool):
    """Each ``Book`` subclass is a single authored testimony, placed to be
    *found*. A second copy on a merchant's shelf breaks the framing — and they
    are all value 0, so they would sell for nothing anyway."""
    offenders = sorted(c.__name__ for c in pool if issubclass(c, Book))
    assert offenders == []


# ── Authority: the item's own economics ─────────────────────────────────────

def test_every_stockable_item_is_worth_something(pool):
    """A merchant selling a 0-gold item is a bug in every case but two.

    ``ClothHood`` and ``TatteredCloth`` are Jean's starting rags: genuine
    tier-0 gear (``level == 0``) that a nomad may legitimately carry. Every
    other zero-value class in the pool is a story item, a puzzle ingredient or
    a document.
    """
    worthless = sorted(
        c.__name__ for c in pool
        if (inst := _try_build(c)) is not None and inst.value <= 0
    )
    assert worthless == ["ClothHood", "TatteredCloth"]


# ── Authority: instantiability (the roller calls a bare cls()) ──────────────

def test_every_stockable_class_can_actually_be_instantiated(pool):
    """``spawn_item`` constructs with no arguments. An abstract base in the
    pool raises ``TypeError``, silently burning one of the roller's 1000 fill
    iterations and thinning stock for no visible reason."""
    broken = []
    for cls in pool:
        try:
            cls()
        except Exception as exc:  # noqa: BLE001 - the roller catches this too
            broken.append((cls.__name__, type(exc).__name__))
    assert sorted(broken) == []


# ── Authority: loot_tables' level sentinel ──────────────────────────────────

def test_no_item_marked_never_randomly_generated_is_stockable(pool):
    """``loot_tables.Loot.random_equipment`` filters on ``obj.level``, so
    ``level = 99`` is the codebase's existing out-of-band way of saying "this
    item is never randomly generated". The shop roller must honour the same
    decision rather than re-deciding it."""
    offenders = sorted(
        c.__name__ for c in pool
        if (inst := _try_build(c)) is not None and getattr(inst, "level", None) == 99
    )
    assert offenders == []


# ── Authority: Jean's authored starting kit ─────────────────────────────────

# Issue #632, maintainer decision (2026-09-19). Three items are excluded by
# authorial intent, NOT by any measurable property: they are instantiable,
# worth 600/1/5 gold, carry no level sentinel, are neither Key nor Book, and
# are absent from Jean's starting kit. Every derived assertion above is blind
# to them, and map authorship does not separate them either -- 45 of the 68
# pool members are authored into map JSON, including Longsword and IronHelm.
# So they are a deliberate registry of a judgement call, not a derivation, and
# they are labelled as such so no reader mistakes them for one.
#
# That registry is written down ONCE, in
# ``tools/harness/scenarios/shop_story_items.py``
# (``MAINTAINER_EXCLUDED_CLASSES``, held as class objects so a rename is an
# AttributeError at import rather than a name that silently stops matching).
# It lives there rather than here purely for dependency direction: this module
# imports pytest, the bug-hunt workflow installs only ``requirements.txt``,
# which has none, and a harness importing the test suite would take the harness
# down with it. This file still owns the assertion -- the test below imports
# the registry instead of re-typing it.


def test_maintainer_excluded_items_are_not_stockable(pool):
    """The judgement-call exclusions, pinned because nothing else pins them.

    This is the one assertion in this file that does not derive its
    expectation from an outside authority, because no authority exists: these
    three look exactly like ordinary merchandise by every property the other
    tests measure. Without this test, deleting their ``stockable = False``
    would leave the whole suite green.

    Matched on class identity rather than name, so renaming one of the three
    cannot quietly turn this into a comparison that matches nothing.
    """
    from tools.harness.scenarios.shop_story_items import MAINTAINER_EXCLUDED_CLASSES

    assert MAINTAINER_EXCLUDED_CLASSES, "the judgement-call registry is empty"
    offenders = sorted(c.__name__ for c in pool if c in MAINTAINER_EXCLUDED_CLASSES)
    assert offenders == []


def test_the_harness_scenarios_story_item_names_track_the_stockable_flags():
    """The #632 harness scenario hand-lists story items by name on purpose.

    ``tools/harness/scenarios/shop_story_items.py`` cannot derive its list from
    the ``stockable`` flags alone: reverting the fix clears every flag, and a
    flag-only sweep would then find no offenders and report success against the
    exact bug it exists to catch. So it names them -- and the price of that
    deliberate duplication is drift. Flag an 18th class, or unflag one, and the
    scenario would go on testing yesterday's list without a word.

    This is the assertion that makes the copy keep up with the original. It is
    deliberately the one place in this file that reads the flag: it is not
    asserting that the right things are excluded (the tests above do that from
    outside authorities), it is asserting that two lists of the same thing
    agree.
    """
    from tools.harness.scenarios.shop_story_items import STORY_ITEM_NAMES

    # The EFFECTIVE flag, not ``"stockable" in c.__dict__``: the flag is
    # inherited, Book sets it for its whole subtree, and a derivation that
    # counted only per-class declarations would shrink the moment a redundant
    # restatement is removed -- silently dropping names from the scenario's
    # discriminator instead of failing.
    flagged = {
        c.__name__
        for c in vars(items_module).values()
        if isinstance(c, type)
        and issubclass(c, items_module.Item)
        and not c.stockable
    }
    assert flagged, "no class carries stockable = False - the #632 fix is gone"
    assert STORY_ITEM_NAMES == flagged, (
        "the harness scenario's story-item names have drifted from the classes "
        f"flagged stockable = False: only in scenario={sorted(STORY_ITEM_NAMES - flagged)}, "
        f"only flagged={sorted(flagged - STORY_ITEM_NAMES)}"
    )


def test_jeans_personal_effects_are_not_merchandise(pool_names):
    """Anything Jean starts the game already carrying is authored, personal, or
    both. Only the two starting rags may legitimately also exist as shop stock;
    his wedding band (issue #632) may not — a second one existing at all
    undercuts the object's meaning."""
    from src.player import Player

    starting_kit = {type(i).__name__ for i in Player().inventory}
    assert starting_kit, "Player() starting inventory is empty - fixture is broken"
    assert starting_kit & pool_names <= {"ClothHood", "TatteredCloth"}
