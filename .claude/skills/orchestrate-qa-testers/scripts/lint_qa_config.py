"""Lint a QA game config before a stack is started.

    python lint_qa_config.py config_qa_x.ini [config_qa_y.ini ...]

(`python` is the repo venv's interpreter.) Prints one PASS/WARN/FAIL line per
check (INFO for the one check that can only inform) and exits non-zero on any
FAIL. Every check is here because a past run lost testers to it:

1. Seeded story flags without what their event grants. On 2026-09-24 a leg
   config seeded `king_slime_defeated` without the `MineralFragment` that
   `AfterDefeatingKingSlime` grants with it; `AfterKingSlimeReturn` silently
   waited for the fragment and the tester spent its whole leg blocked. For each
   seeded flag, every event that sets it is found and the items it constructs
   and the other flags it sets must be seeded too. A missing item is FAIL when a
   still-pending beat waits on it (compares its class name) and that beat's
   gate is a route gate (a map JSON `locked_until_flag`, or read elsewhere in
   src/); WARN otherwise. A seeded flag nothing in src/ mentions is a WARN:
   seeding it does nothing (`lurker_defeated`, as of 2026-09-25).
2. `starting_exp` across a level boundary opens the session on a blocking
   LEVEL UP modal. The engine itself is run (a real `Player`, the same
   starting_exp -> starting_level order as SessionManager), so the curve is the
   engine's, not a copy.
3. `skipdialog = True` silences every scene (issue #547): FAIL.
4. A start tile that hosts an event gated on `previous_tile`: only directional
   moves set it (teleports never do), so such an event never fires for a
   session that starts on its tile. Events are found by AST (they read
   `previous_tile`) and located in src/resources/maps/*.json.
5. Party members (INFO only). Gorran's permanent join is a story event, but
   which maps lie "past" it is route order, which the source does not encode.
   So this check only reports the Gorran scenes placed on the start map when
   `starting_party_members` leaves him out; it never passes or fails a config.

The flag -> co-grant map is derived from source (an AST pass over
src/story/*.py) on every run, never kept by hand: a hand-kept table makes a
missing entry indistinguishable from a correct one. Flag keys are resolved
through string constants, `GATE_KEY`-style class attributes (with base
classes and imports) and module-level helpers the event calls. Writes whose key
cannot be resolved statically are counted and listed, not guessed.

Config parsing is the engine's: `ConfigManager` for [game] flags, and the same
plain `ConfigParser` SessionManager uses for startmap, startposition,
starting_items and starting_equipment.
"""
import ast
import configparser
import json
import os
import random
import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(os.environ.get("HOV_QA_ROOT") or Path(__file__).resolve().parents[4])
STORY_DIR = ROOT / "src" / "story"
MAPS_DIR = ROOT / "src" / "resources" / "maps"
ITEMS_MODULE = "src.items"
TILE_KEY = re.compile(r"^\((-?\d+),\s*(-?\d+)\)$")


def line(status, msg):
    print(f"{status:4} {msg}")
    return status == "FAIL"


# --------------------------------------------------------------------------
# Source model: modules, constants, classes, imports
# --------------------------------------------------------------------------

class _Module:
    """One parsed source file: its top-level constants, classes, functions,
    and every import (function-level ones included)."""

    def __init__(self, dotted, path):
        self.dotted = dotted
        self.path = path
        self.rel = path.relative_to(ROOT).as_posix()
        self.tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        self.consts, self.classes, self.functions, self.imports = {}, {}, {}, {}
        for node in self.tree.body:
            if isinstance(node, ast.ClassDef):
                self.classes[node.name] = node
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions[node.name] = node
            elif isinstance(node, ast.Assign) and _is_str(node.value):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.consts[target.id] = node.value.value
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        self.imports[alias.asname] = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                for alias in node.names:
                    self.imports[alias.asname or alias.name] = f"{node.module}.{alias.name}"


