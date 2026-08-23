"""logcat — condensed TUI-style viewer for the unified JSONL debug stream.

Merges the backend (logs/backend/*.jsonl) and browser (logs/browser/*.jsonl,
plus legacy *.log) streams into one chronological, collapsed, colorized feed
rendered with the game's retro palette. Agents get the same stream raw via
--json; humans get one glanceable line per event.

Usage:
    python tools/logcat.py                     # last 15m, condensed
    python tools/logcat.py --tail              # follow live
    python tools/logcat.py --errors            # errors only
    python tools/logcat.py --grep combat       # regex over event/msg/data
    python tools/logcat.py --since 2h --json   # raw JSONL for agents/tools
    python tools/logcat.py --session 4kc87     # one browser session

Envelope schema: see src/api/structured_log.py. No dependencies beyond
neotermcolor (already required by the engine); rendering degrades to plain
ASCII on consoles that can't encode the glyphs.
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from neotermcolor import colored
except ImportError:  # pragma: no cover - viewer still works uncolored

    def colored(text, *args, **kwargs):
        return text


ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "logs" / "backend"
BROWSER_DIR = ROOT / "logs" / "browser"

LEVEL_ORDER = {"debug": 0, "info": 1, "warning": 2, "error": 3}
_LEVEL_MAP = {"log": "info", "warn": "warning"}

GLYPHS_UNICODE = {"error": "✖", "warning": "⚠", "info": "•", "debug": "·"}
GLYPHS_ASCII = {"error": "E", "warning": "W", "info": "*", "debug": "."}
REPEAT_UNICODE = "×"
REPEAT_ASCII = "x"

LEVEL_COLORS = {"error": "red", "warning": "yellow", "info": "cyan", "debug": None}
SRC_COLORS = {"be": "green", "fe": "cyan"}
SESSION_PALETTE = ["green", "cyan", "yellow", "magenta", "blue"]

# Non-greedy fields: the URL can contain a literal "]" (e.g. an IPv6 host
# like http://[::1]:5000/), which a [^\]]* character class would fail on,
# silently dropping the whole line.
_LEGACY_RE = re.compile(r"^\[(.*?)\] \[(.*?)\] \[(.*?)\] \[(.*?)\] (.*)$")
_SINCE_RE = re.compile(r"^(\d+)([smhd]?)$")
_SINCE_MULT = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}

MSG_CAP = 300
VALUE_CAP = 80


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def parse_jsonl_line(line):
    """One JSONL envelope line -> dict, or None for garbage."""
    line = line.strip()
    if not line:
        return None
    try:
        env = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    return env if isinstance(env, dict) else None


def parse_legacy_browser_line(line):
    """Pre-migration bracket format -> envelope dict, or None.

    Format: [TIMESTAMP] [LEVEL] [SESSION] [URL] MESSAGE
    """
    match = _LEGACY_RE.match(line.strip())
    if not match:
        return None
    ts, level, session, url, msg = match.groups()
    return {
        "ts": ts,
        "src": "fe",
        "lvl": (
            _LEVEL_MAP.get(level.lower(), level.lower())
            if level.lower() in LEVEL_ORDER or level.lower() in _LEVEL_MAP
            else "info"
        ),
        "event": "console",
        "session": session,
        "url": url,
        "msg": msg,
    }


def entry_ts(entry):
    """Envelope -> aware UTC datetime, or None when absent/unparseable."""
    ts = entry.get("ts")
    if not isinstance(ts, str):
        return None
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_since(text):
    """'30s' / '5m' / '2h' / '1d' / bare seconds -> seconds (int)."""
    match = _SINCE_RE.match(text.strip())
    if not match:
        raise ValueError(f"invalid --since value: {text!r} (try 30s, 5m, 2h, 1d)")
    return int(match.group(1)) * _SINCE_MULT[match.group(2)]


# --------------------------------------------------------------------------
# Stream assembly
# --------------------------------------------------------------------------


def parser_for(path):
    """The line parser for one log file, chosen by extension."""
    return parse_jsonl_line if path.suffix == ".jsonl" else parse_legacy_browser_line


def iter_entries(paths):
    """Yield envelopes from a mix of .jsonl and legacy .log files."""
    for path in paths:
        parse = parser_for(path)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    env = parse(line)
                    if env is not None:
                        yield env
        except OSError:
            continue


def merge_entries(iterables):
    """Flatten and sort chronologically; undated entries sort first."""
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    merged = [entry for entries in iterables for entry in entries]
    merged.sort(key=lambda e: entry_ts(e) or epoch)
    return merged


def _collapse_signature(entry):
    """Identity for collapsing. Includes the data payload: structured events
    (e.g. http.request) carry all their meaning in `data` with no `msg`, so
    ignoring it would merge genuinely different events under one ×N line."""
    data = entry.get("data")
    return (
        entry.get("src"),
        entry.get("lvl"),
        entry.get("event"),
        entry.get("msg"),
        entry.get("session"),
        json.dumps(data, sort_keys=True, default=str) if data else None,
    )


def collapse(entries):
    """Collapse consecutive identical entries into one with a summed n.

    The client-side collapse (logger.js) already sums immediate repeats;
    this catches repeats that span flush batches or come from the backend.
    """
    collapsed = []
    prev_sig = None
    for entry in entries:
        signature = _collapse_signature(entry)
        if collapsed and signature == prev_sig:
            collapsed[-1]["n"] = collapsed[-1].get("n", 1) + entry.get("n", 1)
        else:
            collapsed.append(dict(entry))
            prev_sig = signature
    return collapsed


def matches(entry, level=None, grep=None, session=None, src=None):
    """Filter predicate over one envelope."""
    if level is not None:
        threshold = LEVEL_ORDER.get(level, 0)
        if LEVEL_ORDER.get(entry.get("lvl"), 1) < threshold:
            return False
    if src is not None and entry.get("src") != src:
        return False
    if session is not None:
        if not str(entry.get("session", "")).startswith(session):
            return False
    if grep is not None:
        haystack = " ".join(
            str(part)
            for part in (
                entry.get("event", ""),
                entry.get("msg", ""),
                json.dumps(entry.get("data", {}), default=str),
                entry.get("session", ""),
            )
        )
        if not re.search(grep, haystack, re.IGNORECASE):
            return False
    return True


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def _stdout_supports_unicode():
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        "×✖⚠•·".encode(encoding)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def short_session(session):
    """Last five characters — enough to tell sessions apart at a glance."""
    return str(session or "")[-5:]


def _session_color(session):
    return SESSION_PALETTE[hash(session) % len(SESSION_PALETTE)]


def _truncate(text, cap):
    text = str(text)
    return text if len(text) <= cap else text[: cap - 1] + "~"


def format_entry(entry, color=True, unicode_ok=None):
    """One envelope -> one condensed line."""
    if unicode_ok is None:
        unicode_ok = _stdout_supports_unicode()
    glyphs = GLYPHS_UNICODE if unicode_ok else GLYPHS_ASCII
    repeat_mark = REPEAT_UNICODE if unicode_ok else REPEAT_ASCII

    ts = entry_ts(entry)
    clock = f"{ts:%H:%M:%S}.{ts.microsecond // 10000:02d}" if ts else "--:--:--.--"
    src = str(entry.get("src", "??"))[:2]
    lvl = entry.get("lvl", "info")
    glyph = glyphs.get(lvl, glyphs["info"])
    event = str(entry.get("event") or "?")

    parts = []
    msg = entry.get("msg")
    if msg:
        parts.append(_truncate(msg, MSG_CAP))
    data = entry.get("data")
    if isinstance(data, dict):
        parts.extend(
            f"{key}={_truncate(value, VALUE_CAP)}" for key, value in data.items()
        )
    details = " ".join(parts)

    suffix = ""
    n = entry.get("n", 1)
    if isinstance(n, int) and n > 1:
        suffix = f" {repeat_mark}{n}"
    session = entry.get("session")
    session_tag = f" #{short_session(session)}" if session else ""

    if color:
        level_color = LEVEL_COLORS.get(lvl)
        glyph = colored(glyph, level_color) if level_color else glyph
        event = (
            colored(event, level_color)
            if lvl in ("error", "warning")
            else colored(event, attrs=["bold"])
        )
        src = colored(src, SRC_COLORS.get(src))
        clock = colored(clock, attrs=["dark"])
        if suffix:
            suffix = colored(suffix, "yellow")
        if session_tag:
            session_tag = colored(session_tag, _session_color(session))

    return f"{clock} {src} {glyph} {event:<20} {details}{suffix}{session_tag}".rstrip()


# --------------------------------------------------------------------------
# File gathering / CLI
# --------------------------------------------------------------------------


def gather_files(backend_dir, browser_dir, cutoff_epoch):
    """Log files plausibly containing entries newer than the cutoff."""
    candidates = []
    for directory, patterns in (
        (backend_dir, ("*.jsonl",)),
        (browser_dir, ("*.jsonl", "*.log")),
    ):
        directory = Path(directory)
        if not directory.is_dir():
            continue
        for pattern in patterns:
            for path in directory.glob(pattern):
                try:
                    if path.stat().st_mtime >= cutoff_epoch:
                        candidates.append(path)
                except OSError:
                    continue
    return sorted(candidates)


def _build_filter(args):
    level = "error" if args.errors else args.level
    return {
        "level": level,
        "grep": args.grep,
        "session": args.session,
        "src": args.src,
    }


def _emit(entry, args, unicode_ok):
    if args.json:
        print(json.dumps(entry, ensure_ascii=False, separators=(",", ":")))
    else:
        print(format_entry(entry, color=not args.no_color, unicode_ok=unicode_ok))


def run_view(args):
    since_s = parse_since(args.since)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=since_s)
    files = gather_files(args.backend_dir, args.browser_dir, cutoff.timestamp() - 86400)
    filters = _build_filter(args)
    entries = [
        e
        for e in merge_entries([iter_entries(files)])
        if ((entry_ts(e) or cutoff) >= cutoff) and matches(e, **filters)
    ]
    entries = collapse(entries)
    limit = args.limit
    if limit and len(entries) > limit:
        entries = entries[-limit:]
    unicode_ok = _stdout_supports_unicode()
    for entry in entries:
        _emit(entry, args, unicode_ok)
    if not entries and not args.json:
        print(f"(no entries in the last {args.since} — is anything running?)")
    return entries


def run_tail(args):
    run_view(args)
    filters = _build_filter(args)
    unicode_ok = _stdout_supports_unicode()
    offsets = {}
    known = set()

    def rescan():
        now = time.time()
        for path in gather_files(args.backend_dir, args.browser_dir, now - 86400):
            if path not in known:
                known.add(path)
                try:
                    offsets[path] = path.stat().st_size
                except OSError:
                    offsets[path] = 0

    rescan()
    ticks = 0
    try:
        while True:
            time.sleep(0.5)
            ticks += 1
            if ticks % 4 == 0:
                rescan()
            fresh = []
            for path in list(known):
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                if size <= offsets.get(path, 0):
                    continue
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(offsets.get(path, 0))
                    chunk = f.read()
                    offsets[path] = f.tell()
                parse = parser_for(path)
                for line in chunk.splitlines():
                    env = parse(line)
                    if env is not None and matches(env, **filters):
                        fresh.append(env)
            for entry in merge_entries([fresh]):
                _emit(entry, args, unicode_ok)
    except KeyboardInterrupt:
        return


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Condensed viewer for the unified JSONL debug log stream"
    )
    parser.add_argument("--tail", "-f", action="store_true", help="follow live")
    parser.add_argument("--since", default="15m", help="window: 30s 5m 2h 1d")
    parser.add_argument("--grep", help="regex over event/msg/data/session")
    parser.add_argument("--level", choices=sorted(LEVEL_ORDER), help="minimum level")
    parser.add_argument(
        "--errors", action="store_true", help="shorthand for --level error"
    )
    parser.add_argument("--session", help="session id prefix or suffix tag")
    parser.add_argument("--src", choices=["be", "fe"], help="one side only")
    parser.add_argument(
        "--json", action="store_true", help="raw JSONL out (for agents/tools)"
    )
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--limit", type=int, default=200, help="max lines")
    parser.add_argument("--backend-dir", default=str(BACKEND_DIR))
    parser.add_argument("--browser-dir", default=str(BROWSER_DIR))
    args = parser.parse_args(argv)

    try:
        if args.tail:
            run_tail(args)
        else:
            run_view(args)
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
