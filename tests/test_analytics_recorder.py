"""The first-party analytics recorder (src/api/services/analytics.py).

Everything runs against a fake writer and an injected clock: nothing here may
reach Turso, and nothing here may depend on wall time.
"""

import asyncio
import inspect
from pathlib import Path
import hashlib
import hmac
import json
import re
import string
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from flask import Flask

from src.api.services import analytics, analytics_report
from src.api.services.analytics import AnalyticsRecorder, Event
from tests._analytics_doubles import (
    FakeClock,
    FakeWriter,
    enabled_recorder,
    flushed,
    inserted,
    real_session,
)

SRC = Path(__file__).resolve().parent.parent / "src"
NPC_KEY = "Gorran_0"  # the engine's f"{class_name}_{instance_count}"


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def writer():
    return FakeWriter()


@pytest.fixture
def rec(clock, writer):
    return enabled_recorder(writer, clock)


def events(writer):
    return [row[0] for row in inserted(writer)]


class TestPseudonymousId:
    def test_pid_is_stable_opaque_hex(self, rec):
        pid = rec.pid_for("user-1")
        assert pid == rec.pid_for("user-1")
        assert set(pid) <= set(string.hexdigits.lower())
        assert pid != rec.pid_for("user-2")

    def test_pid_depends_on_the_secret(self, rec, clock, writer):
        other = AnalyticsRecorder(writer=writer, clock=clock, secret="another")
        assert other.pid_for("user-1") != rec.pid_for("user-1")

    def test_encryption_key_is_never_itself_the_pid_key(self, monkeypatch, writer):
        # Key separation: without HOV_ANALYTICS_SECRET the key is a subkey
        # derived from ENCRYPTION_KEY, not ENCRYPTION_KEY used directly.
        monkeypatch.setenv("HOV_ANALYTICS_SECRET", "")
        monkeypatch.setenv("ENCRYPTION_KEY", "enc-key")
        derived = AnalyticsRecorder(writer=writer).pid_for("user-1")
        direct = AnalyticsRecorder(writer=writer, secret="enc-key").pid_for("user-1")
        assert derived != direct
        expected_key = hmac.new(b"enc-key", b"hov-analytics-pid-v1", hashlib.sha256).digest()
        expected = hmac.new(expected_key, b"pid:user-1", hashlib.sha256).hexdigest()
        assert derived == expected[: analytics._PID_HEX_CHARS]

    def test_no_key_means_no_pid_rather_than_an_unkeyed_one(self, monkeypatch, writer):
        monkeypatch.setenv("HOV_ANALYTICS_SECRET", "")
        monkeypatch.setenv("ENCRYPTION_KEY", "")
        r = AnalyticsRecorder(writer=writer)
        with pytest.raises(RuntimeError):
            r.pid_for("user-1")
        r.enabled = True  # as if the key vanished after configure()
        r.record(Event.LOGIN, real_session())
        assert r.flush() == 0


