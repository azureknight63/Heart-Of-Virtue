"""Issue #620, root fix: an instance never carries an attribute that shadows
behaviour its class declares -- not from a map, not from a save.

``resolve_interaction`` sources handlers from the class, which closed the
first hop. It did not close the rest: the handlers it returns call
``self.<method>`` (``go`` -> ``self.enter``, ``wash`` -> ``self.clean``,
``take_all`` -> ``self.refresh_description``), and an instance ``__dict__``
entry wins over any non-data descriptor. The legacy map loader ``setattr``s
every authored prop and a restored save carries ``__dict__`` verbatim, so
either could put an engine class there and have it called.

So the refusal lives where instance state is WRITTEN, once per loader:

* the map loader (``Universe._deserialize_saved_instance``) skips such props;
* ``SafeUnpickler.load_build`` drops such keys, and refuses BUILD onto a
  class, function or module -- pickle's slot-state branch is a bare
  ``setattr`` on whatever is on the stack, which rewrote engine classes for
  every session in the process;
* the class-marker gate requires a real, trusted CLASS, so an allowed
  ``module:name`` pair that resolves to a re-exported function
  (``story:import_module``) is refused.

``secure_pickle.shadows_class_behaviour`` is the one rule both loaders apply.
"""

import io
import pickle
import struct

import pytest

import src.secure_pickle as secure_pickle
import src.states as states_module
from src import map_placeholders
from src.narration import capture_narration
from src.objects import Container, HealingSpring, Passageway
from src.secure_pickle import (
    RestrictedUnpicklingError,
    safe_pickle_load,
    shadows_class_behaviour,
)
from tests._gs_fixtures import live_world
from tests._map_scan import all_placements, resolve_class

#: What a hostile prop or saved attribute nominates: an allow-listed engine
#: class that a stray call would construct.
_NOMINATED = ("states:Clean", states_module.Clean)

#: Dunders the grid adds by hand: ``dir()`` lists ``__class__`` and friends,
#: but the point of naming these two is that ``setattr(inst, "__class__",
#: X)`` retypes the instance and ``"__dict__"`` replaces its whole state.
_DUNDERS = ("__class__", "__dict__")


# ---------------------------------------------------------------------------
# The rule itself
# ---------------------------------------------------------------------------


class _Sample:
    POLICY = ("a", "b")
    _PRIVATE_POLICY = ("c",)
    plain_default = False

    def method(self):
        return "method"

    @staticmethod
    def helper():
        return "helper"

    @classmethod
    def factory(cls):
        return cls()

    @property
    def settable(self):
        return getattr(self, "_settable", None)

    @settable.setter
    def settable(self, value):
        self._settable = value

    class Nested:
        pass


@pytest.mark.parametrize(
    "name",
    ["method", "helper", "factory", "Nested", "POLICY", "_PRIVATE_POLICY",
     "__class__", "__dict__", "__init__"],
)
def test_behaviour_and_policy_constants_are_protected(name):
    assert shadows_class_behaviour(_Sample, name)


@pytest.mark.parametrize(
    "name", ["plain_default", "settable", "undeclared", "UNDECLARED_CAPS", 3]
)
def test_data_is_not_protected(name):
    """Plain defaults, data descriptors and undeclared names stay writable --
    they are what map props and saved state exist to carry."""
    assert not shadows_class_behaviour(_Sample, name)


def test_the_nearest_declaration_decides():
    """A subclass that turns an inherited method into data owns that name."""
    class Child(_Sample):
        method = "now data"

    assert not shadows_class_behaviour(Child, "method")


# ---------------------------------------------------------------------------
# The map loader
# ---------------------------------------------------------------------------


def _placed_classes():
    """Every class the shipped maps place, in every section the loader reads."""
    return sorted({resolve_class(p) for p in all_placements()}, key=lambda c: c.__qualname__)


_PLACED = _placed_classes()


def _protected_names(cls):
    return sorted(
        n for n in dir(cls)
        if not (n.startswith("__") and n.endswith("__"))
        and shadows_class_behaviour(cls, n)
    ) + list(_DUNDERS)


def test_the_placed_class_population_is_real():
    names = {cls.__name__ for cls in _PLACED}
    assert {"Passageway", "HealingSpring", "Container"} <= names, sorted(names)
    assert all(_protected_names(cls) for cls in _PLACED)


def _load(cls, props):
    player, game_map = live_world()
    tile = game_map[(0, 0)]
    payload = {
        "__class__": cls.__name__,
        "__module__": cls.__module__.removeprefix("src."),
        "props": props,
    }
    with capture_narration():
        inst = player.universe._deserialize_saved_instance(payload, tile=tile)
    assert inst is not None, f"the loader refused {cls.__name__} outright"
    return inst


def test_no_map_prop_can_shadow_class_behaviour():
    """Every placed class, every name it declares as behaviour or policy,
    each authored as a class-marker prop: none may reach ``__dict__``."""
    marker = {"__class_type__": _NOMINATED[0]}
    leaked = []
    for cls in _PLACED:
        names = _protected_names(cls)
        inst = _load(cls, {name: marker for name in names})
        assert type(inst) is cls, f"{cls.__name__} was retyped to {type(inst)}"
        leaked += [f"{cls.__name__}.{n}" for n in names if n in vars(inst) and n not in _DUNDERS]
    assert leaked == [], f"map props shadowed class behaviour: {leaked}"


