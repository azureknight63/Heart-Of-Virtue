"""The objective chain and the transcript, driven through real story events.

Unit tests cover :class:`src.journal.Journal` and the segment coalescing in
isolation. This file runs the actual Chapter 1-3 events that were backfilled
for issue #538, through the same ``capture_narration`` -> ``_capture_scene``
path the API uses, so a renamed objective key or a story edit that drops a
``set_objective`` call fails here rather than in a play-through.
"""

import ast

import pytest

import src.journal as journal
from src.api.services.game_service import GameService
from src.narration import capture_narration
from src.player import Player
from src.story import ch01, ch02, ch03
from src.universe import Universe
from tests._ast_helpers import call_target
from tests._story_scan import (
    COMPLETE_OBJECTIVE,
    OBJECTIVE_CALLS,
    SET_OBJECTIVE,
    declared_objectives,
    is_objective_name,
    objective_key_name,
    objective_key_node,
    story_modules,
)


@pytest.fixture
def player():
    """A player with a universe and a stub current room, and no dialog skip.

    ``skip_dialog`` is left False on purpose: the whole point is that the real
    prose runs, so the transcript has something to record.
    """
    player = Player()
    player.universe = Universe(player)
    player.skip_dialog = False
    return player


class _Tile:
    """The minimum an Event touches: a name and its own event list."""

    def __init__(self, name="Camp Entry"):
        self.name = name
        self.events_here = []
        self.npcs_here = []
        self.objects_here = []

    def remove_event(self, _name):
        self.events_here.clear()


def run_event(gs, player, event):
    """Process ``event`` the way the API does and return its staged segments."""
    with capture_narration() as messages:
        event.process()
    _clean, segments, _conversation = gs._capture_scene(messages, player)
    return segments


@pytest.fixture
def gs():
    return GameService()


def _prerequisite_names(event_cls):
    """Who an event waits on: the first word of each prerequisite beat's gate.

    Read off the event's own ``PREREQUISITE_BEATS`` so the roster an objective
    must name comes from the event that actually enforces it, not from a copy
    in this file.
    """
    return {beat.GATE_KEY.split("_", 1)[0] for beat in event_cls.PREREQUISITE_BEATS}


def objective_keys(player, status="active"):
    journal = player.universe.journal
    source = journal.active_objectives() if status == "active" else journal.completed_objectives()
    return [o["key"] for o in source]


