"""Issue #620: the "step through?" arm must look at the verb, not just the type.

``_dispatch_interaction``'s fourth arm read

    isinstance(target, Passageway) and not _is_demo_end_passageway(target)
    and session_data is not None

and never mentioned the handler it had already resolved two lines above. So
every verb on ``GameService._ALLOWED_INTERACTION_VERBS`` -- LOOT, TAKE, EQUIP,
EXAMINE, the lot -- armed a crossing confirmation on any ordinary passageway,
and ``_queue_passageway_confirmation`` side-effects BEFORE the player is asked
anything: it runs ``player.drop_merchandise_items()`` and then every one of the
passageway's ``events_before``, and only then stores the pending event.

LOOT a city gate and Jean put down everything he was carrying to sell.

The gate is now ``is_crossing_handler(handler) or action in target.keywords``.
The second half is not slack: ``Passageway.__init__``'s alias loop binds words
of the placement's NAME (over three letters, alphabetic), so a placement that
authors a crossing verb its name does not contain resolves to nothing. Three
shipped ones do -- grondia (11, 5) ``inside``, grondia (15, 5) ``east`` and
eastern-descent (0, 2) ``west``, two of them main-path city gates -- and they
worked only because this arm ignored the handler. An authored keyword is the
author saying "this verb uses it", which ``_verb_refusal`` already treats as
authoritative, and issue #620's other half independently stops a map from
nominating a handler at all.

Both directions are checked here: the unadvertised allow-list verbs must arm
nothing and drop nothing, and every verb a shipped passageway does advertise
must still cross.
"""

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.api.services.game_service import GameService  # noqa: E402
from src.events import PassagewayTransitionEvent  # noqa: E402
from src.objects import Passageway, resolve_interaction  # noqa: E402
from tests._ferry_fixtures import (  # noqa: E402
    REACHABLE_DESTINATION,
    REACHABLE_WORLD_COORDS,
    interact_with,
    plain_passageway,
)
from tests._gs_fixtures import live_world  # noqa: E402
from tests._map_scan import class_ref, map_data, tiles  # noqa: E402


def _probe_passageway():
    """A ``plain_passageway`` built only to read its keywords off.

    The non-crossing population below is ``allow-list - this passageway's own
    keywords``, and it has to be THIS passageway's: ``test_ferry_demo_end.py``
    subtracts the shipped ferry's, which is right there and wrong here --
    ``plain_passageway`` is named "Tent Flap", so it binds ``flap`` and
    ``tent``, and the ferry binds ``ferry`` and ``landing``.
    """
    player, game_map = live_world()
    return plain_passageway(player, game_map[(0, 0)])


#: Every verb a shipped passageway of this name renders -- ``enter``, the three
#: delegators, and the words of its own name.
_ADVERTISED_VERBS = tuple(sorted(_probe_passageway().keywords))

#: The allow-list verbs the placement does NOT advertise. These are the hole:
#: reachable by any client at any target, and on a passageway they used to arm
#: a crossing.
_UNADVERTISED_VERBS = tuple(
    sorted(GameService._ALLOWED_INTERACTION_VERBS - set(_ADVERTISED_VERBS))
)


@pytest.fixture
def game_service():
    return GameService()


@pytest.fixture
def passageway_world():
    """A two-tile world with an ordinary passageway that can really cross."""
    player, game_map = live_world(coords=REACHABLE_WORLD_COORDS, start=(0, 0))
    tile = game_map[(0, 0)]
    way = plain_passageway(player, tile)
    way.teleport_map, way.teleport_tile = REACHABLE_DESTINATION
    tile.objects_here = [way]
    return player, way


class _MerchandiseSpy:
    """Counts ``drop_merchandise_items`` calls on one player.

    Installed on the INSTANCE rather than patched on the class: the queueing
    helper reaches it through ``hasattr(player, "drop_merchandise_items")``,
    and the drop is the side effect the ferry guard never looked at -- it
    asserts only on queued events, so a fix that stopped queuing while still
    dropping would pass it.
    """

    def __init__(self, player):
        self.calls = 0
        self._real = player.drop_merchandise_items
        player.drop_merchandise_items = self

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return self._real(*args, **kwargs)


