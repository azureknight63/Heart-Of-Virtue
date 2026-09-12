"""Positive and negative controls for ``tests/_map_scan.py``.

The walk is the population several shipped-map guards assert over, so its
shape-reader, its completeness and its class resolution get controls of their
own: a reader that silently drops a payload the game loads makes every guard
downstream approve of that placement without looking at it.
"""

import pytest

from src import map_placeholders
from src.objects import Passageway
from src.story.ch03 import FerryLandingObjectiveEvent
from src.universe import Universe
from tests._ferry_fixtures import FERRY_LANDING_NAME, FERRY_MAP, FERRY_TILE_KEY
from tests._map_scan import (
    ClassRef,
    Placement,
    class_ref,
    event_placements,
    map_data,
    object_placements,
    resolve_class,
    tiles,
)

#: Legacy ``props`` values that are not an object: truthy, which the loader
#: drops and the walk raises on, and falsy -- ``null`` among them -- which
#: both read as no props.
_TRUTHY_NON_OBJECT_PROPS = (["x"], "x", 7)
_FALSY_PROPS = ([], "", 0, None)


def _legacy_dump(**fields):
    """A legacy full dump naming ``objects.Passageway``, plus ``fields``."""
    return {"__class__": "Passageway", "__module__": "objects", **fields}


#: Every legacy dump that must read as carrying no props: one per falsy
#: ``props`` value, plus the dump that omits the key altogether.
_NO_PROPS_DUMPS = tuple(_legacy_dump(props=p) for p in _FALSY_PROPS) + (_legacy_dump(),)


class TestClassRef:
    def test_reads_the_legacy_full_dump(self):
        payload = {"__class__": "Passageway", "__module__": "objects", "props": {"name": "Gate"}}
        assert class_ref(payload) == ClassRef("objects", "Passageway", {"name": "Gate"})

    def test_reads_the_dotted_placeholder_shape(self):
        payload = {"class": "story.ch03.MaraObservationEvent", "params": {"repeat": False}}
        ref = class_ref(payload)
        assert ref == ClassRef("story.ch03", "MaraObservationEvent", {"repeat": False})
        assert ref.dotted == "story.ch03.MaraObservationEvent"

    def test_reads_the_colon_placeholder_shape_the_engine_also_accepts(self):
        # map_placeholders prefers ":" when present; a walk that split only on
        # "." would drop this placement silently.
        assert class_ref({"class": "objects:Passageway"}) == ClassRef("objects", "Passageway", {})

    @pytest.mark.parametrize(
        "payload",
        [None, "Passageway", {}, {"__class__": "Passageway"}, {"__module__": "objects"}],
    )
    def test_a_value_that_is_no_payload_is_not_a_placement(self, payload):
        assert class_ref(payload) is None

    @pytest.mark.parametrize(
        "payload",
        [
            {"class": ""},
            {"class": "Passageway"},
            {"class": 7},
            {"class": "objects."},
            {"class": "objects.Passageway", "params": []},
            {"class": "objects.Passageway", "params": "x"},
        ],
    )
    def test_a_malformed_placeholder_raises_as_the_engine_does(self, payload):
        with pytest.raises(map_placeholders.PlaceholderError):
            class_ref(payload)
        with pytest.raises(map_placeholders.PlaceholderError):
            map_placeholders.instantiate_placeholder(payload)

    def test_a_placeholders_overrides_apply_over_its_params(self):
        """The loader sets ``overrides`` after construction, so an override of
        an authored param is the value the game ends up with."""
        payload = {
            "class": "objects.Crate",
            "params": {"name": "Box", "overrides": {"name": "Chest", "hidden": True}},
        }
        assert class_ref(payload).props == {"name": "Chest", "hidden": True}

    @pytest.mark.parametrize("props", _TRUTHY_NON_OBJECT_PROPS, ids=repr)
    def test_a_legacy_dump_whose_props_is_truthy_but_not_an_object_raises(self, props):
        # Stricter than the loader, which drops such a placement without a
        # word (see ``test_the_loader_reads_legacy_props_the_same_way``):
        # raising is what keeps the placement in front of the guards.
        with pytest.raises(map_placeholders.PlaceholderError):
            class_ref(_legacy_dump(props=props))

    @pytest.mark.parametrize("payload", _NO_PROPS_DUMPS, ids=repr)
    def test_a_legacy_dump_without_object_props_reads_as_empty(self, payload):
        # As at load: the loader reads ``payload.get("props") or {}``.
        assert class_ref(payload) == ClassRef("objects", "Passageway", {})

    @pytest.mark.parametrize(
        "payload, loads",
        [(payload, True) for payload in _NO_PROPS_DUMPS]
        + [(_legacy_dump(props=p), False) for p in _TRUTHY_NON_OBJECT_PROPS],
        ids=repr,
    )
    def test_the_loader_reads_legacy_props_the_same_way(self, payload, loads):
        """The engine side of the legacy-props tests above: the loader keeps
        every dump the walk reads as having no props, and drops -- rather than
        raising on -- every dump the walk raises on."""
        instance = Universe()._deserialize_saved_instance(payload)
        assert (instance is not None) is loads, instance


class TestPlacement:
    def test_ref_is_the_class_reference_it_carries(self):
        placement = Placement("x.json", "(0, 0)", "objects", "Passageway", {"name": "Gate"})
        assert placement.ref == ClassRef("objects", "Passageway", {"name": "Gate"})
        assert placement.ref.dotted == "objects.Passageway"


class TestResolveClass:
    def test_resolves_a_shipped_placement_through_the_engine(self):
        ferry = next(
            p for p in object_placements()
            if p.class_name == "Passageway" and p.props.get("name") == FERRY_LANDING_NAME
        )
        assert resolve_class(ferry) is Passageway

    def test_applies_the_engine_trust_gate(self):
        hostile = Placement("x.json", "(0, 0)", "os", "system", {})
        with pytest.raises(map_placeholders.PlaceholderSecurityError):
            resolve_class(hostile)


class TestTheWalks:
    @pytest.mark.parametrize(
        "section, walk",
        [("objects", object_placements), ("events", event_placements)],
        ids=["objects", "events"],
    )
    def test_every_shipped_payload_becomes_a_placement(self, section, walk):
        """Completeness, not just presence: the walk drops no payload a
        shipped tile carries, so no placement is invisible to the guards."""
        shipped = sum(
            1
            for _path, decoded in map_data()
            for _coord, tile in tiles(decoded)
            for payload in tile.get(section) or []
            if isinstance(payload, dict)
        )
        assert shipped, f"no shipped tile carries any {section}"
        assert len(walk()) == shipped

    def test_every_shipped_event_resolves_through_the_engine_gate(self):
        """The guards built on the event walk match on class NAME, so a stale
        module reference would satisfy them while the game refuses to load
        the placement. Resolving each one here closes that."""
        for placement in event_placements():
            resolve_class(placement)

    def test_the_event_walk_sees_the_ferry_landing_completer(self):
        placed = {(p.map_name, p.coord, p.class_name) for p in event_placements()}
        assert (FERRY_MAP.name, FERRY_TILE_KEY, FerryLandingObjectiveEvent.__name__) in placed
