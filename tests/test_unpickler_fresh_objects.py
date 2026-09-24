"""SafeUnpickler may only mutate what the load itself allocated, and may only
call a closed set of reconstruction helpers (issue #638).

Two root causes, each reachable more than one way:

1. **State applied to shared objects.** BUILD (and the container opcodes
   APPEND/APPENDS/SETITEM/SETITEMS/ADDITEMS) apply attacker state to whatever
   object sits beneath them on the stack. Two routes put a *pre-existing,
   process-wide* object there:

   * ``find_class`` handed back module-level engine INSTANCES. The provenance
     gate read ``obj.__module__``, which an instance inherits from its class,
     and a missing ``__name__`` became ``""`` -- so ``src.npc._loot:loot``
     (the shared loot table every NPC drop reads) passed as "engine code".
   * REDUCE / NEWOBJ on a class whose constructor returns an existing object:
     ``Direction(0)`` is the ``Direction.N`` singleton.

   Either way one crafted save rewrote state for every session in the
   process.

2. **Engine callables run with attacker arguments.** REDUCE (and OBJ/INST,
   which call their class) invoked any allow-listed engine function:
   ``save_format.write_v2_file`` opens an arbitrary path for writing,
   ``functions.seek_class`` resolves attributes of story/tileset modules
   without the provenance gate.

The fix is positive, not a filter on these inputs: the loader tracks the
objects it allocated and refuses to mutate anything else, and REDUCE calls
only classes whose construction is known (stdlib reconstruction types, engine
enums by value, engine exceptions) plus three stdlib helpers.
"""

import io
import pickle

import pytest

import src.secure_pickle as sp

PROTO4 = b"\x80\x04"
STACK_GLOBAL = b"\x93"
MARK = b"("
TUPLE = b"t"
TUPLE1 = b"\x85"
EMPTY_TUPLE = b")"
EMPTY_DICT = b"}"
EMPTY_LIST = b"]"
SETITEM = b"s"
APPEND = b"a"
BUILD = b"b"
REDUCE = b"R"
NEWOBJ = b"\x81"
OBJ = b"o"
NONE = b"N"
STOP = b"."


def su(text):
    """SHORT_BINUNICODE."""
    encoded = text.encode()
    assert len(encoded) < 256
    return b"\x8c" + bytes([len(encoded)]) + encoded


def int1(value):
    """BININT1."""
    return b"K" + bytes([value])


def glob(module, name):
    return su(module) + su(name) + STACK_GLOBAL


def state(key, value_ops):
    return EMPTY_DICT + su(key) + value_ops + SETITEM


def load(stream, strict=True, events=None):
    return sp.safe_pickle_load(io.BytesIO(PROTO4 + stream + STOP),
                               strict=strict, events=events)


# ---------------------------------------------------------------------------
# 1. BUILD onto shared objects
# ---------------------------------------------------------------------------

@pytest.fixture
def shared_loot():
    from src.npc._loot import loot

    original = loot.__dict__.copy()
    yield loot
    loot.__dict__.clear()
    loot.__dict__.update(original)


def test_build_onto_the_shared_loot_table_is_refused(shared_loot):
    lev0 = shared_loot.lev0
    stream = glob("src.npc._loot", "loot") + state("lev0", su("pwned")) + BUILD

    with pytest.raises(sp.RestrictedUnpicklingError):
        load(stream)

    assert shared_loot.lev0 is lev0
    assert isinstance(shared_loot.lev0, dict)


def test_find_class_never_returns_an_engine_instance(shared_loot):
    """The resolution step alone: no BUILD needed to see the instance leak."""
    with pytest.raises(sp.RestrictedUnpicklingError):
        load(glob("src.npc._loot", "loot"))


@pytest.mark.parametrize("module,name", [
    ("src.positions", "Direction.N"),                     # enum member
    ("src.moves._base", "UnavailableReason.ON_COOLDOWN"),
    ("src.npc._loot", "loot.__init__"),                   # bound method of an instance
    ("src.positions", "CombatPosition.set_grid_bounds"),  # classmethod bound to a class
])
def test_find_class_refuses_members_and_bound_methods(module, name):
    with pytest.raises(sp.RestrictedUnpicklingError):
        load(glob(module, name))


