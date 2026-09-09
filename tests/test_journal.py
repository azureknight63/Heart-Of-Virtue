"""Journal state, narration coalescing, and the scene-recording seam (issue #538).

Covers the two halves of the journal feature that live in the engine/API layer:
:class:`src.journal.Journal` itself, and ``GameService``'s pacing/recording work
on captured narration. The frontend half is covered by the Vitest suite.
"""

import ast
import inspect
import io
import logging
import pickle

import pytest

from src.api.services.game_service import GameService
from src.journal import (
    LOG_CAP,
    LOG_CHAR_CAP,
    Journal,
    complete_objective,
    existing_journal,
    journal_for,
    set_objective,
)
from src.universe import Universe
from tests._gs_fixtures import GRID_3X3, live_world


@pytest.fixture
def gs():
    return GameService()


@pytest.fixture
def player():
    return live_world(GRID_3X3)[0]


class _PlayerWith:
    """Minimal stand-in for the journal helpers, which read only `.universe`."""

    def __init__(self, universe):
        self.universe = universe


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------


class TestObjectives:
    def test_set_then_complete_moves_between_the_two_lists(self):
        journal = Journal()
        journal.set_objective("cross", "Cross the river.", chapter=3)

        assert [o["text"] for o in journal.active_objectives()] == ["Cross the river."]
        assert journal.completed_objectives() == []

        journal.complete_objective("cross")

        assert journal.active_objectives() == []
        assert [o["key"] for o in journal.completed_objectives()] == ["cross"]

    def test_reissuing_an_objective_keeps_its_position_and_reactivates_it(self):
        journal = Journal()
        journal.set_objective("a", "First")
        journal.set_objective("b", "Second")
        journal.complete_objective("a")

        journal.set_objective("a", "First, again")

        # Reactivated, retitled, and still ahead of "b" -- an objective the
        # player has been staring at must not jump to the bottom of the list
        # because the story re-issued it.
        assert [o["key"] for o in journal.active_objectives()] == ["a", "b"]
        assert journal.objectives["a"]["text"] == "First, again"

    def test_completing_an_unknown_key_is_a_no_op_not_an_error(self):
        """Objective keys are authored in story files and cleared from handlers
        that may run in an order the author did not anticipate."""
        journal = Journal()
        assert journal.complete_objective("never-set") is None

    def test_blank_text_is_refused(self):
        journal = Journal()
        assert journal.set_objective("k", "   ") is None
        assert journal.objectives == {}

