"""Issue #552: the Ferry Landing must end the demo, not silently cross it.

The Ferry Landing at ``eastern-descent-nomad-camp`` (0, 2) is an ordinary
``Passageway`` with ``teleport_map: "eastern-descent"`` and
``teleport_tile: [2, 6]``, so using it teleported Jean back into the descent
map with no acknowledgement that the story stops here. The event written for
this moment was placed on no tile in any map.

The maintainer's chosen mechanism is the frontend's ``BetaEndDialog``, which is
already built and unit tested and carries a real **Send Feedback** button. The
backend's job is therefore to (a) not cross the river and (b) tell the client
``beta_end``, which is the same flag the combat adapter sets on the (currently
disabled) Lurker path and the same one ``GamePage`` reads off ``endState``.

Issue #579: the fix above shipped with no gate at all -- every crossing verb
ended the demo unconditionally, so a player who reached the Ferry Landing
without ever finishing Mara's conversation chain still got the closing beat
and the end-of-beta dialog. The gate is now authored per placement
(``Passageway.demo_end_ready_flag``); the shipped ferry's key is the one
``ch03.py``'s ``MaraObservationEvent`` writes, and a test below pins that the
map's authored key and the event's written key are the same string.
Behaviour that turns on the gate runs in both worlds (``world_by_readiness``)
and ends the demo only in the ready one. It is checked on ``enter`` (which
every crossing verb reaches) and, separately, on the ``_commit_teleport``
primitive that ``PassagewayTransitionEvent.process`` reaches without going
through ``enter`` at all.

The world under test is the shipped placement, loaded through the real map
loader -- see ``tests/_ferry_fixtures.py``.
"""

import pytest

from src import map_placeholders
from src.api.services.game_service import GameService
from src.events import PassagewayTransitionEvent, set_story_gate
from src.narration import capture_narration
from src.objects import Passageway, resolve_interaction
from src.story.ch03 import MaraObservationEvent
from tests._ferry_fixtures import (
    OTHER_EDGE_FLAG,
    REACHABLE_DESTINATION,
    REACHABLE_WORLD_COORDS,
    build_ferry_world,
    demo_edge,
    demo_has_ended,
    ferry_is_ready,
    ferry_placement,
    ferry_placement_props,
    instantiate_authored,
    interact_with,
    mark_ferry_ready,
    plain_passageway,
    reported_beta_end,
)
from tests._map_scan import class_ref


#: Every verb the client renders on the shipped ferry: ``ObjectSerializer``
#: ships ``keywords`` as the button list. Read off the ferry as the real
#: loader builds it -- the map authors its own ``keywords``, which the loader
#: sets over the list ``Passageway.__init__`` derives -- so a verb the map
#: starts rendering is exercised without anyone remembering to. Every one of
#: them is a way to say "use it".
def _verbs_the_shipped_ferry_renders():
    """The verbs the shipped Ferry Landing offers, from the real placement.

    A function rather than three module globals plus a ``del``: the world is
    only needed to read one attribute, and leaving it at module scope would
    make any later import-time constant thread itself between the build and
    the cleanup.
    """
    _player, _game_map, ferry = build_ferry_world(with_tile_events=False)
    return tuple(sorted(ferry.keywords))


_CROSSING_VERBS = _verbs_the_shipped_ferry_renders()

#: The instance attribute a passageway keeps its authored ``demo_end_ready_flag``
#: in, as ``Passageway`` itself declares it -- the one spelling of where the
#: authored key lives, for the tests that read or remove it.
_AUTHORED_READY_SLOT = Passageway.MAP_AUTHORED_ATTR_ALIASES["demo_end_ready_flag"]

#: Every verb the API's allow-list admits that the ferry does not render --
#: the looks, and the allow-list's item verbs. Reachable only by a hand-built
#: request, and none may end the demo.
_NON_CROSSING_VERBS = tuple(
    sorted(GameService._ALLOWED_INTERACTION_VERBS - set(_CROSSING_VERBS))
)