def _is_str(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


@lru_cache(maxsize=None)
def _load(dotted):
    base = ROOT.joinpath(*dotted.split("."))
    for path in (base.with_suffix(".py"), base / "__init__.py"):
        if path.is_file():
            return _Module(dotted, path)
    return None


def _follow_import(mod, name):
    """(module, name) that ``name`` imported into ``mod`` refers to, or None."""
    target = mod.imports.get(name)
    if not target:
        return None
    owner, _, attr = target.rpartition(".")
    other = _load(owner)
    return (other, attr) if other else None


def _module_const(mod, name, depth=0):
    if name in mod.consts:
        return mod.consts[name]
    hop = _follow_import(mod, name)
    return _module_const(*hop, depth + 1) if hop and depth < 5 else None


def _find_class(mod, name, depth=0):
    if name in mod.classes:
        return mod, mod.classes[name]
    hop = _follow_import(mod, name)
    return _find_class(*hop, depth + 1) if hop and depth < 5 else None


def _class_attr(mod, cls, attr, depth=0):
    """String value of class attribute ``attr`` on ``cls``, searching bases."""
    if depth > 10:
        return None
    for node in cls.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == attr for t in node.targets
        ):
            return _resolve(node.value, mod, (mod, cls), depth + 1)
    for base in cls.bases:
        found = _find_class(mod, base.id) if isinstance(base, ast.Name) else None
        if found:
            value = _class_attr(*found, attr, depth + 1)
            if value is not None:
                return value
    return None


def _is_self(node):
    if isinstance(node, ast.Name):
        return node.id in ("self", "cls")
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "type" and len(node.args) == 1 and _is_self(node.args[0]))


def _resolve(node, mod, self_ctx, depth=0):
    """The string an expression statically evaluates to, or None.

    ``self_ctx`` is the (module, ClassDef) that ``self`` means: the concrete
    event, even when the code being read lives in a base class.
    """
    if node is None or depth > 10:
        return None
    if _is_str(node):
        return node.value
    if isinstance(node, ast.Name):
        return _module_const(mod, node.id)
    if isinstance(node, ast.Attribute):
        if _is_self(node.value):
            return _class_attr(*self_ctx, node.attr, depth) if self_ctx else None
        if isinstance(node.value, ast.Name):
            found = _find_class(mod, node.value.id)
            if found:
                return _class_attr(*found, node.attr, depth)
    return None


# --------------------------------------------------------------------------
# Story scopes: what each event (class) or module-level helper does
# --------------------------------------------------------------------------

@dataclass
class Scope:
    name: str
    rel: str
    lineno: int
    writes: list = field(default_factory=list)      # (key, value|None, "file:line")
    unresolved: list = field(default_factory=list)  # "file:line" of unresolvable keys
    items: dict = field(default_factory=dict)       # item class -> "file:line"
    compared: set = field(default_factory=set)      # strings compared against
    referenced: set = field(default_factory=set)    # every string the scope resolves
    reads_previous_tile: bool = False

    def static_flags(self):
        return {key for key, value, _ in self.writes if value is not None}


def _story_modules():
    mods = []
    for path in sorted(STORY_DIR.glob("*.py")):
        mod = _load("src.story." + path.stem if path.stem != "__init__" else "src.story")
        if mod:
            mods.append(mod)
    return mods


@lru_cache(maxsize=None)
def _gate_default():
    """``set_story_gate``'s default value (``GATE_SET``), read from src/events.py."""
    return _module_const(_load("src.events"), "GATE_SET")


def _gate_write_args(call, mod):
    """(key_node, value_node) when ``call`` writes a story gate, else None."""
    func = call.func
    module_level = isinstance(func, ast.Name) and func.id == "set_story_gate"
    if (isinstance(func, ast.Attribute) and func.attr == "set_story_gate"
            and isinstance(func.value, ast.Name)
            and mod.imports.get(func.value.id) == "src.events"):
        module_level = True
    if not module_level and not (isinstance(func, ast.Attribute) and func.attr == "set_story_gate"):
        return None
    args = call.args[1:] if module_level else call.args
    kwargs = {kw.arg: kw.value for kw in call.keywords}
    key = args[0] if args else kwargs.get("key")
    value = args[1] if len(args) > 1 else kwargs.get("value")
    return key, value


