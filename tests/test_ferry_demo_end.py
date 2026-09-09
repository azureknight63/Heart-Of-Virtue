"""Issue #552: the Ferry Landing must end the demo, not silently cross it.

The Ferry Landing at ``eastern-descent-nomad-camp`` (0, 2) is an ordinary
``Passageway`` with ``teleport_map: "eastern-descent"`` and
``teleport_tile: [2, 6]``, so using it teleported Jean back into the descent
map with no acknowledgement that the story stops here. ``DemoEndEvent``
(``src/story/ch03.py``) was written for this moment but is placed on no tile in
any map — ``grep -rl DemoEnd src/resources/maps/`` returns nothing.

The maintainer's chosen mechanism is the frontend's ``BetaEndDialog``, which is
already built and unit tested and carries a real **Send Feedback** button. The
backend's job is therefore to (a) not cross the river and (b) tell the client
``beta_end``, which is the same flag the combat adapter sets on the (currently
disabled) Lurker path and the same one ``GamePage`` reads off ``endState``.
"""

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.api.services.game_service import GameService  # noqa: E402
from src.combatant import wire_handle  # noqa: E402
from src.narration import capture_narration  # noqa: E402
from src.objects import Passageway  # noqa: E402
from tests._gs_fixtures import live_world  # noqa: E402

_FERRY_MAP = _ROOT / "src" / "resources" / "maps" / "eastern-descent-nomad-camp.json"


def _ferry_placement():
    """The authored Ferry Landing props, straight out of the shipped map."""
    raw = json.loads(_FERRY_MAP.read_text(encoding="utf-8"))
    for payload in raw["(0, 2)"]["objects"]:
        if (payload.get("props") or {}).get("name") == "Ferry Landing":
            return payload
    raise AssertionError("Ferry Landing is no longer at nomad-camp (0, 2)")


@pytest.fixture
def game_service():
    return GameService()


@pytest.fixture
def ferry_world():
    """A two-tile world carrying the real Ferry Landing placement.

    Built the way ``Universe._deserialize_saved_instance`` builds it: authored
    props filtered to the real constructor signature, then the rest applied by
    ``setattr``. So this fixture reflects the *shipped map*, and the assertions
    below fail if either the code or the placement is missing.
    """
    import inspect

    player, game_map = live_world(coords=((0, 0), (1, 0)))
    props = dict(_ferry_placement()["props"])
    props.pop("player", None)
    props.pop("tile", None)
    accepted = set(inspect.signature(Passageway.__init__).parameters)
    kwargs = {k: v for k, v in props.items() if k in accepted}
    ferry = Passageway(player=player, tile=game_map[(0, 0)], **kwargs)
    for key, value in props.items():
        if key not in kwargs:
            setattr(ferry, key, value)
    game_map[(0, 0)].objects_here = [ferry]
    return player, game_map, ferry


# ---------------------------------------------------------------------------
# The shipped map must actually carry the flag — otherwise the code below is
# correct and the game still crosses the river.
# ---------------------------------------------------------------------------


def test_the_shipped_ferry_placement_is_flagged_as_the_demo_end():
    props = _ferry_placement()["props"]
    assert props.get("demo_end") is True, (
        "the Ferry Landing placement no longer declares demo_end, so using it "
        "teleports Jean to eastern-descent (2, 6) with no end-of-demo dialog "
        "(issue #552)"
    )


def test_demo_end_is_a_real_map_authored_parameter():
    """A prop the loader would drop is not a wiring mechanism."""
    assert "demo_end" in Passageway.MAP_AUTHORED_PARAMS


# ---------------------------------------------------------------------------
# Engine behaviour
# ---------------------------------------------------------------------------


def test_entering_a_demo_end_passageway_does_not_teleport(ferry_world):
    player, _game_map, ferry = ferry_world
    # Repoint the destination at a tile this world actually has. The shipped
    # target ("eastern-descent" (2, 6)) is absent here and Player.teleport is a
    # silent no-op for a missing map, so without this the assertion would pass
    # for the wrong reason.
    ferry.teleport_map = "gs-test-map"
    ferry.teleport_tile = (1, 0)
    before = (player.location_x, player.location_y, player.map.get("name"))

    with capture_narration():
        ferry.enter(player)

    assert (player.location_x, player.location_y, player.map.get("name")) == before


