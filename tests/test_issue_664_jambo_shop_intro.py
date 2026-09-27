"""Regression coverage for issue #664: Jambo's first-entry shop introduction.

``JamboShopIntroEvent`` fires once, the first time Jean steps into either of
Jambo's tents (Grondia's, and the nomad camp's for a player who never went
into the Grondia one), and teaches the shop through Jambo's own patter.

The dialogue makes factual claims about the shop, so this file also pins each
claim to the mechanic that makes it true (``TestTheIntroTellsTheTruth``). If
one of those mechanics changes, the matching test fails and points at the line
of dialogue that has become a lie -- the issue asked for the rules to be taught
in character, and a character who misstates the rules is worse than none.
"""

from unittest.mock import Mock, patch

from src.narration import capture_narration
from tests._real_map_helpers import (
    build_universe as _build_universe,
    find_passage,
    map_named as _map,
    spoken as _spoken,
    text_of as _text,
)

#: Both tents, as (outer map file, outer map name, exterior coords,
#: tent map file, tent map name).
TENTS = (
    ("grondia.json", "grondia", (12, 4),
     "grondia-jambos_shop.json", "grondia-jambos_shop"),
    ("eastern-descent-nomad-camp.json", "eastern-descent-nomad-camp", (3, 0),
     "eastern-descent-jambos-tent.json", "eastern-descent-jambos-tent"),
)


def _intro(story=None):
    from src.story.ch02 import JamboShopIntroEvent

    player = Mock()
    player.skip_dialog = False
    player.universe = Mock()
    player.combat_list_allies = []
    player.universe.story = {} if story is None else story
    tile = Mock()
    event = JamboShopIntroEvent(player=player, tile=tile)
    tile.events_here = [event]
    return event, player, tile


class TestJamboShopIntroEvent:
    def test_fires_once_and_sets_its_gate(self):
        from src.story.ch02 import JamboShopIntroEvent

        event, player, tile = _intro()
        with capture_narration() as messages:
            event.check_conditions()
        assert _spoken(messages, "Jambo"), "Jambo never spoke"
        assert _spoken(messages, "Jean"), "Jean never spoke"
        assert player.universe.story[JamboShopIntroEvent.GATE_KEY] == "1"
        assert event not in tile.events_here

    def test_retires_silently_once_its_gate_is_set(self):
        from src.story.ch02 import JamboShopIntroEvent

        event, _player, tile = _intro({JamboShopIntroEvent.GATE_KEY: "1"})
        with capture_narration() as messages:
            event.check_conditions()
        assert messages == []
        assert event not in tile.events_here

    def test_jambo_enters_the_stage_on_his_first_line(self):
        """The portrait arrives with Jambo's first beat, not before it."""
        event, _player, _tile = _intro()
        with capture_narration() as messages:
            event.check_conditions()
        begin = next(m for m in messages if m.get("type") == "conversation_begin")
        assert [c["id"] for c in begin["cast"]] == ["Jean"]
        first_jambo = _spoken(messages, "Jambo")[0]
        assert [op["id"] for op in first_jambo.get("enter", [])] == ["Jambo"]

    def test_teaches_buying_selling_back_stock_and_restock(self):
        event, _player, _tile = _intro()
        with capture_narration() as messages:
            event.check_conditions()
        jambo = _text(_spoken(messages, "Jambo"))
        for needle in ("Restoratives", "Draughts", "Antidotes",  # always stocked
                       "half",                                  # sell price
                       "crate",                                 # back stock
                       "counter"):                              # where it's priced
            assert needle in jambo, needle

    def test_jambo_greets_gorran_when_he_is_in_the_party(self):
        """At the camp tent Gorran is usually at Jean's side; Jambo notices."""
        event, player, _tile = _intro()
        gorran = type("Gorran", (), {})()  # ch02 matches Gorran by class name
        player.combat_list_allies = [player, gorran]
        with capture_narration() as messages:
            event.check_conditions()
        begin = next(m for m in messages if m.get("type") == "conversation_begin")
        assert [c["id"] for c in begin["cast"]] == ["Jean", "Gorran"]
        assert "potion for stone" in _text(_spoken(messages, "Jambo"))

    def test_no_gorran_line_when_jean_is_alone(self):
        event, _player, _tile = _intro()
        with capture_narration() as messages:
            event.check_conditions()
        assert "stone" not in _text(_spoken(messages, "Jambo"))

    def test_skip_dialog_still_sets_the_gate(self):
        from src.story.ch02 import JamboShopIntroEvent

        event, player, _tile = _intro()
        player.skip_dialog = True
        with capture_narration() as messages:
            event.check_conditions()
        assert _spoken(messages) == []
        assert player.universe.story[JamboShopIntroEvent.GATE_KEY] == "1"


