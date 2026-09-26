"""The analytics read side (src/api/services/analytics_report.py).

The queries run for real against an in-memory SQLite database built from the
production DDL (``migrations.USERS_TABLE``/``SAVES_TABLE`` and
``analytics.SCHEMA_STATEMENTS``): libsql speaks SQLite's dialect, so a query
that works here works on Turso, and a mock could not tell a wrong GROUP BY from
a right one.
"""

import asyncio
import json
import re
import sqlite3
from pathlib import Path

import pytest

from src.api.migrations import SAVES_TABLE, USERS_TABLE
from src.api.services import analytics_report as report
from src.api.services.analytics import HEARTBEAT_SECONDS, SCHEMA_STATEMENTS, Event, Outcome

DAY = report.DAY
NOW = 1_800_000_000  # 2027-01-15T08:00:00Z
HALF_BEAT_MIN = HEARTBEAT_SECONDS / 2 / 60


class DB:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        for stmt in (USERS_TABLE, SAVES_TABLE, *SCHEMA_STATEMENTS):
            self.conn.execute(stmt)

    async def execute(self, sql, params=None):
        return self.conn.execute(sql, params or []).fetchall()

    def user(self, uid, created_ts):
        self.conn.execute(
            "INSERT INTO users (id, username, password_hash, email_encrypted, created_at) "
            "VALUES (?, ?, 'hash', 'enc', datetime(?, 'unixepoch'))",
            [uid, uid, created_ts],
        )

    def autosave(self, uid, ts, level, map_name, room):
        self.conn.execute(
            """INSERT INTO saves (id, user_id, name, data, timestamp, is_autosave, level, map_name, room_title)
            VALUES (?, ?, 'Autosave', x'00', datetime(?, 'unixepoch'), 1, ?, ?, ?)""",
            [uid + "-auto", uid, ts, level, map_name, room],
        )

    def event(self, pid, ts, event, sid="s", **props):
        self.conn.execute(
            "INSERT INTO analytics_events (ts, pid, sid, event, props) VALUES (?, ?, ?, ?, ?)",
            [ts, pid, sid, event, json.dumps(props)],
        )

    def beats(self, pid, sid, start, minutes):
        """Heartbeats every HEARTBEAT_SECONDS covering ``minutes`` from ``start``."""
        for offset in range(0, minutes * 60 + 1, HEARTBEAT_SECONDS):
            self.event(pid, start + offset, Event.HEARTBEAT, sid=sid)


@pytest.fixture
def db():
    return DB()


def build(db, days=30):
    return asyncio.run(report.build_report(db.execute, now=NOW, days=days))


class TestPlayers:
    def test_account_counts_by_age(self, db):
        db.user("old", NOW - 40 * DAY)
        db.user("month", NOW - 20 * DAY)
        db.user("week", NOW - 3 * DAY)
        db.user("today", NOW - 3600)
        players = build(db)["players"]
        assert players["total_accounts"] == 4
        assert players["new_accounts"] == {"1d": 1, "7d": 2, "30d": 3}

    def test_started_playing_counts_accounts_with_any_save(self, db):
        db.user("a", NOW - DAY)
        db.user("b", NOW - DAY)
        db.autosave("a", NOW - 100, 1, "dark-grotto", "Cave Entrance")
        assert build(db)["players"]["started_playing"] == 1

    def test_active_players_are_distinct_pids_per_window(self, db):
        db.event("p1", NOW - 60, Event.HEARTBEAT)
        db.event("p1", NOW - 120, Event.HEARTBEAT)
        db.event("p2", NOW - 3 * DAY, Event.HEARTBEAT)
        db.event("p3", NOW - 20 * DAY, Event.HEARTBEAT)
        db.event("p4", NOW - 40 * DAY, Event.HEARTBEAT)
        assert build(db)["players"]["active"] == {"dau": 1, "wau": 2, "mau": 3}


class TestDaily:
    def test_one_row_per_day_oldest_first_with_zero_days_filled(self, db):
        db.user("a", NOW - 2 * DAY)
        db.event("p1", NOW - 2 * DAY, Event.HEARTBEAT)
        db.event("p1", NOW - 60, Event.HEARTBEAT)
        db.event("p2", NOW - 60, Event.CHAT_TURN, npc="Gorran")
        daily = build(db, days=3)["daily"]
        assert [d["day"] for d in daily] == ["2027-01-13", "2027-01-14", "2027-01-15"]
        assert [d["signups"] for d in daily] == [1, 0, 0]
        assert [d["active"] for d in daily] == [1, 0, 2]
        assert [d["chat_turns"] for d in daily] == [0, 0, 1]


