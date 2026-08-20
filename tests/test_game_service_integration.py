"""GameService's internal plumbing: output cleaning, event queueing, BGM, patches.

History
-------
This file promised "integration tests ... with minimal mocking" and delivered
48 tests against a ``MagicMock`` player, 21 of which asserted only
``isinstance(result, dict)``. Three were unfalsifiable by construction::

    assert len(mock_player_with_universe.explored) > 0 or True
    assert True                                    # "Should complete without error"
    assert result is not None or result is None    # "Should fail gracefully"

Two more (``test_apply_tile_modifications_*``) fed a ``"tile_mods"`` key the
service never reads — the real key is ``"tile_modifications"`` — so they proved
only that an unrecognised key is ignored, while claiming to prove the opposite.

The status/inventory/equipment/combat/"complex integration" classes were the
weakest copies of tests that now live properly in
``test_game_service_high_roi.py`` (stats & skills), ``test_game_service_methods.py``
(inventory & equipment), ``test_game_service_combat.py`` (combat) and
``test_game_service_world.py`` (tiles & exits).

What remains — and what this file is now about — is the **private plumbing every
event path runs through**: ``_clean_event_output``, ``_store_pending_event`` /
``_queue_interactive_event``, ``_resolve_bgm``, ``_serialize_active_states`` and
the event-patch construction. These are cheap to test directly and nothing else
covers them.
"""

import pytest

from src.api.services.game_service import GameService
from src.events import Event
from tests._gs_fixtures import GRID_3X3, live_world


@pytest.fixture(scope="session")
def game_service():
    """``GameService.__init__`` is ``pass`` — the service is stateless."""
    return GameService()


@pytest.fixture
def world():
    return live_world(GRID_3X3)


@pytest.fixture
def player(world):
    return world[0]


@pytest.fixture
def tile(world):
    return world[1][(0, 0)]


class _State:
    """The duck-typed shape ``_serialize_active_states`` reads."""

    def __init__(self, name="Poisoned", statustype="damage", beats_left=3, hidden=False):
        self.name = name
        self.statustype = statustype
        self.beats_left = beats_left
        self.hidden = hidden


class TestCleanEventOutput:
    """``_clean_event_output`` keeps internal diagnostics out of the UI."""

    def test_none_and_empty_become_the_empty_string(self, game_service):
        assert game_service._clean_event_output(None) == ""
        assert game_service._clean_event_output("") == ""

    @pytest.mark.parametrize(
        "prefix",
        [
            "[ERROR]",
            "[WARNING]",
            "Traceback (most recent call last):",
            "NameError:",
            "AttributeError:",
            "TypeError:",
            "KeyError:",
            "RuntimeError:",
            "DEBUG:",
        ],
    )
    def test_diagnostic_lines_are_dropped(self, game_service, prefix):
        clean = game_service._clean_event_output(f"{prefix} boom\nNormal message")
        assert clean == "Normal message"

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "PRODUCT BUG: the '  File ' entry in GameService._ERROR_PREFIXES is "
            "unreachable. _clean_event_output matches with line.strip().startswith(p), "
            "which removes the two leading spaces the prefix requires, so traceback "
            "frame lines leak into player-facing event text while the neighbouring "
            "'Traceback (most recent call last):' line is filtered. Either strip the "
            "prefix to 'File \"' or match with lstrip() as the LLM-noise filter does."
        ),
    )
    def test_indented_traceback_frames_are_dropped(self, game_service):
        dirty = 'Normal message\n  File "x.py", line 1, in <module>'
        assert game_service._clean_event_output(dirty) == "Normal message"

    def test_the_traceback_banner_itself_is_dropped(self, game_service):
        """The banner line has no leading whitespace, so its prefix does match."""
        dirty = "Traceback (most recent call last):\nNormal message"
        assert game_service._clean_event_output(dirty) == "Normal message"

    def test_llm_diagnostics_are_dropped(self, game_service):
        dirty = "OpenRouter returned 200\nActual response\nPrimary model failed"
        assert game_service._clean_event_output(dirty) == "Actual response"

    def test_ansi_sequences_are_stripped_in_place(self, game_service):
        clean = game_service._clean_event_output(
            "Normal text \x1B[32mgreen text\x1B[0m more text"
        )
        assert clean == "Normal text green text more text"

    def test_256_colour_sequences_are_stripped_too(self, game_service):
        clean = game_service._clean_event_output("Text \x1B[38;5;196mred\x1B[0m normal")
        assert clean == "Text red normal"

    def test_surrounding_whitespace_is_trimmed(self, game_service):
        assert game_service._clean_event_output("\n\n  Hello.  \n\n") == "Hello."

    def test_a_line_merely_containing_a_prefix_is_kept(self, game_service):
        """Only line-leading diagnostics are filtered — prose survives."""
        prose = "Jean muttered DEBUG: under his breath."
        assert game_service._clean_event_output(prose) == prose


