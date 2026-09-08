"""Container.open() must not narrate physical features the object lacks.

Issue #565 (2026-09-08 live beta QA): one templated line —

    "The <nickname> creaks eerily. The lid lifts back on the hinge, revealing
     the contents inside."

— was narrated for every ``Container`` placement in the game, including a Cold
Hearth, a Conclave Niche, a Ledge Niche and a Stream Trough. None of those has
a lid, and a stone trough with a hinge is simply false.

The project rule this breaks: descriptions are permanent and must stay true.
The generic path therefore says only what is true of *any* container — that
Jean gets it open and can see inside — and a placement that really does have a
lid can author its own line through ``open_message``, which is a genuine
map-authored parameter (declared in ``MAP_AUTHORED_PARAMS``) rather than a
prop the loader would silently drop.

The population these tests assert against is derived from the shipped maps, not
from a hand-written list, and the derivation is asserted non-empty so it cannot
quietly stop matching and approve everything.
"""

import importlib
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.narration import capture_narration  # noqa: E402
from src.objects import Container  # noqa: E402

_MAPS_DIR = _ROOT / "src" / "resources" / "maps"

# Words that assert a specific physical mechanism. A line built for every
# container in the game may not use any of them.
_FALSE_MECHANISM_WORDS = ("lid", "hinge")


def _shipped_container_placements():
    """Every ``Container``-family placement in the shipped maps.

    Yields ``(map_name, coord, class_name, authored_props)``. The map JSON is
    the independent authority here — nothing about the expected set is written
    down in this file.
    """
    placements = []
    for path in sorted(_MAPS_DIR.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        for coord, tile_data in raw.items():
            if coord == "metadata" or not isinstance(tile_data, dict):
                continue
            for payload in tile_data.get("objects", []) or []:
                mod_name = payload.get("__module__")
                cls_name = payload.get("__class__")
                if not mod_name or not cls_name:
                    continue
                try:
                    module = importlib.import_module(f"src.{mod_name}")
                    cls = getattr(module, cls_name)
                except (ImportError, AttributeError):
                    continue
                if isinstance(cls, type) and issubclass(cls, Container):
                    placements.append(
                        (path.name, coord, cls_name, payload.get("props") or {})
                    )
    return placements


def _lidless_placements():
    """Placements whose authored name/nickname names no lid-bearing thing.

    Deliberately generous about what counts as lidded: anything a player could
    reasonably picture with a lid is excluded, so what remains is the set the
    old line was unambiguously lying about.
    """
    lidded_nouns = (
        "chest", "coffer", "box", "crate", "lockbox", "locker", "pot",
        "satchel", "sack", "bundle", "tent", "cart", "handcart",
    )
    out = []
    for map_name, coord, cls_name, props in _shipped_container_placements():
        label = f"{props.get('name', '')} {props.get('nickname', '')}".lower()
        if not any(noun in label for noun in lidded_nouns):
            out.append((map_name, coord, cls_name, props))
    return out


def _open_narration(**kwargs):
    """Narration text emitted by opening a fresh closed Container."""
    container = Container(**kwargs)
    with capture_narration() as messages:
        container.open()
    return container, " ".join(m.get("text", "") for m in messages)


# ---------------------------------------------------------------------------
# Derivation guards — these keep the assertions below from going fail-open.
# ---------------------------------------------------------------------------


def test_the_shipped_container_population_is_not_empty():
    placements = _shipped_container_placements()
    assert len(placements) > 20, (
        "map scan found almost no Container placements — the scan broke, and "
        f"every assertion below would now be vacuous. Found: {placements}"
    )


def test_most_shipped_containers_are_not_lid_bearing():
    """The premise of the fix: the lie was the common case, not the edge case."""
    lidless = _lidless_placements()
    total = len(_shipped_container_placements())
    assert len(lidless) > total / 2, (
        f"only {len(lidless)} of {total} shipped containers are lidless — "
        "re-check the fix's premise before trusting these tests"
    )


# ---------------------------------------------------------------------------
# The regression itself
# ---------------------------------------------------------------------------


def test_generic_open_narration_claims_no_lid_or_hinge():
    _container, text = _open_narration(name="Stream Trough", nickname="stream trough")
    lowered = text.lower()
    for word in _FALSE_MECHANISM_WORDS:
        assert word not in lowered, (
            f"the generic open line still claims a {word!r}: {text!r}"
        )


def test_generic_locked_narration_claims_no_lid_or_hinge():
    """The locked branch had the same bug: "pulls on the lid ... It's locked"."""
    container = Container(name="Sealed Stone Plate", nickname="stone plate", locked=True)
    with capture_narration() as messages:
        container.open()
    text = " ".join(m.get("text", "") for m in messages).lower()
    for word in _FALSE_MECHANISM_WORDS:
        assert word not in text, f"the locked line still claims a {word!r}: {text!r}"
    assert "lock" in text, f"the locked refusal must still say it is locked: {text!r}"


@pytest.mark.parametrize(
    "map_name,coord,cls_name,props",
    [pytest.param(*p, id=f"{p[0]}:{p[1]}:{p[3].get('name', p[2])}")
     for p in _lidless_placements()],
)
def test_no_shipped_lidless_container_is_narrated_a_lid(map_name, coord, cls_name, props):
    """Every real placement, with its real authored nickname."""
    _container, text = _open_narration(
        name=props.get("name", "Container"),
        nickname=props.get("nickname", "container"),
    )
    lowered = text.lower()
    for word in _FALSE_MECHANISM_WORDS:
        assert word not in lowered, (
            f"{map_name} {coord} {props.get('name')!r} is narrated a {word!r}: {text!r}"
        )


def test_open_still_narrates_and_still_opens():
    """The fix must not be "say nothing" — opening is a visible beat."""
    container, text = _open_narration(name="Cold Hearth", nickname="cold hearth")
    assert text.strip(), "opening a container narrated nothing at all"
    assert "cold hearth" in text.lower(), (
        f"the open line no longer names the object: {text!r}"
    )
    assert container.state == "opened"
    assert container.revealed is True


# ---------------------------------------------------------------------------
# Per-placement override — the escape hatch for the genuinely lidded ones
# ---------------------------------------------------------------------------


def test_authored_open_message_is_used_verbatim():
    authored = "The chest lid swings up on its iron hinge."
    _container, text = _open_narration(
        name="Wooden Chest",
        nickname="wooden chest",
        open_message=authored,
    )
    assert authored in text, f"authored open_message ignored: {text!r}"


def test_open_message_is_a_real_map_authored_parameter():
    """An override the map loader would drop is not an escape hatch at all."""
    assert "open_message" in Container.MAP_AUTHORED_PARAMS
