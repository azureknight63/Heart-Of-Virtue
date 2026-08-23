"""Tests for tools/logcat.py — the condensed TUI-style debug log viewer.

logcat merges the backend (logs/backend/*.jsonl) and browser
(logs/browser/*.jsonl, plus legacy *.log) streams into one chronological,
collapsed, colorized feed. The rendering core is pure functions so the
formatting behavior stays testable without a terminal.
"""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def logcat():
    path = _ROOT / "tools" / "logcat.py"
    spec = importlib.util.spec_from_file_location("_logcat", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestParsing:
    def test_parse_jsonl_line(self, logcat):
        line = (
            '{"ts":"2026-08-22T16:13:23.901Z","src":"fe","lvl":"debug",'
            '"event":"event.enqueue","session":"s1","data":{"name":"X"}}'
        )
        env = logcat.parse_jsonl_line(line)
        assert env["event"] == "event.enqueue"
        assert env["src"] == "fe"

    def test_parse_jsonl_line_garbage_returns_none(self, logcat):
        assert logcat.parse_jsonl_line("not json at all") is None
        assert logcat.parse_jsonl_line('"a bare string"') is None
        assert logcat.parse_jsonl_line("") is None

    def test_parse_legacy_browser_line(self, logcat):
        line = (
            "[2026-08-22T16:12:36.309Z] [ERROR] [session_178_692d4kc87] "
            "[http://localhost:3000/game] Error fetching explored tiles: {}"
        )
        env = logcat.parse_legacy_browser_line(line)
        assert env["ts"] == "2026-08-22T16:12:36.309Z"
        assert env["src"] == "fe"
        assert env["lvl"] == "error"
        assert env["event"] == "console"
        assert env["session"] == "session_178_692d4kc87"
        assert env["msg"].startswith("Error fetching")

    def test_parse_legacy_browser_line_garbage_returns_none(self, logcat):
        assert logcat.parse_legacy_browser_line("random text") is None

    def test_parse_legacy_line_with_bracket_in_url(self, logcat):
        # IPv6 loopback URLs contain a literal "]" — the line must still parse
        line = (
            "[2026-08-22T10:00:00.000Z] [ERROR] [sess123] "
            "[http://[::1]:5000/] some message"
        )
        env = logcat.parse_legacy_browser_line(line)
        assert env is not None
        assert env["url"] == "http://[::1]:5000/"
        assert env["msg"] == "some message"

    def test_entry_ts(self, logcat):
        entry = {"ts": "2026-08-22T16:13:23.901Z"}
        ts = logcat.entry_ts(entry)
        assert ts == datetime(2026, 8, 22, 16, 13, 23, 901000, tzinfo=timezone.utc)
        assert logcat.entry_ts({"ts": "garbage"}) is None
        assert logcat.entry_ts({}) is None


class TestSince:
    def test_parse_since_units(self, logcat):
        assert logcat.parse_since("30s") == 30
        assert logcat.parse_since("5m") == 300
        assert logcat.parse_since("2h") == 7200
        assert logcat.parse_since("1d") == 86400

    def test_parse_since_bare_number_is_seconds(self, logcat):
        assert logcat.parse_since("90") == 90

    def test_parse_since_invalid_raises(self, logcat):
        with pytest.raises(ValueError):
            logcat.parse_since("soon")


class TestCollapse:
    def test_consecutive_identical_entries_collapse(self, logcat):
        entry = {
            "ts": "2026-08-22T16:12:36.246Z",
            "src": "fe",
            "lvl": "debug",
            "event": "event.queue",
            "msg": "event.queue idle",
        }
        entries = [dict(entry) for _ in range(4)]
        collapsed = logcat.collapse(entries)
        assert len(collapsed) == 1
        assert collapsed[0]["n"] == 4

    def test_collapse_sums_existing_repeat_counts(self, logcat):
        a = {"ts": "t1", "src": "fe", "lvl": "debug", "event": "e", "n": 3}
        b = {"ts": "t2", "src": "fe", "lvl": "debug", "event": "e"}
        collapsed = logcat.collapse([a, b])
        assert len(collapsed) == 1
        assert collapsed[0]["n"] == 4

    def test_same_event_different_data_does_not_collapse(self, logcat):
        # Structured events (http.request) carry all meaning in data with no
        # msg — two different requests must never merge into one ×2 line.
        a = {
            "src": "be",
            "lvl": "info",
            "event": "http.request",
            "data": {"path": "/api/combat/status", "status": 200},
        }
        b = {
            "src": "be",
            "lvl": "info",
            "event": "http.request",
            "data": {"path": "/api/player/state", "status": 200},
        }
        collapsed = logcat.collapse([a, b])
        assert len(collapsed) == 2

    def test_different_events_do_not_collapse(self, logcat):
        a = {"ts": "t1", "src": "fe", "lvl": "debug", "event": "e1"}
        b = {"ts": "t2", "src": "fe", "lvl": "debug", "event": "e2"}
        assert len(logcat.collapse([a, b])) == 2

    def test_interleaved_entries_do_not_collapse(self, logcat):
        a = {"ts": "t1", "src": "fe", "lvl": "debug", "event": "e"}
        other = {"ts": "t2", "src": "be", "lvl": "info", "event": "x"}
        c = {"ts": "t3", "src": "fe", "lvl": "debug", "event": "e"}
        assert len(logcat.collapse([a, other, c])) == 3


class TestFiltering:
    ENTRY = {
        "ts": "2026-08-22T16:13:23.901Z",
        "src": "fe",
        "lvl": "warning",
        "event": "audio.blocked",
        "session": "sess_abc123",
        "msg": "awaiting user interaction",
    }

    def test_level_threshold(self, logcat):
        assert logcat.matches(self.ENTRY, level="warning")
        assert logcat.matches(self.ENTRY, level="debug")
        assert not logcat.matches(self.ENTRY, level="error")

    def test_grep_searches_event_msg_and_data(self, logcat):
        assert logcat.matches(self.ENTRY, grep="audio")
        assert logcat.matches(self.ENTRY, grep="interaction")
        assert not logcat.matches(self.ENTRY, grep="combat")
        with_data = dict(self.ENTRY, data={"name": "KingSlime"})
        assert logcat.matches(with_data, grep="KingSlime")

    def test_session_prefix_and_src(self, logcat):
        assert logcat.matches(self.ENTRY, session="sess_abc")
        assert not logcat.matches(self.ENTRY, session="other")
        assert logcat.matches(self.ENTRY, src="fe")
        assert not logcat.matches(self.ENTRY, src="be")


class TestFormatting:
    def test_format_entry_is_condensed(self, logcat):
        entry = {
            "ts": "2026-08-22T16:13:23.901Z",
            "src": "fe",
            "lvl": "debug",
            "event": "event.enqueue",
            "session": "session_178_692d4kc87",
            "data": {"name": "Passage_Camp Entrance", "needsInput": True},
            "n": 3,
        }
        line = logcat.format_entry(entry, color=False)
        assert "event.enqueue" in line
        assert "16:13:23" in line
        assert "fe" in line
        assert "name=Passage_Camp Entrance" in line
        assert "x3" in line or "×3" in line
        # Condensed: no JSON braces, no full session id, single line
        assert "session_178_692d4kc87" not in line
        assert "\n" not in line

    def test_format_entry_truncates_long_values(self, logcat):
        entry = {
            "ts": "2026-08-22T16:13:23.901Z",
            "src": "be",
            "lvl": "info",
            "event": "log",
            "msg": "z" * 1000,
        }
        line = logcat.format_entry(entry, color=False)
        assert len(line) < 400

    def test_format_entry_survives_missing_fields(self, logcat):
        line = logcat.format_entry({}, color=False)
        assert isinstance(line, str)

    def test_short_session_stable_suffix(self, logcat):
        assert logcat.short_session("session_178_692d4kc87") == "4kc87"
        assert logcat.short_session("") == ""


class TestFileGathering:
    def test_iter_entries_reads_jsonl_and_legacy(self, logcat, tmp_path):
        jsonl = tmp_path / "2026-08-22.jsonl"
        jsonl.write_text(
            '{"ts":"2026-08-22T10:00:00Z","src":"be","lvl":"info","event":"log","msg":"a"}\n'
            "garbage line that must not crash\n",
            encoding="utf-8",
        )
        legacy = tmp_path / "2026-08-22_bucket14.log"
        legacy.write_text(
            "[2026-08-22T09:00:00.000Z] [LOG] [s1] [http://x/] old style\n",
            encoding="utf-8",
        )
        entries = list(logcat.iter_entries([jsonl, legacy]))
        assert len(entries) == 2
        events = {e["event"] for e in entries}
        assert events == {"log", "console"}

    def test_merge_sorts_by_timestamp(self, logcat):
        a = {"ts": "2026-08-22T10:00:02Z", "src": "be", "lvl": "info", "event": "log"}
        b = {
            "ts": "2026-08-22T10:00:01Z",
            "src": "fe",
            "lvl": "info",
            "event": "console",
        }
        merged = logcat.merge_entries([[a], [b]])
        assert [e["ts"] for e in merged] == [
            "2026-08-22T10:00:01Z",
            "2026-08-22T10:00:02Z",
        ]