def _step_throughs(result):
    """The "Jean steps through..." confirmations an interaction armed."""
    return [
        event.get("name", "")
        for event in result.get("events_triggered") or []
        if str(event.get("name", "")).startswith(
            PassagewayTransitionEvent.NAME_PREFIX
        )
    ]


# ---------------------------------------------------------------------------
# The populations
# ---------------------------------------------------------------------------


def test_the_verb_populations_are_real():
    """A parametrize over an empty tuple SKIPS rather than fails, so a
    derivation that stops matching would silently approve of everything."""
    assert _ADVERTISED_VERBS, "the probe passageway advertises no verbs at all"
    assert _UNADVERTISED_VERBS, (
        "every allow-list verb is now advertised by a plain passageway; the "
        "guard below has nothing left to exercise"
    )
    assert set(Passageway.CROSSING_METHOD_NAMES) <= set(_ADVERTISED_VERBS), (
        _ADVERTISED_VERBS
    )
    # The probe is named "Tent Flap", so its name words must be in there too --
    # this is what distinguishes it from the ferry's population.
    assert {"tent", "flap"} <= set(_ADVERTISED_VERBS), _ADVERTISED_VERBS


# ---------------------------------------------------------------------------
# The hole
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("verb", _UNADVERTISED_VERBS)
def test_an_unadvertised_allow_list_verb_arms_no_crossing(
    game_service, passageway_world, verb
):
    player, way = passageway_world
    session_data = {}

    result = interact_with(game_service, player, way, verb, session_data)

    assert _step_throughs(result) == [], result
    assert not session_data.get("pending_events"), session_data


@pytest.mark.parametrize("verb", _UNADVERTISED_VERBS)
def test_an_unadvertised_allow_list_verb_drops_no_merchandise(
    game_service, passageway_world, verb
):
    """The other side effect, and the one no existing guard watched.

    ``_queue_passageway_confirmation`` drops Jean's merchandise before the
    player has confirmed anything, so LOOT on a city gate emptied his stock
    with no prompt and no way back.
    """
    player, way = passageway_world
    spy = _MerchandiseSpy(player)

    interact_with(game_service, player, way, verb, {})

    assert spy.calls == 0


@pytest.mark.parametrize("verb", _UNADVERTISED_VERBS)
def test_an_unadvertised_allow_list_verb_runs_no_events_before(
    game_service, passageway_world, verb
):
    """``events_before`` runs inside the same helper, ahead of the prompt."""
    player, way = passageway_world
    processed = []

    class _SpyEvent:
        def process(self):
            processed.append(True)

    way.events_before = [_SpyEvent()]

    interact_with(game_service, player, way, verb, {})

    assert processed == []


@pytest.mark.parametrize("verb", _UNADVERTISED_VERBS)
def test_an_unadvertised_allow_list_verb_is_refused_in_fiction(
    game_service, passageway_world, verb
):
    """Falling to the generic arm must read as prose, never as an exception
    (#553) and never as silence."""
    player, way = passageway_world

    result = interact_with(game_service, player, way, verb, {})

    assert result["success"] is False, result
    assert way.name in result["message"], result
    for leak in ("Traceback", "AttributeError", "object has no attribute"):
        assert leak not in result["message"], result


# ---------------------------------------------------------------------------
# What must keep working
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("verb", _ADVERTISED_VERBS)
def test_every_verb_the_placement_advertises_still_arms_the_crossing(
    game_service, passageway_world, verb
):
    player, way = passageway_world
    session_data = {}

    result = interact_with(game_service, player, way, verb, session_data)

    assert _step_throughs(result) == [
        f"{PassagewayTransitionEvent.NAME_PREFIX}{way.name}"
    ], result


