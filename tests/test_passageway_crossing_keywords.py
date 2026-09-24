"""Issue #630: extra crossing verbs are declared per placement, not inferred.

#620 gated the passageway "step through?" arm on
``is_crossing_handler(handler) or action in advertised_keywords(self)``. The
second half was an escape hatch for three shipped placements whose crossing
verb their name does not contain -- grondia (11, 5) ``inside``, grondia
(15, 5) ``east``, eastern-descent (0, 2) ``west`` -- and it accepted ANY
advertised keyword as meaning "cross", including one authored for another
purpose. Arming the crossing is not free: ``_queue_passageway_confirmation``
drops Jean's unpaid merchandise and runs ``events_before`` before the player
confirms anything.

A placement now declares its extra crossing verbs in ``crossing_keywords``.
They resolve to ``enter`` through the class-declared
``instance_keyword_aliases``, exactly as the name words do, so the gate is
``is_crossing_handler(handler)`` alone and the author's intent is stated.
"""

import pytest

from src import map_placeholders
from src.api.services.game_service import GameService
from src.events import PassagewayTransitionEvent
from src.narration import capture_narration
from src.objects import Passageway, resolve_interaction
from tests._ferry_fixtures import (
    REACHABLE_DESTINATION,
    REACHABLE_WORLD_COORDS,
    interact_with,
    plain_passageway,
)
from tests._gs_fixtures import live_world
from tests._map_scan import class_ref, map_data, tiles

#: The three shipped placements that forced #620's escape hatch, and the verb
#: each now declares. Named rather than derived on purpose: if one is renamed
#: or re-authored, this fails and the decision is made deliberately.
SHIPPED_CROSSING_KEYWORDS = {
    ("grondia.json", "(11, 5)"): ("The Guesthold", "inside"),
    ("grondia.json", "(15, 5)"): ("Eastern Gate", "east"),
    ("eastern-descent.json", "(0,2)"): ("Eastern Gate", "west"),
}

#: A verb a placement may advertise without meaning "cross". Not on the API
#: allow-list and not a Passageway method, so only the advertised keyword
#: authorizes it -- which is exactly the case the escape hatch waved through.
NON_CROSSING_KEYWORD = "admire"


@pytest.fixture
def game_service():
    return GameService()


def _world_with(way_kwargs=None, keywords_extra=()):
    player, game_map = live_world(coords=REACHABLE_WORLD_COORDS, start=(0, 0))
    tile = game_map[(0, 0)]
    destination_map, destination_tile = REACHABLE_DESTINATION
    way = Passageway(
        player=player, tile=tile, name="Eastern Gate",
        teleport_map=destination_map, teleport_tile=destination_tile,
        **(way_kwargs or {}),
    )
    way.keywords.extend(keywords_extra)
    tile.objects_here = [way]
    return player, way


class _MerchandiseSpy:
    """Counts ``drop_merchandise_items`` calls, installed on the instance
    (see tests/test_passageway_step_through_gate.py for why)."""

    def __init__(self, player):
        self.calls = 0
        self._real = player.drop_merchandise_items
        player.drop_merchandise_items = self

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return self._real(*args, **kwargs)


def _step_throughs(result):
    return [
        event.get("name", "")
        for event in result.get("events_triggered") or []
        if str(event.get("name", "")).startswith(PassagewayTransitionEvent.NAME_PREFIX)
    ]


# ---------------------------------------------------------------------------
# The engine rule
# ---------------------------------------------------------------------------


def test_a_declared_crossing_keyword_resolves_to_a_crossing():
    way = Passageway(player=None, tile=None, name="Eastern Gate",
                     crossing_keywords=["east"])
    handler = resolve_interaction(way, "east")
    assert handler is not None
    assert way.is_crossing_handler(handler)
    assert way.accepts_step_through(handler)
    # Advertised, so the client renders it and the API authorizes it.
    assert "east" in way.keywords


def test_an_advertised_keyword_alone_no_longer_crosses():
    """The escape hatch, closed: advertising a verb is not declaring it."""
    way = Passageway(player=None, tile=None, name="Eastern Gate")
    way.keywords.append(NON_CROSSING_KEYWORD)
    handler = resolve_interaction(way, NON_CROSSING_KEYWORD)
    assert handler is None
    assert not way.accepts_step_through(handler)


def test_crossing_keywords_never_redirect_a_declared_method():
    """What a crossing keyword reaches is fixed by the class (#620): a word
    naming a real method keeps that method, and is not a crossing."""
    class _Plaque(Passageway):
        def admire(self, player=None):
            return "admired"

    way = _Plaque(player=None, tile=None, name="Gate",
                  crossing_keywords=["admire"])
    handler = resolve_interaction(way, "admire")
    assert handler == way.admire
    assert not way.is_crossing_handler(handler)
    assert "admire" not in way.instance_keyword_aliases()