class TestTranscript:
    def test_records_lines_with_speaker_attribution(self):
        journal = Journal()
        journal.record_scene(
            "Camp Entry",
            [
                {"speaker": None, "text": "Jean stopped at the edge."},
                {"speaker": "Jean", "text": "Tents."},
            ],
            tick=7,
        )

        entry = journal.log[0]
        assert entry["title"] == "Camp Entry"
        assert entry["tick"] == 7
        assert entry["lines"][1] == {"speaker": "Jean", "text": "Tents."}

    def test_blank_lines_are_dropped_and_an_all_blank_scene_is_not_recorded(self):
        journal = Journal()
        journal.record_scene("Nowhere", [{"speaker": None, "text": "  "}])
        assert journal.log == []

    def test_log_is_capped_by_entry_count_keeping_the_newest(self):
        journal = Journal()
        for i in range(LOG_CAP + 5):
            journal.record_scene("Room", [{"speaker": None, "text": "line %d" % i}])

        assert len(journal.log) == LOG_CAP
        assert journal.log[-1]["lines"][0]["text"] == "line %d" % (LOG_CAP + 4)
        assert journal.log[0]["lines"][0]["text"] == "line 5"

    def test_log_is_also_capped_by_character_budget(self):
        """The entry cap alone bounds the wrong quantity.

        A scene is an unbounded list of unbounded lines, so 300 of them is
        unbounded in bytes -- and this structure is pickled into the save,
        which secure_pickle refuses to load past its own size ceiling.
        """
        journal = Journal()
        fat = "x" * 10_000
        for i in range(60):
            journal.record_scene("Room %d" % i, [{"speaker": None, "text": fat}])

        assert len(journal.log) < 60, "the entry cap alone would have kept all 60"
        total = sum(
            len(line["text"]) for entry in journal.log for line in entry["lines"]
        )
        assert total <= LOG_CHAR_CAP
        # The newest scene always survives, however fat.
        assert journal.log[-1]["title"] == "Room 59"

    def test_a_single_oversized_scene_is_still_kept(self):
        """Trimming must never empty the log of the scene just recorded."""
        journal = Journal()
        journal.record_scene("Room", [{"speaker": None, "text": "x" * (LOG_CHAR_CAP * 2)}])
        assert len(journal.log) == 1

    def test_an_identical_consecutive_scene_is_not_recorded_twice(self):
        """This runs on the per-beat combat path.

        A repeatable event re-emitting the same prose on every beat would
        otherwise file one copy per beat and evict real story scenes.
        """
        journal = Journal()
        lines = [{"speaker": None, "text": "The slime quivers."}]
        journal.record_scene("Arena", lines)
        journal.record_scene("Arena", lines)

        assert len(journal.log) == 1

    def test_the_same_scene_is_recorded_again_after_a_different_one(self):
        """Dedupe is consecutive-only -- a scene revisited later is new."""
        journal = Journal()
        lines = [{"speaker": None, "text": "The river was close."}]
        journal.record_scene("Camp", lines)
        journal.record_scene("Forge", [{"speaker": None, "text": "Hammering."}])
        journal.record_scene("Camp", lines)

        assert len(journal.log) == 3


class TestUniverseIntegration:
    def test_journal_survives_a_pickle_round_trip(self):
        """Saves are pickled ``Universe`` graphs -- the journal rides along."""
        universe = Universe()
        universe.journal.set_objective("k", "Persisted")

        restored = pickle.loads(pickle.dumps(universe))

        assert restored.journal.objectives["k"]["text"] == "Persisted"

    def test_a_save_written_before_the_journal_existed_gets_a_fresh_one(self):
        """``__init__`` does not run on unpickling, so the attribute is lazy."""
        universe = Universe()
        universe.journal  # force creation
        del universe.__dict__["_journal"]

        assert universe.journal.to_dict() == {
            "objectives": [],
            "completed": [],
            "log": [],
        }

    def test_existing_journal_does_not_create_one(self):
        """The read path must not dirty the save.

        `Universe.journal` is lazy, so reading it through the property attaches
        a Journal that then rides into the next pickle -- which would make
        GET /api/journal a writer.
        """
        universe = Universe()
        assert existing_journal(_PlayerWith(universe)) is None
        assert "_journal" not in universe.__dict__

        universe.journal.set_objective("k", "Now it exists")
        assert existing_journal(_PlayerWith(universe)) is not None

    def test_journal_for_does_create_one(self):
        """The write path is the half that is allowed to attach."""
        universe = Universe()
        assert journal_for(_PlayerWith(universe)) is not None
        assert "_journal" in universe.__dict__

    def test_the_lazy_property_constructs_exactly_one_journal(self, monkeypatch):
        """Two requests on one session must not each build a Journal and lose
        whichever wrote first.

        Counted rather than compared by identity: `universe.journal is
        universe.journal` is true under the get-then-set version `setdefault`
        replaced, so it cannot see the race it is named for.
        """
        built = []
        real_init = Journal.__init__

        def counting_init(self, *args, **kwargs):
            built.append(self)
            return real_init(self, *args, **kwargs)

        monkeypatch.setattr(Journal, "__init__", counting_init)

        universe = Universe()
        assert universe.journal is universe.journal
        assert len(built) == 1

    def test_module_helpers_no_op_without_a_universe(self):
        class Detached:
            universe = None

        detached = Detached()
        assert journal_for(detached) is None
        assert set_objective(detached, "k", "text") is None
        assert complete_objective(detached, "k") is None

    def test_set_objective_stamps_the_current_game_tick(self, player):
        player.universe.game_tick = 42
        entry = set_objective(player, "k", "Now")
        assert entry["tick"] == 42


