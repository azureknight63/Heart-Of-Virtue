"""Issue #651: the legacy map loader applies only declared props.

Two loaders apply map-authored props. The #463 placeholder path
(``map_placeholders.instantiate_placeholder``) drops any override its class
does not declare in ``MAP_AUTHORED_OVERRIDES``. The legacy full-dump path
(``Universe._deserialize_saved_instance``) used to ``setattr`` EVERY remaining
prop, so map data could shadow any class-level default per instance -- the
same defect class as #620, reachable through the path every shipped map uses.

Both now apply one rule, ``map_placeholders.legacy_prop_allowed``: a prop
reaches ``setattr`` only if its class declares it an override -- or, when the
constructor could not be called with the authored kwargs (the ``__new__``
fallback), a constructor param its class declares authored, since nothing
else would apply it. A dropped key is dropped silently, as the placeholder
path drops one; a key that would shadow behaviour still narrates its refusal.

The guard at the bottom derives, from the shipped maps themselves, every prop
whose authored value actually changes the loaded instance, and requires each
to land -- so the allow-list is checked against what ships rather than
against a hand-kept list.
"""

import functools
import json

import pytest

from src import map_placeholders
from src.items import Book
from src.narration import capture_narration
from src.objects import Passageway
from src.player import Player
from src.tiles import MapTile
from src.universe import Universe
from tests._gs_fixtures import live_world
from tests._map_scan import map_data, tiles

# ---------------------------------------------------------------------------
# Reproduction: a prop shadowing a class-level default
# ---------------------------------------------------------------------------


def _payload(cls, props):
    return {
        "__class__": cls.__name__,
        "__module__": cls.__module__.removeprefix("src."),
        "props": props,
    }


def _load(payload):
    player, game_map = live_world()
    with capture_narration():
        return player.universe._deserialize_saved_instance(
            payload, tile=game_map[(0, 0)]
        )


def test_a_prop_shadowing_a_class_default_is_dropped():
    """``Book.stockable = False`` is a lowercase class-level policy flag
    (#632), so the #620 shadowing rule -- dunders, behaviour, UPPER_CASE
    constants -- does not cover it. Nothing declares it authorable."""
    assert Book.stockable is False
    assert "stockable" not in map_placeholders.authored_override_names(Book)

    book = _load(_payload(Book, {"name": "Ledger", "stockable": True}))

    assert "stockable" not in vars(book), "a map prop shadowed Book.stockable"
    assert book.stockable is False
    # Positive control: a declared override still lands.
    assert book.name == "Ledger"


def test_an_undeclared_prop_is_dropped():
    way = _load(_payload(Passageway, {"is_shop_exit": True, "description": "A gate."}))
    assert "is_shop_exit" not in vars(way)
    assert way.description == "A gate."


def test_a_dropped_prop_is_never_deserialized(monkeypatch):
    """A key the class does not accept must not build the engine instance
    it nominates either -- dropping it after construction would still run
    that class's ``__init__`` on map data."""
    built = []
    real = Universe._deserialize_saved_instance

    def spy(self, payload, _depth=0, tile=None):
        if isinstance(payload, dict) and payload.get("__class__") == "Clean":
            built.append(payload)
        return real(self, payload, _depth=_depth, tile=tile)

    monkeypatch.setattr(Universe, "_deserialize_saved_instance", spy)
    nested = {"__class__": "Clean", "__module__": "states", "props": {}}
    book = _load(_payload(Book, {"undeclared": nested}))

    assert "undeclared" not in vars(book)
    assert built == []


def test_the_constructor_fallback_still_applies_declared_params(monkeypatch):
    """When the authored kwargs cannot construct the class, the loader falls
    back to a bare instance; the declared constructor params are then the
    only way the authored values arrive, so they stay applicable there --
    and an undeclared prop is still dropped."""
    assert "chars_per_page" in map_placeholders.authored_param_names(Book)
    real_init = Book.__init__

    # functools.wraps keeps Book's real signature visible to inspect, which
    # is what both the loader and legacy_prop_allowed read.
    @functools.wraps(real_init)
    def refuse_kwargs(self, **kwargs):
        if kwargs:
            raise TypeError("forced constructor failure")
        real_init(self)

    monkeypatch.setattr(Book, "__init__", refuse_kwargs)
    book = _load(_payload(Book, {"name": "Tome", "chars_per_page": 50,
                                 "stockable": True}))
    assert book.name == "Tome"
    assert book.chars_per_page == 50
    assert "stockable" not in vars(book)