class TestRetention:
    def test_returned_means_active_n_days_after_first_seen(self, db):
        # p1 first seen 10 days ago, back 8 days later: counts for D1 and D7.
        db.event("p1", NOW - 10 * DAY, Event.HEARTBEAT)
        db.event("p1", NOW - 2 * DAY, Event.HEARTBEAT)
        # p2 first seen 10 days ago, never back.
        db.event("p2", NOW - 10 * DAY, Event.HEARTBEAT)
        # p3 first seen today: too new for any cohort.
        db.event("p3", NOW - 60, Event.HEARTBEAT)
        # p4 first seen 40 days ago, back 5 days later: D1 only.
        db.event("p4", NOW - 40 * DAY, Event.HEARTBEAT)
        db.event("p4", NOW - 35 * DAY, Event.HEARTBEAT)
        rows = {r["day"]: r for r in build(db)["retention"]}
        assert rows[1] == {"day": 1, "eligible": 3, "returned": 2}
        assert rows[7] == {"day": 7, "eligible": 3, "returned": 1}
        assert rows[30] == {"day": 30, "eligible": 1, "returned": 0}


class TestProgress:
    def test_maps_and_flags_count_distinct_players(self, db):
        for pid in ("p1", "p2"):
            db.event(pid, NOW - 60, Event.PROGRESS_MAP, map="dark-grotto")
        db.event("p1", NOW - 50, Event.PROGRESS_MAP, map="dark-grotto")
        db.event("p1", NOW - 40, Event.PROGRESS_MAP, map="grondia")
        db.event("p1", NOW - 30, Event.PROGRESS_FLAG, flag="met_gorran")
        progress = build(db)["progress"]
        assert progress["maps"] == [
            {"map": "dark-grotto", "players": 2},
            {"map": "grondia", "players": 1},
        ]
        assert progress["flags"] == [{"flag": "met_gorran", "players": 1}]

    def test_stall_threshold_travels_with_the_report(self, db):
        assert build(db)["progress"]["stalled_after_days"] == report.STALLED_AFTER_DAYS

    def test_progress_is_all_time_not_windowed(self, db):
        db.event("p1", NOW - 200 * DAY, Event.PROGRESS_MAP, map="dark-grotto")
        r = build(db, days=7)
        assert r["scope"]["progress"] == report.ALL_TIME
        assert r["progress"]["maps"] == [{"map": "dark-grotto", "players": 1}]

    def test_levels_come_from_autosaves(self, db):
        db.autosave("a", NOW, 1, "dark-grotto", "Cave")
        db.autosave("b", NOW, 3, "grondia", "Gate")
        db.autosave("c", NOW, 3, "grondia", "Gate")
        assert build(db)["progress"]["levels"] == [
            {"level": 1, "players": 1},
            {"level": 3, "players": 2},
        ]

    def test_stalled_lists_where_inactive_autosaves_sit(self, db):
        db.autosave("gone1", NOW - 10 * DAY, 2, "dark-grotto", "Wall Depression")
        db.autosave("gone2", NOW - 9 * DAY, 2, "dark-grotto", "Wall Depression")
        db.autosave("here", NOW - DAY, 4, "grondia", "Gate")
        assert build(db)["progress"]["stalled"] == [
            {"map": "dark-grotto", "room": "Wall Depression", "x": None, "y": None, "players": 2}
        ]


class TestCombat:
    def end(self, db, pid, enc, outcome, duration_s, beats, hp_pct):
        db.event(pid, NOW - 80, Event.COMBAT_END, encounter=enc, outcome=outcome,
                 duration_s=duration_s, beats=beats, hp_pct=hp_pct)

    def test_outcomes_per_encounter(self, db):
        for pid in ("p1", "p2", "p3", "p4"):
            db.event(pid, NOW - 90, Event.COMBAT_START, encounter="Slime")
        self.end(db, "p1", "Slime", Outcome.VICTORY, 40, 6, 80)
        self.end(db, "p2", "Slime", Outcome.VICTORY, 50, 8, 20)
        self.end(db, "p3", "Slime", Outcome.DEFEAT, 20, 4, 0)
        db.event("p5", NOW - 90, Event.COMBAT_START, encounter="KingSlime")
        self.end(db, "p5", "KingSlime", Outcome.FLEE, 5, 1, 60)
        combat = {c["encounter"]: c for c in build(db)["combat"]}
        slime = combat["Slime"]
        assert slime["starts"] == 4
        assert (slime["victories"], slime["defeats"], slime["flees"], slime["abandoned"]) == (2, 1, 0, 1)
        assert slime["avg_duration_s"] == round((40 + 50 + 20) / 3)
        assert slime["avg_beats"] == 6.0
        # HP left is averaged over wins only: a defeat's 0 is not difficulty data.
        assert slime["avg_hp_pct_on_win"] == 50
        # No wins, nothing to average: null, not "won with 0% left".
        assert combat["KingSlime"]["avg_hp_pct_on_win"] is None
        assert combat["KingSlime"]["flees"] == 1
        assert list(combat) == ["Slime", "KingSlime"]  # most-fought first