@pytest.fixture
def ferry_world():
    """A two-tile world carrying the real Ferry Landing, gate UNSATISFIED,
    repointed at a destination this world has.

    Repointed so every "Jean did not move" assertion is about the demo-end
    gate: at the shipped destination, which this world lacks, the teleport
    would fail on its own and the assertion would pass with the gate gone.
    The not-ready tests depend on the gate being unsatisfied; that is
    asserted once here rather than in each of them.
    """
    player, game_map, ferry = build_ferry_world(
        with_tile_events=False, coords=REACHABLE_WORLD_COORDS
    )
    ferry.teleport_map, ferry.teleport_tile = REACHABLE_DESTINATION
    assert not ferry_is_ready(player, ferry), (
        "fixture drift: a fresh world must start with the ferry gate unsatisfied"
    )
    return player, game_map, ferry


@pytest.fixture
def ferry_ready_world(ferry_world):
    """The same world with the ferry's gate set -- by ``mark_ferry_ready``,
    keyed off the placement's own authored key, not by running Mara's
    conversation chain."""
    player, game_map, ferry = ferry_world
    mark_ferry_ready(player, ferry)
    return player, game_map, ferry


@pytest.fixture(params=[True, False], ids=["ready", "not ready"])
def world_by_readiness(request, ferry_world):
    """``(ready, (player, game_map, ferry))``: a test using it runs once with
    the ferry's gate satisfied and once without."""
    player, game_map, ferry = ferry_world
    if request.param:
        mark_ferry_ready(player, ferry)
    return request.param, ferry_world


def _assert_declines_until_the_ferry_is_ready(player, ferry, cross):
    """``cross`` declines (False) while the ferry's gate is unset, and closes
    the demo (True) once it is set."""
    with capture_narration():
        assert cross(player) is False
        mark_ferry_ready(player, ferry)
        assert cross(player) is True


def _position(player):
    return (player.location_x, player.location_y, player.map.get("name"))


def _queued_event_ids(result):
    """The ids of the events ``result`` left waiting for a confirmation."""
    ids = (event.get("event_id") for event in result.get("events_triggered", []))
    return [event_id for event_id in ids if event_id]


def _drive_queued_events(game_service, player, result, session_data):
    """Confirm anything the interaction queued.

    The teleport lands on the SECOND request (``/world/events/input``), so an
    assertion on the interact response alone passes with the bug fully
    present.
    """
    for event_id in _queued_event_ids(result):
        game_service.process_event_input(player, event_id, "continue", session_data)


def _interact_and_confirm(game_service, player, target, verb="enter"):
    """Interact with ``target`` by ``verb``, then confirm whatever that
    queued; returns the interaction's own result."""
    session_data = {}
    result = interact_with(game_service, player, target, verb, session_data)
    _drive_queued_events(game_service, player, result, session_data)
    return result


def _narrated_text(messages):
    return " ".join(m.get("text", "") for m in messages)


def _step_through_names(result):
    """The "Step through?" confirmations an interaction armed."""
    names = (event.get("name", "") for event in result.get("events_triggered", []))
    return [name for name in names if name.startswith(PassagewayTransitionEvent.NAME_PREFIX)]


# ---------------------------------------------------------------------------
# The populations the tests below run over
# ---------------------------------------------------------------------------


def test_the_verb_populations_are_real():
    """A derived population that empties approves of everything, and a
    parametrize over an empty tuple skips instead of failing -- so the
    populations are pinned here, where an empty one fails loudly."""
    assert set(Passageway.CROSSING_METHOD_NAMES) <= set(_CROSSING_VERBS), _CROSSING_VERBS
    assert Passageway._DELEGATED_CROSSING_VERBS
    assert _NON_CROSSING_VERBS


@pytest.mark.parametrize("verb", _CROSSING_VERBS)
def test_every_verb_rendered_on_the_ferry_resolves_to_a_crossing(ferry_world, verb):
    """The API's demo-end arm fires only for a handler the engine calls a
    crossing (``Passageway.is_crossing_handler``). A rendered verb it does not
    -- a new delegator missing from ``CROSSING_METHOD_NAMES`` -- would fall to
    the step-through arm instead: the #552 seam."""
    _player, _game_map, ferry = ferry_world
    assert ferry.is_crossing_handler(resolve_interaction(ferry, verb)), verb


# ---------------------------------------------------------------------------
# The shipped map must actually carry the wiring — otherwise the code below is
# correct and the game still crosses the river.
# ---------------------------------------------------------------------------


def test_the_shipped_ferry_placement_is_flagged_as_the_demo_end():
    assert ferry_placement_props().get("demo_end") is True, (
        "the Ferry Landing placement no longer declares demo_end, so using it "
        "teleports Jean to eastern-descent (2, 6) with no end-of-demo dialog "
        "(issue #552)"
    )