def test_legacy_prop_allowed_is_the_one_rule():
    assert map_placeholders.legacy_prop_allowed(Book, "name", constructed=True)
    assert not map_placeholders.legacy_prop_allowed(Book, "stockable", constructed=True)
    assert not map_placeholders.legacy_prop_allowed(Book, "stockable", constructed=False)
    # A declared constructor param its __init__ takes is accepted, as the
    # placeholder path accepts it; an undeclared one only on the fallback,
    # where the constructor never received it.
    assert "text_file_path" not in map_placeholders.authored_override_names(Book)
    assert map_placeholders.legacy_prop_allowed(Book, "text_file_path", constructed=True)
    assert "chars_per_page" in map_placeholders._init_param_names(Book)
    assert "chars_per_page" in map_placeholders.authored_param_names(Book)
    assert not map_placeholders.legacy_prop_allowed(Passageway, "player", constructed=True)
    assert map_placeholders.legacy_prop_allowed(Passageway, "player", constructed=False)
    # Never a behaviour-shadowing name, even if one were declared.
    assert not map_placeholders.legacy_prop_allowed(Passageway, "enter", constructed=False)
    assert not map_placeholders.legacy_prop_allowed(Passageway, "__class__", constructed=False)


# ---------------------------------------------------------------------------
# Guard: every prop the shipped maps legitimately author still lands
# ---------------------------------------------------------------------------

#: Props shipped legacy dumps carry that are deliberately NOT authorable, by
#: attribute name, with the reason. A full dump is a snapshot of ``__dict__``,
#: so it carries runtime state and stale derived values alongside what the
#: author meant; these are the ones the loader now leaves to the class. Each
#: entry is a decision (#651), not an exemption -- a newly authored key that
#: changes a loaded instance fails the guard until it is declared on its class
#: or added here with a reason.
NOT_AUTHORABLE = {
    # Runtime state and back-references the engine owns.
    "target": "combat target, set by the engine at spawn and in combat",
    "user": "a move's owner, bound when the move is built",
    "thread": "event session bookkeeping (#463 excludes it for every Event)",
    "has_run": "event session bookkeeping",
    "referenceobj": "event session bookkeeping",
    "interactions": "derived by the item class (Book adds read/use)",
    "known_moves": "built by the NPC class with the NPC bound as user",
    # Derived stats the engine recomputes from *_base (functions.reset_stats)
    # or its own tables; authors set maxhp/damage/... and *_base via the
    # declared overrides instead.
    "hp": "derived from maxhp at construction",
    "maxhp_base": "base stat; author maxhp",
    "damage_base": "base stat; author damage",
    "finesse_base": "base stat; author finesse",
    "exp_award_base": "base stat; author exp_award",
    "resistance": "live copy of resistance_base, reset from it",
    "status_resistance": "live copy of status_resistance_base, reset from it",
    "loquacity_recovery": "recomputed by the chat persona at load",
    # Item classification is class identity, and subtype gates move and
    # enchantment eligibility.
    "type_s": "not an Item attribute; stale dump",
    "subtype": "class-defined classification",
    "gives_exp": "class-defined",
    # Attributes nothing reads.
    "is_shop_exit": "read nowhere in src/",
    "allowed_subtypes": "constructor kwarg; the attribute is allowed_item_types",
    "items": "stale Container dump of '<circular_ref:...>' strings",
    "range_decay": "per-class ranged falloff tuning; only a testing-map bow dumps it",
    # Event constructor params the testing-map statue re-dumps.
    "name": None,
    "repeat": None,
    "params": None,
}

#: ``name``/``repeat``/``params`` are authorable on every class that declares
#: them; they are only unauthorable where the class does not (the
#: testing-map WhisperingStatue). Keyed by class so they stay narrow.
_CLASS_SCOPED = {"name", "repeat", "params"}
_CLASS_SCOPED_ALLOWED = {("WhisperingStatue", k) for k in _CLASS_SCOPED}

#: Floor for the derived population: ``(class, key)`` pairs whose authored
#: value changes the loaded instance. Well under the real count; it exists to
#: catch a derivation that has stopped matching, since a scan that matches
#: nothing approves of everything.
MIN_EFFECTIVE_PROPS = 40


def _plain(value):
    """True for a JSON value holding no nested payload."""
    if isinstance(value, dict):
        if "__class__" in value or "__class_type__" in value or "class" in value:
            return False
        return all(_plain(v) for v in value.values())
    if isinstance(value, list):
        return all(_plain(v) for v in value)
    return True


def _norm(value):
    return json.loads(json.dumps(value, default=repr))


def _legacy_dumps(value, dropped_parent=False):
    """Every legacy dump in ``value``, recursing into the props of each --
    but not under a NOT_AUTHORABLE key, which the loader never builds."""
    if isinstance(value, list):
        for v in value:
            yield from _legacy_dumps(v)
    elif isinstance(value, dict):
        if "__class__" in value and "__module__" in value:
            yield value
            for key, v in (value.get("props") or {}).items():
                if key not in NOT_AUTHORABLE or key in _CLASS_SCOPED:
                    yield from _legacy_dumps(v)
        else:
            for v in value.values():
                yield from _legacy_dumps(v)