class TestSessions:
    def test_mean_median_and_per_player_are_distinct_measures(self, db):
        # p1: two separate logins of 10 and 40 minutes. p2: one login, one beat.
        db.beats("p1", "s1", NOW - 5 * 3600, 10)
        db.beats("p1", "s2", NOW - 3 * 3600, 40)
        db.beats("p2", "s3", NOW - 3600, 0)
        s = build(db)["sessions"]
        lengths = sorted([10 + HALF_BEAT_MIN, 40 + HALF_BEAT_MIN, HALF_BEAT_MIN])
        assert (s["count"], s["players"]) == (3, 2)
        assert s["avg_minutes"] == pytest.approx(sum(lengths) / 3, abs=0.1)
        assert s["median_minutes"] == pytest.approx(lengths[1], abs=0.1)
        assert s["avg_minutes_per_player"] == pytest.approx(sum(lengths) / 2, abs=0.1)  # two players
        assert len({s["avg_minutes"], s["median_minutes"], s["avg_minutes_per_player"]}) == 3

    def test_a_long_gap_on_one_login_starts_a_new_session(self, db):
        # One cookie, two sittings four hours apart: two sessions, not one of 4h.
        db.beats("p1", "s1", NOW - 6 * 3600, 20)
        db.beats("p1", "s1", NOW - 2 * 3600, 20)
        s = build(db)["sessions"]
        assert s["count"] == 2
        assert s["median_minutes"] == pytest.approx(20 + HALF_BEAT_MIN, abs=0.1)

    def test_no_sessions(self, db):
        s = build(db)["sessions"]
        assert (s["count"], s["avg_minutes"], s["median_minutes"]) == (0, 0.0, 0.0)


class TestNpcChat:
    def test_frequency_and_duration_per_npc(self, db):
        db.event("p1", NOW - 90, Event.CHAT_OPEN, npc="Gorran")
        db.event("p1", NOW - 80, Event.CHAT_TURN, npc="Gorran", latency_ms=800)
        db.event("p1", NOW - 70, Event.CHAT_TURN, npc="Gorran", latency_ms=1200)
        db.event("p1", NOW - 60, Event.CHAT_END, npc="Gorran", turns=2, duration_s=30)
        db.event("p2", NOW - 90, Event.CHAT_OPEN, npc="Gorran")
        db.event("p2", NOW - 60, Event.CHAT_END, npc="Gorran", turns=0, duration_s=10)
        db.event("p2", NOW - 50, Event.CHAT_OPEN, npc="Mynx")
        chat = build(db)["npc_chat"]
        assert (chat["conversations"], chat["turns"], chat["players"]) == (3, 2, 2)
        assert chat["avg_duration_s"] == 20
        assert chat["avg_latency_ms"] == 1000
        by_npc = {row["npc"]: row for row in chat["by_npc"]}
        assert by_npc["Mynx"]["avg_duration_s"] is None  # opened, never ended
        assert by_npc["Gorran"] == {
            "npc": "Gorran",
            "conversations": 2,
            "turns": 2,
            "players": 2,
            "avg_turns": 1.0,
            "avg_duration_s": 20,
        }
        assert by_npc["Mynx"]["conversations"] == 1


class TestChatAbandoned:
    def test_abandoned_conversations_count_but_stay_out_of_the_average(self, db):
        db.event("p1", NOW - 90, Event.CHAT_OPEN, npc="Gorran")
        db.event("p1", NOW - 60, Event.CHAT_END, npc="Gorran", turns=1, duration_s=30)
        db.event("p1", NOW - 50, Event.CHAT_OPEN, npc="Gorran")
        # Walked away for hours; closed only by the next open.
        db.event("p1", NOW - 10, Event.CHAT_END, npc="Gorran", turns=0, duration_s=9000, abandoned=True)
        chat = build(db)["npc_chat"]
        assert chat["conversations"] == 2
        assert chat["avg_duration_s"] == 30