@pytest.mark.parametrize("param", ["demo_end", "demo_end_ready_flag"])
def test_the_demo_end_wiring_is_map_authored(param):
    """A prop the loader would drop is not a wiring mechanism."""
    assert param in Passageway.MAP_AUTHORED_PARAMS


def test_the_shipped_placement_authors_the_key_mara_writes(ferry_world):
    """The map's ``demo_end_ready_flag`` and the key ``MaraObservationEvent``
    sets have to be the same string, or the ferry never opens in real play.

    The chain is held link by link: the map JSON authors a key, the loaded
    passageway carries that key (not the class fallback, which happens to be
    the same string), and running the real ``_set_gate`` writes it. The map
    value is data and the event's key is code; this is the one place the two
    are held to each other.
    """
    player, _game_map, ferry = ferry_world
    authored = ferry_placement_props().get("demo_end_ready_flag")
    carried = vars(ferry).get(_AUTHORED_READY_SLOT)
    assert carried == authored, (
        f"the placement authors {authored!r}; the loaded ferry carries {carried!r}"
    )
    before = set(player.universe.story)

    with capture_narration():
        MaraObservationEvent(player=player, tile=ferry.tile)._set_gate()

    written = set(player.universe.story) - before
    assert written == {authored}, (
        f"Mara's gate wrote {sorted(written)}; the shipped Ferry Landing is "
        f"authored to wait on {authored!r}"
    )


def test_the_map_export_writes_the_key_as_authored_not_the_fallback(ferry_world):
    """``demo_end_ready_flag`` validates where it is read and falls back to
    the ferry's key, but the Map Editor's export must write what was
    authored. Otherwise every passageway it saves comes back declaring the
    ferry's gate, and "no key of its own" stops being expressible."""
    player, _game_map, ferry = ferry_world
    plain = plain_passageway(player, ferry.tile)
    door = demo_edge(player, ferry.tile, ready_flag=OTHER_EDGE_FLAG)
    authored = ferry_placement_props()["demo_end_ready_flag"]

    def exported(passageway):
        return map_placeholders.to_placeholder(passageway)["params"]

    def round_tripped(passageway):
        return map_placeholders.instantiate_placeholder(
            map_placeholders.to_placeholder(passageway), player=player, tile=ferry.tile
        )

    assert exported(plain).get("demo_end_ready_flag") is None
    assert exported(door)["demo_end_ready_flag"] == OTHER_EDGE_FLAG
    assert exported(ferry)["demo_end_ready_flag"] == authored
    # Each export loads back to the gate it left with -- and "no key of its
    # own" loads back as no key, not as the fallback written in.
    assert round_tripped(door).demo_end_ready_flag == OTHER_EDGE_FLAG
    assert vars(round_tripped(plain)).get(_AUTHORED_READY_SLOT) is None


# ---------------------------------------------------------------------------
# Engine behaviour
# ---------------------------------------------------------------------------


def test_entering_a_demo_end_passageway_never_teleports(world_by_readiness):
    _ready, (player, _game_map, ferry) = world_by_readiness
    before = _position(player)

    with capture_narration():
        ferry.enter(player)

    assert _position(player) == before


def test_entering_sets_the_story_gate_only_when_the_ferry_is_ready(world_by_readiness):
    """Issue #579: reaching the ferry before Mara's chain completes must not
    close the demo; after it, it must."""
    ready, (player, _game_map, ferry) = world_by_readiness

    with capture_narration():
        ferry.enter(player)

    assert demo_has_ended(player) is ready


def test_end_demo_reports_whether_this_call_closed_the_demo(ferry_world):
    """The return value is about THIS call, not about the sticky gate.

    ``DEMO_ENDED_FLAG`` only says the demo has ended at some point; a caller
    (the API's ``beta_end``) needs to know whether the interaction it just
    dispatched did the ending or declined.
    """
    player, _game_map, ferry = ferry_world

    _assert_declines_until_the_ferry_is_ready(player, ferry, ferry.end_demo)


