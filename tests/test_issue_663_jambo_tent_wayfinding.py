"""Regression coverage for issue #663: Jambo's tent is hard to find.

Two halves, one per map the tent lives on:

* **Grondia.** ``Ch02GuideToCitadel`` used to close by sending Jean to "the
  merchants of the Eastern Gate" and teleporting him to the Citadel forecourt
  ``grondia (10, 5)`` -- several tiles from the Ecumerium tile that actually
  holds Jambo's tent passageway. Votha Krr now names Jambo and the event lands
  Jean on the tent's exterior tile.
* **Nomad Camp.** The tent passageway sits on ``CampEntry (3, 0)`` among two
  existing one-shot arrival beats (``NomadCampSmellEvent`` and
  ``CampEntryGreetingEvent``). ``JamboTentNoticeEvent`` draws Jean's attention
  to it, and is sequenced strictly after the greeting.

The map-level tests load the REAL map JSON through the engine loader and drive
real ``Passageway.enter`` crossings (the same ``player.teleport`` path the
API's confirmation event commits), because a hand-built tile cannot tell us
the teleport lands somewhere the tent actually is.
"""

from unittest.mock import Mock

from src.events import set_story_gate
from src.narration import capture_narration
from tests._real_map_helpers import (
    build_universe as _build_universe,
    find_passage as _find_passage,
    map_named as _map,
    spoken as _spoken,
    text_of as _text,
)


def _place(player, map_dict, coords):
    player.map = map_dict
    player.location_x, player.location_y = coords
    player.current_room = map_dict[coords]


# ---------------------------------------------------------------------------
# Grondia: Votha Krr names Jambo and sends Jean to the tent exterior
# ---------------------------------------------------------------------------


def _guide_event(skip_dialog=False):
    from src.story.ch02 import Ch02GuideToCitadel

    player = Mock()
    player.skip_dialog = skip_dialog
    player.combat_list = []
    player.universe = Mock()
    player.universe.story = {}
    tile = Mock()
    tile.events_here = []
    tile.remove_event = Mock()
    return Ch02GuideToCitadel(player=player, tile=tile, params=None), player


def _play_to_stage_7(event):
    for _ in range(5):
        event.process()          # stages 1-5
    event.process(user_input="b")  # stage 6 -> 7


class TestVothaKrrSendsJeanToJambo:
    def test_the_tent_exterior_is_the_ecumerium_tile_holding_jambos_tent(self):
        """The teleport target is the tile whose passageway enters the tent --
        pinned against the real Grondia map, not a coordinate typed twice."""
        from src.story.ch02 import JAMBO_TENT_EXTERIOR

        universe, _player = _build_universe("grondia.json")
        map_name, coords = JAMBO_TENT_EXTERIOR
        tile = _map(universe, map_name)[coords]
        assert tile.name == "Ecumerium"
        passage = _find_passage(tile, "Jambo's Tent")
        assert passage is not None, "no Jambo's Tent passageway on the teleport target"
        assert passage.teleport_map == "grondia-jambos_shop"
        assert tuple(passage.teleport_tile) == (2, 2)

    def test_the_teleport_lands_where_the_tent_intro_can_trigger(self):
        """The two issues authored together: Votha's teleport target is one
        "enter" away from Jambo's first-entry introduction (#664)."""
        from src.story.ch02 import JAMBO_TENT_EXTERIOR

        universe, player = _build_universe("grondia.json", "grondia-jambos_shop.json")
        player.teleport(*JAMBO_TENT_EXTERIOR)
        passage = _find_passage(player.current_room, "Jambo's Tent")
        with capture_narration() as messages:
            passage.enter(player)
        assert player.map.get("name") == "grondia-jambos_shop"
        assert _spoken(messages, "Jambo")

    def test_farewell_names_jambo_and_the_market(self):
        event, _player = _guide_event()
        _play_to_stage_7(event)
        with capture_narration() as messages:
            event.process()  # stage 7: supplies + farewell
        votha = _text(_spoken(messages, "Votha Krr"))
        assert "Jambo" in votha
        assert "Ecumerium" in votha
        # The old, wrong direction is gone.
        assert "merchants of the Eastern Gate" not in _text(messages)

    def test_the_walk_leaves_jean_at_the_tent_flap_with_its_sign_read(self):
        """The attendant's walk is the player's wayfinding: it quotes the sign
        the Ecumerium tile shows ("Jambo Heals U") and names the flap, the way
        in, so the next move is obvious (maintainer review 2026-09-24)."""
        event, _player = _guide_event()
        _play_to_stage_7(event)
        with capture_narration() as messages:
            event.process()
        after_votha = messages[max(i for i, m in enumerate(messages)
                                   if m.get("speaker") == "Votha Krr") + 1:]
        walk = _text([m for m in after_votha if m.get("type") != "dialogue"])
        assert "Jambo Heals U" in walk
        assert "flap" in walk

    def test_closing_stage_teleports_to_the_tent_exterior(self):
        from src.story.ch02 import JAMBO_TENT_EXTERIOR

        event, player = _guide_event()
        _play_to_stage_7(event)
        event.process()  # stage 7 -> 8
        event.process()  # stage 8: cleanup
        player.teleport.assert_called_once_with(*JAMBO_TENT_EXTERIOR)
        assert JAMBO_TENT_EXTERIOR == ("grondia", (12, 4))
        assert event.completed is True

    def test_skip_dialog_fast_path_lands_on_the_same_tile(self):
        from src.story.ch02 import JAMBO_TENT_EXTERIOR

        event, player = _guide_event(skip_dialog=True)
        event.process()
        player.teleport.assert_called_once_with(*JAMBO_TENT_EXTERIOR)