class TestWindow:
    def test_windowed_sections_ignore_old_events(self, db):
        old = NOW - 40 * DAY
        db.event("p1", old, Event.COMBAT_START, encounter="Slime")
        db.event("p1", old, Event.CHAT_OPEN, npc="Gorran")
        db.beats("p1", "s1", old, 10)
        r = build(db, days=30)
        windowed = [key for key, scope in r["scope"].items() if scope == report.WINDOW]
        assert set(windowed) == {"daily", "combat", "sessions", "npc_chat"}
        assert r["combat"] == []
        assert r["npc_chat"]["conversations"] == 0
        assert r["sessions"]["count"] == 0
        assert all(d["active"] == 0 for d in r["daily"])

    def test_every_section_declares_a_scope(self, db):
        assert set(build(db)["scope"]) == set(report.SECTIONS)

    def test_days_is_clamped(self, db):
        assert build(db, days=0)["window_days"] == 1
        assert build(db, days=10_000)["window_days"] == report.MAX_WINDOW_DAYS


class TestRenderers:
    def test_every_section_has_a_text_renderer(self):
        assert set(report.TEXT_SECTIONS) == set(report.SECTIONS)

    def test_every_allowed_prop_is_a_plain_identifier(self):
        # The report interpolates these names into SQL.
        assert all(re.fullmatch(r"[a-z_]+", key) for key in report.ALLOWED_PROPS)


class TestResilience:
    def test_a_failing_section_is_reported_not_raised(self, db):
        async def broken(sql, params=None):
            if "json_extract(props, '$.npc')" in sql:  # the per-NPC query only
                raise RuntimeError("boom")
            return await db.execute(sql, params)

        r = asyncio.run(report.build_report(broken, now=NOW, days=30))
        assert r["npc_chat"] == report.UNAVAILABLE
        assert [k for k in report.SECTIONS if report.section_unavailable(r[k])] == ["npc_chat"]

    def test_empty_database(self, db):
        r = build(db)
        assert r["players"]["total_accounts"] == 0
        assert r["combat"] == []
        json.dumps(r)  # the route returns it as-is

    def test_only_allowed_props_reach_sql(self):
        with pytest.raises(ValueError):
            report._prop("x'); DROP TABLE users; --")


class TestFormatting:
    @pytest.fixture
    def populated(self, db):
        db.user("a", NOW - DAY)
        db.beats("p1", "s1", NOW - 3600, 10)
        db.event("p1", NOW - 90, Event.COMBAT_START, encounter="KingSlime")
        db.event("p1", NOW - 80, Event.COMBAT_END, encounter="KingSlime", outcome=Outcome.DEFEAT)
        db.autosave("a", NOW - 10 * DAY, 2, "dark-grotto", "Wall Depression")
        return build(db)

    def test_text_report_renders_values_and_scopes(self, populated):
        text = report.format_text(populated)
        assert "accounts 1 (new: 1 in 1d, 1 in 7d, 1 in 30d); 1 have played" in text
        assert "active: 1 in 1d, 1 in 7d, 1 in 30d" in text
        assert "PROGRESS (all time)" in text
        assert "COMBAT (last 30 days)" in text
        assert re.search(r"KingSlime\s+1\s+0\s+1", text)
        assert "1 sessions by 1 players" in text
        assert "dark-grotto" in text and "Wall Depression" in text

    def test_digest_summarises(self, populated):
        text = report.format_digest(populated, 1024)
        assert "**1** accounts" in text
        assert "Combat (last 30 days): 1 fights, 1 deaths (most: KingSlime, 1)" in text
        assert "Retention (all time):" in text
        assert "Most stalled at: dark-grotto / Wall Depression (1)" in text

    def test_digest_drops_whole_lines_to_fit(self, populated):
        full = report.format_digest(populated, 1024)
        lines = full.split("\n")
        limit = len("\n".join(lines[:3]))
        cut = report.format_digest(populated, limit)
        assert cut == "\n".join(lines[:3])

    def test_digest_cuts_a_single_overlong_line(self, populated):
        assert report.format_digest(populated, 10) == report.format_digest(populated, 1024)[:10]

    def test_formatters_survive_failed_or_missing_sections(self, db):
        r = build(db)
        for key in report.SECTIONS:
            r[key] = dict(report.UNAVAILABLE)
        assert report.format_text(r).count("unavailable") == len(report.SECTIONS)
        assert report.format_digest(r, 1024) == "No player data yet."
        assert report.format_text({"window_days": 7}).count("unavailable") == len(report.SECTIONS)


