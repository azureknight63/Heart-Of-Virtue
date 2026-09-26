"""Player analytics reports: the read side of ``analytics.py``.

One report, three readers: ``GET /api/admin/analytics`` (the admin page),
``tools/analytics.py`` (a terminal) and the ``players`` section of the Discord
digest (``ai/provider_digest.py``). All three call :func:`build_report`, so a
number means the same thing wherever it is read. Event names, outcomes and
prop keys come from ``analytics.py`` rather than being spelled again here.

Every query takes an ``execute(sql, params) -> list[tuple]`` coroutine, so the
tests run the real SQL against SQLite and production runs it against Turso.

Not every section follows the ``days`` window. ``SECTION_SCOPES`` says which
do, the report carries it as ``scope``, and every reader labels from it:

* ``window``: daily, combat, sessions, npc_chat cover the last ``days``.
* ``rolling``: players counts over fixed 1/7/30-day windows.
* ``all_time``: retention (a cohort measure needs everyone's first visit) and
  progress (how far anyone has ever got).

Definitions a reader needs:

* **Active** means any analytics event, keyed by pseudonymous player id (pid).
  DAU/WAU/MAU are distinct pids in the last 1/7/30 days.
* **Retention Dn** is the share of players first seen at least n days ago who
  were seen again n or more days after their first visit. It is "came back
  eventually", not "came back on exactly day n", because a beta with a few
  dozen players has too few people for the strict version to be readable.
* **A session** is a run of one login's heartbeats with no gap longer than
  ``SESSION_GAP_SECONDS``. A login lives up to a day, so a player who comes
  back hours later on the same cookie starts a new session. Its length is the
  run's span plus half a heartbeat interval, the expected time played after the
  last beat, so a one-beat session reads as about 2.5 minutes, not zero. A
  session straddling the window's start counts only its in-window beats.
* **Combat** counts starts and ends that fall in the window separately, so a
  fight that began just before it can add an end without a start. "Quit" is
  starts minus ends: fights left by loading a save, starting a new game or
  signing out, which record no end. Averages are over fights that ended, and
  HP left is over wins only; each is null when there is nothing to average.
* **Chat duration** averages conversations the player closed, or the NPC
  ended. An abandoned one (another conversation opened first) is counted but
  kept out of the average: its length is only "until the next open".
* **Stalled** is where the autosaves of players inactive for
  ``STALLED_AFTER_DAYS`` sit. It reads the saves table, so it also covers
  players who stopped before analytics existed.
"""

import logging
import statistics
import time
from datetime import datetime, timezone

from src.api.services.analytics import (
    ALLOWED_PROPS,
    CHAT_EVENTS,
    HEARTBEAT_SECONDS,
    Event,
    Outcome,
    run_with_private_client,
)
from src.text_format import pct

logger = logging.getLogger(__name__)

DAY = 86400
DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 365
ACCOUNT_WINDOWS = (("1d", 1), ("7d", 7), ("30d", 30))
ACTIVE_WINDOWS = (("dau", 1), ("wau", 7), ("mau", 30))
RETENTION_DAYS = (1, 7, 30)
STALLED_AFTER_DAYS = 7
SESSION_GAP_SECONDS = 2 * HEARTBEAT_SECONDS
TOP_N = 25
FLAG_ROWS = 2 * TOP_N

# What a section that could not be computed reads as.
UNAVAILABLE = {"error": "unavailable"}

# Terminal layout for format_text.
TEXT_DAILY_ROWS = 14
TEXT_FLAG_ROWS = 20
ENCOUNTER_COL = 32
MAP_COL = 28
FLAG_COL = 40
ROOM_COL = 36
NPC_COL = 20

WINDOW, ROLLING, ALL_TIME = "window", "rolling", "all_time"


def _prop(key):
    """SQL for one prop of an event row. Only ``ALLOWED_PROPS`` names reach SQL."""
    if key not in ALLOWED_PROPS:
        raise ValueError("not an analytics prop: %r" % key)
    return "json_extract(props, '$.%s')" % key


def _count(condition):
    return "SUM(CASE WHEN %s THEN 1 ELSE 0 END)" % condition


