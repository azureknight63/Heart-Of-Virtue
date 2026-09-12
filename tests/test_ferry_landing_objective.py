"""The ch03 ferry-landing objective must be completable in real play.

``MaraObservationEvent._set_gate`` sets ``OBJ_CH03_FERRY_LANDING`` ("Meet Mara
at the ferry landing to cross the river") the moment ``nomad_ferry_ready`` is
set. Until the fix this module guards, the only call in the tree that
completed it lived in an event class that was placed on no tile in any
shipped map, across the project's whole history. So the objective was set for
every player who finished Mara's chain and could never be cleared: it sat in
the journal forever.

It stayed invisible because the guard that should have caught it,
``TestObjectiveKeyRegistry`` in ``test_journal_story_integration.py``, matches
on the *syntactic presence* of a ``complete_objective(...)`` call inside the
chapter modules. A call in dead code satisfies that scan exactly as well as a
call that runs, so the registry was green throughout. The reachability guard
at the bottom of this module closes that hole: presence is no longer enough,
the class holding the call has to be wired to something.

Found while fixing #579 (gating ``Passageway.end_demo`` on
``nomad_ferry_ready``): deleting the unwired event as dead code turned the
registry's "set but never completed" assertion red, which is what surfaced
the gap.
"""

import ast
import functools
import itertools
import pathlib
import textwrap

import pytest

from src import journal
from src.journal import OBJ_CH03_FERRY_LANDING
from src.narration import capture_narration
from src.story import repair_loaded_save
from src.story.ch01 import AfterGorranIntro
from src.story.ch03 import FerryLandingObjectiveEvent, MaraObservationEvent
from tests._ast_helpers import call_target
from tests._ferry_fixtures import (
    FERRY_MAP,
    FERRY_TILE_KEY,
    FERRY_WORLD_COORD,
    OTHER_EDGE_FLAG,
    build_ferry_world,
    demo_edge,
    demo_has_ended,
    interact_with,
    mark_ferry_ready,
    plain_passageway,
    reported_beta_end,
)
from tests._map_scan import event_placements
from tests._source_scan import SourceFile, src_trees
from tests._story_scan import (
    COMPLETE_OBJECTIVE,
    declared_objectives,
    objective_key_name,
    story_modules,
)

#: The AST identifier the scans match -- the NAME of the journal constant,
#: not its value. A literal, so a rename of the constant can leave it stale
#: (an IDE rename updates the import above, not this string); the assert at
#: the top of the test that uses it is what ties the two together.
FERRY_OBJECTIVE_NAME = "OBJ_CH03_FERRY_LANDING"

#: How the wiring index opens each piece of evidence, one per kind.
CONSTRUCTED = "constructed in"
NAMED_BY_STRING = "named as a string literal in"


# ---------------------------------------------------------------------------
# Derived populations
# ---------------------------------------------------------------------------


def _walk_with_enclosing_class(tree):
    """``(node, name of the innermost class around it)`` for every node of
    ``tree``, depth-first pre-order, children in AST field order.

    Field order is not line order: ``ClassDef``/``FunctionDef`` list
    ``decorator_list`` after ``body``, so a decorator is visited after the
    body it sits above. Pass and fail do not depend on that order, but
    ``_index_wiring`` keeps the FIRST evidence it sees, so the order decides
    which site and which kind of wiring a failure reports.

    A class's own decorators, bases and class keywords are children of its
    ``ClassDef``, so they are credited to that class, not to the one around
    it: ``@register("Foo")`` on ``class Foo`` is Foo naming itself.

    An explicit stack rather than recursion: the walk covers all of
    ``src/``, and a deeply nested expression would otherwise hit the
    interpreter's recursion limit.
    """
    pending = [(tree, None)]
    while pending:
        node, enclosing = pending.pop()
        if isinstance(node, ast.ClassDef):
            enclosing = node.name
        yield node, enclosing
        pending.extend(
            reversed([(child, enclosing) for child in ast.iter_child_nodes(node)])
        )


