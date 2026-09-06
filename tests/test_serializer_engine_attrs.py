"""Derived guard: every attribute a serializer reads off a combatant/state must
be a name the engine actually defines or sets.

WHY THIS EXISTS
---------------
Issues #411/#412/#430/#431/#432 and the ``health``/``max_health`` defect in
``serialize_health_bar`` were all the same shape:

    getattr(combatant, "<name-the-engine-never-had>", <plausible default>)

The ``getattr`` default swallows the miss, so the wire silently carries the
default forever and no per-function test notices — a hand-written test asserts
the default and passes.  Fixing them one at a time only ever closes the
instance, never the class.

So this module does not hand-list the bad names.  It DERIVES the legal name set
from two authorities that are independent of the serializer under test, then
checks every attribute read in ``src/api/serializers/`` against them:

  AUTHORITY 1 — the live engine objects.  A real ``Player``, a real ``NPC`` and
  a real ``State`` are constructed and probed with ``hasattr``, widened by the
  class-level names of every ``Combatant`` subclass in the project (so a
  mixin-provided method such as ``ConversationalNPCMixin._init_chat_attrs``,
  which a base ``NPC`` does not have, is still recognised).  Rename an engine
  attribute and this set moves with it.

  AUTHORITY 2 — attributes the codebase ASSIGNS onto a combatant.  Several
  legitimate wire fields (``suggested_moves``, ``suggestions_loading``,
  ``last_move_name``, ``last_move_target_id``, ``battle_symbol``) are attached
  at runtime by the API layer or by an NPC subclass, so they are absent from a
  freshly constructed object but are not dead names.  These are discovered by
  scanning ``src/`` for ``<combatant>.<name> = ...`` stores.

A name that appears in NEITHER authority has no writer anywhere in the project:
nothing can ever produce it, so reading it is dead code by construction.  That
is the failure this guard names.

Both the receiver-resolution and the two authorities are exercised by
self-tests below, so the scan cannot quietly degrade into "found nothing,
passed".
"""

import ast
import pathlib
from typing import Dict, FrozenSet, List, NamedTuple, Optional, Set

import pytest

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = _REPO_ROOT / "src"
SERIALIZER_DIR = SRC_ROOT / "api" / "serializers"


# --------------------------------------------------------------------------
# AUTHORITY 1 — real engine objects
# --------------------------------------------------------------------------
def _engine_probes() -> Dict[str, object]:
    """One real instance per engine kind the serializers read from.

    Real objects, never mocks: a mock materialises whatever attribute is asked
    of it and so cannot disagree with the code under test.
    """
    from src.npc import NPC
    from src.player import Player
    from src.states import State

    npc = NPC(
        name="Probe",
        description="attribute probe",
        damage=1,
        aggro=False,
        exp_award=1,
        maxhp=10,
        protection=1,
        speed=1,
        finesse=1,
        endurance=1,
        strength=1,
        charisma=1,
        intelligence=1,
    )
    return {
        "Player": Player(),
        "NPC": npc,
        "State": State(name="Probe", target=npc),
    }


def _subclass_class_attrs() -> Set[str]:
    """Class-level names on every combatant class the project defines.

    A base ``NPC`` instance does not carry mixin methods that only some NPC
    subclasses inherit (``ConversationalNPCMixin._init_chat_attrs`` is the live
    example — ``npc_serializer`` uses its presence as the "can chat" probe).
    Walking the concrete subclasses picks those up without hand-listing them.
    """
    import importlib
    import inspect

    from src.combatant import Combatant

    names: Set[str] = set()
    for module_name in ("src.player", "src.npc", "src.combatant"):
        module = importlib.import_module(module_name)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, Combatant):
                names.update(dir(obj))
                for base in obj.__mro__:
                    names.update(vars(base))
    return names