class TestConfigure:
    @pytest.mark.parametrize(
        "testing, url, flag, expected",
        [
            (True, "libsql://x", "1", False),
            (False, "", "1", False),
            (False, "libsql://x", "0", False),
            (False, "libsql://x", "off", False),
            (False, "libsql://x", " OFF ", False),
            (False, "libsql://x", "false", False),
            (False, "libsql://x", "no", False),
            # Blank means off, as everywhere else that reads a flag (config.env_flag).
            (False, "libsql://x", "", False),
            (False, "libsql://x", None, True),
            (False, "libsql://x", "1", True),
        ],
    )
    def test_enabled_only_outside_testing_with_a_database(
        self, monkeypatch, testing, url, flag, expected
    ):
        if flag is None:
            monkeypatch.delenv("HOV_ANALYTICS_ENABLED", raising=False)
        else:
            monkeypatch.setenv("HOV_ANALYTICS_ENABLED", flag)
        r = AnalyticsRecorder(writer=FakeWriter(), secret="s")
        r.enabled = not expected  # configure must overwrite it either way
        assert r.configure(testing=testing, database_url=url) is expected
        assert r.enabled is expected

    def test_no_key_at_all_disables_the_recorder(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_ENABLED", "1")  # so the key is the only reason
        monkeypatch.setenv("HOV_ANALYTICS_SECRET", "")
        monkeypatch.setenv("ENCRYPTION_KEY", "")
        r = AnalyticsRecorder(writer=FakeWriter())
        assert r.configure(testing=False, database_url="libsql://x") is False


class TestRecord:
    def test_disabled_recorder_buffers_nothing(self, rec, writer):
        rec.enabled = False
        rec.record(Event.LOGIN, real_session())
        assert rec.flush() == 0
        assert writer.batches == []

    def test_record_carries_pid_and_sid_never_the_account_id(self, rec, writer):
        session = real_session(db_user_id="user-1", session_id="sess-1")
        rec.record(Event.LOGIN, session, type="password")
        assert rec.flush() == 1
        [(event, pid, sid, props)] = inserted(writer)
        assert (event, props) == (Event.LOGIN, {"type": "password"})
        assert pid == rec.pid_for("user-1")
        assert sid and sid != session.session_id

    def test_no_recorder_method_writes_identifying_data(self, rec, writer):
        """Every recording method, on a session carrying every identifier."""
        session = real_session(db_user_id="user-1", session_id="sess-1", email="jean@example.com")
        markers = {"map": "dark-grotto", "flags": {"a"}}
        rec.heartbeat(session)
        rec.reset_progress(session, markers)
        rec.observe_progress(session, {"map": "grondia", "flags": {"a", "b"}})
        rec.chat_opened(session, NPC_KEY)
        rec.chat_turn(session, NPC_KEY, latency_ms=5)
        rec.chat_ended(session, NPC_KEY)
        rec.record(Event.FEEDBACK, session, type="bug")
        rec.flush()
        flat = json.dumps(writer.batches)
        # heartbeat, baseline map, map + flag, open, turn, end, feedback: every
        # entry point wrote, so the scan below covers each of them.
        assert len(inserted(writer)) == 8
        for identifier in ("user-1", "sess-1", "player_1", "jean_claire", "jean@example.com"):
            assert identifier not in flat

    def test_sid_is_stable_within_a_session_and_differs_across_them(self, rec, writer):
        one, two = real_session(), real_session()
        rec.record(Event.LOGIN, one)
        rec.record(Event.GAME_NEW, one)
        rec.record(Event.LOGIN, two)
        rec.flush()
        sids = [row[2] for row in inserted(writer)]
        assert sids[0] == sids[1] != sids[2]

    def test_a_session_with_no_account_is_ignored(self, rec):
        # /api/test/session makes these; they are harness traffic, not players.
        rec.record(Event.LOGIN, real_session(db_user_id=None))
        assert rec.flush() == 0

    def test_no_session_at_all_is_ignored(self, rec):
        rec.record(Event.COMBAT_START)
        assert rec.flush() == 0

    def test_an_unknown_event_name_is_dropped(self, rec):
        rec.record("combat.strat", real_session())
        assert rec.flush() == 0

    def test_props_are_limited_to_the_allowed_keys_and_scalars(self, rec, writer):
        rec.record(
            Event.COMBAT_END,
            real_session(),
            encounter="y" * 500,
            outcome=object(),
            beats=3,
            hp_pct=0.5,
            abandoned=True,
            level=None,
            username="jean_claire",
            jean_text="what the player typed",
        )
        rec.flush()
        [(_, _, _, props)] = inserted(writer)
        assert props == {
            "encounter": "y" * analytics.MAX_PROP_CHARS,
            "beats": 3,
            "hp_pct": 0.5,
            "abandoned": True,
            "level": None,
        }

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_numbers_are_dropped(self, rec, writer, bad):
        # json.dumps would write a bare NaN, which SQLite's json functions
        # reject -- failing a whole report section, not just this row.
        rec.record(Event.COMBAT_END, real_session(), hp_pct=bad, beats=3)
        rec.flush()
        [(_, _, _, props)] = inserted(writer)
        assert props == {"beats": 3}

    def test_buffer_is_bounded_and_keeps_the_newest(self, rec, writer):
        session = real_session()
        total = analytics.MAX_BUFFERED_EVENTS + 50
        for i in range(total):
            rec.record(Event.GAME_SAVE, session, beats=i)
        assert rec.flush() == analytics.MAX_BUFFERED_EVENTS
        kept = [props["beats"] for _, _, _, props in inserted(writer)]
        assert kept[0] == 50 and kept[-1] == total - 1

    def test_record_never_raises(self, rec):
        class Hostile:
            @property
            def __dict__(self):
                raise RuntimeError("boom")

        rec.record(Event.LOGIN, Hostile())  # must not raise


class TestFlush:
    def test_schema_is_ensured_once_before_the_first_insert(self, rec, writer):
        session = real_session()
        rec.record(Event.LOGIN, session)
        rec.flush()
        rec.record(Event.GAME_NEW, session)
        rec.flush()
        first, second = writer.batches
        assert [s for s, _ in first[: len(analytics.SCHEMA_STATEMENTS)]] == list(analytics.SCHEMA_STATEMENTS)
        assert not any(s.startswith("CREATE") for s, _ in second)

    def test_empty_flush_does_not_touch_the_database(self, rec, writer):
        assert rec.flush() == 0
        assert writer.batches == []

    def test_failed_write_is_swallowed_and_retries_the_schema(self, clock):
        failing = FakeWriter(fail=True)
        r = enabled_recorder(failing, clock)
        r.record(Event.LOGIN, real_session())
        assert r.flush() == 0  # no raise
        failing.fail = False
        r.record(Event.GAME_NEW, real_session())
        assert r.flush() == 1
        assert failing.batches[0][0][0].startswith("CREATE TABLE")

    def test_the_default_writer_is_bounded_by_a_timeout(self, monkeypatch):
        # The exit-time flush must not hang a deploy on an unreachable database.
        seen = {}

        def fake_run(work, timeout=None):
            seen["timeout"] = timeout

        monkeypatch.setattr(analytics, "run_with_private_client", fake_run)
        analytics._turso_writer([("SELECT 1", [])])
        assert seen["timeout"] == analytics.WRITE_TIMEOUT_SECONDS

    def test_the_timeout_also_covers_closing_the_client(self, monkeypatch):
        class HangingClose:
            async def batch(self, statements):
                return None

            async def close(self):
                await asyncio.sleep(30)

        monkeypatch.setattr(analytics, "create_client_from_env", HangingClose)
        with pytest.raises(asyncio.TimeoutError):
            analytics.run_with_private_client(lambda c: c.batch([]), timeout=0.05)

    def test_a_close_after_a_timed_out_write_is_bounded_too(self, monkeypatch):
        # The write times out; the close then runs inside the cancellation,
        # where the outer bound no longer reaches it.
        class Unreachable:
            async def batch(self, statements):
                await asyncio.sleep(30)

            async def close(self):
                await asyncio.sleep(30)

        monkeypatch.setattr(analytics, "create_client_from_env", Unreachable)
        monkeypatch.setattr(analytics, "CLOSE_TIMEOUT_SECONDS", 0.05)
        started = time.monotonic()
        with pytest.raises(asyncio.TimeoutError):
            analytics.run_with_private_client(lambda c: c.batch([]), timeout=0.05)
        assert time.monotonic() - started < 5

    def test_the_flush_loop_survives_a_failing_flush(self, rec, monkeypatch):
        class Stop(BaseException):
            pass

        sleeps = []

        def fake_sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) == 3:
                raise Stop

        def broken_flush():
            raise RuntimeError("boom")

        monkeypatch.setattr(rec, "flush", broken_flush)
        with pytest.raises(Stop):
            rec._flush_forever(sleep=fake_sleep)
        assert len(sleeps) == 3  # two failed flushes did not end the loop