# Every report field frontend/src/pages/AdminAnalyticsPage.jsx reads, by path.
# Checked two ways: the real report must emit each path
# (test_every_listed_field_is_emitted), and the page must still read each field
# name in an access form -- `.field`, `['field']`, a Table column `key: 'field'`,
# a DailyBars `field="field"`, or for `scope` a `<Section id="field">`
# (test_every_listed_read_is_still_in_the_page). That second check is by name,
# not path: a name several sections read ("players") passes while any of them
# still reads it. A bare substring would match "day" inside "daily" and could
# never fail at all.
ADMIN_PAGE_READS = {
    "scope": ["players", "daily", "retention", "progress", "combat", "sessions", "npc_chat"],
    "players": ["total_accounts", "started_playing", "new_accounts.7d", "active.dau", "active.wau", "active.mau"],
    "daily[]": ["day", "signups", "active", "chat_turns"],
    "retention[]": ["day", "returned", "eligible"],
    "progress": ["maps", "flags", "levels", "stalled", "stalled_after_days"],
    "progress.maps[]": ["map", "players"],
    "progress.flags[]": ["flag", "players"],
    "progress.levels[]": ["level", "players"],
    "progress.stalled[]": ["map", "room", "x", "y", "players"],
    "combat[]": ["encounter", "starts", "victories", "defeats", "flees", "abandoned",
                 "avg_beats", "avg_duration_s", "avg_hp_pct_on_win"],
    "sessions": ["count", "players", "median_minutes", "avg_minutes", "avg_minutes_per_player"],
    "npc_chat": ["conversations", "turns", "players", "avg_duration_s", "avg_latency_ms", "by_npc"],
    "npc_chat.by_npc[]": ["npc", "conversations", "turns", "avg_turns", "players", "avg_duration_s"],
}

PAGE = Path(__file__).resolve().parent.parent / "frontend" / "src" / "pages" / "AdminAnalyticsPage.jsx"


def _resolve(obj, path):
    for part in path.split("."):
        obj = obj[part]
    return obj


def _read_forms(leaf):
    return re.compile(
        r"\.{0}\b|\['{0}'\]|key: '{0}'|field=\"{0}\"|\bid=\"{0}\"".format(re.escape(leaf))
    )


class TestAdminPageContract:
    def test_every_listed_field_is_emitted(self, db):
        db.user("a", NOW - DAY)
        db.autosave("a", NOW - 10 * DAY, 2, "dark-grotto", "Wall Depression")
        db.beats("p1", "s1", NOW - 3 * DAY, 5)
        db.event("p1", NOW - 60, Event.PROGRESS_MAP, map="dark-grotto")
        db.event("p1", NOW - 60, Event.PROGRESS_FLAG, flag="met_gorran")
        db.event("p1", NOW - 60, Event.COMBAT_START, encounter="Slime")
        db.event("p1", NOW - 50, Event.COMBAT_END, encounter="Slime", outcome=Outcome.VICTORY)
        db.event("p1", NOW - 60, Event.CHAT_OPEN, npc="Gorran")
        r = build(db)
        for container, fields in ADMIN_PAGE_READS.items():
            node = _resolve(r, container.removesuffix("[]"))
            if container.endswith("[]"):
                assert node, "fixture left %s empty, so its fields went unchecked" % container
                node = node[0]
            for field_path in fields:
                _resolve(node, field_path)  # KeyError names the drifted field

    def test_every_listed_read_is_still_in_the_page(self):
        page = PAGE.read_text(encoding="utf-8")
        missing = sorted(
            "%s.%s" % (container, field_path)
            for container, fields in ADMIN_PAGE_READS.items()
            for field_path in fields
            if not _read_forms(field_path.split(".")[-1]).search(page)
        )
        assert missing == [], "listed but no longer read by the page: %s" % missing

    def test_the_read_check_can_fail(self):
        # Non-vacuity: a name the page does not read must not match.
        assert not _read_forms("no_such_field").search(PAGE.read_text(encoding="utf-8"))
        assert not _read_forms("day").search("const daily = report.dailyish")