def _shipped_legacy_dumps():
    found = []
    for path, decoded in map_data():
        for coord, tile_data in tiles(decoded):
            for section in ("objects", "events", "items", "npcs"):
                for payload in tile_data.get(section) or []:
                    for dump in _legacy_dumps(payload):
                        found.append((path.name, coord, dump))
    return found


def _read(inst, cls, key):
    attr = map_placeholders.authored_attr_aliases(cls).get(key, key)
    return getattr(inst, attr)


@pytest.fixture(scope="module")
def effective_props():
    """``{(class, key): [(map, coord, authored, loaded, props), ...]}`` for every
    plain prop whose authored value differs from what the class builds
    without it -- i.e. every prop a shipped legacy dump actually changes.

    The reference instance is the same dump loaded with only the constructor
    kwargs it authors, through the real loader, so it is what the class
    builds from that placement when no prop is applied after construction.
    """
    import random

    player = Player()
    universe = Universe(player=player)
    game_map = {"name": "allowlist-guard"}
    tile = MapTile(universe, game_map, 0, 0)
    game_map[(0, 0)] = tile
    universe.maps = [game_map]
    player.universe, player.map, player.current_room = universe, game_map, tile

    found = {}
    with capture_narration():
        for map_name, coord, dump in _shipped_legacy_dumps():
            cls = map_placeholders.resolve_class(f"{dump['__module__']}:{dump['__class__']}")
            props = dump.get("props") or {}
            ctor = map_placeholders._init_param_names(cls)
            random.seed(651)
            reference = universe._deserialize_saved_instance(
                {**dump, "props": {k: v for k, v in props.items() if k in ctor}}, tile=tile
            )
            random.seed(651)
            loaded = universe._deserialize_saved_instance(dump, tile=tile)
            if reference is None or loaded is None:
                continue
            for key, authored in props.items():
                if not _plain(authored) or key in ("player", "tile"):
                    continue
                try:
                    built = _norm(_read(reference, cls, key))
                except Exception:
                    built = object()
                if built == _norm(authored):
                    continue
                try:
                    landed = _norm(_read(loaded, cls, key))
                except Exception:
                    landed = "<unset>"
                found.setdefault((cls, key), []).append((map_name, coord, authored, landed, props))
    return found


def test_the_derived_population_is_real(effective_props):
    assert len(effective_props) >= MIN_EFFECTIVE_PROPS, sorted(
        f"{c.__name__}.{k}" for c, k in effective_props
    )
    # The props the issue names, and the ones #630 depends on.
    names = {(c.__name__, k) for c, k in effective_props}
    assert ("Passageway", "keywords") in names
    assert ("WallInscription", "announce") in names
    assert ("Gold", "count") in names


def _not_authorable(cls, key):
    if key in _CLASS_SCOPED:
        return (cls.__name__, key) in _CLASS_SCOPED_ALLOWED
    return key in NOT_AUTHORABLE


def test_every_legitimately_authored_prop_is_declared(effective_props):
    """Every prop a shipped dump changes is on its class's allow-list,
    or is a recorded NOT_AUTHORABLE decision."""
    undeclared = sorted(
        f"{cls.__name__}.{key} ({hits[0][0]} {hits[0][1]})"
        for (cls, key), hits in effective_props.items()
        if key not in map_placeholders.authored_override_names(cls)
        and not _not_authorable(cls, key)
    )
    assert undeclared == [], undeclared


#: ``(class, key) -> key`` whose authored truthy value legitimately rewrites
#: the first after it lands: ``Container.start_open``'s setter sets ``state``,
#: so Milo's Weapon Rack authors ``state: "closed"`` and still starts open.
_SUPERSEDED_BY = {("Container", "state"): "start_open"}


def _superseded(cls, key, props):
    later = _SUPERSEDED_BY.get((cls.__name__, key))
    return bool(later and props.get(later))


def test_every_legitimately_authored_prop_lands(effective_props):
    """...and the loader actually applies it: the loaded instance carries the
    authored value, not the class default."""
    lost = sorted(
        f"{cls.__name__}.{key} {map_name} {coord}: authored {authored!r}, loaded {landed!r}"
        for (cls, key), hits in effective_props.items()
        if not _not_authorable(cls, key)
        for map_name, coord, authored, landed, props in hits
        if landed != _norm(authored)
        and not _superseded(cls, key, props)
    )
    assert lost == [], lost


def test_not_authorable_keys_are_really_dropped(effective_props):
    """The other half of the decision: a NOT_AUTHORABLE key is not applied."""
    applied = sorted(
        f"{cls.__name__}.{key} {map_name} {coord}"
        for (cls, key), hits in effective_props.items()
        if _not_authorable(cls, key)
        and key not in map_placeholders.authored_override_names(cls)
        for map_name, coord, authored, landed, props in hits
        if landed == _norm(authored)
    )
    assert applied == [], applied