class TestStorePendingEvent:
    """``_store_pending_event`` is how an interactive event survives a request."""

    def test_assigns_an_id_and_parks_the_event_in_the_session(self, game_service):
        event = Event(name="TestEvent")
        session_data = {"pending_events": {}}

        result = game_service._store_pending_event(event, {"name": "TestEvent"}, session_data)

        event_id = result["event_id"]
        assert event.api_event_id == event_id
        assert session_data["pending_events"][event_id]["event"] is event

    def test_an_existing_id_is_reused(self, game_service):
        event = Event(name="TestEvent")
        event.api_event_id = "already-assigned"
        result = game_service._store_pending_event(event, {"name": "TestEvent"}, {})
        assert result["event_id"] == "already-assigned"

    def test_a_second_event_of_the_same_name_reuses_the_first_id(self, game_service):
        """Two blocking entries for one event would deadlock the client."""
        session_data = {"pending_events": {}}
        first = Event(name="ItemFound")
        second = Event(name="ItemFound")

        first_id = game_service._store_pending_event(
            first, {"name": "ItemFound"}, session_data
        )["event_id"]
        second_id = game_service._store_pending_event(
            second, {"name": "ItemFound"}, session_data
        )["event_id"]

        assert second_id == first_id
        assert second.api_event_id == first_id
        assert len(session_data["pending_events"]) == 1

    def test_a_differently_named_event_gets_its_own_id(self, game_service):
        session_data = {"pending_events": {}}
        game_service._store_pending_event(
            Event(name="ItemFound"), {"name": "ItemFound"}, session_data
        )
        game_service._store_pending_event(
            Event(name="DoorLocked"), {"name": "DoorLocked"}, session_data
        )
        assert len(session_data["pending_events"]) == 2

    def test_tile_coordinates_are_stored_alongside(self, game_service, tile):
        session_data = {"pending_events": {}}
        result = game_service._store_pending_event(
            Event(name="LocationEvent"), {"name": "LocationEvent"}, session_data, tile=tile
        )
        payload = session_data["pending_events"][result["event_id"]]
        assert (payload["tile_x"], payload["tile_y"]) == (tile.x, tile.y)

    def test_a_tile_without_coordinates_is_skipped(self, game_service):
        session_data = {"pending_events": {}}
        result = game_service._store_pending_event(
            Event(name="E"), {"name": "E"}, session_data, tile=object()
        )
        assert "tile_x" not in session_data["pending_events"][result["event_id"]]

    def test_no_session_still_stamps_the_event_id(self, game_service):
        """The id must land on the event even when there is nowhere to park it."""
        event = Event(name="E")
        result = game_service._store_pending_event(event, {"name": "E"}, None)
        assert result["event_id"] == event.api_event_id


class TestQueueInteractiveEvent:
    """``_queue_interactive_event`` gates ``_store_pending_event`` on need-for-input."""

    def test_queues_an_event_awaiting_input(self, game_service):
        event = Event(name="E")
        session_data = {"pending_events": {}}

        result = game_service._queue_interactive_event(
            event, {"needs_input": True}, session_data
        )

        assert result["event_id"] in session_data["pending_events"]

    def test_a_completed_event_is_not_queued(self, game_service):
        event = Event(name="E")
        event.completed = True
        session_data = {}

        assert (
            game_service._queue_interactive_event(event, {"needs_input": True}, session_data)
            is None
        )
        assert session_data == {}

    def test_an_event_needing_no_input_is_not_queued(self, game_service):
        session_data = {}
        assert (
            game_service._queue_interactive_event(
                Event(name="E"), {"needs_input": False}, session_data
            )
            is None
        )
        assert session_data == {}


class TestResolveBgm:
    """``_resolve_bgm``: tile track, then map metadata, then a map-name guess."""

    def test_the_tile_track_wins(self, game_service, player, tile):
        tile.bgm = "special_tile.mp3"
        player.map["metadata"] = {"bgm": "map_default.mp3"}
        assert game_service._resolve_bgm(tile, player) == "special_tile.mp3"

    def test_map_metadata_is_the_fallback(self, game_service, player, tile):
        player.map["metadata"] = {"bgm": "map_default.mp3"}
        assert game_service._resolve_bgm(tile, player) == "map_default.mp3"

    @pytest.mark.parametrize(
        "map_name,expected",
        [
            ("dark-grotto", "dark_grotto"),
            ("nomad-camp", "nomad_camp"),
            ("jambos-tent", "jambos_tent"),
            ("eastern-descent", "eastern_descent"),
            ("verdette-caverns", "verdette_caverns"),
            ("mineral-pools", "mineral_pools"),
            ("grondia", "grondia"),
        ],
    )
    def test_known_map_names_have_a_default_track(
        self, game_service, player, tile, map_name, expected
    ):
        player.map = {"name": map_name}
        assert game_service._resolve_bgm(tile, player) == expected

    def test_map_name_matching_is_case_insensitive(self, game_service, player, tile):
        player.map = {"name": "Dark-Grotto-Depths"}
        assert game_service._resolve_bgm(tile, player) == "dark_grotto"

    def test_an_unknown_map_has_no_track(self, game_service, player, tile):
        player.map = {"name": "somewhere-new", "metadata": {}}
        assert game_service._resolve_bgm(tile, player) is None

    def test_a_non_dict_map_falls_back_to_the_tile(self, game_service, player, tile):
        tile.bgm = "tile.mp3"
        player.map = None
        assert game_service._resolve_bgm(tile, player) == "tile.mp3"