@functools.lru_cache(maxsize=1)
def _objective_completers():
    """``{class_name: (chapter, frozenset of OBJ_* names it completes)}``.

    A call is credited to the innermost class around it. A call outside any
    class body belongs to no class and is left to ``TestObjectiveKeyRegistry``.
    """
    found = {}
    for module in story_modules():
        keys_by_class = {}
        for node, enclosing in _walk_with_enclosing_class(module.tree):
            if enclosing is None or call_target(node) != COMPLETE_OBJECTIVE:
                continue
            key = objective_key_name(node)
            if key is not None:
                keys_by_class.setdefault(enclosing, set()).add(key)
        for cls, keys in keys_by_class.items():
            assert cls not in found, (
                f"{cls} is defined in both {found[cls][0]} and {module.name}; "
                "keyed by bare name, one would hide the other"
            )
            found[cls] = (module.name, frozenset(keys))
    return found


def _completers_of(key_name):
    """Every story class that completes ``key_name``."""
    return {
        cls for cls, (_chapter, keys) in _objective_completers().items()
        if key_name in keys
    }


def _string_literal_args(call, enclosing):
    """Every string literal ``call`` is passed, positionally or by keyword,
    other than the enclosing class's own name."""
    for arg in itertools.chain(call.args, (k.value for k in call.keywords)):
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value != enclosing:
            yield arg.value


def _index_wiring(trees):
    """``{name: where it is wired}`` from one walk over ``trees``.

    A class is wired by being CONSTRUCTED (a call whose target names it) or
    NAMED by a string literal passed to a call -- ``functions.seek_class(
    "AfterGorranIntro", ...)`` instantiates by name. Neither counts inside
    the class's own body: a class constructing itself, or passing its own
    name to ``remove_event``, is not wiring. A ``name="Foo"`` constructor
    default is not a call argument, a docstring is a bare expression
    statement rather than a call argument, and comments are not in the tree
    at all -- so a class mentioned only in prose is unwired, which is the
    point of an AST walk over a text search.
    """
    index = {}
    for source in trees:
        rel_path = source.rel_posix
        for node, enclosing in _walk_with_enclosing_class(source.tree):
            if not isinstance(node, ast.Call):
                continue
            target = call_target(node)
            if target and target != enclosing:
                index.setdefault(target, f"{CONSTRUCTED} {rel_path} line {node.lineno}")
            for name in _string_literal_args(node, enclosing):
                index.setdefault(name, f"{NAMED_BY_STRING} {rel_path} line {node.lineno}")
    return index


@functools.lru_cache(maxsize=1)
def _engine_wiring():
    """The wiring index over every ``src/**/*.py``, built once per worker."""
    return _index_wiring(src_trees())


def _engine_evidence(cls_name):
    """Where the engine constructs or names ``cls_name``, or None."""
    return _engine_wiring().get(cls_name)


def _evidence_in(trees, cls_name):
    """The same answer over hand-built ``SourceFile``s -- how the control test
    feeds the walk code it wrote itself."""
    return _index_wiring(trees).get(cls_name)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def shipped_landing_world():
    """The shipped Ferry Landing passageway AND the tile's shipped events.

    Both come from the map JSON through the real loader, so every test built
    on this runs the completer the map actually places there -- the wiring
    is the thing under test, not just the event class. The tile's other
    authored content is not installed. ``TestTheShippedTileIsWired`` names
    the missing class if the placement is ever dropped.
    """
    return build_ferry_world(with_tile_events=True)


def _arm_ferry_objective(player):
    """Put the journal in the state Mara's chain leaves it in.

    The text is a placeholder on purpose: nothing here asserts on prose.
    Running the real ``MaraObservationEvent._set_gate`` instead is not an
    option because it also sets ``DEMO_END_READY_FLAG``, which the negative
    control below needs unset.
    """
    journal.set_objective(player, OBJ_CH03_FERRY_LANDING, "(armed by test)", chapter=3)


def _open_maras_gate(player, tile):
    """Run the real ``MaraObservationEvent._set_gate`` from ``tile``."""
    with capture_narration():
        MaraObservationEvent(player=player, tile=tile)._set_gate()