class TestHeartbeat:
    def test_first_access_beats_then_throttles(self, rec, writer, clock):
        session = real_session()
        rec.heartbeat(session)
        rec.heartbeat(session)
        clock.now += analytics.HEARTBEAT_SECONDS - 1
        rec.heartbeat(session)
        clock.now += 1
        rec.heartbeat(session)
        rec.flush()
        assert events(writer) == [Event.HEARTBEAT, Event.HEARTBEAT]


class TestRequestBinding:
    @pytest.fixture
    def bound(self, rec, monkeypatch):
        monkeypatch.setattr(analytics, "recorder", rec)
        return rec

    def test_record_uses_the_session_bound_to_the_request(self, bound, writer):
        app = Flask(__name__)
        with app.test_request_context("/api/combat/move", method="POST"):
            analytics.bind_request_session(real_session())
            analytics.record(Event.COMBAT_START, encounter="Slime")
        written = bound.flush()
        assert written == 2
        assert events(writer) == [Event.HEARTBEAT, Event.COMBAT_START]

    def test_a_get_binds_but_is_not_activity(self, bound, writer):
        # The client polls combat status by GET while a fight is on screen; an
        # idle tab mid-fight must not read as someone playing.
        app = Flask(__name__)
        with app.test_request_context("/api/combat/status", method="GET"):
            analytics.bind_request_session(real_session())
            analytics.record(Event.COMBAT_START, encounter="Slime")
        bound.flush()
        assert events(writer) == [Event.COMBAT_START]

    def test_record_outside_a_request_is_a_no_op(self, bound):
        analytics.record(Event.COMBAT_START)
        assert bound.flush() == 0


