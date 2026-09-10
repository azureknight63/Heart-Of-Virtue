"""The ch03 ferry-landing objective must be completable in real play.

``MaraObservationEvent._set_gate`` sets ``OBJ_CH03_FERRY_LANDING`` ("Meet Mara
at the ferry landing to cross the river") the moment ``nomad_ferry_ready`` is
set. Until this module, the **only** call in the tree that completed it lived
in ``ch03.DemoEndEvent.process`` -- and ``DemoEndEvent`` is placed on no tile
in any shipped map, across the project's whole history. So the objective was
set for every player who finished Mara's chain and could never be cleared: it
sat in the journal forever.

It stayed invisible because the guard that should have caught it,
``TestObjectiveKeyRegistry`` in ``test_journal_story_integration.py``, matches
on the *syntactic presence* of a ``complete_objective(...)`` call inside
``ch01``/``ch02``/``ch03``. A call in dead code satisfies that scan exactly as
well as a call that runs, so the registry was green throughout. The
reachability guard at the bottom of this module closes that hole: presence is
no longer enough, the class holding the call has to be wired to something.

Found while fixing #579 (gating ``Passageway.end_demo`` on
``nomad_ferry_ready``): deleting ``DemoEndEvent`` as dead code turned the
registry's "set but never completed" assertion red, which is what surfaced the
gap.
"""

import ast
import io
import json
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src import journal  # noqa: E402
from src.api.services.game_service import GameService  # noqa: E402
from src.journal import OBJ_CH03_FERRY_LANDING  # noqa: E402
from src.narration import capture_narration  # noqa: E402
from src.objects import Passageway  # noqa: E402
from tests._gs_fixtures import live_world  # noqa: E402

_MAPS = _ROOT / "src" / "resources" / "maps"
_FERRY_MAP = _MAPS / "eastern-descent-nomad-camp.json"
_FERRY_TILE_KEY = "(0, 2)"
_STORY_MODULES = ("ch01", "ch02", "ch03")

_STATUS_ACTIVE = "active"
_STATUS_DONE = "done"


def _ferry_tile_payload():
    raw = json.loads(_FERRY_MAP.read_text(encoding="utf-8"))
    assert _FERRY_TILE_KEY in raw, (
        f"the Ferry Landing tile {_FERRY_TILE_KEY} is gone from {_FERRY_MAP.name}"
    )
    return raw[_FERRY_TILE_KEY]


def _ferry_placement():
    """The authored Ferry Landing props, straight out of the shipped map."""
    for payload in _ferry_tile_payload()["objects"]:
        if (payload.get("props") or {}).get("name") == "Ferry Landing":
            return payload
    raise AssertionError("Ferry Landing is no longer at nomad-camp (0, 2)")


def _placed_event_classes():
    """Every event ``__class__`` authored onto a tile in any shipped map."""
    placed = set()
    files = sorted(_MAPS.glob("*.json"))
    assert files, "no map JSON found -- the scan below would approve of anything"
    for path in files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        for value in raw.values():
            if not isinstance(value, dict):
                continue
            for entry in value.get("events") or []:
                if isinstance(entry, dict) and entry.get("__class__"):
                    placed.add(entry["__class__"])
    return placed


def _story_trees():
    trees = []
    for name in _STORY_MODULES:
        path = _ROOT / "src" / "story" / f"{name}.py"
        trees.append((name, ast.parse(io.open(path, encoding="utf-8").read())))
    return trees


def _objective_completing_classes():
    """``{class_name: module}`` for every story class that completes an objective."""
    found = {}
    for module_name, tree in _story_trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                name = getattr(inner.func, "id", None) or getattr(
                    inner.func, "attr", None
                )
                if name == "complete_objective":
                    found[node.name] = module_name
    return found


def _engine_source():
    """Every ``src/**/*.py`` file's text, keyed by path."""
    files = sorted((_ROOT / "src").rglob("*.py"))
    assert files, "no engine source found -- the scan below would approve of anything"
    return {path: io.open(path, encoding="utf-8").read() for path in files}


@pytest.fixture
def game_service():
    return GameService()


def _instantiate_authored(payload, player, tile):
    """Build one authored map payload the way ``Universe`` builds it.

    Props are filtered to the real constructor signature and the remainder
    applied by ``setattr`` -- the same two steps
    ``_deserialize_saved_instance`` performs, so anything the shipped JSON
    gets wrong shows up here rather than being papered over.
    """
    import importlib
    import inspect

    from src import functions

    module = importlib.import_module(
        functions.canonical_module_name(payload["__module__"])
    )
    cls = getattr(module, payload["__class__"])
    props = dict(payload.get("props") or {})
    props.pop("player", None)
    props.pop("tile", None)
    accepted = set(inspect.signature(cls.__init__).parameters)
    kwargs = {key: value for key, value in props.items() if key in accepted}
    instance = cls(player=player, tile=tile, **kwargs)
    for key, value in props.items():
        if key not in kwargs:
            setattr(instance, key, value)
    return instance