class TestChapterThreeObjectiveChain:
    """The nomad-camp route: the beta's play path and the issue's worked example."""

    def _camp_entry(self, gs, player):
        tile = _Tile("Camp Entry")
        player.current_room = tile
        event = ch03.CampEntryGreetingEvent(player=player, tile=tile)
        return run_event(gs, player, event)

    def test_camp_entry_records_the_goal_jean_states_aloud(self, gs, player):
        # Jean ends the scene with "let's ask around, see if anyone knows a way
        # across that river" — said once, in a modal that then closed.
        self._camp_entry(gs, player)
        assert "ch03_canvass_camp" in objective_keys(player)

    def test_mara_hands_over_the_actionable_objective(self, gs, player):
        self._camp_entry(gs, player)

        tile = _Tile("River's Edge")
        player.current_room = tile
        run_event(gs, player, ch03.MaraFirstContactEvent(player=player, tile=tile))

        # The canvassing objective is discharged and replaced by the hinge the
        # QA report named. Mara says "come back when the sun's lower"; there is
        # no clock in the game, so the objective states what to actually do.
        assert "ch03_canvass_camp" in objective_keys(player, "done")
        assert "ch03_walk_the_camp" in objective_keys(player)
        text = player.universe.journal.objectives["ch03_walk_the_camp"]["text"]
        assert "sun" not in text.lower()
        assert "Mara" in text

    def test_the_objective_names_exactly_the_gates_the_game_waits_on(self, gs, player):
        """An objective must not send the player after optional work.

        The roster is derived from `MaraObservationEvent.PREREQUISITE_BEATS`
        rather than restated here, so adding a fourth beat fails this instead
        of leaving the objective quietly stale.
        """
        names = _prerequisite_names(ch03.MaraObservationEvent)
        assert names, "MaraObservationEvent waits on no beats to derive the roster from"

        self._camp_entry(gs, player)
        tile = _Tile("River's Edge")
        player.current_room = tile
        run_event(gs, player, ch03.MaraFirstContactEvent(player=player, tile=tile))

        text = player.universe.journal.objectives["ch03_walk_the_camp"]["text"].lower()
        # Mara is the scene that just ran; the rest must be named.
        for name in names - {"mara"}:
            assert name in text, f"the objective never names {name}, which gates the ferry"
        # ...and nothing the game does not wait on.
        for optional in ("forge", "smith"):
            assert optional not in text

    def test_the_crossing_objective_closes_where_the_crossing_is_arranged(self, gs, player):
        """`ch02_find_mara` is "arrange a crossing" -- done at first contact,
        not two scenes later when Mara makes her observation."""
        self._camp_entry(gs, player)
        tile = _Tile("River's Edge")
        player.current_room = tile
        player.universe.journal.set_objective(
            "ch02_find_mara", "Find Mara at the river camp and arrange a crossing.", chapter=2
        )
        run_event(gs, player, ch03.MaraFirstContactEvent(player=player, tile=tile))

        assert "ch02_find_mara" in objective_keys(player, "done")

    def test_the_ferry_objective_replaces_it_once_the_camp_is_walked(self, gs, player):
        self._camp_entry(gs, player)
        tile = _Tile("River's Edge")
        player.current_room = tile
        run_event(gs, player, ch03.MaraFirstContactEvent(player=player, tile=tile))
        run_event(gs, player, ch03.MaraObservationEvent(player=player, tile=tile))

        assert "ch03_walk_the_camp" in objective_keys(player, "done")
        assert "ch03_ferry_landing" in objective_keys(player)

    def test_the_ferry_landing_completer_closes_the_last_objective(self, gs, player):
        """The closer is ``FerryLandingObjectiveEvent``, and it needs the gate.

        This used to run ``DemoEndEvent``, which closed the objective when
        called -- but nothing ever called it, so the objective was in fact
        uncloseable in play.

        ``run_event`` calls ``process()`` directly, bypassing the gate, so
        this only shows the class closes the objective once it runs. The two
        facts it cannot see -- that the completer waits for the demo to end,
        and that the shipped Ferry Landing tile carries it at all (the
        missing placement WAS the bug) -- are pinned in
        ``test_ferry_landing_objective.py``.
        """
        tile = _Tile("Ferry Landing")
        player.current_room = tile
        run_event(gs, player, ch03.MaraObservationEvent(player=player, tile=tile))
        run_event(
            gs, player, ch03.FerryLandingObjectiveEvent(player=player, tile=tile)
        )

        assert "ch03_ferry_landing" in objective_keys(player, "done")

    def test_objectives_are_set_even_when_the_prose_is_skipped(self, gs, player):
        """``skip_dialog`` is a QA/automation flag; it must not desync state."""
        player.skip_dialog = True
        tile = _Tile("Camp Entry")
        player.current_room = tile
        run_event(gs, player, ch03.CampEntryGreetingEvent(player=player, tile=tile))

        assert "ch03_canvass_camp" in objective_keys(player)

    def test_the_camp_smell_discharges_the_head_east_objective(self, gs, player):
        player.universe.journal.set_objective(
            "ch02_head_east", "Exit Grondia and head east to the river.", chapter=2
        )
        tile = _Tile("Camp Entry")
        player.current_room = tile
        run_event(gs, player, ch03.NomadCampSmellEvent(player=player, tile=tile))

        assert "ch02_head_east" in objective_keys(player, "done")