class TestProgress:
    @staticmethod
    def markers(map_name="dark-grotto", flags=()):
        return {"map": map_name, "flags": set(flags)}

    def baselined(self, rec, writer, session, **markers):
        rec.reset_progress(session, self.markers(**markers))
        rec.flush()
        writer.batches.clear()

    def test_baseline_records_the_map_but_not_existing_flags(self, rec, writer):
        rec.reset_progress(real_session(), self.markers(flags={"start_flag"}))
        assert flushed(rec, writer) == [(Event.PROGRESS_MAP, {"map": "dark-grotto"})]

    def test_changes_after_the_baseline_are_recorded_once(self, rec, writer):
        session = real_session()
        self.baselined(rec, writer, session, flags={"start_flag"})
        advanced = self.markers(map_name="grondia", flags={"start_flag", "met_gorran"})
        rec.observe_progress(session, advanced)
        rec.observe_progress(session, advanced)  # nothing new the second time
        assert flushed(rec, writer) == [
            (Event.PROGRESS_MAP, {"map": "grondia"}),
            (Event.PROGRESS_FLAG, {"flag": "met_gorran"}),
        ]

    def test_observe_without_a_baseline_takes_one_silently_for_flags(self, rec, writer):
        rec.observe_progress(real_session(), self.markers(flags={"old_flag"}))
        assert flushed(rec, writer) == [(Event.PROGRESS_MAP, {"map": "dark-grotto"})]

    def test_no_markers_takes_no_baseline(self, rec, writer):
        # analytics_markers answers None when it cannot read the player; a
        # baseline of "no flags" would make every existing flag look new.
        session = real_session()
        rec.reset_progress(session, None)
        rec.observe_progress(session, self.markers(flags={"old_flag"}))
        assert Event.PROGRESS_FLAG not in [e for e, _ in flushed(rec, writer)]

    def test_an_older_observation_cannot_undo_a_newer_one(self, rec, writer):
        # Two overlapping requests can observe out of order; the older must not
        # shrink the baseline and make the newer flag look new again.
        session = real_session()
        self.baselined(rec, writer, session)
        rec.observe_progress(session, self.markers(flags={"a", "b"}))
        rec.observe_progress(session, self.markers(flags={"a"}))
        rec.observe_progress(session, self.markers(flags={"a", "b"}))
        assert [p["flag"] for e, p in flushed(rec, writer) if e == Event.PROGRESS_FLAG] == ["a", "b"]

    def test_flag_burst_is_capped(self, rec, writer):
        session = real_session()
        self.baselined(rec, writer, session)
        many = {"f%03d" % i for i in range(analytics.MAX_FLAGS_PER_OBSERVATION + 10)}
        rec.observe_progress(session, self.markers(flags=many))
        assert [e for e, _ in flushed(rec, writer)].count(Event.PROGRESS_FLAG) == (
            analytics.MAX_FLAGS_PER_OBSERVATION
        )