def _item_constructed(call, mod):
    func = call.func
    if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
            and mod.imports.get(func.value.id) == ITEMS_MODULE and func.attr[:1].isupper()):
        return func.attr
    if isinstance(func, ast.Name) and mod.imports.get(func.id, "").startswith(ITEMS_MODULE + "."):
        return func.id
    return None


def _scan(scope, mod, node, self_ctx, seen_funcs):
    """Fold everything under ``node`` (code living in ``mod``) into ``scope``,
    following calls to ``mod``'s own module-level functions."""
    for sub in ast.walk(node):
        # player.previous_tile, or getattr(player, "previous_tile", None)
        if (isinstance(sub, ast.Attribute) and sub.attr == "previous_tile") or (
                _is_str(sub) and sub.value == "previous_tile"):
            scope.reads_previous_tile = True
        if isinstance(sub, (ast.Name, ast.Attribute, ast.Constant)):
            value = _resolve(sub, mod, self_ctx)
            if value:
                scope.referenced.add(value)
        if isinstance(sub, ast.Compare):
            for operand in [sub.left, *sub.comparators]:
                parts = operand.elts if isinstance(operand, (ast.Tuple, ast.List, ast.Set)) else [operand]
                for part in parts:
                    value = _resolve(part, mod, self_ctx)
                    if value:
                        scope.compared.add(value)
        if not isinstance(sub, ast.Call):
            continue
        where = f"{mod.rel}:{sub.lineno}"
        item = _item_constructed(sub, mod)
        if item:
            scope.items.setdefault(item, where)
        gate = _gate_write_args(sub, mod)
        if gate:
            key_node, value_node = gate
            key = _resolve(key_node, mod, self_ctx)
            value = _gate_default() if value_node is None else _resolve(value_node, mod, self_ctx)
            if key:
                scope.writes.append((key, value, where))
            else:
                scope.unresolved.append(where)
        if isinstance(sub.func, ast.Name) and sub.func.id in mod.functions and sub.func.id not in seen_funcs:
            seen_funcs.add(sub.func.id)
            _scan(scope, mod, mod.functions[sub.func.id], None, seen_funcs)


def _story_bases(mod, cls):
    """``cls`` and its base classes that live in src/story, nearest first."""
    chain, todo = [], [(mod, cls)]
    while todo:
        m, c = todo.pop(0)
        if any(c is seen for _, seen in chain):
            continue
        chain.append((m, c))
        for base in c.bases:
            found = _find_class(m, base.id) if isinstance(base, ast.Name) else None
            if found and found[0].dotted.startswith("src.story"):
                todo.append(found)
    return chain


@lru_cache(maxsize=None)
def derive_story_scopes():
    """Every top-level class and function in src/story/*.py, as a Scope."""
    scopes = {}
    for mod in _story_modules():
        for name, cls in mod.classes.items():
            scope = Scope(name, mod.rel, cls.lineno)
            seen = set()
            for base_mod, base_cls in _story_bases(mod, cls):
                _scan(scope, base_mod, base_cls, (mod, cls), seen)
            scopes[name] = scope
        for name, func in mod.functions.items():
            scope = Scope(name + "()", mod.rel, func.lineno)
            _scan(scope, mod, func, None, {name})
            scopes.setdefault(scope.name, scope)
    return scopes


def derive_flag_cogrants():
    """flag key -> [{event, where, value, items, flags}], one entry per writer.

    ``items`` are the item classes the writer constructs, ``flags`` the other
    flags it sets to a static value. Derived from src/story on every call.
    """
    out = {}
    for scope in derive_story_scopes().values():
        static = scope.static_flags()
        seen = set()
        for key, value, where in scope.writes:
            if (key, value) in seen:
                continue
            seen.add((key, value))
            out.setdefault(key, []).append({
                "event": scope.name, "where": where, "value": value,
                "items": sorted(scope.items), "flags": sorted(static - {key}),
            })
    return out