# ---------------------------------------------------------------------------
# Nomad Camp: JamboTentNoticeEvent on CampEntry (3, 0)
# ---------------------------------------------------------------------------


def _notice_event(story=None):
    from src.story.ch03 import JamboTentNoticeEvent

    player = Mock()
    player.skip_dialog = False
    player.universe = Mock()
    player.universe.story = {} if story is None else story
    tile = Mock()
    event = JamboTentNoticeEvent(player=player, tile=tile)
    tile.events_here = [event]
    return event, player, tile


class TestJamboTentNoticeEvent:
    def test_waits_for_the_camp_greeting(self):
        """Sequencing: never before CampEntryGreetingEvent has played."""
        from src.story.ch03 import JamboTentNoticeEvent

        event, player, tile = _notice_event()
        with capture_narration() as messages:
            event.check_conditions()
        assert messages == []
        assert event in tile.events_here
        assert JamboTentNoticeEvent.GATE_KEY not in player.universe.story

    def test_fires_once_after_the_greeting_and_sets_its_gate(self):
        from src.story.ch03 import CampEntryGreetingEvent, JamboTentNoticeEvent

        event, player, tile = _notice_event({CampEntryGreetingEvent.GATE_KEY: "1"})
        with capture_narration() as messages:
            event.check_conditions()
        assert "Jambo Heals U" in _text(messages)
        assert _spoken(messages, "Jean"), "the notice should be a Jean/Gorran beat"
        assert player.universe.story[JamboTentNoticeEvent.GATE_KEY] == "1"
        assert event not in tile.events_here

    def test_retires_silently_once_its_gate_is_set(self):
        from src.story.ch03 import CampEntryGreetingEvent, JamboTentNoticeEvent

        event, _player, tile = _notice_event({
            CampEntryGreetingEvent.GATE_KEY: "1",
            JamboTentNoticeEvent.GATE_KEY: "1",
        })
        with capture_narration() as messages:
            event.check_conditions()
        assert messages == []
        assert event not in tile.events_here

    def test_recognises_jambo_when_jean_already_met_him_in_grondia(self):
        from src.story.ch02 import JamboShopIntroEvent
        from src.story.ch03 import CampEntryGreetingEvent

        fresh, _p, _t = _notice_event({CampEntryGreetingEvent.GATE_KEY: "1"})
        met, _p, _t = _notice_event({
            CampEntryGreetingEvent.GATE_KEY: "1",
            JamboShopIntroEvent.GATE_KEY: "1",
        })
        with capture_narration() as fresh_msgs:
            fresh.check_conditions()
        with capture_narration() as met_msgs:
            met.check_conditions()
        assert "Grondia" in _text(_spoken(met_msgs, "Jean"))
        assert "Grondia" not in _text(fresh_msgs)