class TestChat:
    def test_turns_and_duration_land_on_the_end_event(self, rec, writer, clock):
        session = real_session()
        rec.chat_opened(session, NPC_KEY)
        clock.now += 10
        rec.chat_turn(session, NPC_KEY, latency_ms=850)
        clock.now += 20
        rec.chat_turn(session, NPC_KEY, latency_ms=900)
        clock.now += 5
        rec.chat_ended(session, NPC_KEY)
        assert flushed(rec, writer) == [
            (Event.CHAT_OPEN, {"npc": "Gorran"}),
            (Event.CHAT_TURN, {"npc": "Gorran", "latency_ms": 850}),
            (Event.CHAT_TURN, {"npc": "Gorran", "latency_ms": 900}),
            (Event.CHAT_END, {"npc": "Gorran", "turns": 2, "duration_s": 35}),
        ]

    def test_end_without_open_records_nothing(self, rec):
        rec.chat_ended(real_session(), NPC_KEY)
        assert rec.flush() == 0

    def test_turn_without_open_records_nothing(self, rec):
        # The key arrives in the request body; only a conversation the server
        # opened may put a name into a row.
        rec.chat_turn(real_session(), "Anything_I_like", latency_ms=1)
        assert rec.flush() == 0

    def test_reopening_the_same_npc_abandons_the_earlier_conversation(self, rec, writer, clock):
        session = real_session()
        rec.chat_opened(session, NPC_KEY)
        clock.now += 15
        rec.chat_opened(session, NPC_KEY)
        assert flushed(rec, writer) == [
            (Event.CHAT_OPEN, {"npc": "Gorran"}),
            (Event.CHAT_END, {"npc": "Gorran", "turns": 0, "duration_s": 15, "abandoned": True}),
            (Event.CHAT_OPEN, {"npc": "Gorran"}),
        ]

    def test_opening_another_chat_abandons_the_first(self, rec, writer, clock):
        session = real_session()
        rec.chat_opened(session, NPC_KEY)
        rec.chat_turn(session, NPC_KEY)
        clock.now += 40
        rec.chat_opened(session, "Mynx_77")
        assert flushed(rec, writer)[2:] == [
            (Event.CHAT_END, {"npc": "Gorran", "turns": 1, "duration_s": 40, "abandoned": True}),
            (Event.CHAT_OPEN, {"npc": "Mynx"}),
        ]


class TestLabels:
    def test_encounter_counts_and_sorts_enemy_names(self):
        class Slime:
            pass

        class CaveBat:
            pass

        assert analytics.encounter_label([Slime(), CaveBat(), Slime()]) == "CaveBat+Slime x2"

    def test_empty_roster(self):
        assert analytics.encounter_label([]) == analytics.NO_ENCOUNTER

    @pytest.mark.parametrize(
        "key, label",
        [
            (NPC_KEY, "Gorran"),
            # Keys are f"{class_name}_{instance_count}": only the last part is the instance.
            ("Old_Hermit_3", "Old_Hermit"),
            ("", analytics.UNKNOWN_LABEL),
            (None, analytics.UNKNOWN_LABEL),
        ],
    )
    def test_npc_label(self, key, label):
        assert analytics.npc_label(key) == label


class TestVocabulary:
    def test_every_event_the_reports_read_is_emitted_somewhere(self):
        # The authority is the emit sites: a report section reading an event
        # nothing records would show zeros forever.
        read = set(re.findall(r"Event\.([A-Z_]+)", inspect.getsource(analytics_report)))
        emitted = set()
        for path in SRC.rglob("*.py"):
            if path.name != "analytics_report.py":
                emitted |= set(re.findall(r"Event\.([A-Z_]+)", path.read_text(encoding="utf-8")))
        assert read and emitted, "the scan matched nothing"
        assert read <= emitted, "read but never recorded: %s" % sorted(read - emitted)


class TestMigration:
    def test_init_db_creates_the_analytics_table(self):
        mock_db = MagicMock()
        mock_db.batch = AsyncMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=None)
        mock_db.close = AsyncMock(return_value=None)
        with patch("src.api.migrations.db", mock_db):
            from src.api.migrations import init_db

            asyncio.run(init_db())
        statements = mock_db.batch.call_args.args[0]
        for stmt in analytics.SCHEMA_STATEMENTS:
            assert stmt in statements