@lru_cache(maxsize=None)
def _src_text():
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in (ROOT / "src").rglob("*.py"))


@lru_cache(maxsize=None)
def _map_strings():
    """Every string value appearing in any map JSON."""
    found = set()

    def walk(obj):
        if isinstance(obj, dict):
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)
        elif isinstance(obj, str):
            found.add(obj)

    for path in MAPS_DIR.glob("*.json"):
        walk(json.loads(path.read_text(encoding="utf-8")))
    return found


def _mentioned_in_src(key):
    return f'"{key}"' in _src_text() or f"'{key}'" in _src_text()


def _is_route_gate(key, writers):
    """True when something other than ``key``'s own writers depends on it:
    a map JSON value (e.g. a Passageway's ``locked_until_flag``) or another
    story scope that resolves it."""
    if key in _map_strings():
        return True
    return any(key in s.referenced for s in derive_story_scopes().values() if s.name not in writers)


# --------------------------------------------------------------------------
# Config parsing (the engine's)
# --------------------------------------------------------------------------

@dataclass
class QAConfig:
    path: Path
    game: object              # src.config_manager.GameConfig
    startmap: str
    startposition: tuple
    items: list               # starting_items + starting_equipment class names
    parse_error: str = ""

    def seeded_flags(self):
        """{key: value} with SessionManager._apply_starting_story_flags semantics."""
        flags = {}
        for token in self.game.starting_story_flags:
            key, has_value, value = token.partition("=")
            if key.strip():
                flags[key.strip()] = value.strip() if has_value else _gate_default()
        return flags


def load_config(path):
    sys.path.insert(0, str(ROOT))
    from src.config_manager import ConfigManager

    path = Path(path).resolve()
    game = ConfigManager(str(path)).load()
    # SessionManager reads these with a plain ConfigParser (no inline comments).
    startmap, startpos, names, error = "dark-grotto", (1, 1), [], ""
    parser = configparser.ConfigParser()
    try:
        parser.read(path)
        if parser.has_option("game", "startmap"):
            startmap = parser.get("game", "startmap")
        if parser.has_option("game", "startposition"):
            coords = [int(x.strip()) for x in parser.get("game", "startposition").strip("() ").split(",")]
            if len(coords) == 2:
                startpos = tuple(coords)
        for option in ("starting_items", "starting_equipment"):
            if parser.has_option("game", option):
                names += [t.split(":")[0].strip() for t in parser.get("game", option).split(",") if t.strip()]
    except (configparser.Error, ValueError) as exc:
        error = str(exc)
    return QAConfig(path, game, startmap, startpos, names, error)


# --------------------------------------------------------------------------
# Checks: each returns [(status, message)]
# --------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _map_tiles(map_name):
    """{(x, y): tile} for a map JSON; keys are written both "(1,2)" and "(1, 2)"."""
    path = MAPS_DIR / f"{map_name}.json"
    if not path.is_file():
        return None
    tiles = {}
    for key, tile in json.loads(path.read_text(encoding="utf-8")).items():
        match = TILE_KEY.match(key)
        if match and isinstance(tile, dict):
            tiles[(int(match.group(1)), int(match.group(2)))] = tile
    return tiles


def _events_on(tiles):
    return [e.get("__class__") for tile in tiles for e in tile.get("events", []) if isinstance(e, dict)]


def check_start_tile(cfg):
    if cfg.parse_error:
        return [("FAIL", f"SessionManager's parser cannot read this config: {cfg.parse_error}")]
    tiles = _map_tiles(cfg.startmap)
    if tiles is None:
        return [("FAIL", f"startmap '{cfg.startmap}' has no src/resources/maps/{cfg.startmap}.json; "
                         "the session falls back to another map")]
    if cfg.startposition not in tiles:
        return [("FAIL", f"startposition {cfg.startposition} is not a tile of {cfg.startmap}")]
    return [("PASS", f"start tile {cfg.startmap} {cfg.startposition} exists")]