# ---------------------------------------------------------------------------
# Narration coalescing (issue #538 item 1)
# ---------------------------------------------------------------------------


def _narration(text, in_conversation=False):
    return {"text": text, "type": "narration", "in_conversation": in_conversation}


class TestCoalesceNarrationSegments:
    def test_consecutive_plain_narration_beats_merge(self):
        """One ``narrate()`` call used to mean one mandatory full-screen click."""
        segments = [
            _narration("Jean smelled the camp before he saw it."),
            _narration("The sound of the river was constant behind it."),
        ]

        out = GameService._coalesce_narration_segments(segments)

        assert len(out) == 1
        assert "Jean smelled the camp" in out[0]["text"]
        assert "sound of the river" in out[0]["text"]

    def test_spoken_beats_are_never_merged(self):
        """One ``say()`` is one beat is one line -- the authored rhythm."""
        segments = [
            {"text": "Tents.", "type": "dialogue", "speaker": "Jean",
             "in_conversation": True},
            {"text": "Real ones, too.", "type": "dialogue", "speaker": "Jean",
             "in_conversation": True},
        ]

        assert GameService._coalesce_narration_segments(segments) == segments

    @pytest.mark.parametrize(
        "blocker",
        [
            {"enter": [{"id": "Liss"}]},
            {"exit": [{"id": "Liss"}]},
            {"reactions": {"Mara": "skeptical"}},
            {"thought": True},
            {"conversation_end": True},
            # The allow-list's whole point: a field nobody has thought of yet
            # must default to un-mergeable rather than being dropped.
            {"some_future_field": "value"},
        ],
    )
    def test_a_beat_carrying_stage_work_is_never_merged(self, blocker):
        segments = [
            _narration("Before."),
            dict(_narration("Anchored."), **blocker),
            _narration("After."),
        ]

        out = GameService._coalesce_narration_segments(segments)

        assert [s["text"] for s in out] == ["Before.", "Anchored.", "After."]

    def test_runs_do_not_cross_the_conversation_boundary(self):
        segments = [
            _narration("Unstaged prose.", in_conversation=False),
            _narration("Staged aside.", in_conversation=True),
        ]

        out = GameService._coalesce_narration_segments(segments)

        assert [s["text"] for s in out] == ["Unstaged prose.", "Staged aside."]

    def test_a_merged_run_longer_than_the_chunk_budget_is_re_split(self):
        """Merging is re-paced by ``_chunk_narration_text``, not unbounded."""
        long_line = "A sentence about the river. " * 12
        segments = [_narration(long_line), _narration(long_line)]

        out = GameService._coalesce_narration_segments(segments)

        assert len(out) > 1
        assert all(
            len(s["text"]) <= GameService._NARRATION_CHUNK_MAX_CHARS for s in out
        )

    def test_an_empty_segment_list_stays_empty(self):
        assert GameService._coalesce_narration_segments([]) == []

    def test_every_mergeable_key_is_one_the_run_splitter_compares(self):
        """The allow-list and the run splitter are two halves of one rule.

        A merged chunk is rebuilt from ``run[0]`` alone, so any mergeable key
        the splitter does NOT compare would be silently taken from the first
        beat and applied to the rest. `text` is the exception by definition --
        it is the thing being joined.
        """
        mergeable = set(GameService._MERGEABLE_SEGMENT_KEYS)
        assert mergeable, "the allow-list is empty; nothing would ever merge"

        source = io.open(
            inspect.getsourcefile(GameService._coalesce_narration_segments.__func__),
            encoding="utf-8",
        ).read()
        splitter = source[source.index("def _coalesce_narration_segments"):]
        splitter = splitter[: splitter.index("\n    @") if "\n    @" in splitter else len(splitter)]

        for key in mergeable - {"text"}:
            assert 'get("%s")' % key in splitter, (
                f"{key!r} may be merged but the run splitter never compares it, "
                "so beats 2..n would silently inherit beat 1's value"
            )