def _objective_status(player, key):
    """The journal's status for ``key``, or None when it was never set."""
    entry = player.universe.journal.objectives.get(key)
    return None if entry is None else entry.get("status")


def _landing_completers(tile):
    """The ``FerryLandingObjectiveEvent`` instances on ``tile``."""
    return [e for e in tile.events_here if isinstance(e, FerryLandingObjectiveEvent)]


def _assert_demo_end_closes_objective(game_service, player, ferry):
    """The client's request closes the objective in the same round trip:
    ``interact_with_target`` dispatches the demo-end arm and THEN
    re-evaluates the tile's events, rather than returning early."""
    assert _objective_status(player, OBJ_CH03_FERRY_LANDING) == journal.STATUS_ACTIVE

    result = interact_with(game_service, player, ferry)

    assert reported_beta_end(result), result
    assert _objective_status(player, OBJ_CH03_FERRY_LANDING) == journal.STATUS_DONE, (
        "the ferry objective is still open after the demo ended at the "
        "landing -- the player can never clear it"
    )


# ---------------------------------------------------------------------------
# The shipped tile
# ---------------------------------------------------------------------------


class TestTheShippedTileIsWired:
    """The completing event has to be ON the Ferry Landing tile.

    This is the assertion the original bug would have failed: the code that
    completed the objective existed, and was attached to nothing.
    """

    def test_the_ferry_tile_carries_a_completer_for_the_ferry_objective(self):
        assert getattr(journal, FERRY_OBJECTIVE_NAME, None) == OBJ_CH03_FERRY_LANDING, (
            f"{FERRY_OBJECTIVE_NAME} no longer names the ferry objective's journal "
            "constant -- the scans below would match a name nothing uses"
        )
        placed_here = {
            placement.class_name
            for placement in event_placements()
            if placement.map_name == FERRY_MAP.name
            and placement.coord == FERRY_TILE_KEY
        }
        completers = _completers_of(FERRY_OBJECTIVE_NAME)
        assert completers, f"no story class completes {FERRY_OBJECTIVE_NAME} -- scan is broken"
        assert placed_here & completers, (
            "the Ferry Landing tile carries no event that completes "
            f"{FERRY_OBJECTIVE_NAME}; it has {sorted(placed_here)} and the "
            f"classes completing that objective are {sorted(completers)}"
        )


# ---------------------------------------------------------------------------
# The objective clears
# ---------------------------------------------------------------------------


class TestTheObjectiveClearsInPlay:
    """Through ``interact_with_target`` -- the request the client actually
    sends -- plus one control that skips the interaction dispatch."""

    def test_using_the_ready_ferry_landing_completes_the_objective(
        self, game_service, shipped_landing_world
    ):
        player, _game_map, ferry = shipped_landing_world
        mark_ferry_ready(player, ferry)
        _arm_ferry_objective(player)

        _assert_demo_end_closes_objective(game_service, player, ferry)

    def test_enter_then_a_tile_re_evaluation_closes_it_without_the_interaction_dispatch(
        self, game_service, shipped_landing_world
    ):
        """Control: ``enter`` then a tile re-evaluation, with no API dispatch
        in between, so a failure above can be told apart from a failure of
        the event itself."""
        player, _game_map, ferry = shipped_landing_world
        mark_ferry_ready(player, ferry)
        _arm_ferry_objective(player)

        with capture_narration():
            ferry.enter(player)
            game_service.trigger_tile_events(player, ferry.tile, {})

        assert demo_has_ended(player)
        assert _objective_status(player, OBJ_CH03_FERRY_LANDING) == journal.STATUS_DONE

    def test_entering_the_landing_before_the_ferry_is_ready_leaves_the_objective_open(
        self, game_service, shipped_landing_world
    ):
        """Negative control: no ready flag, so nothing should close."""
        player, _game_map, ferry = shipped_landing_world
        _arm_ferry_objective(player)

        result = interact_with(game_service, player, ferry)

        assert not reported_beta_end(result), result
        assert not demo_has_ended(player)
        assert _objective_status(player, OBJ_CH03_FERRY_LANDING) == journal.STATUS_ACTIVE


