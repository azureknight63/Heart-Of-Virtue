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

import inspect
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.narration import capture_narration  # noqa: E402
from src.objects import Container  # noqa: E402
from tests._map_scan import object_placements, resolve_class  # noqa: E402

# Words that assert a specific physical mechanism. A line built for every
# container in the game may not use any of them.
_FALSE_MECHANISM_WORDS = ("lid", "hinge")


def _shipped_container_placements():
    """Every ``Container``-family placement in the shipped maps.

    Yields ``(map_name, coord, cls, authored_props)`` — the resolved CLASS, not
    its name, so a caller can instantiate the real subclass rather than a base
    ``Container``. The map JSON is the independent authority here; nothing
    about the expected set is written down in this file.

    The walk itself lives in :mod:`tests._map_scan`, shared with the two other
    guards added alongside this one.
    """
    placements = []
    for placement in object_placements():
        cls = resolve_class(placement)
        if isinstance(cls, type) and issubclass(cls, Container):
            placements.append(
                (placement.map_name, placement.coord, cls, placement.props)
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
    for map_name, coord, cls, props in _shipped_container_placements():
        label = f"{props.get('name', '')} {props.get('nickname', '')}".lower()
        if not any(noun in label for noun in lidded_nouns):
            out.append((map_name, coord, cls, props))
    return out


def _open_narration(**kwargs):
    """Narration text emitted by opening a fresh closed Container."""
    container = Container(**kwargs)
    with capture_narration() as messages:
        container.open()
    return container, " ".join(m.get("text", "") for m in messages)


def _assert_no_false_mechanism(text, context):
    """No line may name a mechanism the object might not have.

    One spelling of the check: it was written three times with three different
    messages, and the words being checked are the point -- a fourth entry in
    ``_FALSE_MECHANISM_WORDS`` has to reach every site.
    """
    lowered = text.lower()
    for word in _FALSE_MECHANISM_WORDS:
        assert word not in lowered, f"{context} claims a {word!r}: {text!r}"


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
    _assert_no_false_mechanism(text, "the generic open line")


def test_generic_locked_narration_claims_no_lid_or_hinge():
    """The locked branch had the same bug: "pulls on the lid ... It's locked"."""
    _container, text = _open_narration(
        name="Sealed Stone Plate", nickname="stone plate", locked=True
    )
    _assert_no_false_mechanism(text, "the locked line")
    assert "lock" in text.lower(), (
        f"the locked refusal must still say it is locked: {text!r}"
    )


@pytest.mark.parametrize(
    "map_name,coord,cls,props",
    [pytest.param(*p, id=f"{p[0]}:{p[1]}:{p[3].get('name', p[2].__name__)}")
     for p in _lidless_placements()],
)
def test_no_shipped_lidless_container_is_narrated_a_lid(map_name, coord, cls, props):
    """Every lidless placement's authored name and nickname, through the
    GENERIC line.

    Not through ``cls``: two of the three shipped container classes take
    ``player``/``tile`` in ``__init__``, and constructing them here would need
    a try/except that fell back to the base class -- which is how a guard stops
    covering the rows most likely to be wrong. What a subclass overrides is
    covered by
    :func:`test_every_container_subclass_that_overrides_open_is_checked`
    instead, whose population is derived the same way.
    """
    _container, text = _open_narration(
        name=props.get("name", "Container"),
        nickname=props.get("nickname", "container"),
    )
    _assert_no_false_mechanism(text, f"{map_name} {coord} {props.get('name')!r}")


def _container_classes_overriding_open():
    """Every ``Container`` subclass in ``src/objects.py`` with its own ``open``.

    Derived from the module rather than listed, so a subclass written next week
    is checked the day it is written. The base ``Container`` is excluded
    because the tests above are what cover its line.
    """
    import src.objects as objects_module

    return [
        cls
        for _name, cls in inspect.getmembers(objects_module, inspect.isclass)
        if issubclass(cls, Container)
        and cls is not Container
        and "open" in cls.__dict__
    ]


def test_there_are_open_overriding_subclasses_to_check():
    """Positive control: an empty derivation approves of every subclass."""
    overriders = _container_classes_overriding_open()
    assert overriders, (
        "no Container subclass appears to override open() -- either the "
        "derivation broke or SupplyTent.open was deleted. The parametrized "
        "test below is vacuous either way."
    )


@pytest.mark.parametrize(
    "cls", _container_classes_overriding_open(), ids=lambda c: c.__name__
)
def test_every_container_subclass_that_overrides_open_is_checked(cls):
    """A subclass writes its own line, so the generic tests never see it.

    ``SupplyTent`` is the shipped instance: it has a flap, not a lid, and its
    own ``open`` narrates accordingly -- which is legitimate, and exactly why
    it has to be asserted rather than assumed. A subclass added later that
    copied the old lid-and-hinge wording would otherwise ship unchecked.
    """
    instance = cls(player=None, tile=None)
    with capture_narration() as messages:
        instance.open()
    text = " ".join(m.get("text", "") for m in messages)
    assert text.strip(), f"{cls.__name__}.open() narrated nothing at all"
    _assert_no_false_mechanism(text, f"{cls.__name__}.open()")


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