def test_the_hops_past_the_resolver_are_closed_by_name():
    """The specific hops the security review traced, pinned by name so the
    grid above cannot quietly stop covering them."""
    marker = {"__class_type__": _NOMINATED[0]}
    for cls, name in (
        (Passageway, "enter"),
        (Passageway, "_name_alias_words"),
        (Passageway, "CROSSING_METHOD_NAMES"),
        (HealingSpring, "clean"),
        (Container, "refresh_description"),
    ):
        assert name in _protected_names(cls), (cls.__name__, name)
        assert name not in vars(_load(cls, {name: marker})), (cls.__name__, name)


def test_ordinary_props_and_property_setters_still_apply():
    """Positive control: the refusal is narrow. A data prop lands, and a
    property with a setter still runs its setter -- including on the loader's
    ``cls.__new__`` fallback path, where nothing else would apply it."""
    way = _load(Passageway, {"description": "A worn gate.",
                             "demo_end_ready_flag": "custom_gate"})
    assert way.description == "A worn gate."
    assert way.demo_end_ready_flag == "custom_gate"
    assert not shadows_class_behaviour(Passageway, "demo_end_ready_flag")


def test_no_shipped_placement_authors_a_refused_prop():
    """The refusal changes nothing that ships: no authored prop names
    behaviour its class declares."""
    offenders = [
        f"{p.map_name} {p.coord} {p.class_name}.{key}"
        for p in all_placements()
        for key in p.props
        if shadows_class_behaviour(resolve_class(p), key)
    ]
    assert offenders == [], offenders


# ---------------------------------------------------------------------------
# The class-marker gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spec", ["story:import_module", "functions:canonical_module_name"]
)
def test_a_class_marker_must_resolve_to_a_class(spec):
    """Both pairs pass the module allow-list; neither is a class. The first
    is ``importlib.import_module``, re-exported by ``src.story``."""
    player, _map = live_world()
    with capture_narration():
        assert player.universe._deserialize_saved_instance({"__class_type__": spec}) is None
    with pytest.raises(map_placeholders.PlaceholderSecurityError):
        map_placeholders.resolve_class(spec)


def test_a_real_class_marker_still_resolves():
    player, _map = live_world()
    with capture_narration():
        resolved = player.universe._deserialize_saved_instance(
            {"__class_type__": _NOMINATED[0]}
        )
    assert resolved is _NOMINATED[1]
    assert map_placeholders.resolve_class(_NOMINATED[0]) is _NOMINATED[1]


# ---------------------------------------------------------------------------
# The save loader
# ---------------------------------------------------------------------------


def _unicode(text):
    raw = text.encode("utf-8")
    return b"X" + struct.pack("<I", len(raw)) + raw


def _build_onto_global(module, name, attribute, value_module, value_name):
    """A protocol-2 stream: push global ``module.name``, then BUILD it with
    slot-state ``{attribute: global value_module.value_name}``."""
    return (
        b"\x80\x02"
        + b"c" + f"{module}\n{name}\n".encode()
        + b"N"                                   # no __dict__ state
        + b"}" + _unicode(attribute)             # slot-state dict ...
        + b"c" + f"{value_module}\n{value_name}\n".encode()
        + b"s"                                   # ... {attribute: value}
        + b"\x86"                                # TUPLE2 (state, slotstate)
        + b"b"                                   # BUILD
        + b"."
    )


def test_the_crafted_stream_is_live_under_a_stock_unpickler():
    """Non-vacuity for the two refusals below: the same stream shape DOES
    write onto an engine class when nothing gates BUILD. Aimed at a throwaway
    attribute and removed again, so no class is left modified."""
    data = _build_onto_global("src.objects", "Passageway", "_probe_620",
                              "src.states", "Clean")
    try:
        pickle.loads(data)
        assert Passageway.__dict__.get("_probe_620") is states_module.Clean
    finally:
        if "_probe_620" in Passageway.__dict__:
            delattr(Passageway, "_probe_620")


@pytest.mark.parametrize("strict", [True, False])
def test_build_onto_a_class_is_refused_and_the_class_is_untouched(strict):
    original = Passageway.__dict__["enter"]
    data = _build_onto_global("src.objects", "Passageway", "enter",
                              "src.states", "Clean")
    try:
        with pytest.raises(RestrictedUnpicklingError):
            safe_pickle_load(io.BytesIO(data), strict=strict)
        assert Passageway.__dict__["enter"] is original
    finally:
        if Passageway.__dict__.get("enter") is not original:
            Passageway.enter = original


def test_build_onto_a_function_is_refused():
    data = _build_onto_global("src.functions", "canonical_module_name",
                              "__defaults__", "src.states", "Clean")
    with pytest.raises(RestrictedUnpicklingError):
        safe_pickle_load(io.BytesIO(data), strict=True)


def test_a_restored_attribute_that_shadows_behaviour_is_dropped():
    """A saved spring whose ``__dict__`` names ``clean`` (the staticmethod
    ``wash`` calls) and ``drink`` loads without them -- and keeps its data."""
    spring = HealingSpring(player=None, tile=None)
    spring.description = "A spring someone has tampered with."
    spring.__dict__["clean"] = _NOMINATED[1]
    spring.__dict__["drink"] = _NOMINATED[1]
    events = []

    loaded = safe_pickle_load(
        io.BytesIO(secure_pickle.serialize_for_save(spring)), strict=True, events=events
    )

    assert "clean" not in vars(loaded) and "drink" not in vars(loaded)
    assert loaded.description == "A spring someone has tampered with."
    dropped = sorted(e["attribute"] for e in events if e["kind"] == "dropped")
    assert dropped == ["clean", "drink"], events


# A whole built universe round-trips with no drop and no refusal:
# tests/api/test_save_shadowing_roundtrip.py (Universe.build mutates
# module-level registries, so it runs in the per-file job).