class TestNomadCampArrivalSequence:
    def test_notice_is_authored_after_the_greeting_on_the_tent_tile(self):
        universe, _player = _build_universe("eastern-descent-nomad-camp.json")
        tile = _map(universe, "eastern-descent-nomad-camp")[(3, 0)]
        assert _find_passage(tile, "Jambo's Tent") is not None
        names = [type(e).__name__ for e in tile.events_here]
        assert names == [
            "NomadCampSmellEvent",
            "CampEntryGreetingEvent",
            "JamboTentNoticeEvent",
        ]

    def test_real_crossing_plays_smell_greeting_then_notice_once(self):
        """Cross eastern-descent -> nomad camp through the real passageway:
        all three arrival beats play in order on the first arrival; a second
        arrival plays nothing."""
        from src.story.ch03 import (
            CampEntryGreetingEvent,
            JamboTentNoticeEvent,
            NomadCampSmellEvent,
        )

        universe, player = _build_universe(
            "eastern-descent.json", "eastern-descent-nomad-camp.json"
        )
        descent = _map(universe, "eastern-descent")
        camp = _map(universe, "eastern-descent-nomad-camp")
        # The descent tile whose passage leads into the camp at (3, 0).
        coords, passage = next(
            (c, o)
            for c, t in descent.items()
            if isinstance(c, tuple)
            for o in getattr(t, "objects_here", [])
            if type(o).__name__ == "Passageway"
            and getattr(o, "teleport_map", None) == "eastern-descent-nomad-camp"
        )
        _place(player, descent, coords)

        with capture_narration() as first:
            passage.enter(player)
        assert (player.location_x, player.location_y) == (3, 0)
        story = universe.story
        for gate in (
            NomadCampSmellEvent.GATE_KEY,
            CampEntryGreetingEvent.GATE_KEY,
            JamboTentNoticeEvent.GATE_KEY,
        ):
            assert story.get(gate) == "1", gate
        text = _text(first)
        assert text.index("smelled the camp") < text.index("My name's Liss")
        assert text.index("My name's Liss") < text.index("Jambo Heals U")
        assert camp[(3, 0)].events_here == []

        # Leave and come back: nothing replays.
        back = _find_passage(camp[(3, 0)], "Camp Boundary")
        back.enter(player)
        _place(player, descent, coords)
        with capture_narration() as second:
            passage.enter(player)
        assert "Jambo Heals U" not in _text(second)
        assert _spoken(second) == []

    def test_notice_does_not_fire_if_greeting_gate_is_somehow_unset(self):
        """A save that already consumed the smell beat but not the greeting
        still keeps the notice behind the greeting."""
        from src.story.ch03 import JamboTentNoticeEvent, NomadCampSmellEvent

        universe, player = _build_universe("eastern-descent-nomad-camp.json")
        camp = _map(universe, "eastern-descent-nomad-camp")
        tile = camp[(3, 0)]
        _place(player, camp, (3, 0))
        set_story_gate(player, NomadCampSmellEvent.GATE_KEY)
        notice = next(e for e in tile.events_here if isinstance(e, JamboTentNoticeEvent))
        tile.events_here = [notice]
        notice.player, notice.tile = player, tile
        notice.check_conditions()
        assert JamboTentNoticeEvent.GATE_KEY not in universe.story


def _exit_reminder(story):
    from src.story.ch02 import JamboTentExitReminderEvent

    player = Mock()
    player.skip_dialog = False
    player.universe = Mock()
    player.universe.story = story
    player.combat_list_allies = []
    tile = Mock()
    event = JamboTentExitReminderEvent(player=player, tile=tile)
    tile.events_here = [event]
    return event, player, tile


class TestLeavingJambosTentPointsAtThePools:
    """Maintainer review 2026-09-24: once Jean has shopped, the next step is
    the Mineral Pools. Stepping back out of the tent flap is where he
    remembers it -- southwest, as Votha Krr told him."""

    def test_waits_while_jean_has_not_been_inside_yet(self):
        """Votha's teleport lands Jean on this tile BEFORE the tent: no
        reminder until Jambo's introduction has played."""
        event, player, tile = _exit_reminder({})
        with capture_narration() as messages:
            event.check_conditions()
        assert messages == []
        assert event in tile.events_here

    def test_fires_once_on_the_way_out(self):
        from src.story.ch02 import JamboShopIntroEvent, JamboTentExitReminderEvent

        event, player, tile = _exit_reminder({JamboShopIntroEvent.GATE_KEY: "1"})
        with capture_narration() as messages:
            event.check_conditions()
        jean = _text(_spoken(messages, "Jean"))
        assert "pools" in jean and "southwest" in jean
        assert player.universe.story[JamboTentExitReminderEvent.GATE_KEY] == "1"
        assert event not in tile.events_here

    def test_retires_silently_once_the_pools_are_cleansed(self):
        from src.story.ch02 import AfterDefeatingKingSlime, JamboShopIntroEvent

        event, _player, tile = _exit_reminder({
            JamboShopIntroEvent.GATE_KEY: "1",
            AfterDefeatingKingSlime.GATE_KEY: "1",
        })
        with capture_narration() as messages:
            event.check_conditions()
        assert messages == []
        assert event not in tile.events_here

    def test_authored_on_the_tile_the_tent_flap_returns_to(self):
        universe, _player = _build_universe("grondia.json", "grondia-jambos_shop.json")
        flap = _find_passage(_map(universe, "grondia-jambos_shop")[(2, 2)], "Tent Flap")
        outside = _map(universe, flap.teleport_map)[tuple(flap.teleport_tile)]
        assert any(type(e).__name__ == "JamboTentExitReminderEvent"
                   for e in outside.events_here)