def test_entering_a_demo_end_passageway_sets_the_story_gate(ferry_world):
    player, _game_map, ferry = ferry_world

    with capture_narration():
        ferry.enter(player)

    assert player.universe.story.get("demo_ended") == "1"


def test_the_demo_end_line_claims_nothing_about_the_surroundings(ferry_world):
    """It lives on Passageway, so it must be true for any passageway.

    Same rule as issue #565's lid: a line reused across placements may not
    assert scenery only one of them has. If the demo's edge moves to a door or
    a tunnel mouth, "the far bank" becomes a lie.
    """
    player, game_map, _ferry = ferry_world
    door = Passageway(
        player=player,
        tile=game_map[(0, 0)],
        name="Archive Door",
        demo_end=True,
    )

    with capture_narration() as messages:
        door.enter(player)
    text = " ".join(m.get("text", "") for m in messages)

    assert "Archive Door".lower() in text.lower(), text
    for scenery in ("bank", "water", "river", "ferry", "crossing"):
        assert scenery not in text.lower(), f"{scenery!r} is not there: {text!r}"


def test_an_ordinary_passageway_still_teleports(ferry_world):
    """The flag must be opt-in; every other passageway is unaffected."""
    player, game_map, _ferry = ferry_world
    plain = Passageway(
        player=player,
        tile=game_map[(0, 0)],
        name="Tent Flap",
        teleport_map="gs-test-map",
        teleport_tile=(1, 0),
    )

    with capture_narration():
        plain.enter(player)

    assert (player.location_x, player.location_y) == (1, 0)


# ---------------------------------------------------------------------------
# The API contract the frontend reads
# ---------------------------------------------------------------------------


def test_using_the_ferry_reports_beta_end(game_service, ferry_world):
    player, game_map, ferry = ferry_world

    result = game_service.interact_with_target(
        player, wire_handle(ferry), "enter", session_data={}
    )

    assert result["success"] is True, result
    assert result["beta_end"] is True, result


def test_every_crossing_verb_ends_the_demo_rather_than_crossing(
    game_service, ferry_world
):
    """The verbs the client actually renders must all hit the demo-end branch.

    ``Passageway.__init__`` pushes ``go``/``leave``/``exit`` into both
    ``action_aliases`` and ``keywords``, and ``ObjectSerializer`` ships
    ``keywords`` to the client -- so those three are buttons on the ferry, and
    on the shipped placement they are the ONLY authored ones
    (``eastern-descent-nomad-camp.json`` (0, 2) authors
    ``action_aliases: ["go", "leave", "exit"]``).

    They are separate methods delegating to ``enter``, not aliases of it, so a
    gate that compared the resolved handler against ``enter`` answered False
    for all three. Control then fell to the generic Passageway arm, which
    queues a ``PassagewayTransitionEvent`` whose ``process`` calls
    ``_commit_teleport`` directly -- past ``enter``'s ``demo_end`` guard. The
    demo's edge was crossable by three of the four ways to say "use it", and
    by the only three the map authors.

    ``ferry`` and ``landing`` are the instance-bound name words, which DO
    resolve to ``enter``; they are included so the fix cannot regress them.
    """
    player, _game_map, ferry = ferry_world

    for verb in ("enter", "go", "leave", "exit", "ferry", "landing"):
        session_data = {}
        before = (player.location_x, player.location_y)

        result = game_service.interact_with_target(
            player, wire_handle(ferry), verb, session_data=session_data
        )
        # Drive any queued confirmation too: the teleport lands on the SECOND
        # request, so asserting on the interact response alone passes with the
        # bug fully present.
        for event in result["events_triggered"]:
            event_id = event.get("event_id")
            if event_id:
                game_service.process_event_input(
                    player, event_id, "continue", session_data
                )

        assert result["beta_end"] is True, (verb, result)
        assert (player.location_x, player.location_y) == before, (verb, result)
        story = getattr(getattr(player, "universe", None), "story", {}) or {}
        assert story.get("demo_ended") == "1", (verb, story)
        story.pop("demo_ended", None)