@pytest.fixture
def direction_n():
    from src.positions import Direction

    original = Direction.N.__dict__.copy()
    yield Direction
    Direction.N.__dict__.clear()
    Direction.N.__dict__.update(original)


def test_reduce_direction_then_build_cannot_rewrite_the_enum(direction_n):
    stream = (glob("src.positions", "Direction") + int1(0) + TUPLE1 + REDUCE
              + state("_value_", int1(99)) + BUILD)

    with pytest.raises(sp.RestrictedUnpicklingError):
        load(stream)

    assert direction_n.N.value == 0
    assert direction_n(0) is direction_n.N


def test_newobj_direction_then_build_cannot_rewrite_the_enum(direction_n):
    """NEWOBJ reaches the same singleton through ``Enum.__new__``."""
    stream = (glob("src.positions", "Direction") + int1(0) + TUPLE1 + NEWOBJ
              + state("_value_", int1(99)) + BUILD)

    with pytest.raises(sp.RestrictedUnpicklingError):
        load(stream)

    assert direction_n.N.value == 0


def test_container_opcodes_cannot_mutate_a_shared_object(direction_n):
    """APPEND onto an object the load did not allocate is refused outright,
    not left to whatever ``append`` the object happens to have."""
    stream = (glob("src.positions", "Direction") + int1(0) + TUPLE1 + REDUCE
              + su("x") + APPEND)

    with pytest.raises(sp.RestrictedUnpicklingError):
        load(stream)


def test_reduce_direction_by_value_still_loads(direction_n):
    """The legitimate half of the same opcode: a combat save stores facing as
    ``Direction(value)`` and must get the singleton back."""
    stream = glob("src.positions", "Direction") + int1(90) + TUPLE1 + REDUCE
    assert load(stream) is direction_n.E


# ---------------------------------------------------------------------------
# 2. REDUCE / OBJ calling engine functions
# ---------------------------------------------------------------------------

def test_reduce_write_v2_file_is_refused_and_writes_nothing(tmp_path):
    target = tmp_path / "clobbered.json"
    stream = (glob("src.save_format", "write_v2_file")
              + NONE + su(str(target)) + b"\x86" + REDUCE)

    with pytest.raises(sp.RestrictedUnpicklingError):
        load(stream)

    assert not target.exists()


def test_reduce_seek_class_is_refused():
    stream = glob("src.functions", "seek_class") + su("Universe") + TUPLE1 + REDUCE
    with pytest.raises(sp.RestrictedUnpicklingError):
        load(stream)


@pytest.mark.parametrize("module,name", [
    ("src.functions", "canonical_module_name"),
    ("src.secure_pickle", "canonical_module_name"),
    ("src.functions", "copy_item_state"),
    ("src.player", "Player.gain_exp"),
])
def test_reduce_an_engine_function_is_refused(module, name):
    stream = glob(module, name) + su("items") + TUPLE1 + REDUCE
    with pytest.raises(sp.RestrictedUnpicklingError):
        load(stream)


def test_obj_opcode_cannot_call_an_engine_function():
    """OBJ calls its first argument when given args: the same primitive as
    REDUCE through a different opcode."""
    stream = (MARK + glob("src.functions", "canonical_module_name")
              + su("items") + OBJ)
    with pytest.raises(sp.RestrictedUnpicklingError):
        load(stream)


def test_inst_opcode_cannot_call_an_engine_function():
    stream = MARK + su("items") + b"isrc.functions\ncanonical_module_name\n"
    with pytest.raises(sp.RestrictedUnpicklingError):
        load(stream)


def test_reduce_an_ordinary_engine_class_is_refused():
    """Calling an engine class runs its ``__init__`` with attacker arguments;
    no save the engine writes reduces one (they all use NEWOBJ + BUILD)."""
    stream = glob("src.items", "Gold") + int1(5) + TUPLE1 + REDUCE
    with pytest.raises(sp.RestrictedUnpicklingError):
        load(stream)


