"""Tests for src/api/structured_log.py — the unified JSONL debug-log core.

Every log line (backend and frontend alike) shares one envelope schema:

    {"ts": ..., "src": "be"|"fe", "lvl": ..., "event": ..., ...}

so tools/logcat.py and AI agents can consume a single stream. These tests
cover the backend half: the JSONL formatter, the date-stamped file handler,
environment-driven configuration, the log_event helper, and the canonical
per-request line emitted by init_request_logging.
"""

import json
import logging
import uuid
from datetime import datetime

import pytest
from flask import Flask

from src.api.structured_log import (
    DateStampedJsonlHandler,
    JsonlFormatter,
    configure_logging,
    init_request_logging,
    log_event,
)


def _fresh_logger():
    """An isolated logger so tests never touch the root logger's handlers."""
    logger = logging.getLogger(f"_test_structured_{uuid.uuid4().hex}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    return logger


class _ListHandler(logging.Handler):
    """Collects formatted JSONL lines for assertions."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.lines = []
        self.setFormatter(JsonlFormatter())

    def emit(self, record):
        self.lines.append(self.format(record))


class TestJsonlFormatter:
    def _format_one(self, log_call):
        logger = _fresh_logger()
        handler = _ListHandler()
        logger.addHandler(handler)
        log_call(logger)
        assert len(handler.lines) == 1
        line = handler.lines[0]
        assert "\n" not in line
        return json.loads(line)

    def test_plain_message_becomes_log_event_envelope(self):
        env = self._format_one(lambda lg: lg.info("hello world"))
        assert env["src"] == "be"
        assert env["lvl"] == "info"
        assert env["event"] == "log"
        assert env["msg"] == "hello world"
        assert env["logger"].startswith("_test_structured_")
        # ts is ISO-8601 UTC with a Z suffix
        assert env["ts"].endswith("Z")
        datetime.fromisoformat(env["ts"].replace("Z", "+00:00"))

    def test_percent_args_are_rendered(self):
        env = self._format_one(lambda lg: lg.warning("hp=%s of %s", 3, 10))
        assert env["msg"] == "hp=3 of 10"
        assert env["lvl"] == "warning"

    def test_structured_event_and_data(self):
        env = self._format_one(
            lambda lg: lg.info(
                "combat.start",
                extra={"event": "combat.start", "data": {"enemy": "Slime"}},
            )
        )
        assert env["event"] == "combat.start"
        assert env["data"] == {"enemy": "Slime"}
        # msg identical to the event name is redundant — omitted
        assert "msg" not in env

    def test_session_in_data_is_promoted_to_top_level(self):
        env = self._format_one(
            lambda lg: lg.info(
                "http.request",
                extra={
                    "event": "http.request",
                    "data": {"session": "ab12", "path": "/api/x"},
                },
            )
        )
        assert env["session"] == "ab12"
        assert env["data"] == {"path": "/api/x"}

    def test_exception_info_is_captured(self):
        def call(lg):
            try:
                raise ValueError("boom")
            except ValueError:
                lg.error("it broke", exc_info=True)

        env = self._format_one(call)
        assert "ValueError" in env["data"]["error"]
        assert "boom" in env["data"]["error"]
        assert "Traceback" in env["data"]["trace"]

    def test_unserializable_data_falls_back_to_str(self):
        class Odd:
            def __repr__(self):
                return "<odd thing>"

        env = self._format_one(
            lambda lg: lg.info("x", extra={"event": "x", "data": {"obj": Odd()}})
        )
        assert env["data"]["obj"] == "<odd thing>"


class TestDateStampedJsonlHandler:
    def test_writes_date_stamped_jsonl_file(self, tmp_path):
        clock = lambda: datetime(2026, 8, 22, 12, 0, 0)  # noqa: E731
        handler = DateStampedJsonlHandler(tmp_path, clock=clock)
        logger = _fresh_logger()
        logger.addHandler(handler)
        logger.info("first")
        logger.info("second")
        handler.close()

        path = tmp_path / "2026-08-22.jsonl"
        assert path.exists()
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["msg"] == "first"
        assert json.loads(lines[1])["msg"] == "second"

    def test_rolls_to_new_file_when_date_changes(self, tmp_path):
        current = {"now": datetime(2026, 8, 22, 23, 59)}
        handler = DateStampedJsonlHandler(tmp_path, clock=lambda: current["now"])
        logger = _fresh_logger()
        logger.addHandler(handler)
        logger.info("before midnight")
        current["now"] = datetime(2026, 8, 23, 0, 1)
        logger.info("after midnight")
        handler.close()

        assert (tmp_path / "2026-08-22.jsonl").exists()
        assert (tmp_path / "2026-08-23.jsonl").exists()

    def test_default_clock_is_utc(self, tmp_path):
        # The filename's date must agree with the UTC ts fields inside the
        # file; a local-time default would disagree near midnight on any
        # non-UTC host.
        from datetime import timezone

        handler = DateStampedJsonlHandler(tmp_path)
        assert handler._clock().tzinfo == timezone.utc
        handler.close()

    def test_emit_failure_does_not_raise(self, tmp_path, monkeypatch):
        handler = DateStampedJsonlHandler(tmp_path)
        logger = _fresh_logger()
        logger.addHandler(handler)
        monkeypatch.setattr(
            handler, "_open_stream", lambda *a: (_ for _ in ()).throw(OSError())
        )
        logger.info("does not crash the app")  # logging swallows via handleError
        handler.close()


class TestConfigureLogging:
    def test_console_level_from_env(self):
        logger = _fresh_logger()
        logger.handlers = []
        configure_logging(env={"LOG_LEVEL": "INFO"}, logger=logger)
        assert logger.level == logging.INFO
        console = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert console and console[0].level == logging.INFO

    def test_jsonl_dir_enables_debug_capture(self, tmp_path):
        logger = _fresh_logger()
        logger.handlers = []
        configure_logging(
            env={"LOG_LEVEL": "WARNING", "LOG_JSONL_DIR": str(tmp_path)},
            logger=logger,
        )
        # Logger drops to DEBUG so the JSONL file catches everything, while
        # the console handler keeps the quiet WARNING threshold.
        assert logger.level == logging.DEBUG
        jsonl = [h for h in logger.handlers if isinstance(h, DateStampedJsonlHandler)]
        assert jsonl and jsonl[0].level == logging.DEBUG
        console = [
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, DateStampedJsonlHandler)
        ]
        assert console and console[0].level == logging.WARNING

        logger.debug("captured %s", "detail")
        for h in logger.handlers:
            h.close()
        files = list(tmp_path.glob("*.jsonl"))
        assert files, "debug record should land in the JSONL file"
        assert "captured detail" in files[0].read_text(encoding="utf-8")

    def test_reconfigure_replaces_only_own_handlers(self, tmp_path):
        logger = _fresh_logger()
        logger.handlers = []
        foreign = logging.NullHandler()
        logger.addHandler(foreign)
        configure_logging(env={"LOG_LEVEL": "INFO"}, logger=logger)
        first_count = len(logger.handlers)
        configure_logging(env={"LOG_LEVEL": "INFO"}, logger=logger)
        assert len(logger.handlers) == first_count
        assert foreign in logger.handlers

    def test_bad_level_falls_back_to_warning(self):
        logger = _fresh_logger()
        logger.handlers = []
        configure_logging(env={"LOG_LEVEL": "SHOUTING"}, logger=logger)
        assert logger.level == logging.WARNING


class TestLogEvent:
    def test_emits_named_event_with_data(self):
        logger = _fresh_logger()
        handler = _ListHandler()
        logger.addHandler(handler)
        log_event("shop.buy", level=logging.INFO, logger=logger, item="Sword", gold=30)
        env = json.loads(handler.lines[0])
        assert env["event"] == "shop.buy"
        assert env["data"] == {"item": "Sword", "gold": 30}
        assert env["lvl"] == "info"


class TestRequestLogging:
    @pytest.fixture
    def app_and_lines(self):
        # No TESTING flag: the 5xx test needs Flask to convert the raised
        # exception into a 500 response instead of propagating it.
        app = Flask(__name__)

        @app.route("/api/thing")
        def thing():
            return {"ok": True}

        @app.route("/api/broken")
        def broken():
            raise RuntimeError("kaput")

        @app.route("/api/logs/browser", methods=["POST"])
        def browser_logs():
            return {"ok": True}

        @app.route("/health")
        def health():
            return {"ok": True}

        capture = _ListHandler()
        http_logger = logging.getLogger("hov.http")
        http_logger.addHandler(capture)
        http_logger.setLevel(logging.DEBUG)
        http_logger.propagate = False
        init_request_logging(app)
        yield app, capture.lines
        http_logger.removeHandler(capture)

    def _events(self, lines):
        return [json.loads(line) for line in lines]

    def test_canonical_line_per_request(self, app_and_lines):
        app, lines = app_and_lines
        with app.test_client() as c:
            rv = c.get("/api/thing")
        assert rv.status_code == 200
        events = self._events(lines)
        assert len(events) == 1
        env = events[0]
        assert env["event"] == "http.request"
        assert env["data"]["method"] == "GET"
        assert env["data"]["path"] == "/api/thing"
        assert env["data"]["status"] == 200
        assert env["data"]["dur_ms"] >= 0
        assert len(env["data"]["request_id"]) == 8
        assert env["lvl"] == "info"

    def test_5xx_logs_at_error_level(self, app_and_lines):
        app, lines = app_and_lines
        with app.test_client() as c:
            rv = c.get("/api/broken")
        assert rv.status_code == 500
        events = self._events(lines)
        assert events and events[-1]["lvl"] == "error"
        assert events[-1]["data"]["status"] == 500

    def test_session_fingerprint_never_the_raw_token(self, app_and_lines):
        app, lines = app_and_lines
        token = "super-secret-session-token-value"
        with app.test_client() as c:
            c.get("/api/thing", headers={"Authorization": f"Bearer {token}"})
        env = self._events(lines)[0]
        fingerprint = env["session"]
        assert fingerprint != token
        assert token not in json.dumps(env)
        assert len(fingerprint) == 4
        # Stable: the same token maps to the same fingerprint
        with app.test_client() as c:
            c.get("/api/thing", headers={"Authorization": f"Bearer {token}"})
        assert self._events(lines)[1]["session"] == fingerprint

    def test_log_shipping_and_health_routes_are_skipped(self, app_and_lines):
        app, lines = app_and_lines
        with app.test_client() as c:
            c.post("/api/logs/browser", json={"logs": []})
            c.get("/health")
        assert lines == []

    def test_options_preflight_is_skipped(self, app_and_lines):
        app, lines = app_and_lines
        with app.test_client() as c:
            c.options("/api/thing")
        assert lines == []

    def test_path_control_characters_are_stripped(self, app_and_lines):
        # request.path is attacker-chosen; a crafted path must not smuggle
        # terminal escape sequences into the stream logcat renders.
        app, lines = app_and_lines
        with app.test_client() as c:
            c.get("/api/thing\x1b[31mevil\x07")
        env = self._events(lines)[0]
        assert "\x1b" not in json.dumps(env)
        assert "\x07" not in json.dumps(env)

    def test_handled_500_logs_exactly_once(self, app_and_lines):
        # after_request logs it; the teardown backstop must not double-log
        app, lines = app_and_lines
        with app.test_client() as c:
            c.get("/api/broken")
        assert len(self._events(lines)) == 1


class TestCrashLogging:
    def test_unhandled_exception_still_logs_in_propagating_mode(self):
        # In debug mode Flask re-raises before after_request runs, so the
        # canonical line would vanish for exactly the crashes a debug log
        # exists to capture. The teardown hook backstops it.
        app = Flask(__name__)
        app.config["PROPAGATE_EXCEPTIONS"] = True

        @app.route("/api/crash")
        def crash():
            raise RuntimeError("kaput in debug")

        capture = _ListHandler()
        http_logger = logging.getLogger("hov.http")
        http_logger.addHandler(capture)
        http_logger.setLevel(logging.DEBUG)
        http_logger.propagate = False
        init_request_logging(app)
        try:
            with pytest.raises(RuntimeError):
                with app.test_client() as c:
                    c.get("/api/crash")
        finally:
            http_logger.removeHandler(capture)

        events = [json.loads(line) for line in capture.lines]
        assert len(events) == 1
        env = events[0]
        assert env["lvl"] == "error"
        assert env["data"]["status"] == 500
        assert "RuntimeError" in env["data"]["error"]
        assert "kaput in debug" in env["data"]["error"]
        # The whole point of the backstop is crash visibility — losing
        # the traceback would defeat that.
        assert "Traceback" in env["data"]["trace"]
        assert "raise RuntimeError" in env["data"]["trace"]


class TestConfigureLoggingLogFile:
    def test_log_file_writes_plain_text(self, tmp_path):
        logger = _fresh_logger()
        logger.handlers = []
        path = tmp_path / "app.log"
        configure_logging(
            env={"LOG_LEVEL": "INFO", "LOG_FILE": str(path)}, logger=logger
        )
        logger.info("hello plain file")
        for handler in logger.handlers:
            handler.close()
        assert "hello plain file" in path.read_text(encoding="utf-8")

    def test_log_file_oserror_is_swallowed(self, tmp_path, monkeypatch):
        logger = _fresh_logger()
        logger.handlers = []
        monkeypatch.setattr(
            logging,
            "FileHandler",
            lambda *a, **k: (_ for _ in ()).throw(OSError("nope")),
        )
        # Must not raise — a bad LOG_FILE path degrades, never crashes the app
        configure_logging(
            env={"LOG_LEVEL": "INFO", "LOG_FILE": str(tmp_path / "x.log")},
            logger=logger,
        )


class TestJsonlDirRetention:
    def test_configure_logging_prunes_old_backend_logs(self, tmp_path):
        # logs/backend/*.jsonl otherwise has no retention at all: nothing
        # else ever touches this directory (unlike the browser logs, which
        # get pruned on every write). configure_logging must prune it too.
        import os
        import time

        old = tmp_path / "2020-01-01.jsonl"
        old.write_text("{}\n", encoding="utf-8")
        stale = time.time() - 400 * 86400
        os.utime(old, (stale, stale))
        fresh = tmp_path / "fresh.jsonl"
        fresh.write_text("{}\n", encoding="utf-8")

        logger = _fresh_logger()
        logger.handlers = []
        configure_logging(env={"LOG_JSONL_DIR": str(tmp_path)}, logger=logger)
        for h in logger.handlers:
            h.close()

        assert not old.exists()
        assert fresh.exists()

    def test_cleanup_failure_does_not_block_configure(self, tmp_path, monkeypatch):
        from src.api import structured_log

        def boom(*a, **k):
            raise OSError("disk full")

        monkeypatch.setattr(structured_log.LogCleanupManager, "cleanup", boom)
        logger = _fresh_logger()
        logger.handlers = []
        # Must not raise — a cleanup failure must never block server startup
        configure_logging(env={"LOG_JSONL_DIR": str(tmp_path)}, logger=logger)
        for h in logger.handlers:
            h.close()