@lru_cache(maxsize=None)
def _item_classes():
    return set(_load(ITEMS_MODULE).classes)


def check_item_names(cfg):
    unknown = [n for n in cfg.items if n not in _item_classes()]
    if unknown:
        return [("WARN", f"not item classes in src/items.py (the engine skips them silently): {unknown}")]
    return [("PASS", f"{len(cfg.items)} starting item/equipment names are src/items.py classes")]


def _waiter_verdict(item, writer_event, seeded):
    """How badly a missing ``item`` matters: (status, reason)."""
    scopes = derive_story_scopes()
    cogrants = derive_flag_cogrants()
    pending, blocking = [], []
    for scope in scopes.values():
        gates = scope.static_flags()
        if scope.name == writer_event or item not in scope.compared or not gates:
            continue
        if gates <= set(seeded):
            continue  # that beat is seeded as already done; it had the item
        pending.append(scope)
        for gate in gates - set(seeded):
            if _is_route_gate(gate, {w["event"] for w in cogrants.get(gate, [])}):
                blocking.append((scope, gate))
    if blocking:
        scope, gate = blocking[0]
        return "FAIL", (f"{scope.name} ({scope.rel}:{scope.lineno}) waits for it, and its "
                        f"'{gate}' gates the route")
    if pending:
        names = ", ".join(f"{s.name} ({s.rel}:{s.lineno})" for s in pending)
        return "WARN", f"{names} wait(s) for it; that scene will not fire"
    return "WARN", "no pending story beat checks for it (fidelity only)"


def check_seeded_flags(cfg):
    seeded = cfg.seeded_flags()
    if not seeded:
        return [("PASS", "no starting_story_flags seeded")]
    cogrants = derive_flag_cogrants()
    out = []
    for key, value in seeded.items():
        writers = cogrants.get(key, [])
        if not writers:
            if _mentioned_in_src(key):
                out.append(("WARN", f"flag '{key}': no src/story event sets it, so its co-grants cannot be checked"))
            else:
                out.append(("WARN", f"flag '{key}': nothing in src/ mentions it; seeding it does nothing"))
            continue
        writers = [w for w in writers if w["value"] in (None, value)] or writers
        problems, status = [], "PASS"
        for writer in writers:
            for item in writer["items"]:
                if item in cfg.items:
                    continue
                verdict, reason = _waiter_verdict(item, writer["event"], seeded)
                if verdict == "FAIL":
                    status = "FAIL"
                elif status == "PASS":
                    status = "WARN"
                problems.append(f"{writer['event']} ({writer['where']}) grants {item}, not in "
                                f"starting_items/equipment: {reason}")
            missing = [f for f in writer["flags"] if f not in seeded]
            if missing:
                status = "WARN" if status == "PASS" else status
                problems.append(f"{writer['event']} ({writer['where']}) also sets {missing}, not seeded")
        if problems:
            out += [(status, f"flag '{key}': {p}") for p in problems]
        else:
            events = ", ".join(sorted({w['event'] for w in writers}))
            out.append(("PASS", f"flag '{key}': everything {events} grants is seeded"))
    return out


def simulate_start(exp, level, allocation):
    """Run the engine's start-up leveling on a fresh Player, in SessionManager's
    order (starting_exp, then starting_level). Returns (first_boundary, level,
    pending_attribute_points, crossed_by_exp)."""
    sys.path.insert(0, str(ROOT))
    from src.player import Player

    state = random.getstate()
    random.seed(0)
    try:
        player = Player()
        first_boundary = player.exp_to_level
        if exp > 0:
            player.apply_starting_experience(exp)
        crossed = player.level > 1
        if level > player.level:
            player.apply_starting_level(level, allocation=allocation)
        return first_boundary, player.level, int(player.pending_attribute_points or 0), crossed
    finally:
        random.setstate(state)