# ---------------------------------------------------------------------------
# Saves that predate the placement
# ---------------------------------------------------------------------------


class TestSavesThatPredateThePlacement:
    """``load_game`` keeps a save's pickled maps, so a save made before the
    completer was authored onto the landing tile has a tile with no
    completer. ``ch03.wire_ferry_landing_completers`` re-adds it, found by
    what the edge IS rather than by a coordinate.

    Both reaches are covered here. A save already past Mara gets it at load,
    through ``src.story.repair_loaded_save`` -- no runtime hook could, since
    ``MaraObservationEvent`` has retired itself by then (``repeat=False``).
    A session that crosses Mara's gate without reloading gets it from
    ``_set_gate``, which runs the same repair.
    """

    def test_loading_a_save_already_past_mara_installs_the_completer(
        self, game_service
    ):
        """The reach no runtime hook has: Mara's event retired before the
        upgrade, so the load path is the only thing left to wire the tile."""
        player, _game_map, ferry = build_ferry_world(with_tile_events=False)
        landing = ferry.tile
        # The save is already past Mara: she set the gate and handed out the
        # objective on the old build, where nothing on a tile could close it.
        mark_ferry_ready(player, ferry)
        journal.set_objective(player, OBJ_CH03_FERRY_LANDING, "Meet Mara.", chapter=3)
        assert _landing_completers(landing) == []

        assert repair_loaded_save(player) == 1

        installed = _landing_completers(landing)
        assert len(installed) == 1, installed
        assert installed[0].tile is landing and installed[0].player is player
        # A second load finds it already wired and changes nothing.
        assert repair_loaded_save(player) == 0
        assert len(_landing_completers(landing)) == 1

        _assert_demo_end_closes_objective(game_service, player, ferry)

    def test_maras_gate_installs_the_completer_on_a_bare_landing(self, game_service):
        player, _game_map, ferry = build_ferry_world(with_tile_events=False)
        landing = ferry.tile
        assert _landing_completers(landing) == []

        _open_maras_gate(player, landing)

        installed = _landing_completers(landing)
        assert len(installed) == 1, installed
        assert installed[0].tile is landing and installed[0].player is player

        # And the installed event actually works: the demo end closes the
        # objective the gate just handed out.
        _assert_demo_end_closes_objective(game_service, player, ferry)

    def test_the_install_is_idempotent_on_the_shipped_tile(self, shipped_landing_world):
        player, _game_map, ferry = shipped_landing_world
        landing = ferry.tile
        assert len(_landing_completers(landing)) == 1, "shipped tile lost its completer"

        for _ in range(2):
            _open_maras_gate(player, landing)

        assert len(_landing_completers(landing)) == 1

    def test_the_install_targets_only_the_edge_gated_on_maras_key(self):
        """A demo edge waiting on some OTHER key is not this event's to
        wire; a plain passageway is not a demo edge at all."""
        other_edge_coord, plain_coord = (1, 0), (2, 0)
        player, game_map, ferry = build_ferry_world(
            with_tile_events=False, coords=(FERRY_WORLD_COORD, other_edge_coord, plain_coord)
        )
        other_edge = game_map[other_edge_coord]
        other_edge.objects_here = [demo_edge(player, other_edge, ready_flag=OTHER_EDGE_FLAG)]
        plain = game_map[plain_coord]
        plain.objects_here = [plain_passageway(player, plain)]

        # On the plain tile on purpose: the install must find the edge, not
        # wire the tile the gate-setting event happens to sit on.
        _open_maras_gate(player, plain)

        assert len(_landing_completers(ferry.tile)) == 1
        assert _landing_completers(other_edge) == []
        assert _landing_completers(plain) == []


# ---------------------------------------------------------------------------
# Every completer is reachable
# ---------------------------------------------------------------------------


