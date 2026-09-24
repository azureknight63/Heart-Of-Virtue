"""``items.Relic`` is retired (issue #646); saves that hold one still load.

The Relic named Jerusalem, which the story withholds, and its one job --
curing Hollowed -- moved to prayer (``tests/test_prayer.py``). It was
dropped from Jean's starting kit first, so a save holding one exists only
from before that; ``LEGACY_ALLOWED_MISSING`` keeps those loading as inert
placeholders under strict unpickling.
"""

import io

import pytest

import src.items as items
import src.secure_pickle as sp
from src.items import Consumable
from src.player import Player


def test_relic_is_gone_from_the_engine():
    assert not hasattr(items, "Relic")


@pytest.fixture
def save_bytes_holding_a_relic(monkeypatch):
    """A real headered Player save whose inventory names ``src.items.Relic``.

    The class no longer exists, so a stand-in is registered under that exact
    global just long enough to pickle it -- the bytes are what an old save
    carries -- and removed again before the load.
    """
    class Relic(Consumable):
        def __init__(self):
            super().__init__(
                name="Relic", description="A small, dark stone.", value=0,
                weight=0.05, maintype="Consumable", subtype="Relic",
            )

    Relic.__module__ = "src.items"
    Relic.__qualname__ = "Relic"
    monkeypatch.setattr(items, "Relic", Relic, raising=False)
    player = Player()
    player.__dict__.pop("_combat_adapter", None)
    player.inventory.append(Relic())
    data = sp.serialize_for_save(player)
    monkeypatch.delattr(items, "Relic")
    return data


def test_strict_load_of_a_save_holding_a_relic_degrades_to_a_placeholder(
    save_bytes_holding_a_relic,
):
    events = []
    loaded = sp.safe_pickle_load(
        io.BytesIO(save_bytes_holding_a_relic), strict=True, events=events
    )

    assert type(loaded).__name__ == "Player"
    relics = [i for i in loaded.inventory if getattr(i, "name", None) == "Relic"]
    assert len(relics) == 1
    assert getattr(relics[0], "_legacy_placeholder", False) is True
    assert not [e for e in events if e["kind"] == "rejected"]


@pytest.mark.parametrize("module", ["items", "src.items"])
def test_the_relic_is_curated_under_both_module_spellings(module):
    """Legacy pickles store the bare module name; both must resolve."""
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=True)
    cls = up.find_class(module, "Relic")
    assert getattr(cls(), "_legacy_placeholder", False) is True