@pytest.mark.parametrize("verb", Passageway._DELEGATED_CROSSING_VERBS)
def test_the_delegating_verbs_hand_back_enters_verdict(ferry_world, verb):
    """``go``/``leave``/``exit`` are separate methods delegating to ``enter``;
    a delegator that dropped the return would read as "declined" to any
    caller dispatching the resolved handler -- the #552 seam a third time."""
    player, _game_map, ferry = ferry_world

    _assert_declines_until_the_ferry_is_ready(player, ferry, getattr(ferry, verb))


def test_is_demo_edge_answers_for_the_edge_and_its_key(ferry_world):
    player, _game_map, ferry = ferry_world
    door = demo_edge(player, ferry.tile, ready_flag=OTHER_EDGE_FLAG)
    plain = plain_passageway(player, ferry.tile)

    assert ferry.is_demo_edge() and door.is_demo_edge()
    assert not plain.is_demo_edge()
    assert ferry.is_demo_edge(ferry.demo_end_ready_flag)
    assert not ferry.is_demo_edge(OTHER_EDGE_FLAG)
    assert door.is_demo_edge(OTHER_EDGE_FLAG)
    assert not plain.is_demo_edge(ferry.demo_end_ready_flag)


def test_a_demo_edge_honours_its_own_authored_key(ferry_ready_world):
    """The gate key is per placement, so a second demo edge waits on ITS
    prerequisite -- not on the ferry's -- which is what lets the demo's edge
    move without re-plumbing the engine."""
    player, _game_map, ferry = ferry_ready_world
    door = demo_edge(player, ferry.tile, ready_flag=OTHER_EDGE_FLAG)

    with capture_narration():
        # The ferry's key is set (ready world); the door's is not.
        assert door.enter(player) is False
        assert not demo_has_ended(player)
        set_story_gate(player, OTHER_EDGE_FLAG)
        assert door.enter(player) is True
    assert demo_has_ended(player)


def test_a_passageway_from_an_older_save_falls_back_to_the_ferry_key(ferry_world):
    """Save compatibility: a pickled passageway from before the per-placement
    key existed carries no authored key in its instance dict, and the only
    demo edge ever shipped was the ferry -- so it must keep waiting on the
    ferry's key rather than on nothing."""
    player, _game_map, ferry = ferry_world
    door = demo_edge(player, ferry.tile, ready_flag=OTHER_EDGE_FLAG)
    assert vars(door)[_AUTHORED_READY_SLOT] == OTHER_EDGE_FLAG, vars(door)
    del vars(door)[_AUTHORED_READY_SLOT]  # what an older pickle restores

    assert door.demo_end_ready_flag == Passageway.DEMO_END_READY_FLAG
    _assert_declines_until_the_ferry_is_ready(player, ferry, door.enter)


def _door_built_directly(player, tile, authored):
    return demo_edge(player, tile, ready_flag=authored)


def _door_loaded_from_the_map(player, tile, authored):
    payload = ferry_placement()
    class_ref(payload).props["demo_end_ready_flag"] = authored
    # The edit has to land in the payload itself, not in a copy of its props.
    assert class_ref(payload).props["demo_end_ready_flag"] == authored
    return instantiate_authored(player.universe, payload, tile)


@pytest.mark.parametrize(
    "build", [_door_built_directly, _door_loaded_from_the_map],
    ids=["constructor", "map-loader"],
)
@pytest.mark.parametrize(
    "authored", [None, "", ["not", "a", "key"], {"nor": "this"}, 7], ids=repr
)
def test_anything_but_a_non_empty_string_falls_back_to_the_ferry_key(
    ferry_world, build, authored
):
    """Map JSON and saves are attacker-influenceable and the value becomes a
    dict key, so anything that is not a non-empty string -- None, empty,
    unhashable, or simply not a string -- must fall back to the ferry's key
    rather than reach ``end_demo``.

    Checked through the real map loader as well as the constructor: the
    loader re-applies every authored prop with a bare ``setattr`` after
    construction, so a check that lived only in ``__init__`` never saw the
    value the game keeps.
    """
    player, _game_map, ferry = ferry_world
    door = build(player, ferry.tile, authored)

    assert door.demo_end_ready_flag == Passageway.DEMO_END_READY_FLAG
    _assert_declines_until_the_ferry_is_ready(player, ferry, door.enter)