def _combatant_kind() -> FrozenSet[str]:
    """The set of concrete classes a "combatant" can be, per the engine itself.

    Derived from ``Combatant.__subclasses__()`` — not a literal ``{"Player",
    "NPC"}`` — so a new combat participant class is picked up automatically
    rather than silently exempted.
    """
    from src.combatant import Combatant

    # Import both subclass modules so __subclasses__() is fully populated.
    import src.npc  # noqa: F401
    import src.player  # noqa: F401

    return frozenset(c.__name__ for c in Combatant.__subclasses__())


def _kind_by_receiver_name() -> Dict[str, FrozenSet[str]]:
    """Map a parameter/loop identifier to the engine kind it denotes.

    Keyed on the engine class names themselves (lower-cased), so the mapping
    follows a class rename instead of going stale:
      ``combatant`` -> every ``Combatant`` subclass,
      ``player``    -> ``Player``,
      ``npc``       -> ``NPC``,
      ``state``     -> ``State``.
    """
    from src.combatant import Combatant
    from src.states import State

    combatant_kind = _combatant_kind()
    mapping = {
        Combatant.__name__.lower(): combatant_kind,
        State.__name__.lower(): frozenset({State.__name__}),
    }
    for name in combatant_kind:
        mapping[name.lower()] = frozenset({name})
    return mapping


# --------------------------------------------------------------------------
# AUTHORITY 2 — attributes the codebase assigns onto a combatant
# --------------------------------------------------------------------------
def _combatant_source_dirs() -> Set[pathlib.Path]:
    """Directories that define combatant classes, from the classes' own modules.

    Used to decide that a bare ``self.<attr> = ...`` is a combatant store.
    """
    import importlib

    from src.combatant import Combatant

    dirs = set()
    for cls in (Combatant, *Combatant.__subclasses__()):
        module = importlib.import_module(cls.__module__)
        path = pathlib.Path(module.__file__).resolve()
        dirs.add(path.parent)
    return dirs