@pytest.fixture
def ferry_world():
    """A one-tile world carrying the real Ferry Landing tile's contents.

    Both the passageway **and** the tile's authored events come from the
    shipped map, so this fixture fails if the placement that makes the fix
    work is ever dropped -- the wiring is the thing under test, not just the
    event class.
    """
    player, game_map = live_world(coords=((0, 0),))
    tile = game_map[(0, 0)]
    payload = _ferry_tile_payload()

    ferry = _instantiate_authored(_ferry_placement(), player, tile)
    tile.objects_here = [ferry]
    tile.events_here = [
        _instantiate_authored(entry, player, tile)
        for entry in (payload.get("events") or [])
    ]
    assert isinstance(ferry, Passageway)
    return player, game_map, ferry


def _arm_ferry_objective(player):
    """Put the journal in the state Mara's chain leaves it in."""
    journal.set_objective(
        player,
        OBJ_CH03_FERRY_LANDING,
        "Meet Mara at the ferry landing to cross the river.",
        chapter=3,
    )


def _objective_status(player, key):
    entry = player.universe.journal.objectives.get(key)
    return None if entry is None else entry.get("status")


class TestTheShippedTileIsWired:
    """The completing event has to be ON the Ferry Landing tile.

    This is the assertion the original bug would have failed: the code that
    completed the objective existed, and was attached to nothing.
    """

    def test_the_ferry_tile_carries_an_objective_completing_event(self):
        placed_here = {
            entry.get("__class__")
            for entry in (_ferry_tile_payload().get("events") or [])
            if isinstance(entry, dict)
        }
        completers = set(_objective_completing_classes())
        assert completers, "no story class completes an objective -- scan is broken"
        assert placed_here & completers, (
            "the Ferry Landing tile carries no event that completes an "
            f"objective; it has {sorted(placed_here)} and the objective-"
            f"completing classes are {sorted(completers)}"
        )


class TestTheObjectiveClearsInPlay:
    """Driven through the real engine path, not a hand-called helper."""

    def test_using_the_ready_ferry_landing_completes_the_objective(
        self, game_service, ferry_world
    ):
        player, game_map, ferry = ferry_world
        tile = game_map[(0, 0)]
        player.universe.story[Passageway.DEMO_END_READY_FLAG] = "1"
        _arm_ferry_objective(player)
        assert _objective_status(player, OBJ_CH03_FERRY_LANDING) == _STATUS_ACTIVE

        with capture_narration():
            ferry.enter(player)
            game_service.trigger_tile_events(player, tile, {})

        assert player.universe.story.get("demo_ended") == "1"
        assert _objective_status(player, OBJ_CH03_FERRY_LANDING) == _STATUS_DONE, (
            "the ferry objective is still open after the demo ended at the "
            "landing -- the player can never clear it"
        )

    def test_declining_at_the_landing_leaves_the_objective_open(
        self, game_service, ferry_world
    ):
        """Negative control: no ready flag, so nothing should close."""
        player, game_map, ferry = ferry_world
        tile = game_map[(0, 0)]
        _arm_ferry_objective(player)

        with capture_narration():
            ferry.enter(player)
            game_service.trigger_tile_events(player, tile, {})

        assert player.universe.story.get("demo_ended") != "1"
        assert _objective_status(player, OBJ_CH03_FERRY_LANDING) == _STATUS_ACTIVE


class TestEveryObjectiveCompleterIsReachable:
    """A ``complete_objective`` call in unwired code is the bug this module fixes.

    Reachability is deliberately generous -- a class counts as wired if it is
    authored onto a tile in a shipped map, constructed anywhere in ``src/``, or
    named as a string literal (``functions.seek_class("AfterGorranIntro", ...)``
    in ``src/npc/_friends.py`` instantiates by name, and a narrower scan
    false-positives on it). What it will not accept is a class nothing mentions
    at all.
    """

    def test_the_scan_finds_the_classes_it_is_meant_to_guard(self):
        completers = _objective_completing_classes()
        assert len(completers) >= 5, (
            f"only {len(completers)} objective-completing classes found; the "
            "AST scan has probably stopped matching"
        )
        assert _placed_event_classes(), "no events are placed in any map"

    def test_every_objective_completing_class_is_wired_to_something(self):
        completers = _objective_completing_classes()
        placed = _placed_event_classes()
        sources = _engine_source()

        unwired = {}
        for cls, module_name in sorted(completers.items()):
            if cls in placed:
                continue
            defining = _ROOT / "src" / "story" / f"{module_name}.py"
            construct = re.compile(r"(?<![A-Za-z_])" + re.escape(cls) + r"\s*\(")
            literal = re.compile("[\"']" + re.escape(cls) + "[\"']")
            wired = False
            for path, text in sources.items():
                if literal.search(text):
                    wired = True
                    break
                # The class statement itself matches `Cls(` -- discount it.
                hits = len(construct.findall(text))
                if path == defining:
                    hits -= len(
                        re.findall(r"class\s+" + re.escape(cls) + r"\s*\(", text)
                    )
                if hits > 0:
                    wired = True
                    break
            if not wired:
                unwired[cls] = module_name

        assert not unwired, (
            "these story classes complete a journal objective but are wired to "
            "nothing -- no map places them, nothing constructs them, nothing "
            f"names them: {unwired}. The objective they complete can never be "
            "cleared in real play."
        )