# ---------------------------------------------------------------------------
# Regressions: what genuine saves need keeps loading, strictly
# ---------------------------------------------------------------------------

def _round_trip(obj):
    events = []
    loaded = sp.safe_pickle_load(io.BytesIO(sp.serialize_for_save(obj)),
                                 strict=True, events=events)
    assert [e for e in events if e["kind"] in ("rejected", "dropped")] == []
    return loaded


def test_combat_position_with_direction_round_trips():
    from src.positions import CombatPosition, Direction

    loaded = _round_trip({"pos": CombatPosition(x=3, y=4, facing=Direction.SW)})
    assert loaded["pos"].facing is Direction.SW
    assert (loaded["pos"].x, loaded["pos"].y) == (3, 4)


def test_player_mid_combat_position_round_trips():
    from src.player import Player
    from src.positions import CombatPosition, Direction

    player = Player()
    player.__dict__.pop("_combat_adapter", None)
    player.combat_position = CombatPosition(x=1, y=2, facing=Direction.E)
    loaded = _round_trip(player)
    assert loaded.combat_position.facing is Direction.E


def test_engine_exceptions_round_trip():
    from src.map_placeholders import PlaceholderError

    err = PlaceholderError("bad placeholder")
    err.detail = "kept"
    loaded = _round_trip(err)
    assert type(loaded) is PlaceholderError
    assert loaded.args == ("bad placeholder",)
    assert loaded.detail == "kept"


def test_sanctioned_stdlib_reconstruction_round_trips():
    import collections
    import datetime
    import decimal
    import functools
    import re
    import uuid

    from src.functions import canonical_module_name

    payload = {
        "when": datetime.datetime(2026, 9, 24, 12, 0),
        "day": datetime.date(2026, 9, 24),
        "span": datetime.timedelta(seconds=5),
        "dd": collections.defaultdict(list, {"a": [1]}),
        "od": collections.OrderedDict([("k", 1)]),
        "dec": decimal.Decimal("1.5"),
        "id": uuid.UUID(int=7),
        "rx": re.compile(r"ab+", re.I),
        "fn": functools.partial(canonical_module_name, "items"),
        "cx": complex(1, 2),
        "fs": frozenset({1, 2}),
        "ba": bytearray(b"xy"),
    }
    loaded = _round_trip(payload)
    assert loaded["dd"]["a"] == [1] and loaded["dd"].default_factory is list
    assert loaded["od"] == payload["od"]
    assert loaded["rx"].pattern == "ab+"
    assert loaded["fn"]() == "src.items"
    for key in ("when", "day", "span", "dec", "id", "cx", "fs", "ba"):
        assert loaded[key] == payload[key]


@pytest.mark.parametrize("protocol", [0, 1, 2, 3, 4, 5])
def test_every_protocol_round_trips_an_engine_graph(protocol):
    """Protocols 0/1 reconstruct through ``copyreg._reconstructor`` and
    INST/OBJ rather than NEWOBJ; all of them must still load strictly."""
    from src.items import Gold
    from src.positions import CombatPosition, Direction

    gold = Gold(12)
    graph = {"gold": gold, "again": gold, "pos": CombatPosition(1, 1, Direction.S),
             "items": [gold, {"nested": (1, 2)}]}
    events = []
    loaded = sp.safe_pickle_load(io.BytesIO(pickle.dumps(graph, protocol)),
                                 strict=True, events=events)
    assert [e for e in events if e["kind"] in ("rejected", "dropped")] == []
    assert loaded["gold"] is loaded["again"] is loaded["items"][0]
    assert loaded["gold"].amt == 12
    assert loaded["pos"].facing is Direction.S


def test_function_references_still_load_as_values():
    """Engine functions stay resolvable as DATA (``actions.Save`` holds an
    unbound method); only calling them at load time is refused."""
    from src.player import Player
    from src.save_format import write_v2_file

    loaded = _round_trip({"meth": Player.gain_exp, "fn": write_v2_file})
    assert loaded["meth"] is Player.gain_exp
    assert loaded["fn"] is write_v2_file