class TestSerializeActiveStates:
    """``_serialize_active_states`` must never 500 on a degraded save (#295)."""

    def test_states_are_serialized_to_json_safe_primitives(self, game_service, player):
        player.states = [_State("Poisoned", "damage", 3)]
        assert game_service._serialize_active_states(player) == [
            {"name": "Poisoned", "status_type": "damage", "beats_left": 3}
        ]

    def test_hidden_states_are_omitted(self, game_service, player):
        player.states = [_State("Poisoned"), _State("SecretCurse", hidden=True)]
        assert [s["name"] for s in game_service._serialize_active_states(player)] == [
            "Poisoned"
        ]

    @pytest.mark.parametrize("bad", [None, "not a list", 7])
    def test_a_non_list_states_attribute_yields_nothing(self, game_service, player, bad):
        player.states = bad
        assert game_service._serialize_active_states(player) == []

    def test_a_missing_states_attribute_yields_nothing(self, game_service):
        assert game_service._serialize_active_states(object()) == []

    @pytest.mark.parametrize("beats", [None, "three", True])
    def test_a_non_numeric_beat_count_is_coerced_to_zero(
        self, game_service, player, beats
    ):
        """``True`` is an ``int`` in Python; the guard rejects bools explicitly."""
        player.states = [_State(beats_left=beats)]
        assert game_service._serialize_active_states(player)[0]["beats_left"] == 0

    def test_missing_fields_get_defaults(self, game_service, player):
        player.states = [object()]
        assert game_service._serialize_active_states(player) == [
            {"name": "Unknown", "status_type": "generic", "beats_left": 0}
        ]


class TestEventTargetModules:
    """``_get_event_target_modules`` decides what ``_build_event_patches`` neutralizes."""

    ENGINE_MODULES = {
        "src.functions",
        "src.player",
        "src.interface",
        "src.items",
        "src.objects",
        "src.events",
        "src.story.effects",
    }

    def test_animations_are_included_by_default(self, game_service):
        modules = game_service._get_event_target_modules(Event(name="E"))
        assert "src.animations" in modules

    def test_animations_can_be_excluded(self, game_service):
        modules = game_service._get_event_target_modules(
            Event(name="E"), include_animations=False
        )
        assert "src.animations" not in modules

    def test_the_core_engine_modules_are_always_targeted(self, game_service):
        modules = set(game_service._get_event_target_modules(Event(name="E")))
        assert self.ENGINE_MODULES <= modules

    def test_the_events_own_module_is_added(self, game_service):
        """A story event defined outside ``src.events`` still gets patched."""
        modules = game_service._get_event_target_modules(Event(name="E"))
        assert Event.__module__ in modules

    def test_module_paths_are_all_canonical(self, game_service):
        """Bare-name imports create duplicate module objects — see CLAUDE.md."""
        modules = game_service._get_event_target_modules(Event(name="E"))
        assert all(m.startswith("src.") or m.startswith("tests") for m in modules)

    def test_patches_suppress_real_sleeping(self, game_service):
        """An event that pauses dramatically must not block the HTTP request."""
        import contextlib
        import time

        patches = game_service._build_event_patches(["src.functions"])
        with contextlib.ExitStack() as stack:
            for p in patches:
                with contextlib.suppress(AttributeError, ImportError, TypeError, ValueError):
                    stack.enter_context(p)
            started = time.monotonic()
            time.sleep(5)
            assert time.monotonic() - started < 1

    def test_patch_list_covers_every_requested_module(self, game_service):
        one = game_service._build_event_patches(["src.functions"])
        two = game_service._build_event_patches(["src.functions", "src.items"])
        # One shared time.sleep patch, then three per module.
        assert len(one) == 1 + 3
        assert len(two) == 1 + 3 * 2

    def test_duplicate_modules_are_patched_once(self, game_service):
        patches = game_service._build_event_patches(
            ["src.functions", "src.functions", "src.functions"]
        )
        assert len(patches) == 1 + 3


class TestStaticUniverseHelpers:
    """``_story``/``_game_tick`` — ``GameService`` has no ``self.universe``."""

    def test_story_reads_through_the_player(self, game_service, player):
        player.universe.story = {"ch01": True, "ch02": False}
        assert game_service._story(player) == {"ch01": True, "ch02": False}

    def test_story_without_a_universe_is_empty(self, game_service, player):
        player.universe = None
        assert game_service._story(player) == {}

    def test_game_tick_reads_through_the_player(self, game_service, player):
        player.universe.game_tick = 42
        assert game_service._game_tick(player) == 42

    def test_game_tick_without_a_universe_is_zero(self, game_service, player):
        player.universe = None
        assert game_service._game_tick(player) == 0

    def test_both_helpers_are_static(self, game_service):
        """They are called as ``self._story(player)`` but hold no instance state."""
        assert GameService._story(None) == {}
        assert GameService._game_tick(None) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