def _assigned_combatant_attrs() -> Set[str]:
    """Attribute names the project STORES onto a combatant, anywhere under src/.

    Three receiver shapes count, all of them derived from the engine class
    names via :func:`_kind_by_receiver_name`:

      * ``player.foo = ...``      — a bare identifier naming a combatant kind
      * ``self.player.foo = ...`` — an attribute whose last segment does
      * ``self.foo = ...``        — inside a module that defines a combatant

    Deliberately narrow: a blanket "any ``x.foo = ...`` anywhere" set would be
    large enough to wave through a genuinely dead name, which is exactly the
    fail-open this guard exists to prevent.
    """
    receiver_names = set(_kind_by_receiver_name())
    combatant_dirs = _combatant_source_dirs()
    found: Set[str] = set()

    for path in sorted(SRC_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - defensive
            continue
        self_is_combatant = path.parent in combatant_dirs
        for node in ast.walk(tree):
            targets: List[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                targets = [node.target]
            for target in targets:
                for leaf in _flatten_targets(target):
                    if not isinstance(leaf, ast.Attribute):
                        continue
                    base = leaf.value
                    if isinstance(base, ast.Name):
                        if base.id.lower() in receiver_names:
                            found.add(leaf.attr)
                        elif base.id == "self" and self_is_combatant:
                            found.add(leaf.attr)
                    elif isinstance(base, ast.Attribute):
                        if base.attr.lower() in receiver_names:
                            found.add(leaf.attr)
    return found


def _flatten_targets(target: ast.expr) -> List[ast.expr]:
    if isinstance(target, (ast.Tuple, ast.List)):
        out: List[ast.expr] = []
        for elt in target.elts:
            out.extend(_flatten_targets(elt))
        return out
    return [target]


# --------------------------------------------------------------------------
# The scanner
# --------------------------------------------------------------------------
class Read(NamedTuple):
    module: str
    lineno: int
    function: str
    receiver: str
    attr: str
    kind: FrozenSet[str]


def _annotation_kind(node: Optional[ast.expr], kinds: Dict[str, FrozenSet[str]]):
    """Resolve an annotation to ``(kind, is_sequence)``.

    Understands ``"NPC"``, ``NPC``, ``List["NPC"]`` and ``list[NPC]``.
    """
    if node is None:
        return None, False
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return kinds.get(node.value.lower()), False
    if isinstance(node, ast.Name):
        return kinds.get(node.id.lower()), False
    if isinstance(node, ast.Attribute):
        return kinds.get(node.attr.lower()), False
    if isinstance(node, ast.Subscript):
        container = node.value
        container_name = getattr(container, "id", getattr(container, "attr", ""))
        container_name = str(container_name).lower()
        if container_name in ("list", "sequence", "iterable", "tuple", "optional"):
            inner, _ = _annotation_kind(node.slice, kinds)
            if container_name == "optional":
                return inner, False
            return inner, True
    return None, False


def _attribute_read_helpers(tree: ast.Module) -> Set[str]:
    """Module-level ``f(obj, attr, ...)`` helpers that are just ``getattr``.

    Discovered structurally — a helper whose body contains
    ``getattr(<param0>, <param1>, ...)`` reads an attribute exactly the way
    ``getattr`` does, so its call sites must be checked the same way.  This is
    how ``_num(combatant, "protection")`` in the combat serializer gets
    covered without naming ``_num`` here.
    """
    helpers = set()
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        params = [a.arg for a in node.args.args]
        if len(params) < 2:
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == "getattr"
                and len(inner.args) >= 2
                and isinstance(inner.args[0], ast.Name)
                and inner.args[0].id == params[0]
                and isinstance(inner.args[1], ast.Name)
                and inner.args[1].id == params[1]
            ):
                helpers.add(node.name)
                break
    return helpers


class _FunctionScanner(ast.NodeVisitor):
    """Collect attribute reads on engine-typed receivers within one function."""

    def __init__(
        self, module, function, bindings, seq_bindings, helpers, reads
    ):
        self.module = module
        self.function = function
        self.bindings: Dict[str, FrozenSet[str]] = dict(bindings)
        self.seq_bindings: Dict[str, FrozenSet[str]] = dict(seq_bindings)
        self.helpers = helpers
        self.reads: List[Read] = reads

    # -- element-type propagation through loops / comprehensions ------------
    def _bind_iteration(self, target: ast.expr, iter_node: ast.expr):
        kind = self._sequence_kind(iter_node)
        if kind is None:
            return
        if isinstance(target, ast.Name):
            self.bindings[target.id] = kind
        elif isinstance(target, ast.Tuple) and iter_node_is_enumerate(iter_node):
            # ``for i, e in enumerate(enemies)`` -> ``e`` is the element
            if len(target.elts) == 2 and isinstance(target.elts[1], ast.Name):
                self.bindings[target.elts[1].id] = kind

    def _sequence_kind(self, iter_node: ast.expr) -> Optional[FrozenSet[str]]:
        if iter_node_is_enumerate(iter_node):
            iter_node = iter_node.args[0]
        if isinstance(iter_node, ast.Name):
            return self.seq_bindings.get(iter_node.id)
        # ``for s in getattr(combatant, "states", [])`` — a combatant's state
        # list is a list of States.
        if (
            isinstance(iter_node, ast.Call)
            and isinstance(iter_node.func, ast.Name)
            and iter_node.func.id == "getattr"
            and len(iter_node.args) >= 2
            and isinstance(iter_node.args[0], ast.Name)
            and isinstance(iter_node.args[1], ast.Constant)
        ):
            named_states = iter_node.args[1].value == "states"
            if named_states and iter_node.args[0].id in self.bindings:
                return frozenset({"State"})
        if isinstance(iter_node, ast.Attribute) and iter_node.attr == "states":
            base = iter_node.value
            if isinstance(base, ast.Name) and base.id in self.bindings:
                return frozenset({"State"})
        return None

    def visit_For(self, node: ast.For):
        self._bind_iteration(node.target, node.iter)
        self.generic_visit(node)

    def _visit_comprehension(self, node):
        for gen in node.generators:
            self._bind_iteration(gen.target, gen.iter)
        self.generic_visit(node)

    visit_ListComp = _visit_comprehension
    visit_SetComp = _visit_comprehension
    visit_DictComp = _visit_comprehension
    visit_GeneratorExp = _visit_comprehension

    # -- the reads themselves ----------------------------------------------
    def _record(self, receiver: ast.expr, attr: str, lineno: int):
        if not isinstance(receiver, ast.Name):
            return
        kind = self.bindings.get(receiver.id)
        if kind is None:
            return
        self.reads.append(
            Read(self.module, lineno, self.function, receiver.id, attr, kind)
        )

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name in ("getattr", "hasattr") or name in self.helpers:
                if (
                    len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant)
                    and isinstance(node.args[1].value, str)
                ):
                    self._record(node.args[0], node.args[1].value, node.lineno)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if isinstance(node.ctx, ast.Load):
            self._record(node.value, node.attr, node.lineno)
        self.generic_visit(node)


