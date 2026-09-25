"""check_contamination.py -- the "within five minutes of dispatch" check.

    python check_contamination.py [DIR ...] [--since MINUTES]

Why this exists: `references/tester-roles.md` and `references/gotchas.md` both
say to grep every tester's `<name>_events.jsonl` for `"status": 400` and
`socket.io` within the first five minutes of a dispatch, and to watch each
stack's `api.log` for tracebacks -- by hand, with ad hoc grep, every run. This
turns that hand grep into one command with a clear PASS/WARN/FAIL verdict, in
the style of `scripts/preflight.py`.

It scans, under one or more root directories (default: `logs/qa` under the
worktree root, resolved like the other scripts via `HOV_QA_ROOT` or four
parents up from this file):

- every `*_events.jsonl` browser-tester log (`scripts/qa_driver.py`'s output)
  for HTTP 400s, socket.io-origin failures specifically (a 400 on a
  `/socket.io/` request, or the text "not an accepted origin"), and
  console.error lines;
- every `api.log` under a stack directory (`scripts/start_stack.py`'s output)
  for Python tracebacks (deduplicated), ERROR-level log lines, and the
  engineio "not an accepted origin" line that means the Vite port is not an
  accepted Socket.IO origin (`references/gotchas.md`, "Vite port must be an
  accepted Socket.IO origin").

Exit status is non-zero if any stack shows a socket.io origin fault (from
either its api.log or a tester's events file) or a Python traceback -- per
the skill, that means stop and fix the stack before more testers run.

Assumption (documented per the skill's format-guess rule): a distinct
traceback is identified by its exception summary line (the last, unindented
line of the block, e.g. "ValueError: ..."), not the literal first line
("Traceback (most recent call last):"), which is identical for every
traceback and so cannot distinguish them. The "first line" printed for each
distinct traceback is that summary line.

`--since MINUTES` limits both source lines to recent entries. Browser events
carry only a bare `HH:MM:SS` (no date), so recency is judged against today's
date -- fixture/archived logs from other days will not be filtered
correctly; this is a best-effort convenience, not a guarantee, and is noted
here since the format doesn't allow better. `api.log` lines carry a full
timestamp and are filtered exactly.
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(os.environ.get("HOV_QA_ROOT") or Path(__file__).resolve().parents[4])
DEFAULT_DIR = ROOT / "logs" / "qa"

ORIGIN_FAULT_TEXT = "not an accepted origin"
LOG_LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ (\S+) (\S+) (.*)$")
TRACEBACK_START = "Traceback (most recent call last):"


def line(status, msg):
    print(f"{status:4} {msg}")
    return status == "FAIL"


def find_events_files(dirs):
    out = []
    for d in dirs:
        out.extend(sorted(Path(d).rglob("*_events.jsonl")))
    return out


def find_stack_logs(dirs):
    out = []
    for d in dirs:
        out.extend(sorted(Path(d).rglob("api.log")))
    return out


def _within_since_bare_time(ts, since_minutes):
    """Best-effort recency check for a bare HH:MM:SS timestamp (see module docstring)."""
    if since_minutes is None:
        return True
    try:
        t = datetime.strptime(ts, "%H:%M:%S")
    except ValueError:
        return True
    now = datetime.now()
    candidate = now.replace(hour=t.hour, minute=t.minute, second=t.second, microsecond=0)
    return now - candidate <= timedelta(minutes=since_minutes)


def _within_since_full_time(ts, since_minutes):
    if since_minutes is None:
        return True
    try:
        t = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return True
    return datetime.now() - t <= timedelta(minutes=since_minutes)


def analyze_events_file(path, since_minutes=None):
    """Return HTTP-400, socket.io-fault, and console.error counts for one tester log."""
    http_400 = 0
    socketio_fault = 0
    console_errors = 0
    total = 0
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not _within_since_bare_time(ev.get("ts", ""), since_minutes):
            continue
        total += 1
        kind = ev.get("kind", "")
        status = ev.get("status")
        url = ev.get("url", "") or ""
        text = ev.get("text", "") or ""
        if kind == "http" and status == 400:
            http_400 += 1
            if "/socket.io/" in url or ORIGIN_FAULT_TEXT in text:
                socketio_fault += 1
        if ORIGIN_FAULT_TEXT in text:
            socketio_fault += 1
        if kind == "console.error":
            console_errors += 1
    return {"total": total, "http_400": http_400, "socketio_fault": socketio_fault,
            "console_errors": console_errors}


def _iter_log_lines_with_timestamp(path):
    """Yield (timestamp_or_None, raw_line) for every line, carrying forward the last
    full timestamp seen so lines without their own timestamp (traceback frames,
    engineio's raw print lines) can still be filtered by --since."""
    last_ts = None
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        m = LOG_LINE_RE.match(raw)
        if m:
            last_ts = m.group(1)
        yield last_ts, raw


def analyze_stack_log(path, since_minutes=None):
    """Return traceback, ERROR-line, and origin-fault counts for one stack's api.log."""
    lines = list(_iter_log_lines_with_timestamp(path))
    error_lines = 0
    origin_fault = 0
    traceback_groups = {}
    i = 0
    n = len(lines)
    while i < n:
        ts, raw = lines[i]
        in_window = _within_since_full_time(ts, since_minutes) if ts else True
        if in_window:
            if " ERROR " in raw:
                error_lines += 1
            if ORIGIN_FAULT_TEXT in raw:
                origin_fault += 1
        if raw.strip() == TRACEBACK_START:
            j = i + 1
            summary = None
            while j < n:
                _, frame = lines[j]
                if frame.startswith((" ", "\t")) or not frame.strip():
                    j += 1
                    continue
                summary = frame.strip()
                j += 1
                break
            if in_window:
                key = summary or "(unterminated traceback)"
                traceback_groups[key] = traceback_groups.get(key, 0) + 1
            i = j
            continue
        i += 1
    return {"error_lines": error_lines, "origin_fault": origin_fault,
            "traceback_groups": traceback_groups,
            "traceback_total": sum(traceback_groups.values())}


def report(dirs, since_minutes=None):
    failed = False
    events_files = find_events_files(dirs)
    stack_logs = find_stack_logs(dirs)

    if not events_files and not stack_logs:
        failed |= line("WARN", f"nothing found under {', '.join(str(d) for d in dirs)}")

    print("== testers (browser events) ==")
    for f in events_files:
        stats = analyze_events_file(f, since_minutes)
        name = f.stem.replace("_events", "")
        if stats["socketio_fault"]:
            msg = f"{name}: {stats['socketio_fault']} socket.io origin failure(s) -- {f}"
            failed |= line("FAIL", msg)
        elif stats["http_400"]:
            line("WARN", f"{name}: {stats['http_400']} HTTP 400(s), 0 socket.io faults -- {f}")
        else:
            line("PASS", f"{name}: 0 HTTP 400s -- {f}")
        status = "WARN" if stats["console_errors"] else "PASS"
        msg = f"{name}: {stats['console_errors']} console error(s) ({stats['total']} events total)"
        line(status, msg)

    print("== stacks (api.log) ==")
    for f in stack_logs:
        stats = analyze_stack_log(f, since_minutes)
        tag = f.parent.name
        if stats["origin_fault"]:
            msg = f"{tag}: {stats['origin_fault']} socket.io origin fault line(s) -- {f}"
            failed |= line("FAIL", msg)
        else:
            line("PASS", f"{tag}: no socket.io origin fault")
        if stats["traceback_total"]:
            n_distinct = len(stats["traceback_groups"])
            msg = f"{tag}: {stats['traceback_total']} traceback(s), {n_distinct} distinct -- {f}"
            failed |= line("FAIL", msg)
            by_count = sorted(stats["traceback_groups"].items(), key=lambda kv: -kv[1])
            for key, count in by_count:
                print(f"         x{count}  {key}")
        else:
            line("PASS", f"{tag}: no tracebacks")
        status = "WARN" if stats["error_lines"] else "PASS"
        line(status, f"{tag}: {stats['error_lines']} ERROR line(s)")

    return failed


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "dirs", nargs="*", default=[str(DEFAULT_DIR)],
        help="QA output directories to scan (default: logs/qa)")
    ap.add_argument(
        "--since", type=float, default=None,
        help="only consider entries from the last N minutes")
    args = ap.parse_args(argv)

    start = time.time()
    failed = report(args.dirs, args.since)
    elapsed = time.time() - start
    print(f"---- done in {elapsed:.1f}s ----")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