def test_an_instance_attribute_cannot_move_the_fallback_key(ferry_world):
    """A pickled save restores ``__dict__`` verbatim, so a tampered one can
    carry a ``DEMO_END_READY_FLAG`` of its own on one passageway. The
    fallback is read off the class, so that cannot re-gate a door that
    authors no key."""
    player, _game_map, ferry = ferry_world
    door = demo_edge(player, ferry.tile)
    vars(door)["DEMO_END_READY_FLAG"] = OTHER_EDGE_FLAG

    assert door.demo_end_ready_flag == Passageway.DEMO_END_READY_FLAG


def test_the_demo_end_lines_claim_nothing_about_the_surroundings(world_by_readiness):
    """Both lines live on Passageway, so they must be true for any passageway.

    Same rule as issue #565's lid: a line reused across placements may not
    assert scenery only one of them has. If the demo's edge moves to a door or
    a tunnel mouth, "the far bank" becomes a lie. The ready world exercises
    the closing beat, the not-ready world the #579 hint.
    """
    _ready, (player, _game_map, ferry) = world_by_readiness
    # No key of its own, so the door falls back to the ferry's: it declines
    # or closes exactly when the ferry would, in each world.
    door = demo_edge(player, ferry.tile)

    with capture_narration() as messages:
        door.enter(player)
    text = _narrated_text(messages).lower()

    assert "archive door" in text, text
    for scenery in ("bank", "water", "river", "ferry", "crossing"):
        assert scenery not in text, f"{scenery!r} is not there: {text!r}"


def test_the_declined_line_differs_from_the_demo_end_line(ferry_world):
    """A fix that narrates the same beat regardless of readiness would pass
    every assertion above by accident -- pin that the two lines actually
    differ, so the gate is doing more than gating a flag nobody reads."""
    player, _game_map, ferry = ferry_world

    with capture_narration() as not_ready_messages:
        ferry.enter(player)
    not_ready_text = _narrated_text(not_ready_messages)

    mark_ferry_ready(player, ferry)
    with capture_narration() as ready_messages:
        ferry.enter(player)
    ready_text = _narrated_text(ready_messages)

    assert not_ready_text.strip(), not_ready_text
    assert ready_text.strip(), ready_text
    assert not_ready_text != ready_text


def test_an_ordinary_passageway_still_teleports(ferry_world):
    """The flag must be opt-in; every other passageway is unaffected."""
    player, _game_map, ferry = ferry_world
    plain = plain_passageway(player, ferry.tile)

    with capture_narration():
        plain.enter(player)

    destination_map, destination_tile = REACHABLE_DESTINATION
    assert _position(player) == (*destination_tile, destination_map)


# ---------------------------------------------------------------------------
# The API contract the frontend reads
# ---------------------------------------------------------------------------


def test_using_the_ferry_reports_beta_end_only_when_the_ferry_is_ready(
    game_service, world_by_readiness
):
    """Issue #579: the API's ``beta_end`` flag must track whether the engine
    actually closed the demo, not fire unconditionally off the crossing verb."""
    ready, (player, _game_map, ferry) = world_by_readiness

    result = interact_with(game_service, player, ferry)

    assert result["success"] is True, result
    assert reported_beta_end(result) is ready, result
    assert demo_has_ended(player) is ready


def test_beta_end_reports_this_interaction_not_the_sticky_gate(
    game_service, ferry_world
):
    """``DEMO_ENDED_FLAG`` stays set forever once the demo ends. If the API
    read it back after the call, a later interaction that DECLINED would still
    report ``beta_end`` and re-raise ``BetaEndDialog``; the flag has to come
    from what this call did."""
    player, _game_map, ferry = ferry_world
    set_story_gate(player, Passageway.DEMO_ENDED_FLAG)  # ended earlier

    result = interact_with(game_service, player, ferry)

    assert result["success"] is True, result
    assert not reported_beta_end(result), result


@pytest.mark.parametrize("verb", _CROSSING_VERBS)
def test_no_crossing_verb_crosses_and_each_ends_the_demo_only_when_ready(
    game_service, world_by_readiness, verb
):
    """Every verb the ferry renders (``_CROSSING_VERBS``) stays on this bank,
    and ends the demo exactly when the ferry is ready: every one when ready
    (#552), none when not (#579) -- through the request and its confirm."""
    ready, (player, _game_map, ferry) = world_by_readiness
    before = _position(player)

    result = _interact_and_confirm(game_service, player, ferry, verb)

    assert reported_beta_end(result) is ready, result
    assert _position(player) == before, result
    assert demo_has_ended(player) is ready