@pytest.mark.parametrize(
    "authored,expected",
    [
        ("east", {"east"}),                 # a bare string is one whole word
        (["east", 3, None, ""], {"east"}),  # non-strings and blanks ignored
        (None, set()),
        (["East"], {"east"}),               # verbs are lower-case on the wire
    ],
)
def test_malformed_crossing_keywords_declare_only_whole_words(authored, expected):
    way = Passageway(player=None, tile=None, name="Gate")
    way.crossing_keywords = authored
    declared = {
        word for word, method in way.instance_keyword_aliases().items()
        if word not in Passageway._name_alias_words(way.name)
    }
    assert declared == expected
    for word in expected:
        assert way.is_crossing_handler(resolve_interaction(way, word))
    assert resolve_interaction(way, "eas") is None


def test_a_passageway_from_an_older_save_has_no_crossing_keywords():
    way = Passageway.__new__(Passageway)
    way.name = "Eastern Gate"
    assert way.instance_keyword_aliases() == {"eastern": "enter", "gate": "enter"}


def test_crossing_keywords_is_authorable_on_both_map_paths():
    assert "crossing_keywords" in map_placeholders.authored_param_names(Passageway)
    assert map_placeholders.legacy_prop_allowed(Passageway, "crossing_keywords")
    player, game_map = live_world()
    way = map_placeholders.instantiate_placeholder(
        {"class": "objects.Passageway",
         "params": {"name": "Eastern Gate", "crossing_keywords": ["east"]}},
        player=player, tile=game_map[(0, 0)],
    )
    assert way.is_crossing_handler(resolve_interaction(way, "east"))


# ---------------------------------------------------------------------------
# Through the API, with both side effects
# ---------------------------------------------------------------------------


def test_a_crossing_keyword_arms_the_crossing_and_drops_merchandise(game_service):
    player, way = _world_with({"crossing_keywords": ["east"]})
    spy = _MerchandiseSpy(player)
    session_data = {}

    result = interact_with(game_service, player, way, "east", session_data)

    assert _step_throughs(result) == [
        f"{PassagewayTransitionEvent.NAME_PREFIX}{way.name}"
    ], result
    assert spy.calls == 1


def test_an_advertised_non_crossing_keyword_arms_nothing_and_drops_nothing(
    game_service,
):
    """Both side effects of the arm, on the verb the escape hatch let in."""
    player, way = _world_with(keywords_extra=[NON_CROSSING_KEYWORD])
    spy = _MerchandiseSpy(player)
    processed = []

    class _SpyEvent:
        def process(self):
            processed.append(True)

    way.events_before = [_SpyEvent()]
    session_data = {}

    result = interact_with(game_service, player, way, NON_CROSSING_KEYWORD, session_data)

    assert _step_throughs(result) == [], result
    assert not session_data.get("pending_events"), session_data
    assert spy.calls == 0
    assert processed == []
    # Refused in fiction, never an exception (#553).
    assert result["success"] is False and way.name in result["message"], result


# ---------------------------------------------------------------------------
# The shipped placements
# ---------------------------------------------------------------------------


def _shipped_payload(map_name, coord):
    for path, data in map_data():
        if path.name != map_name:
            continue
        for tile_coord, tile_payload in tiles(data):
            if tile_coord != coord:
                continue
            for payload in tile_payload.get("objects") or []:
                ref = class_ref(payload)
                if ref is not None and ref.class_name == "Passageway":
                    yield payload


@pytest.mark.parametrize(
    "where", sorted(SHIPPED_CROSSING_KEYWORDS), ids=lambda w: f"{w[0]}:{w[1]}"
)
def test_each_shipped_placement_declares_its_crossing_verb(game_service, where):
    """Loaded through the real map loader, the placement's verb crosses --
    and it crosses because it is declared, not because it is advertised."""
    name, verb = SHIPPED_CROSSING_KEYWORDS[where]
    matches = [p for p in _shipped_payload(*where) if class_ref(p).props.get("name") == name]
    assert len(matches) == 1, (where, name)
    assert verb in (class_ref(matches[0]).props.get("crossing_keywords") or [])

    player, game_map = live_world(coords=REACHABLE_WORLD_COORDS, start=(0, 0))
    tile = game_map[(0, 0)]
    with capture_narration():
        way = player.universe._deserialize_saved_instance(matches[0], tile=tile)
    assert isinstance(way, Passageway)
    assert way.is_crossing_handler(resolve_interaction(way, verb))

    way.teleport_map, way.teleport_tile = REACHABLE_DESTINATION
    tile.objects_here = [way]
    spy = _MerchandiseSpy(player)
    result = interact_with(game_service, player, way, verb, {})
    assert _step_throughs(result) == [
        f"{PassagewayTransitionEvent.NAME_PREFIX}{way.name}"
    ], result
    assert spy.calls == 1


def test_the_plain_passageway_probe_is_unchanged():
    """Positive control for the fixtures above: a passageway authoring no
    crossing keywords crosses by its name words and the four verbs."""
    player, game_map = live_world()
    way = plain_passageway(player, game_map[(0, 0)])
    for verb in ("enter", "go", "leave", "exit", "tent", "flap"):
        assert way.is_crossing_handler(resolve_interaction(way, verb)), verb
