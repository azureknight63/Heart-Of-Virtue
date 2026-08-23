"""Tests for the JSONL browser-log pipeline (routes/logs.py + log_cleanup).

The browser log endpoint writes one JSON object per line using the shared
envelope schema ({"ts", "src": "fe", "lvl", "event", ...}) instead of the old
bracketed text format, so tools/logcat.py and AI agents can parse the stream
directly. The resource-exhaustion guards from issue #429 (entry cap, field
caps, session bucketing) must survive the format change.
"""

import json
from unittest.mock import patch

import pytest
from flask import Flask

from src.api.utils.log_cleanup import LogCleanupManager


@pytest.fixture
def app():
    from src.api.routes.logs import logs_bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(logs_bp, url_prefix="/api/logs")
    return app


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


def _post_logs(client, tmp_path, logs, session_id="sess_abc"):
    with (
        patch("src.api.routes.logs.LOGS_DIR", tmp_path),
        patch("src.api.routes.logs.cleanup_manager") as mock_cm,
    ):
        mock_cm.cleanup.return_value = {}
        rv = client.post(
            "/api/logs/browser", json={"logs": logs, "session_id": session_id}
        )
    return rv


def _written_envelopes(tmp_path):
    files = sorted(tmp_path.glob("*.jsonl"))
    assert files, "expected a .jsonl log file to be written"
    lines = []
    for f in files:
        lines.extend(f.read_text(encoding="utf-8").strip().splitlines())
    return [json.loads(line) for line in lines]


class TestJsonlWrites:
    def test_writes_envelope_per_entry(self, client, tmp_path):
        rv = _post_logs(
            client,
            tmp_path,
            [
                {
                    "timestamp": "2026-08-22T16:13:23.901Z",
                    "level": "LOG",
                    "message": "hello",
                    "url": "http://localhost:3000/game",
                }
            ],
        )
        assert rv.status_code == 200
        assert rv.get_json()["file"].endswith(".jsonl")
        (env,) = _written_envelopes(tmp_path)
        assert env["ts"] == "2026-08-22T16:13:23.901Z"
        assert env["src"] == "fe"
        # Browser console levels normalize to the backend vocabulary
        assert env["lvl"] == "info"
        assert env["event"] == "console"
        assert env["msg"] == "hello"
        assert env["url"] == "http://localhost:3000/game"
        assert env["session"] == "sess_abc"

    def test_missing_timestamp_defaults_to_utc_z(self, client, tmp_path):
        _post_logs(client, tmp_path, [{"message": "no ts supplied"}])
        (env,) = _written_envelopes(tmp_path)
        # Must match the rest of the stream (UTC, Z suffix) or logcat's
        # chronological merge mis-orders it against backend entries.
        assert env["ts"].endswith("Z")

    def test_level_normalization(self, client, tmp_path):
        _post_logs(
            client,
            tmp_path,
            [
                {"level": "WARN", "message": "w"},
                {"level": "ERROR", "message": "e"},
                {"level": "DEBUG", "message": "d"},
                {"level": "NOT A LEVEL", "message": "x"},
            ],
        )
        envs = _written_envelopes(tmp_path)
        assert [e["lvl"] for e in envs] == ["warning", "error", "debug", "info"]

    def test_structured_event_and_data_pass_through(self, client, tmp_path):
        _post_logs(
            client,
            tmp_path,
            [
                {
                    "level": "DEBUG",
                    "event": "event.enqueue",
                    "data": {"name": "Passage_Camp Entrance", "needsInput": True},
                    "n": 3,
                    "message": "event.enqueue …",
                }
            ],
        )
        (env,) = _written_envelopes(tmp_path)
        assert env["event"] == "event.enqueue"
        assert env["data"]["name"] == "Passage_Camp Entrance"
        assert env["n"] == 3

    def test_event_name_is_sanitized(self, client, tmp_path):
        _post_logs(
            client,
            tmp_path,
            [{"event": "Weird Event!\nName" + "x" * 200, "message": "m"}],
        )
        (env,) = _written_envelopes(tmp_path)
        assert len(env["event"]) <= 64
        assert "\n" not in env["event"]
        assert " " not in env["event"]

    def test_oversized_data_is_truncated_not_written(self, client, tmp_path):
        _post_logs(
            client,
            tmp_path,
            [{"event": "big", "data": {"blob": "y" * 20000}, "message": "m"}],
        )
        (env,) = _written_envelopes(tmp_path)
        assert env["data"].get("_truncated") is True
        assert "y" * 100 not in json.dumps(env)

    def test_non_dict_data_is_dropped(self, client, tmp_path):
        _post_logs(
            client,
            tmp_path,
            [{"event": "odd", "data": ["not", "a", "dict"], "message": "m"}],
        )
        (env,) = _written_envelopes(tmp_path)
        assert "data" not in env

    def test_hostile_message_cannot_forge_lines(self, client, tmp_path):
        _post_logs(
            client,
            tmp_path,
            [{"message": 'fake"} \n{"ts": "x", "lvl": "error", "msg": "forged'}],
        )
        envs = _written_envelopes(tmp_path)
        # One entry in, exactly one parseable line out — no injected second line
        assert len(envs) == 1
        assert envs[0].get("msg") != "forged"

    def test_repeat_count_is_clamped_to_sane_int(self, client, tmp_path):
        _post_logs(
            client,
            tmp_path,
            [
                {"message": "a", "n": "999999999999"},
                {"message": "b", "n": -5},
                {"message": "c", "n": "junk"},
            ],
        )
        envs = _written_envelopes(tmp_path)
        assert envs[0]["n"] <= 100000
        assert "n" not in envs[1]  # n<=1 is the default, not worth a field
        assert "n" not in envs[2]

    def test_entry_cap_still_enforced(self, client, tmp_path):
        logs = [{"message": f"m{i}"} for i in range(600)]
        rv = _post_logs(client, tmp_path, logs)
        assert rv.status_code == 200
        envs = _written_envelopes(tmp_path)
        assert len(envs) == 500  # MAX_LOGS_PER_REQUEST

    def test_listing_includes_jsonl_and_legacy_log_files(self, client, tmp_path):
        (tmp_path / "2026-08-01_bucket00.log").write_text("old format")
        (tmp_path / "2026-08-22_bucket00.jsonl").write_text('{"ts":"t"}\n')
        with patch("src.api.routes.logs.LOGS_DIR", tmp_path):
            rv = client.get("/api/logs/browser/files")
        names = [f["filename"] for f in rv.get_json()["files"]]
        assert "2026-08-01_bucket00.log" in names
        assert "2026-08-22_bucket00.jsonl" in names