def _round(value, places=0):
    """``value`` rounded; None stays None (nothing to average is not zero)."""
    if value is None:
        return None
    value = round(float(value), places)
    return int(value) if places == 0 else value


def _day(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


# -- sections ---------------------------------------------------------------
# Every builder takes (execute, now, since, days); the ones that are not
# windowed ignore since/days, and SECTION_SCOPES says so.


async def _players(execute, now, since, days):
    account_rows = await execute(
        "SELECT COUNT(*), "
        + ", ".join(_count("created_at >= datetime(?, 'unixepoch')") for _ in ACCOUNT_WINDOWS)
        + " FROM users",
        [now - n * DAY for _, n in ACCOUNT_WINDOWS],
    )
    total, *new_by_window = account_rows[0]
    started = (await execute("SELECT COUNT(DISTINCT user_id) FROM saves"))[0][0]
    widest_since = now - max(n for _, n in ACTIVE_WINDOWS) * DAY
    active_by_window = (await execute(
        "SELECT "
        + ", ".join("COUNT(DISTINCT CASE WHEN ts >= ? THEN pid END)" for _ in ACTIVE_WINDOWS)
        + " FROM analytics_events WHERE ts >= ?",
        [now - n * DAY for _, n in ACTIVE_WINDOWS] + [widest_since],
    ))[0]
    return {
        "total_accounts": total or 0,
        "new_accounts": {label: c or 0 for (label, _), c in zip(ACCOUNT_WINDOWS, new_by_window)},
        "started_playing": started or 0,
        "active": {label: c or 0 for (label, _), c in zip(ACTIVE_WINDOWS, active_by_window)},
    }


DAILY_SERIES = (
    (
        "signups",
        "SELECT CAST(strftime('%s', created_at) AS INTEGER) / ? AS d, COUNT(*) "
        "FROM users WHERE created_at >= datetime(?, 'unixepoch') GROUP BY d",
        (),
    ),
    (
        "active",
        "SELECT ts / ? AS d, COUNT(DISTINCT pid) FROM analytics_events WHERE ts >= ? GROUP BY d",
        (),
    ),
    (
        "chat_turns",
        "SELECT ts / ? AS d, COUNT(*) FROM analytics_events "
        "WHERE ts >= ? AND event = ? GROUP BY d",
        (Event.CHAT_TURN,),
    ),
)


async def _daily(execute, now, since, days):
    first_day = now // DAY - (days - 1)
    counts = {}
    for key, sql, extra in DAILY_SERIES:
        for day, count in await execute(sql, [DAY, first_day * DAY, *extra]):
            counts.setdefault(int(day), {})[key] = count
    return [
        {"day": _day(day * DAY), **{key: counts.get(day, {}).get(key, 0) for key, _, _ in DAILY_SERIES}}
        for day in range(first_day, first_day + days)
    ]


async def _retention(execute, now, since, days):
    columns, params = [], []
    for n in RETENTION_DAYS:
        columns.append(_count("first_ts <= ?"))
        columns.append(_count("first_ts <= ? AND last_ts >= first_ts + ?"))
        params += [now - n * DAY, now - n * DAY, n * DAY]
    row = (await execute(
        "SELECT %s FROM (SELECT MIN(ts) AS first_ts, MAX(ts) AS last_ts "
        "FROM analytics_events GROUP BY pid)" % ", ".join(columns),
        params,
    ))[0]
    return [
        {"day": n, "eligible": row[2 * i] or 0, "returned": row[2 * i + 1] or 0}
        for i, n in enumerate(RETENTION_DAYS)
    ]


async def _top_by_players(execute, prop, event, limit):
    """(value, distinct players) for one prop of one event, most players first."""
    return await execute(
        "SELECT %s AS v, COUNT(DISTINCT pid) AS n FROM analytics_events "
        "WHERE event = ? GROUP BY v ORDER BY n DESC, v LIMIT ?" % _prop(prop),
        [event, limit],
    )


async def _progress(execute, now, since, days):
    maps = await _top_by_players(execute, "map", Event.PROGRESS_MAP, TOP_N)
    flags = await _top_by_players(execute, "flag", Event.PROGRESS_FLAG, FLAG_ROWS)
    levels = await execute(
        "SELECT level, COUNT(*) FROM saves WHERE is_autosave = 1 AND level IS NOT NULL "
        "GROUP BY level ORDER BY level"
    )
    # By tile as well as room name: a name can repeat across a map. Saves from
    # before coordinates were recorded group under x/y None.
    stalled = await execute(
        "SELECT map_name, room_title, location_x, location_y, COUNT(*) AS n FROM saves "
        "WHERE is_autosave = 1 AND timestamp < datetime(?, 'unixepoch') "
        "GROUP BY map_name, room_title, location_x, location_y "
        "ORDER BY n DESC, map_name LIMIT ?",
        [now - STALLED_AFTER_DAYS * DAY, TOP_N],
    )
    return {
        "maps": [{"map": m, "players": n} for m, n in maps],
        "flags": [{"flag": f, "players": n} for f, n in flags],
        "levels": [{"level": lvl, "players": n} for lvl, n in levels],
        "stalled": [{"map": m, "room": r, "x": x, "y": y, "players": n} for m, r, x, y, n in stalled],
        "stalled_after_days": STALLED_AFTER_DAYS,
    }


async def _combat(execute, now, since, days):
    """Per-encounter outcomes. Each SQL fragment is built with its own params."""
    outcome = _prop("outcome")
    columns = [(_count("event = ?"), [Event.COMBAT_START])]
    columns += [(_count("%s = ?" % outcome), [o]) for o in (Outcome.VICTORY, Outcome.DEFEAT, Outcome.FLEE)]
    columns += [
        ("AVG(CASE WHEN event = ? THEN %s END)" % _prop("duration_s"), [Event.COMBAT_END]),
        ("AVG(CASE WHEN event = ? THEN %s END)" % _prop("beats"), [Event.COMBAT_END]),
        ("AVG(CASE WHEN %s = ? THEN %s END)" % (outcome, _prop("hp_pct")), [Outcome.VICTORY]),
    ]
    rows = await execute(
        "SELECT COALESCE(%s, 'unknown') AS enc, %s FROM analytics_events "
        "WHERE event IN (?, ?) AND ts >= ? GROUP BY enc ORDER BY 2 DESC, enc LIMIT ?"
        % (_prop("encounter"), ", ".join(sql for sql, _ in columns)),
        [p for _, ps in columns for p in ps] + [Event.COMBAT_START, Event.COMBAT_END, since, TOP_N],
    )
    return [
        {
            "encounter": enc,
            "starts": starts,
            "victories": won,
            "defeats": lost,
            "flees": fled,
            "abandoned": max(0, starts - won - lost - fled),
            "avg_duration_s": _round(dur),
            "avg_beats": _round(beats, 1),
            "avg_hp_pct_on_win": _round(hp),
        }
        for enc, starts, won, lost, fled, dur, beats, hp in rows
    ]


# One row per session: a heartbeat opens a new session when it is its login's
# first, or follows the previous beat by more than the gap. The running sum of
# those openings numbers the sessions within a login.
_SESSIONS_SQL = """
SELECT pid, MAX(ts) - MIN(ts) FROM (
    SELECT sid, pid, ts, SUM(opens) OVER (PARTITION BY sid ORDER BY ts) AS session_no FROM (
        SELECT sid, pid, ts,
               CASE WHEN ts - LAG(ts) OVER (PARTITION BY sid ORDER BY ts) <= ? THEN 0 ELSE 1 END AS opens
        FROM analytics_events WHERE event = ? AND ts >= ?
    )
) GROUP BY sid, session_no
"""


async def _sessions(execute, now, since, days):
    rows = await execute(_SESSIONS_SQL, [SESSION_GAP_SECONDS, Event.HEARTBEAT, since])
    per_player = {}
    lengths = []
    for pid, span in rows:
        minutes = (span + HEARTBEAT_SECONDS / 2) / 60.0
        lengths.append(minutes)
        per_player[pid] = per_player.get(pid, 0.0) + minutes
    return {
        "count": len(lengths),
        "players": len(per_player),
        "avg_minutes": round(statistics.mean(lengths), 1) if lengths else 0.0,
        "median_minutes": round(statistics.median(lengths), 1) if lengths else 0.0,
        "avg_minutes_per_player": round(statistics.mean(per_player.values()), 1) if per_player else 0.0,
    }


def _chat_columns():
    """Aggregates shared by the per-NPC and total chat queries, with their params.

    Duration averages non-abandoned ends only (see the module docstring).
    """
    columns = (
        "%s, %s, COUNT(DISTINCT pid), "
        "AVG(CASE WHEN event = ? AND COALESCE(%s, 0) = 0 THEN %s END)"
        % (_count("event = ?"), _count("event = ?"), _prop("abandoned"), _prop("duration_s"))
    )
    return columns, [Event.CHAT_OPEN, Event.CHAT_TURN, Event.CHAT_END]


async def _npc_chat(execute, now, since, days):
    columns, column_params = _chat_columns()
    in_chat = "event IN (%s) AND ts >= ?" % ", ".join("?" for _ in CHAT_EVENTS)
    where_params = [*CHAT_EVENTS, since]
    rows = await execute(
        "SELECT %s AS npc, %s FROM analytics_events WHERE %s "
        "GROUP BY npc ORDER BY 2 DESC, npc LIMIT ?" % (_prop("npc"), columns, in_chat),
        column_params + where_params + [TOP_N],
    )
    totals = (await execute(
        "SELECT %s, AVG(CASE WHEN event = ? THEN %s END) FROM analytics_events WHERE %s"
        % (columns, _prop("latency_ms"), in_chat),
        column_params + [Event.CHAT_TURN] + where_params,
    ))[0]
    convs, turns, players, duration, latency = totals
    return {
        "conversations": convs or 0,
        "turns": turns or 0,
        "players": players or 0,
        "avg_duration_s": _round(duration),
        "avg_latency_ms": _round(latency),
        "by_npc": [
            {
                "npc": name,
                "conversations": c,
                "turns": t,
                "players": p,
                "avg_turns": round(t / c, 1) if c else 0.0,
                "avg_duration_s": _round(d),
            }
            for name, c, t, p, d in rows
        ],
    }


# Order is render order everywhere.
SECTION_BUILDERS = (
    ("players", _players, ROLLING),
    ("daily", _daily, WINDOW),
    ("retention", _retention, ALL_TIME),
    ("progress", _progress, ALL_TIME),
    ("combat", _combat, WINDOW),
    ("sessions", _sessions, WINDOW),
    ("npc_chat", _npc_chat, WINDOW),
)
SECTIONS = tuple(key for key, _, _ in SECTION_BUILDERS)
SECTION_SCOPES = {key: scope for key, _, scope in SECTION_BUILDERS}


async def build_report(execute, now=None, days=DEFAULT_WINDOW_DAYS):
    """Every section, each computed independently.

    A section whose query fails reads ``UNAVAILABLE`` rather than failing the
    report: one bad query should not blank the dashboard.
    """
    now = int(now if now is not None else time.time())
    days = max(1, min(int(days), MAX_WINDOW_DAYS))
    since = now - days * DAY
    result = {"generated_at": now, "window_days": days, "scope": dict(SECTION_SCOPES)}
    for key, builder, _ in SECTION_BUILDERS:
        try:
            result[key] = await builder(execute, now, since, days)
        except Exception as exc:
            logger.warning("Analytics section %s failed: %s", key, type(exc).__name__)
            result[key] = dict(UNAVAILABLE)
    return result


# -- database access --------------------------------------------------------


def rows_of(result_set):
    """A libsql ResultSet as a list of plain tuples."""
    width = len(result_set.columns)
    return [tuple(row[i] for i in range(width)) for row in result_set.rows]


def executor_for(client):
    """An ``execute(sql, params) -> list[tuple]`` coroutine over a libsql client.

    Also takes ``src.api.db.db``, which has the same ``execute``.
    """

    async def execute(sql, params=None):
        return rows_of(await client.execute(sql, params or []))

    return execute


def fetch_report(days=DEFAULT_WINDOW_DAYS):
    """Build a report synchronously with a private client (CLI and digest threads)."""
    return run_with_private_client(lambda client: build_report(executor_for(client), days=days))


def run_query(sql, params=None):
    """One query, synchronously, with a private client (for tools)."""
    return run_with_private_client(lambda client: executor_for(client)(sql, params))


# -- formatting -------------------------------------------------------------


def section_unavailable(section):
    """True for a section that failed or is missing from the report."""
    return section is None or (isinstance(section, dict) and "error" in section)


def _share(part, whole):
    return pct(part / whole) if whole else "-"


def _or_dash(value, template="%s"):
    return "-" if value is None else template % value


def room_label(stall):
    """``Cave Entrance (14, 5)``, or just the room for a save without a tile."""
    if stall.get("x") is None or stall.get("y") is None:
        return stall["room"]
    return "%s (%d, %d)" % (stall["room"], stall["x"], stall["y"])


_SCOPE_NOTES = {ROLLING: "rolling windows", ALL_TIME: "all time"}


def _scope_note(report, key):
    scope = SECTION_SCOPES[key]
    if scope == WINDOW:
        return "last %d days" % report.get("window_days", DEFAULT_WINDOW_DAYS)
    return _SCOPE_NOTES[scope]


def _windows(counts, windows):
    """``"1 in 1d, 2 in 7d, ..."`` for counts keyed by ``windows``' labels."""
    return ", ".join("%d in %dd" % (counts[label], days) for label, days in windows)


def _text_players(players):
    return [
        "accounts %d (new: %s); %d have played"
        % (players["total_accounts"], _windows(players["new_accounts"], ACCOUNT_WINDOWS),
           players["started_playing"]),
        "active: " + _windows(players["active"], ACTIVE_WINDOWS),
    ]


def _text_daily(daily):
    lines = ["day         signups active chat-turns"]
    lines += [
        "%s  %7d %6d %10d" % (d["day"], d["signups"], d["active"], d["chat_turns"])
        for d in daily[-TEXT_DAILY_ROWS:]
    ]
    return lines


def _text_retention(retention):
    return [
        "D%-3d %s of %d returned" % (row["day"], _share(row["returned"], row["eligible"]), row["eligible"])
        for row in retention
    ]


def _text_progress(progress):
    lines = ["maps reached (players):"]
    lines += ["  %-*s %d" % (MAP_COL, m["map"], m["players"]) for m in progress["maps"]]
    lines.append("story flags reached (players):")
    lines += ["  %-*s %d" % (FLAG_COL, f["flag"], f["players"]) for f in progress["flags"][:TEXT_FLAG_ROWS]]
    lines.append("current level (players): " + ", ".join(
        "L%s: %d" % (lv["level"], lv["players"]) for lv in progress["levels"]
    ))
    lines.append("autosave untouched %d+ days (where it sits):" % progress["stalled_after_days"])
    lines += [
        "  %-*s %-*s %d" % (MAP_COL, s["map"], ROOM_COL, room_label(s), s["players"])
        for s in progress["stalled"]
    ]
    return lines


def _text_combat(combat):
    row_format = "%-{w}s %6s %5s %5s %5s %5s %6s %7s".format(w=ENCOUNTER_COL)
    lines = [row_format % ("encounter", "fights", "won", "died", "fled", "quit", "avg s", "win hp%")]
    lines += [
        row_format % (
            row["encounter"][:ENCOUNTER_COL], row["starts"], row["victories"], row["defeats"],
            row["flees"], row["abandoned"], _or_dash(row["avg_duration_s"]),
            _or_dash(row["avg_hp_pct_on_win"]),
        )
        for row in combat
    ]
    return lines


def _text_sessions(sessions):
    return [
        "%d sessions by %d players; avg %.1f min, median %.1f min; %.1f min per player"
        % (sessions["count"], sessions["players"], sessions["avg_minutes"],
           sessions["median_minutes"], sessions["avg_minutes_per_player"])
    ]


def _text_npc_chat(chat):
    lines = [
        "%d conversations, %d turns, %d players; avg %s per conversation; avg reply %s"
        % (chat["conversations"], chat["turns"], chat["players"],
           _or_dash(chat["avg_duration_s"], "%ds"), _or_dash(chat["avg_latency_ms"], "%dms"))
    ]
    lines += [
        "  %-*s %4d convs %5d turns %4d players %5.1f turns/conv %6s"
        % (NPC_COL, row["npc"], row["conversations"], row["turns"], row["players"],
           row["avg_turns"], _or_dash(row["avg_duration_s"], "%ds"))
        for row in chat["by_npc"]
    ]
    return lines


TEXT_SECTIONS = {
    "players": ("PLAYERS", _text_players),
    "daily": ("DAILY", _text_daily),
    "retention": ("RETENTION", _text_retention),
    "progress": ("PROGRESS", _text_progress),
    "combat": ("COMBAT", _text_combat),
    "sessions": ("SESSIONS", _text_sessions),
    "npc_chat": ("NPC CHAT", _text_npc_chat),
}


def format_text(report):
    """The whole report as plain text for a terminal, in SECTIONS order."""
    lines = ["Heart of Virtue analytics"]
    for key in SECTIONS:
        title, render = TEXT_SECTIONS[key]
        heading = "%s (%s)" % (title, _scope_note(report, key))
        lines += ["", heading, "-" * len(heading)]
        section = report.get(key)
        if section_unavailable(section):
            lines.append("unavailable")
        elif not section:
            lines.append("no data yet")
        else:
            lines += render(section)
    return "\n".join(lines)


def _digest_players(players, note):
    active = players["active"]
    return (
        "**%d** accounts (+%d in 7d), %d have played\nActive: %d in 24h · %d in 7d · %d in 30d"
        % (players["total_accounts"], players["new_accounts"]["7d"], players["started_playing"],
           active["dau"], active["wau"], active["mau"])
    )


def _digest_retention(retention, note):
    return "Retention (%s): %s" % (note, " · ".join(
        "D%d %s" % (row["day"], _share(row["returned"], row["eligible"])) for row in retention
    ))


def _digest_sessions(sessions, note):
    return "Sessions (%s): %d, median %.0f min" % (note, sessions["count"], sessions["median_minutes"])


def _digest_combat(combat, note):
    if not combat:
        return None
    worst = max(combat, key=lambda row: row["defeats"])
    line = "Combat (%s): %d fights, %d deaths" % (
        note, sum(row["starts"] for row in combat), sum(row["defeats"] for row in combat)
    )
    if worst["defeats"]:
        line += " (most: %s, %d)" % (worst["encounter"], worst["defeats"])
    return line


def _digest_npc_chat(chat, note):
    return "NPC chat (%s): %d conversations, %d turns" % (note, chat["conversations"], chat["turns"])


def _digest_progress(progress, note):
    if not progress["stalled"]:
        return None
    top = progress["stalled"][0]
    return "Most stalled at: %s / %s (%d)" % (top["map"], room_label(top), top["players"])


# Digest lines in the order they read, which is not report order.
DIGEST_SECTIONS = (
    ("players", _digest_players),
    ("retention", _digest_retention),
    ("sessions", _digest_sessions),
    ("combat", _digest_combat),
    ("npc_chat", _digest_npc_chat),
    ("progress", _digest_progress),
)


def format_digest(report, limit):
    """A compact summary for one chat-embed field of at most ``limit`` characters.

    Drops whole trailing lines to fit ``limit`` rather than cutting one in
    half, which would split a ``**bold**`` pair. Only a single line longer
    than ``limit`` on its own is cut.
    """
    parts = []
    for key, render in DIGEST_SECTIONS:
        section = report.get(key)
        if not section_unavailable(section):
            line = render(section, _scope_note(report, key))
            if line:
                parts.append(line)
    while len(parts) > 1 and len("\n".join(parts)) > limit:
        parts.pop()
    return "\n".join(parts)[:limit] or "No player data yet."