def test_committing_a_teleport_can_never_cross_a_demo_end_passageway(ferry_world):
    """The crossing primitive refuses on its own, whatever route reached it.

    ``enter`` guards ``demo_end``, but ``PassagewayTransitionEvent.process``
    calls ``_commit_teleport`` directly and so never saw that guard. Guarding
    the primitive means no present or future path can cross the demo's edge --
    the gate above decides WHICH VERB crosses, this decides whether crossing
    is possible at all.
    """
    player, _game_map, ferry = ferry_world
    before = (player.location_x, player.location_y)

    with capture_narration():
        ferry._commit_teleport(player)

    assert (player.location_x, player.location_y) == before
    story = getattr(getattr(player, "universe", None), "story", {}) or {}
    assert story.get("demo_ended") == "1"


def test_merely_examining_the_ferry_does_not_end_the_demo(game_service, ferry_world):
    """Looking at the ferry must not fire the end-of-beta dialog.

    The demo-end branch was gated on the target being a demo_end Passageway
    and nothing else, so every verb `_ALLOWED_INTERACTION_VERBS` permits --
    examine, look, check, inspect, view, peruse -- ended the demo. A player
    who examined the ferry to read its description got the closing beat and a
    set `demo_ended` story gate without ever choosing to cross.
    """
    player, _game_map, ferry = ferry_world

    for verb in ("examine", "look", "check", "inspect", "view", "peruse"):
        result = game_service.interact_with_target(
            player, wire_handle(ferry), verb, session_data={}
        )
        assert result.get("beta_end") is not True, (verb, result)
        story = getattr(player, "story", {}) or {}
        assert not story.get("demo_ended"), (verb, story)


def test_using_the_ferry_does_not_teleport_through_the_api(game_service, ferry_world):
    """The reported bug: INTERACT -> enter dropped Jean at eastern-descent (2,6).

    The API path teleports on the *second* request — ``interact_with_target``
    queues a ``PassagewayTransitionEvent`` and ``/world/events/input`` commits
    the move — so this drives both halves. Asserting only on the interact
    response would pass even with the bug fully present.
    """
    player, game_map, ferry = ferry_world
    ferry.teleport_map = "gs-test-map"
    ferry.teleport_tile = (1, 0)
    session_data = {}

    result = game_service.interact_with_target(
        player, wire_handle(ferry), "enter", session_data=session_data
    )
    for event in result["events_triggered"]:
        event_id = event.get("event_id")
        if event_id:
            game_service.process_event_input(
                player, event_id, "continue", session_data
            )

    assert result["teleported"] is False, result
    assert (player.location_x, player.location_y) == (0, 0)
    assert player.map.get("name") == "gs-test-map"


def test_using_the_ferry_queues_no_step_through_confirmation(
    game_service, ferry_world
):
    """A "Step through?" prompt would be a lie — there is nothing to step to."""
    player, game_map, ferry = ferry_world
    session_data = {}

    result = game_service.interact_with_target(
        player, wire_handle(ferry), "enter", session_data=session_data
    )

    names = [e.get("name", "") for e in result["events_triggered"]]
    assert not any("Passage_" in n for n in names), names


def test_an_ordinary_passageway_does_not_report_beta_end(game_service, ferry_world):
    player, game_map, _ferry = ferry_world
    plain = Passageway(
        player=player,
        tile=game_map[(0, 0)],
        name="Tent Flap",
        teleport_map="gs-test-map",
        teleport_tile=(1, 0),
    )
    game_map[(0, 0)].objects_here = [plain]

    result = game_service.interact_with_target(
        player, wire_handle(plain), "enter", session_data={}
    )

    assert not result.get("beta_end"), result


def test_the_ferry_still_says_something_in_fiction(game_service, ferry_world):
    """The dialog carries the meta-text; the panel still needs a beat of prose."""
    player, game_map, ferry = ferry_world

    result = game_service.interact_with_target(
        player, wire_handle(ferry), "enter", session_data={}
    )

    assert result["message"].strip(), result