class TestTranscriptFromRealProse:
    def test_the_camp_scene_is_recorded_with_its_attribution(self, gs, player):
        tile = _Tile("Camp Entry")
        player.current_room = tile
        run_event(gs, player, ch03.CampEntryGreetingEvent(player=player, tile=tile))

        log = player.universe.journal.log
        assert len(log) == 1
        entry = log[0]
        assert entry["title"] == "Camp Entry"
        speakers = {line["speaker"] for line in entry["lines"]}
        assert "Jean" in speakers and None in speakers

    def test_every_line_of_the_scene_survives_into_the_transcript(self, gs, player):
        """Coalescing merges narration beats; it must never drop prose.

        The expected lines are read out of the capture rather than hand-copied
        here: a hand-copied sample under-covers (any OTHER dropped line still
        passes) and false-fails the day an author rewords a sentence.
        """
        tile = _Tile("Camp Entry")
        player.current_room = tile
        event = ch03.CampEntryGreetingEvent(player=player, tile=tile)

        with capture_narration() as messages:
            event.process()
        gs._capture_scene(messages, player)

        transcript = " ".join(
            line["text"] for line in player.universe.journal.log[0]["lines"]
        )
        emitted = [m["text"].strip() for m in messages if (m.get("text") or "").strip()]
        assert len(emitted) > 5, "expected a multi-beat scene to check"
        missing = [text for text in emitted if text not in transcript]
        assert not missing, f"prose lost in coalescing: {missing}"


class TestCampScenePacing:
    """Issue #538 item 1, measured on the scene the QA report counted."""

    def test_coalescing_cuts_the_camp_scene_beat_count(self, gs, player):
        tile = _Tile("Camp Entry")
        player.current_room = tile
        event = ch03.CampEntryGreetingEvent(player=player, tile=tile)

        with capture_narration() as messages:
            event.process()
        _clean, coalesced, _conv = gs._capture_conversation(messages, player)
        raw_text_beats = sum(1 for m in messages if (m.get("text") or "").strip())

        assert len(coalesced) < raw_text_beats

    def test_every_spoken_line_keeps_its_own_beat(self, gs, player):
        """Dialogue rhythm is authored; only narration is repacked.

        The expected count comes from the RAW capture, not from the coalesced
        output -- comparing the output to itself is how this assertion first
        got written, and it could never fail.
        """
        tile = _Tile("Camp Entry")
        player.current_room = tile
        event = ch03.CampEntryGreetingEvent(player=player, tile=tile)

        with capture_narration() as messages:
            event.process()
        _clean, segments, _conv = gs._capture_conversation(messages, player)

        raw_spoken = [m for m in messages if m.get("speaker")]
        assert raw_spoken, "the scene emitted no dialogue to check"
        merged_spoken = [seg for seg in segments if seg.get("speaker")]

        assert len(merged_spoken) == len(raw_spoken)
        assert [seg["text"] for seg in merged_spoken] == [m["text"] for m in raw_spoken]


class TestChapterOneAndTwoObjectives:
    def test_the_beta_briefing_becomes_the_objective_list(self, gs, player):
        """The briefing's five-step task list was delivered once, in a modal."""
        tile = _Tile("Grondia")
        player.current_room = tile
        event = ch02.BetaTesterBriefing(player=player, tile=tile)
        event._stage = 3
        event.process()

        assert objective_keys(player) == [
            "ch02_explore_grondia",
            "ch02_king_slime",
            "ch02_votha_krr",
            "ch02_head_east",
            "ch02_find_mara",
        ]

    def test_the_briefing_discharges_the_chapter_one_objective(self, gs, player):
        player.universe.journal.set_objective(
            "ch01_follow_gorran", "Follow Gorran through the Verdette Caverns.", chapter=1
        )
        tile = _Tile("Grondia")
        player.current_room = tile
        event = ch02.BetaTesterBriefing(player=player, tile=tile)
        event._stage = 3
        event.process()

        assert "ch01_follow_gorran" in objective_keys(player, "done")

    def test_the_grotto_intro_opens_the_first_objective(self, gs, player):
        tile = _Tile("Dark Grotto")
        player.current_room = tile
        event = ch01.Ch01DarkGrottoIntro(player=player, tile=tile)
        event._stage = 3
        event.process()

        assert "ch01_escape_grotto" in objective_keys(player)