def check_starting_exp(cfg):
    game = cfg.game
    first, level, pending, crossed = simulate_start(
        game.starting_exp, game.starting_level, game.starting_level_allocation)
    if pending and crossed:
        return [("FAIL", f"starting_exp {game.starting_exp} crosses the first level boundary ({first} exp): "
                         f"Jean opens on level {level} with {pending} unspent points behind a blocking "
                         f"LEVEL UP modal (points are rolled per level; seed-0 run). Use starting_level instead")]
    if pending:
        return [("WARN", f"starting_level {game.starting_level} with allocation "
                         f"'{game.starting_level_allocation}' leaves {pending} points: the LEVEL UP modal "
                         f"opens on the first screen by design; say so in the primer")]
    if crossed:
        return [("PASS", f"starting_exp crosses a boundary but starting_level spends every point (level {level})")]
    return [("PASS", f"no level-up modal at start (level {level}; first boundary {first} exp)")]


def check_skipdialog(cfg):
    if cfg.game.skipdialog:
        return [("FAIL", "skipdialog = True silences every scene; set it False for a live run")]
    return [("PASS", "skipdialog is off")]


def _start_tile_events(cfg):
    tile = (_map_tiles(cfg.startmap) or {}).get(cfg.startposition)
    return _events_on([tile]) if tile else []


def check_previous_tile_start(cfg):
    scopes = derive_story_scopes()
    seeded = set(cfg.seeded_flags())
    out = []
    for name in _start_tile_events(cfg):
        scope = scopes.get(name)
        if not scope or not scope.reads_previous_tile:
            continue
        if scope.static_flags() and scope.static_flags() <= seeded:
            continue  # already seeded as done
        out.append(("WARN", f"start tile hosts {name} ({scope.rel}:{scope.lineno}), gated on previous_tile: "
                            "it never fires for a session that starts here. Start one tile before the transition"))
    return out or [("PASS", "start tile hosts no previous_tile-gated event")]


def check_party(cfg):
    gorran = _module_const(_load("src.story.ch02"), "GORRAN")
    if not gorran:
        return [("INFO", "could not resolve Gorran's class name from src/story/ch02.py GORRAN")]
    if gorran in cfg.game.starting_party_members:
        return [("PASS", f"starting_party_members includes {gorran}")]
    scopes = derive_story_scopes()
    scenes = sorted({
        name for name in _events_on((_map_tiles(cfg.startmap) or {}).values())
        if name in scopes and any(gorran in s for s in scopes[name].referenced)
    })
    if scenes:
        return [("INFO", f"starting_party_members lacks {gorran}; {cfg.startmap} hosts scenes that name him "
                         f"({', '.join(scenes)}). If the route assumes him, add starting_party_members = {gorran}")]
    return [("INFO", f"starting_party_members lacks {gorran}; no event on {cfg.startmap} names him")]


CHECKS = (check_start_tile, check_item_names, check_seeded_flags, check_starting_exp,
          check_skipdialog, check_previous_tile_start, check_party)


def lint(path):
    """[(status, message)] for one config file."""
    cfg = load_config(path)
    results = []
    for check in CHECKS:
        results += check(cfg)
    return results


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__.split("\n\n")[1])
        return 2
    scopes = derive_story_scopes()
    unresolved = [w for s in scopes.values() for w in s.unresolved]
    print(f"derived {len(derive_flag_cogrants())} story flags from {len(scopes)} src/story scopes"
          + (f"; unresolvable set_story_gate keys at {sorted(set(unresolved))}" if unresolved else ""))
    failed = False
    for path in argv:
        print(f"\n== {path}")
        if not Path(path).is_file():
            failed |= line("FAIL", "no such file")
            continue
        for status, msg in lint(path):
            failed |= line(status, msg)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
