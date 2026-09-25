"""Offline tests for summarize_api_log.py -- no live REST tester needed.

Builds small fixture request logs under tmp_path in the exact shape
`scripts/qa_api_client.py` writes to `<NAME>_api.jsonl`: one JSON object per
line with keys t/m/path/req/status/body.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import summarize_api_log as sal  # noqa: E402


def _write(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def _move_turn_record(t):
    return {
        "t": t, "m": "POST", "path": "/api/combat/move", "req": {"move": "Turn"},
        "status": 200,
        "body": {"success": True, "combat": {"input_type": "direction_selection"}},
    }


def test_repeat_run_reports_nested_input_type(tmp_path):
    records = [_move_turn_record(f"14:00:{i:02d}") for i in range(25)]
    f = tmp_path / "A4_api.jsonl"
    _write(f, records)

    summary = sal.summarize_file(f)
    assert summary["count"] == 25
    assert len(summary["repeats"]) == 1
    r = summary["repeats"][0]
    assert r["count"] == 25
    assert r["method"] == "POST" and r["path"] == "/api/combat/move"
    assert r["input_type"] == "direction_selection"


def test_repeat_run_below_threshold_not_reported(tmp_path):
    records = [_move_turn_record(f"14:00:{i:02d}") for i in range(10)]
    f = tmp_path / "short_api.jsonl"
    _write(f, records)
    summary = sal.summarize_file(f, repeat_n=20)
    assert summary["repeats"] == []


def test_get_get_pair_losing_events_item_is_flagged(tmp_path):
    records = [
        {"t": "10:00:00", "m": "GET", "path": "/api/world/events/pending", "req": None,
         "status": 200, "body": {"events": ["Victory", "LevelUp"]}},
        {"t": "10:00:05", "m": "GET", "path": "/api/world/events/pending", "req": None,
         "status": 200, "body": {"events": ["LevelUp"]}},
    ]
    f = tmp_path / "V1_api.jsonl"
    _write(f, records)
    summary = sal.summarize_file(f)
    assert len(summary["state_changes_after_get"]) == 1
    change = summary["state_changes_after_get"][0]
    assert change["path"] == "/api/world/events/pending"
    assert "shrank" in change["diff"] or "2 -> 1" in change["diff"]


def test_get_get_pair_differing_only_in_ignored_field_not_flagged(tmp_path):
    records = [
        {"t": "10:00:00", "m": "GET", "path": "/api/full-state", "req": None,
         "status": 200, "body": {"hp": 10, "beat": 3}},
        {"t": "10:00:05", "m": "GET", "path": "/api/full-state", "req": None,
         "status": 200, "body": {"hp": 10, "beat": 4}},
    ]
    f = tmp_path / "V2_api.jsonl"
    _write(f, records)
    summary = sal.summarize_file(f)
    assert summary["state_changes_after_get"] == []


def test_post_between_gets_is_not_flagged_as_a_pair(tmp_path):
    records = [
        {"t": "10:00:00", "m": "GET", "path": "/api/world/events/pending", "req": None,
         "status": 200, "body": {"events": ["Victory"]}},
        {"t": "10:00:02", "m": "POST", "path": "/api/world/events/ack", "req": {},
         "status": 200, "body": {"success": True}},
        {"t": "10:00:05", "m": "GET", "path": "/api/world/events/pending", "req": None,
         "status": 200, "body": {"events": []}},
    ]
    f = tmp_path / "V3_api.jsonl"
    _write(f, records)
    summary = sal.summarize_file(f)
    # the two GETs are not consecutive records (a POST sits between them), so
    # this is not the silent-GET pattern the heuristic targets
    assert summary["state_changes_after_get"] == []


def test_404s_grouped_by_path(tmp_path):
    records = [
        {"t": "10:00:00", "m": "GET", "path": "/api/combat/end", "req": None,
         "status": 404, "body": {"error": "not found"}},
        {"t": "10:00:01", "m": "GET", "path": "/api/combat/end", "req": None,
         "status": 404, "body": {"error": "not found"}},
        {"t": "10:00:02", "m": "GET", "path": "/api/combat/pray", "req": None,
         "status": 404, "body": {"error": "not found"}},
    ]
    f = tmp_path / "A1_api.jsonl"
    _write(f, records)
    summary = sal.summarize_file(f)
    assert summary["not_found_404"] == {"/api/combat/end": 2, "/api/combat/pray": 1}


def test_status_histogram_and_success_false_grouping(tmp_path):
    records = [
        {"t": "10:00:00", "m": "GET", "path": "/api/world", "req": None,
         "status": 200, "body": {"success": True}},
        {"t": "10:00:01", "m": "POST", "path": "/api/world/move", "req": {"direction": "north"},
         "status": 200, "body": {"success": False, "message": "Cannot move while in combat"}},
        {"t": "10:00:02", "m": "POST", "path": "/api/world/move", "req": {"direction": "north"},
         "status": 200, "body": {"success": False, "message": "Cannot move while in combat"}},
        {"t": "10:00:03", "m": "GET", "path": "/api/bogus", "req": None,
         "status": None, "body": {"_error": "connection refused"}},
    ]
    f = tmp_path / "T5_api.jsonl"
    _write(f, records)
    summary = sal.summarize_file(f)
    assert summary["status_histogram"]["2xx"] == 3
    assert summary["status_histogram"]["None"] == 1
    assert summary["success_false"] == {"Cannot move while in combat": 2}


def test_directory_input_resolves_all_jsonl_files(tmp_path):
    _write(tmp_path / "A_api.jsonl", [_move_turn_record("10:00:00")])
    _write(tmp_path / "B_api.jsonl", [_move_turn_record("10:00:00")])
    files = sal._resolve_inputs([str(tmp_path)])
    assert len(files) == 2