def test_committing_a_teleport_never_crosses_a_demo_end_passageway(world_by_readiness):
    """The crossing primitive refuses on its own, whatever route reached it.

    ``enter`` guards ``demo_end``, but ``PassagewayTransitionEvent.process``
    calls ``_commit_teleport`` directly (see ``src/events.py``) and so never
    saw that guard -- exactly how #552 reopened the first time. Calling the
    primitive here, with no session/API layer involved, pins that the gate
    lives somewhere BOTH paths see: ready, it closes the demo; not ready, it
    declines (#579). Neither crosses.
    """
    ready, (player, _game_map, ferry) = world_by_readiness
    before = _position(player)

    with capture_narration():
        ferry._commit_teleport(player)

    assert _position(player) == before
    assert demo_has_ended(player) is ready


def test_using_the_ferry_does_not_teleport_through_the_api(game_service, ferry_world):
    """The reported bug: INTERACT -> enter dropped Jean at eastern-descent (2,6).

    The API path teleports on the *second* request — ``interact_with_target``
    queues a ``PassagewayTransitionEvent`` and ``/world/events/input`` commits
    the move — so this drives both halves.
    """
    player, _game_map, ferry = ferry_world
    before = _position(player)

    result = _interact_and_confirm(game_service, player, ferry)

    assert result["teleported"] is False, result
    assert _position(player) == before


def test_using_the_ferry_queues_no_step_through_confirmation(
    game_service, ferry_world
):
    """A "Step through?" prompt would be a lie — there is nothing to step to."""
    player, _game_map, ferry = ferry_world

    result = interact_with(game_service, player, ferry)

    assert _step_through_names(result) == [], result


@pytest.mark.parametrize("verb", _NON_CROSSING_VERBS)
def test_a_non_crossing_verb_never_ends_the_demo_nor_arms_a_step_through(
    game_service, world_by_readiness, verb
):
    """No verb the allow-list admits may end the demo except a crossing.

    Looking verbs resolve to nothing callable on ``Passageway``, so
    ``_is_demo_end_crossing`` correctly answers False for them -- and control
    then fell to the arm that queues a "Jean steps through..." confirmation
    for ANY Passageway. Confirming it ran ``_commit_teleport``, which ends the
    demo rather than crossing (good) but with ``beta_end`` never set, so the
    player got the closing beat and the story gate and NO BetaEndDialog. A
    test that asserted on the interact response only could not catch this:
    the damage happened on the confirm. The allow-list's item verbs are
    refused in fiction (#553) and must be just as inert.

    The ferry renders none of these, so this is reachable only by a
    hand-built request. Checked in both worlds: in the ready one, a confirm
    that reached ``_commit_teleport`` would actually close the demo -- so the
    check is that there is nothing left to confirm, not that confirming is
    harmless.
    """
    _ready, (player, _game_map, ferry) = world_by_readiness
    session_data = {}

    result = interact_with(game_service, player, ferry, verb, session_data)

    assert _step_through_names(result) == [], result
    assert not session_data.get("pending_events"), session_data
    assert _queued_event_ids(result) == [], result

    assert not reported_beta_end(result), result
    assert not demo_has_ended(player)


def test_an_ordinary_passageway_does_not_report_beta_end(game_service, ferry_world):
    player, _game_map, ferry = ferry_world
    plain = plain_passageway(player, ferry.tile)
    ferry.tile.objects_here = [plain]

    result = interact_with(game_service, player, plain)

    assert result["success"] is True, result
    assert not reported_beta_end(result), result


def test_the_ferry_still_says_something_in_fiction(game_service, world_by_readiness):
    """The dialog carries the meta-text; the panel still needs a beat of prose,
    and it has to be ``end_demo``'s own line in both worlds.

    A non-empty message alone proves nothing: when an interaction narrates
    nothing, the API substitutes a generic "Jean successfully completes..."
    line. Both ``end_demo`` lines name the passageway the way
    ``build_article_phrase`` spells it, and the generic line does not.
    """
    _ready, (player, _game_map, ferry) = world_by_readiness

    result = interact_with(game_service, player, ferry)

    assert result["success"] is True, result
    assert Passageway.build_article_phrase(ferry.name) in result["message"].lower(), result