class TestObjectiveKeyRegistry:
    """Every objective key the story uses comes from `src.journal`.

    `complete_objective` ignores an unknown key by design -- a bookkeeping slip
    must not crash the game loop -- so a mistyped key is silent, and its only
    symptom is an objective the player can never clear. These guards make that
    class of typo fail at test time instead.

    The populations are derived from the story modules' own syntax trees rather
    than from a list kept here, so adding a chapter or an objective cannot leave
    the guard checking a stale roster.
    """

    @staticmethod
    def _trees():
        """``(dotted name, tree)`` for every chapter.

        The roster is derived in ``tests/_story_scan.py`` and shared with the
        reachability guard in ``test_ferry_landing_objective.py``, so neither
        can under-scan the other's chapters.
        """
        return [(module.dotted, module.tree) for module in story_modules()]

    @classmethod
    def _objective_calls(cls):
        """Every objective call that passes a key, as ``(module, func_name, call)``."""
        calls = []
        for module_name, tree in cls._trees():
            for node in ast.walk(tree):
                name = call_target(node)
                if name in OBJECTIVE_CALLS and objective_key_node(node) is not None:
                    calls.append((module_name, name, node))
        return calls

    @classmethod
    def _keys_set(cls):
        """OBJ_* names the story SETS.

        Two shapes, because ch02's five beta-route objectives are authored once
        as a module-level table and set in a loop -- the call's key argument is
        then the loop variable, not an OBJ_* name, so the call alone does not
        name them. Any OBJ_* name inside a module-level assignment therefore
        counts as a set-site too.

        Names that are neither an OBJ_* constant nor a literal (a loop variable)
        are skipped here and covered by the table scan; a bare string literal is
        caught by `test_no_objective_key_is_written_as_a_bare_string`.
        """
        names = cls._keys_passed_to(SET_OBJECTIVE)
        for _module_name, tree in cls._trees():
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                names.update(
                    inner.id for inner in ast.walk(node.value) if is_objective_name(inner)
                )
        return names

    @classmethod
    def _keys_passed_to(cls, fn_name):
        """OBJ_* names passed as the key of every ``fn_name`` call."""
        return {
            objective_key_name(call)
            for _mod, fn, call in cls._objective_calls()
            if fn == fn_name
        } - {None}

    @classmethod
    def _keys_completed(cls):
        """OBJ_* names the story COMPLETES."""
        return cls._keys_passed_to(COMPLETE_OBJECTIVE)

    def test_the_scan_finds_the_calls_it_is_meant_to_guard(self):
        """A scan that matches nothing approves of everything.

        The floor is the objective roster `src.journal` declares, not a number
        written here: a hand-written floor sitting exactly on today's count
        fails for the wrong reason the day an objective is legitimately
        retired.
        """
        declared = declared_objectives()
        assert declared, "src.journal declares no OBJ_* constants"

        calls = self._objective_calls()
        assert len(calls) >= len(declared), calls
        assert {fn for _mod, fn, _call in calls} == set(OBJECTIVE_CALLS)
        assert self._keys_set() == declared
        assert self._keys_completed() == declared

    def test_no_objective_key_is_written_as_a_bare_string(self):
        keys = [
            (mod, fn, objective_key_node(call))
            for mod, fn, call in self._objective_calls()
        ]
        literals = [
            (mod, fn, key.value) for mod, fn, key in keys if isinstance(key, ast.Constant)
        ]
        assert not literals, (
            "objective keys must come from src.journal's OBJ_* constants so a "
            "typo fails at import instead of silently sticking an objective: "
            f"{literals}"
        )

    def test_every_key_the_story_completes_is_one_the_story_also_sets(self):
        """A completed key nobody sets is a dead call; a set key nobody
        completes is an objective the player can never clear."""
        set_keys = self._keys_set()
        done_keys = self._keys_completed()

        assert not (done_keys - set_keys), (
            f"completed but never set: {sorted(done_keys - set_keys)}"
        )
        assert not (set_keys - done_keys), (
            f"set but never completed: {sorted(set_keys - done_keys)}"
        )

    def test_every_objective_name_resolves_to_a_journal_constant(self):
        referenced = self._keys_set() | self._keys_completed()
        assert referenced
        missing = [name for name in referenced if not hasattr(journal, name)]
        assert not missing, f"not defined in src.journal: {sorted(missing)}"

    def test_no_journal_objective_constant_is_dead(self):
        """A constant the story never uses is either a rename that missed a
        call site or an objective that was dropped."""
        declared = declared_objectives()
        assert declared
        unused = declared - (self._keys_set() | self._keys_completed())
        assert not unused, f"declared but never used by the story: {sorted(unused)}"