class TestCleanupCoversJsonl:
    def test_age_cleanup_removes_old_jsonl(self, tmp_path):
        import os
        import time

        old = tmp_path / "2020-01-01_bucket00.jsonl"
        old.write_text("{}\n")
        stale = time.time() - 400 * 86400
        os.utime(old, (stale, stale))
        fresh = tmp_path / "fresh.jsonl"
        fresh.write_text("{}\n")

        result = LogCleanupManager(tmp_path, retention_days=7).cleanup_old_logs()
        assert result["deleted_count"] == 1
        assert not old.exists()
        assert fresh.exists()

    def test_size_cleanup_counts_jsonl(self, tmp_path):
        import os
        import time

        for i in range(3):
            f = tmp_path / f"f{i}.jsonl"
            f.write_bytes(b"x" * (1024 * 1024))
            past = time.time() - (3 - i) * 3600
            os.utime(f, (past, past))

        mgr = LogCleanupManager(tmp_path, retention_days=7, max_size_mb=2)
        result = mgr.cleanup_by_size()
        assert result["deleted_count"] >= 1
        remaining = sum(f.stat().st_size for f in tmp_path.glob("*.jsonl"))
        assert remaining <= 2 * 1024 * 1024

    def test_stats_include_jsonl(self, tmp_path):
        (tmp_path / "a.jsonl").write_text("{}\n")
        (tmp_path / "b.log").write_text("legacy\n")
        stats = LogCleanupManager(tmp_path).get_stats()
        assert stats["total_files"] == 2