class TestEveryObjectiveCompleterIsReachable:
    """A ``complete_objective`` call in unwired code is the shape of the bug
    described at the top of this module.

    Reachability is deliberately generous -- a class counts as wired if it is
    authored onto a tile in a shipped map, constructed anywhere in ``src/``, or
    named by a string literal passed to a call. What it will not accept is a
    class nothing reaches: mentioned only in prose, or only by itself.
    """

    def test_the_scan_finds_the_classes_it_is_meant_to_guard(self):
        """A scan that matches nothing approves of everything.

        Derived from ``src.journal``'s own ``OBJ_*`` roster, not a number
        written here: every declared objective is completed by some story
        class, and no undeclared name is completed. (``TestObjectiveKeyRegistry``
        pins the same equality at module scope; this scan is class-scoped, so
        a ``complete_objective`` call outside any class body would show up
        here as a declared key nothing completes.) ``event_placements``
        is the other population the wiring test draws on, so it is proven
        non-empty here too.
        """
        completers = _objective_completers()
        assert completers, "no story class completes an objective -- scan is broken"
        declared = declared_objectives()
        completed = set().union(*(keys for _chapter, keys in completers.values()))
        assert completed == declared, (
            f"declared but completed by no class: {declared - completed}; completed "
            f"but undeclared: {completed - declared} (this scan is class-scoped)"
        )
        assert event_placements(), "no events are placed in any map"

    def test_the_evidence_walk_sees_constructions_and_string_literal_names_but_not_prose(self):
        """Positive and negative controls for the wiring walk itself."""
        def tree(name, source):
            """One ``SourceFile``, as ``src_trees()`` yields them. The walk
            reads only the name and the tree, so the path is the name."""
            return SourceFile(name, pathlib.Path(name), ast.parse(textwrap.dedent(source)))

        wired = {
            "constructed": tree("a.py", "x = Foo(player)"),
            "attribute": tree("b.py", "x = story.Foo(player)"),
            "named by string literal": tree("c.py", 'seek_class("Foo", tile)'),
        }
        unwired = {
            "prose only": tree("d.py", '''
                """Foo(player) is built elsewhere."""
                # Foo(
                class Bar:
                    """See Foo."""
            '''),
            "own constructor default": tree("e.py", '''
                class Foo(Event):
                    def __init__(self, player, tile, name="Foo"):
                        super().__init__(name=name, player=player, tile=tile)
            '''),
            "names itself": tree("f.py", '''
                class Foo(Event):
                    def process(self):
                        self.tile.remove_event("Foo")
                        Foo(self.player, self.tile)
            '''),
        }
        for label, entry in wired.items():
            assert _evidence_in([entry], "Foo") is not None, label
        for label, entry in unwired.items():
            assert _evidence_in([entry], "Foo") is None, label
        assert _evidence_in([wired["constructed"]], "Foo") == f"{CONSTRUCTED} a.py line 1"
        assert _evidence_in([wired["named by string literal"]], "Foo") == (
            f"{NAMED_BY_STRING} c.py line 1"
        )

    @pytest.mark.parametrize(
        "cls_name, kind",
        [
            (FerryLandingObjectiveEvent.__name__, CONSTRUCTED),
            (AfterGorranIntro.__name__, NAMED_BY_STRING),
        ],
    )
    def test_the_walk_sees_both_kinds_of_wiring_in_the_real_tree(self, cls_name, kind):
        """Against the engine itself: the landing completer is constructed by
        ``ch03.wire_ferry_landing_completers``, which both the load-path repair
        and ``MaraObservationEvent`` run for saves that predate the placement,
        and ch01's ``AfterGorranIntro`` is reached only through a ``seek_class``
        string -- so each kind of evidence is exercised on real code, not only
        on the snippets above."""
        evidence = _engine_evidence(cls_name)
        assert evidence is not None and evidence.startswith(kind), evidence

    def test_every_objective_completing_class_is_wired_to_something(self):
        placed = {placement.class_name for placement in event_placements()}
        unwired = {
            cls: chapter
            for cls, (chapter, _keys) in sorted(_objective_completers().items())
            if cls not in placed and _engine_evidence(cls) is None
        }

        assert not unwired, (
            "these story classes complete a journal objective but are wired to "
            "nothing -- no map places them, nothing constructs them, nothing "
            f"names them: {unwired}. The objective they complete can never be "
            "cleared in real play."
        )
