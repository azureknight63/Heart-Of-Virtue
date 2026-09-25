"""Offline tests for check_contamination.py -- no live stacks required.

Builds small fixture logs under tmp_path in the exact shapes
`scripts/qa_driver.py` (tester `<name>_events.jsonl`) and `scripts/qa_api.py`
via `start_stack.py` (`logs/qa/<tag>/api.log`) actually write, then asserts
the PASS/WARN/FAIL verdicts and the exit code.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check_contamination as cc  # noqa: E402


def _write_events(path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")


def test_socketio_400_events_file_is_fault(tmp_path):
    events = [
        {"seq": 1, "ts": "14:10:54", "kind": "http",
         "url": "http://localhost:3002/socket.io/?transport=polling", "method": "POST",
         "status": 400, "text": "Bad Request", "noise": False},
    ]
    f = tmp_path / "runs" / "T1_events.jsonl"
    _write_events(f, events)
    stats = cc.analyze_events_file(f)
    assert stats["http_400"] == 1
    assert stats["socketio_fault"] == 1


def test_clean_events_file_passes(tmp_path):
    events = [
        {"seq": 1, "ts": "14:10:54", "kind": "console.warning", "text": "noise", "noise": True},
        {"seq": 2, "ts": "14:10:55", "kind": "http", "url": "http://localhost:3001/api/world",
         "method": "GET", "status": 200, "text": "", "noise": False},
    ]
    f = tmp_path / "runs" / "T2_events.jsonl"
    _write_events(f, events)
    stats = cc.analyze_events_file(f)
    assert stats["http_400"] == 0
    assert stats["socketio_fault"] == 0


def _write_api_log(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


ORIGIN_LINE = ("2026-09-06 19:47:40,567 ERROR engineio.server http://localhost:3002 is not an "
               "accepted origin. (further occurrences of this error will be logged with level INFO)")

TRACEBACK_BLOCK = [
    "2026-09-24 17:48:19,133 DEBUG src.moves._base unavailability diagnosis failed for Attack",
    "Traceback (most recent call last):",
    '  File "C:\\repo\\src\\moves\\_base.py", line 1971, in unavailability_reason',
    "    return UnavailableReason(self._unavailability_code())",
    "ValueError: None is not a valid UnavailableReason",
]


def test_stack_with_origin_fault_and_traceback_fails(tmp_path):
    log = tmp_path / "logs" / "qa" / "badstack" / "api.log"
    _write_api_log(log, [ORIGIN_LINE] + TRACEBACK_BLOCK)
    stats = cc.analyze_stack_log(log)
    assert stats["origin_fault"] == 1
    assert stats["traceback_total"] == 1

    failed = cc.report([str(tmp_path / "logs" / "qa")])
    assert failed is True


def test_clean_stack_passes(tmp_path):
    log = tmp_path / "logs" / "qa" / "goodstack" / "api.log"
    _write_api_log(log, [
        "2026-09-24 17:48:19,133 INFO hov.http http.request",
        "2026-09-24 17:48:19,140 INFO hov.http http.request",
    ])
    stats = cc.analyze_stack_log(log)
    assert stats["origin_fault"] == 0
    assert stats["traceback_total"] == 0

    failed = cc.report([str(tmp_path / "logs" / "qa")])
    assert failed is False


def test_traceback_dedup_counts_distinct_exceptions(tmp_path):
    log = tmp_path / "logs" / "qa" / "dupstack" / "api.log"
    other_block = [
        "2026-09-24 17:49:00,000 DEBUG something else",
        "Traceback (most recent call last):",
        '  File "x.py", line 1, in <module>',
        "KeyError: 'oops'",
    ]
    _write_api_log(log, TRACEBACK_BLOCK + TRACEBACK_BLOCK + other_block)
    stats = cc.analyze_stack_log(log)
    assert stats["traceback_total"] == 3
    assert len(stats["traceback_groups"]) == 2
    assert stats["traceback_groups"]["ValueError: None is not a valid UnavailableReason"] == 2
    assert stats["traceback_groups"]["KeyError: 'oops'"] == 1


def test_since_filter_excludes_old_api_log_entries(tmp_path):
    log = tmp_path / "logs" / "qa" / "oldstack" / "api.log"
    old_line = "2020-01-01 00:00:00,000 ERROR engineio.server " + cc.ORIGIN_FAULT_TEXT + "."
    _write_api_log(log, [old_line])
    stats = cc.analyze_stack_log(log, since_minutes=5)
    assert stats["origin_fault"] == 0