def iter_node_is_enumerate(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "enumerate"
        and bool(node.args)
    )


def scan_source(source: str, module: str = "<memory>") -> List[Read]:
    """Every attribute read on an engine-typed receiver in one module's source."""
    kinds = _kind_by_receiver_name()
    tree = ast.parse(source)
    helpers = _attribute_read_helpers(tree)
    reads: List[Read] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        bindings: Dict[str, FrozenSet[str]] = {}
        seq_bindings: Dict[str, FrozenSet[str]] = {}
        args = node.args
        for arg in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs):
            kind, is_seq = _annotation_kind(arg.annotation, kinds)
            if kind is not None:
                (seq_bindings if is_seq else bindings)[arg.arg] = kind
                continue
            # No usable annotation (most of these are ``Any``): fall back to the
            # identifier, which the engine class names define.
            by_name = kinds.get(arg.arg.lower())
            if by_name is not None:
                bindings[arg.arg] = by_name
        if not bindings and not seq_bindings:
            continue
        _FunctionScanner(
            module, node.name, bindings, seq_bindings, helpers, reads
        ).visit(node)
    return reads


def scan_serializers() -> List[Read]:
    reads: List[Read] = []
    for path in sorted(SERIALIZER_DIR.glob("*.py")):
        reads.extend(scan_source(path.read_text(encoding="utf-8"), path.name))
    return reads


def dead_names(reads: List[Read]) -> List[Read]:
    """Reads whose attribute no engine object has and nothing ever assigns."""
    probes = _engine_probes()
    assigned = _assigned_combatant_attrs()
    subclass_attrs = _subclass_class_attrs()
    dead = []
    for read in reads:
        if read.attr.startswith("__"):
            continue
        if any(hasattr(probes[k], read.attr) for k in read.kind if k in probes):
            continue
        if read.attr in assigned:
            continue
        if "State" not in read.kind and read.attr in subclass_attrs:
            continue
        dead.append(read)
    return dead


def _format(reads: List[Read]) -> str:
    return "\n".join(
        f"  src/api/serializers/{r.module}:{r.lineno} "
        f"{r.function}() reads {r.receiver}.{r.attr!r} "
        f"— no {'/'.join(sorted(r.kind))} defines or assigns it"
        for r in reads
    )


# --------------------------------------------------------------------------
# The guard
# --------------------------------------------------------------------------
class TestSerializerAttributeNames:
    def test_no_serializer_reads_a_dead_engine_attribute(self):
        """THE GUARD.

        Every ``getattr``/``hasattr``/direct read the serializers perform on a
        Player, an NPC or a State must name something the engine defines or
        something the project assigns onto a combatant.  A miss here is a wire
        field permanently frozen at its default.
        """
        offenders = dead_names(scan_serializers())
        assert not offenders, (
            "Serializer reads an attribute no engine object has:\n"
            + _format(offenders)
            + "\n\nThe engine is the source of truth — fix the serializer to "
            "read the real name (see src/combatant.py, src/player, src/npc), "
            "or delete the read."
        )