def _shipped_passageway_keywords():
    """``(map, coord, name, keyword)`` for every keyword every shipped
    ``Passageway`` placement authors.

    Read out of the map JSON, so a map that starts authoring a new verb is
    exercised without anyone remembering to add it here. The three rows that
    make this test matter -- ``inside``, ``east``, ``west`` -- resolve to
    nothing and are admitted by the advertised half of the gate alone.
    """
    rows = []
    for path, data in map_data():
        for coord, tile_payload in tiles(data):
            for payload in tile_payload.get("objects") or []:
                ref = class_ref(payload)
                if ref is None or ref.class_name != "Passageway":
                    continue
                name = ref.props.get("name")
                for keyword in ref.props.get("keywords") or []:
                    if isinstance(keyword, str):
                        rows.append((path.name, coord, name, keyword))
    return rows


_SHIPPED_KEYWORDS = _shipped_passageway_keywords()


def test_the_shipped_keyword_population_is_real():
    assert len(_SHIPPED_KEYWORDS) > 30, (
        f"only {len(_SHIPPED_KEYWORDS)} authored Passageway keywords found — "
        "the map scan has stopped matching"
    )
    unresolvable = [
        row for row in _SHIPPED_KEYWORDS
        if resolve_interaction(
            Passageway(player=None, tile=None, **({"name": row[2]} if row[2] else {})),
            row[3],
        ) is None
    ]
    assert unresolvable, (
        "no shipped passageway authors a keyword that resolves to nothing any "
        "more, so the `action in target.keywords` half of the gate is no "
        "longer load-bearing — if the maps were cleaned up, consider dropping "
        "it (and the escape hatch it is) rather than deleting this assertion"
    )


@pytest.mark.parametrize(
    "map_name,coord,name,keyword",
    _SHIPPED_KEYWORDS,
    ids=[f"{r[0]}:{r[1]}:{r[3]}" for r in _SHIPPED_KEYWORDS],
)
def test_every_shipped_passageway_keyword_still_crosses(
    game_service, map_name, coord, name, keyword
):
    """The blocking case: two of these are main-path city gates.

    Built the way the loader builds them -- constructor kwargs first, then the
    authored ``keywords`` applied over whatever ``__init__`` derived -- because
    that overwrite is exactly what makes ``inside``/``east``/``west`` reach the
    gate at all.
    """
    player, game_map = live_world(coords=REACHABLE_WORLD_COORDS, start=(0, 0))
    tile = game_map[(0, 0)]
    way = plain_passageway(player, tile, name=name or "Passageway")
    way.teleport_map, way.teleport_tile = REACHABLE_DESTINATION
    way.keywords = [k for _m, _c, n, k in _SHIPPED_KEYWORDS if n == name]
    tile.objects_here = [way]

    result = interact_with(game_service, player, way, keyword, {})

    assert _step_throughs(result) == [
        f"{PassagewayTransitionEvent.NAME_PREFIX}{way.name}"
    ], f"{map_name} {coord} {name!r} lost its {keyword!r} button: {result}"


def test_the_three_name_less_crossing_keywords_are_still_in_the_maps():
    """Anchor for the placements that forced the advertised half of the gate.

    Named deliberately: if one is renamed or re-authored, this fails and the
    decision is made on purpose rather than by a silently emptier population.
    """
    anchors = {
        ("grondia.json", "(11, 5)", "inside"),
        ("grondia.json", "(15, 5)", "east"),
        ("eastern-descent.json", "(0,2)", "west"),
    }
    found = {(m, c, k) for m, c, _n, k in _SHIPPED_KEYWORDS}
    assert anchors <= found, sorted(anchors - found)


def test_the_map_json_is_what_the_anchors_were_read_from():
    """Positive control for the anchors above: they came out of the shipped
    files, not out of this test's imagination."""
    raw = json.loads(
        (_ROOT / "src" / "resources" / "maps" / "grondia.json").read_text(
            encoding="utf-8"
        )
    )
    assert "(15, 5)" in raw