class TestTheIntroFiresOnFirstEntry:
    def test_both_tent_entrances_carry_the_intro(self):
        from src.story.ch02 import JamboShopIntroEvent

        for _outer_file, _outer, _ext, tent_file, tent_name in TENTS:
            universe, _player = _build_universe(tent_file)
            tile = _map(universe, tent_name)[(2, 2)]
            assert [type(e) for e in tile.events_here] == [JamboShopIntroEvent], tent_name

    def test_enter_fires_intro_and_reentry_does_not(self):
        """Walk in through the real tent passageway, out through the flap,
        and in again -- for both tents."""
        for outer_file, outer_name, exterior, tent_file, tent_name in TENTS:
            universe, player = _build_universe(outer_file, tent_file)
            outer = _map(universe, outer_name)
            player.map = outer
            player.location_x, player.location_y = exterior
            player.current_room = outer[exterior]
            # The camp's arrival beats are #663's business, not this test's.
            outer[exterior].events_here = []
            tent_passage = find_passage(outer[exterior], "Jambo's Tent")

            with capture_narration() as first:
                tent_passage.enter(player)
            assert (player.map.get("name"), (player.location_x, player.location_y)) == (
                tent_name, (2, 2)
            )
            assert _spoken(first, "Jambo"), "no introduction on first entry to " + tent_name
            from src.story.ch02 import JamboShopIntroEvent

            assert universe.story.get(JamboShopIntroEvent.GATE_KEY) == "1"

            flap = find_passage(player.current_room, "Tent Flap")
            flap.enter(player)
            assert (player.location_x, player.location_y) == exterior

            with capture_narration() as second:
                tent_passage.enter(player)
            assert _spoken(second) == [], tent_name

    def test_one_tent_intro_covers_the_other(self):
        """Met in Grondia -> no second introduction at the river."""
        from src.events import set_story_gate
        from src.story.ch02 import JamboShopIntroEvent

        _outer_file, _outer, _ext, tent_file, tent_name = TENTS[1]
        universe, player = _build_universe(tent_file)
        set_story_gate(player, JamboShopIntroEvent.GATE_KEY)
        tent = _map(universe, tent_name)
        player.teleport(tent_name, (2, 2))
        assert tent[(2, 2)].events_here == []


class TestTheIntroTellsTheTruth:
    """Each claim in the intro, pinned to the mechanic behind it."""

    def test_restoratives_draughts_and_antidotes_are_always_stocked(self):
        from src.npc import JamboHealsU

        always = {type(i).__name__ for i in JamboHealsU().always_stock}
        assert {"Restorative", "Draught", "Antidote"} <= always

    def test_jambo_buys_at_half_value(self):
        from src.npc import JamboHealsU

        assert JamboHealsU().sell_modifier == 0.5

    def test_the_back_room_crate_is_jambos_rotating_stock(self):
        """"More in the crate in the back room": the storage tile beside the
        entrance holds a Crate bound to Jambo, which restock fills with
        consumables alongside the counter."""
        for _o, _n, _e, tent_file, tent_name in TENTS:
            universe, _player = _build_universe(tent_file)
            tent = _map(universe, tent_name)
            assert (3, 2) in tent, "no storage tile east of the entrance"
            crates = [o for o in tent[(3, 2)].objects_here if type(o).__name__ == "Crate"]
            assert len(crates) == 1, tent_name
            assert crates[0].merchant == "Jambo"
            assert crates[0].stock_count > 0

    def test_the_back_room_crate_is_stocked_on_a_fresh_game(self):
        """The crate Jambo points at holds goods the moment the world exists,
        not only after the shop has been opened once (issue #727). Uses the
        real build path, since the helper above never runs ``build()``."""
        from tests._world_fixtures import fresh_built_world

        player = fresh_built_world(727)
        for _o, _n, _e, _tent_file, tent_name in TENTS:
            tent = _map(player.universe, tent_name)
            crate = next(o for o in tent[(3, 2)].objects_here if type(o).__name__ == "Crate")
            assert crate.inventory, f"{tent_name}: back-room crate is empty on a fresh game"

    def test_restock_turns_over_the_crate_as_well_as_the_counter(self):
        """"Jambo turns everything over -- the counter and the crate, both"."""
        from src.npc._shop import MerchantShopMixin

        merchant = Mock(spec=["inventory", "current_room", "_resolve_rooms_source", "name"])
        crate = Mock()
        crate.inventory = ["old stock"]
        merchant.inventory = ["old counter stock"]

        with patch("src.npc._shop.iter_rooms", return_value=[Mock(items_here=[])]), \
                patch("src.npc._shop.iter_merchant_containers", return_value=[crate]):
            containers = MerchantShopMixin._reset_stock_state(merchant)
        assert containers == [crate]
        assert crate.inventory == []
        assert merchant.inventory == []

    def test_unpaid_goods_stay_behind_at_the_flap(self):
        """"Nothing walks out of Jambo's tent unpaid": leaving through a
        passageway takes merchandise off Jean (Passageway.enter and
        Player.teleport both drop it), and the flap is the tent's only way out."""
        for _o, _n, _e, tent_file, tent_name in TENTS:
            universe, player = _build_universe(tent_file)
            tent = _map(universe, tent_name)
            player.map = tent
            player.location_x, player.location_y = 2, 2
            player.current_room = tent[(2, 2)]
            player.drop_merchandise_items = Mock(return_value=[])
            find_passage(tent[(2, 2)], "Tent Flap").enter(player)
            player.drop_merchandise_items.assert_called()
        for _o, _n, _e, tent_file, tent_name in TENTS:
            universe, _player = _build_universe(tent_file)
            exits = [
                (c, o.name)
                for c, t in _map(universe, tent_name).items()
                if isinstance(c, tuple)
                for o in t.objects_here
                if type(o).__name__ == "Passageway"
            ]
            assert exits == [((2, 2), "Tent Flap")], tent_name