# ---------------------------------------------------------------------------
# Scene recording
# ---------------------------------------------------------------------------


class TestSceneRecording:
    def test_scene_lines_prefer_segments_for_their_attribution(self):
        lines = GameService._scene_lines(
            "ignored",
            [{"text": "Tents.", "speaker": "Jean"}, {"text": "Narration."}],
        )
        assert lines == [
            {"speaker": "Jean", "text": "Tents."},
            {"speaker": None, "text": "Narration."},
        ]

    def test_scene_lines_fall_back_to_splitting_the_flattened_prose(self):
        lines = GameService._scene_lines("One.\nTwo.", [])
        assert lines == [
            {"speaker": None, "text": "One."},
            {"speaker": None, "text": "Two."},
        ]

    def test_capture_scene_files_the_event_in_the_journal(self, gs, player):
        msgs = [{"text": "The river was close enough to hear.", "type": "narration"}]

        gs._capture_scene(msgs, player)

        log = player.universe.journal.log
        assert len(log) == 1
        assert log[0]["lines"][0]["text"] == "The river was close enough to hear."

    def test_recording_never_raises_out_of_the_event_loop(self, gs, player, caplog):
        """Journal writing is bookkeeping; it must not crash a story event.

        The log assertion is the load-bearing half: swallowing the failure
        silently would satisfy "did not raise" while hiding the fault forever,
        and CLAUDE.md requires a silent failure to be logged.
        """

        class Exploding:
            def record_scene(self, *args, **kwargs):
                raise RuntimeError("boom")

        player.universe.__dict__["_journal"] = Exploding()

        with caplog.at_level(logging.ERROR):
            gs._record_scene(player, "text", [])  # must not raise

        assert any("boom" in record.getMessage() or record.exc_info
                   for record in caplog.records), caplog.text

    def test_capture_scene_is_the_only_seam_that_captures_an_event(self):
        """Fail-open scope: the tests above prove the three known paths record,
        but not that a FOURTH path could not be added that does not.

        ``_capture_conversation`` is the pure transform; ``_capture_scene`` is
        the transform plus the journal write. A new event path calling the
        former directly would record nothing and every other test here would
        stay green, so the call graph itself is the thing to pin.
        """
        source = io.open(
            inspect.getsourcefile(GameService), encoding="utf-8"
        ).read()
        tree = ast.parse(source)

        callers = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Call)
                    and getattr(inner.func, "attr", None) == "_capture_conversation"
                ):
                    callers.add(node.name)

        assert callers, "found no _capture_conversation call sites to check"
        assert callers == {"_capture_scene"}, (
            "every event-processing path must capture through _capture_scene, "
            "which is what files the scene in the journal; these call "
            f"_capture_conversation directly and record nothing: {sorted(callers - {'_capture_scene'})}"
        )

    def test_get_journal_returns_the_full_shape_without_a_universe(self, gs):
        class Detached:
            universe = None

        assert gs.get_journal(Detached()) == {
            "objectives": [],
            "completed": [],
            "log": [],
        }

    def test_get_journal_does_not_attach_a_journal_to_a_save_that_lacks_one(self, gs, player):
        gs.get_journal(player)
        assert "_journal" not in player.universe.__dict__

    def test_get_journal_degrades_to_empty_rather_than_500ing(self, gs, player, caplog):
        """An old save whose `_journal` slot unpickled as a placeholder must
        render as an empty journal, not break every open of the dialog."""

        class Degraded:
            def to_dict(self):
                raise RuntimeError("legacy placeholder")

        player.universe.__dict__["_journal"] = Degraded()

        with caplog.at_level(logging.ERROR):
            assert gs.get_journal(player) == {
                "objectives": [],
                "completed": [],
                "log": [],
            }

        assert caplog.records, "the swallowed failure must still be logged"