class TestGuardIsNotVacuous:
    """The scan must be capable of failing, and must actually be scanning."""

    _DEAD = 'def f(combatant):\n    return getattr(combatant, "health", 0)\n'
    _LIVE = 'def f(combatant):\n    return getattr(combatant, "hp", 0)\n'
    _HASATTR = 'def f(combatant):\n    return hasattr(combatant, "moves")\n'
    _LOOP = (
        'from typing import List\n'
        'def f(enemies: List["NPC"]):\n'
        '    return [getattr(e, "exp_reward", 0) for e in enemies]\n'
    )
    _HELPER = (
        'def _num(obj, attr, default=0.0):\n'
        '    return float(getattr(obj, attr, default))\n'
        'def f(combatant):\n'
        '    return _num(combatant, "max_health")\n'
    )
    _DIRECT = 'def f(combatant):\n    return combatant.max_health\n'

    @pytest.mark.parametrize(
        "source, attr",
        [
            (_DEAD, "health"),
            (_HASATTR, "moves"),
            (_LOOP, "exp_reward"),
            (_HELPER, "max_health"),
            (_DIRECT, "max_health"),
        ],
        ids=["getattr", "hasattr", "annotated-list-loop", "getattr-helper", "direct"],
    )
    def test_scanner_catches_each_read_shape(self, source, attr):
        offenders = dead_names(scan_source(source))
        assert [r.attr for r in offenders] == [attr]

    def test_scanner_does_not_flag_a_real_engine_name(self):
        assert dead_names(scan_source(self._LIVE)) == []

    def test_scanner_does_not_flag_a_runtime_assigned_name(self):
        """``suggested_moves`` is attached by the API layer, not by ``Player``."""
        from src.player import Player

        assert not hasattr(Player(), "suggested_moves")
        source = 'def f(player):\n    return getattr(player, "suggested_moves", [])\n'
        assert dead_names(scan_source(source)) == []

    def test_scan_actually_resolves_the_combat_serializer(self):
        """Guard against the scan silently resolving nothing.

        If receiver resolution regresses (a refactor renames ``combatant``, an
        annotation form stops parsing), the guard above would pass by finding
        zero reads.  Pin a floor on both the number of reads and the number of
        distinct functions they came from.
        """
        reads = [r for r in scan_serializers() if r.module == "combat.py"]
        assert len(reads) >= 40, f"only resolved {len(reads)} reads in combat.py"
        assert len({r.function for r in reads}) >= 8
        # Both engine kinds must be represented, or half the guard is asleep.
        kinds = {k for r in reads for k in r.kind}
        assert {"Player", "NPC", "State"} <= kinds

    def test_authorities_are_populated_and_disagree_with_each_other(self):
        """Neither authority may be empty, and #2 must not be a superset of #1.

        A collapsed authority (empty probe set, or an assignment scan wide
        enough to admit anything) turns the guard into a fail-open table.
        """
        probes = _engine_probes()
        assert set(probes) == {"Player", "NPC", "State"}
        assigned = _assigned_combatant_attrs()
        assert 20 <= len(assigned) < 400, len(assigned)
        subclass_attrs = _subclass_class_attrs()
        assert "_init_chat_attrs" in subclass_attrs, (
            "the subclass widening must admit mixin-only names, or "
            "npc_serializer's chat probe reads as dead"
        )
        # The names the defects used must be absent from ALL THREE authorities,
        # otherwise the guard could never have caught them.
        for dead in (
            "health",
            "max_health",
            "max_hp",
            "moves",
            "exp_reward",
            "max_fatigue",
            "carrying_capacity",
            "inventory_slots",
        ):
            assert dead not in assigned, dead
            assert dead not in subclass_attrs, dead
            assert not any(hasattr(o, dead) for o in probes.values()), dead
