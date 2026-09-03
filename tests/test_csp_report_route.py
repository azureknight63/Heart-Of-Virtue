"""The Content-Security-Policy violation sink (issue #492).

``POST /api/logs/csp-report`` is written by the *browser*, not by the app: it is
unauthenticated, its content type is one Flask does not treat as JSON, and its
body shape depends on which of the two reporting transports the browser
implements. These tests pin all three, plus the invariant that violations land
in the same bounded JSONL stream as console logs so ``tools/logcat.py`` shows
them together.
"""

import json
from unittest.mock import patch

import pytest
from flask import Flask

from src.api.routes.logs import MAX_CSP_REPORTS_PER_REQUEST


@pytest.fixture
def client(tmp_path):
    from src.api.routes.logs import logs_bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(logs_bp, url_prefix="/api/logs")
    with app.test_client() as c:
        with patch("src.api.routes.logs.LOGS_DIR", tmp_path):
            yield c


def _envelopes(tmp_path):
    lines = []
    for path in sorted(tmp_path.glob("*.jsonl")):
        lines.extend(path.read_text(encoding="utf-8").strip().splitlines())
    return [json.loads(line) for line in lines]


REPORT = {
    "document-uri": "http://localhost:3000/games/HeartOfVirtue/game",
    "violated-directive": "script-src",
    "effective-directive": "script-src-elem",
    "blocked-uri": "https://evil.example/x.js",
    "disposition": "report",
    "line-number": 42,
}


def _post(client, payload, content_type="application/csp-report"):
    return client.post(
        "/api/logs/csp-report",
        data=json.dumps(payload),
        content_type=content_type,
    )


class TestLegacyReportUriTransport:
    def test_records_a_violation(self, client, tmp_path):
        assert _post(client, {"csp-report": REPORT}).status_code == 204

        (envelope,) = _envelopes(tmp_path)
        assert envelope["event"] == "csp.violation"
        assert envelope["src"] == "fe"
        assert envelope["lvl"] == "warning"
        assert envelope["url"] == REPORT["document-uri"]
        assert envelope["data"]["violated-directive"] == "script-src"
        assert envelope["data"]["blocked-uri"] == "https://evil.example/x.js"

    def test_content_type_flask_would_not_parse_as_json_is_still_read(
        self, client, tmp_path
    ):
        """The whole route hinges on force-parsing application/csp-report."""
        assert _post(client, {"csp-report": REPORT}).status_code == 204
        assert _envelopes(tmp_path)

    def test_violations_share_one_predictable_bucket(self, client, tmp_path):
        _post(client, {"csp-report": REPORT})
        _post(client, {"csp-report": dict(REPORT, **{"blocked-uri": "inline"})})
        assert len(list(tmp_path.glob("*.jsonl"))) == 1
        assert all(e["session"] == "csp" for e in _envelopes(tmp_path))


class TestReportingApiTransport:
    def test_records_every_report_in_the_batch(self, client, tmp_path):
        payload = [
            {"type": "csp-violation", "body": REPORT},
            {"type": "csp-violation", "body": dict(REPORT, **{"violated-directive": "img-src"})},
        ]
        assert _post(client, payload, "application/reports+json").status_code == 204

        directives = [e["data"]["violated-directive"] for e in _envelopes(tmp_path)]
        assert directives == ["script-src", "img-src"]

    def test_a_single_reporting_api_object_is_accepted(self, client, tmp_path):
        assert _post(client, {"type": "csp-violation", "body": REPORT}).status_code == 204
        assert _envelopes(tmp_path)[0]["data"]["violated-directive"] == "script-src"

    def test_non_dict_entries_in_the_batch_are_skipped(self, client, tmp_path):
        payload = ["nope", {"body": REPORT}, {"no_body": True}, 7]
        assert _post(client, payload).status_code == 204
        assert len(_envelopes(tmp_path)) == 1


class TestBounds:
    def test_report_count_is_capped(self, client, tmp_path):
        payload = [{"body": REPORT}] * (MAX_CSP_REPORTS_PER_REQUEST + 25)
        assert _post(client, payload).status_code == 204
        assert len(_envelopes(tmp_path)) == MAX_CSP_REPORTS_PER_REQUEST

    def test_unknown_fields_are_dropped(self, client, tmp_path):
        report = dict(REPORT, **{"attacker-payload": "x" * 5000})
        _post(client, {"csp-report": report})
        assert "attacker-payload" not in _envelopes(tmp_path)[0]["data"]

    def test_a_report_with_no_known_fields_still_records_something(
        self, client, tmp_path
    ):
        _post(client, {"csp-report": {"unknown": 1}})
        assert _envelopes(tmp_path)[0]["data"] == {"_empty": True}

    def test_control_characters_cannot_forge_extra_log_lines(self, client, tmp_path):
        report = dict(REPORT, **{"blocked-uri": "a\nb\rc"})
        _post(client, {"csp-report": report})
        envelopes = _envelopes(tmp_path)
        assert len(envelopes) == 1
        assert "\n" not in envelopes[0]["data"]["blocked-uri"]


class TestNonReports:
    @pytest.mark.parametrize(
        "payload", [{}, {"csp-report": "not a dict"}, [], "text", 5, None]
    )
    def test_junk_bodies_are_accepted_quietly_and_written_nowhere(
        self, client, tmp_path, payload
    ):
        assert _post(client, payload).status_code == 204
        assert not list(tmp_path.glob("*.jsonl"))

    def test_unparseable_body_does_not_error(self, client, tmp_path):
        rv = client.post(
            "/api/logs/csp-report",
            data=b"\x00 not json at all",
            content_type="application/csp-report",
        )
        assert rv.status_code == 204
        assert not list(tmp_path.glob("*.jsonl"))

    def test_a_write_failure_is_swallowed(self, client):
        """No client is left to act on an error; never 500 at a browser."""
        with patch(
            "src.api.routes.logs._write_log_entries", side_effect=OSError("disk full")
        ):
            assert _post(client, {"csp-report": REPORT}).status_code == 204

    def test_route_is_reachable_without_testing_mode(self, tmp_path):
        """Unlike the log-management routes, this one must work in production."""
        from src.api.routes.logs import logs_bp

        app = Flask(__name__)
        app.register_blueprint(logs_bp, url_prefix="/api/logs")
        with app.test_client() as c, patch("src.api.routes.logs.LOGS_DIR", tmp_path):
            rv = c.post(
                "/api/logs/csp-report",
                data=json.dumps({"csp-report": REPORT}),
                content_type="application/csp-report",
            )
        assert rv.status_code == 204


def test_console_logs_still_write_through_the_shared_helper(client, tmp_path):
    """The extraction must not have changed the console-log route's behaviour."""
    with patch("src.api.routes.logs.cleanup_manager") as cm:
        cm.cleanup.return_value = {}
        rv = client.post(
            "/api/logs/browser",
            json={"logs": [{"level": "ERROR", "message": "boom"}], "session_id": "s1"},
        )
    assert rv.status_code == 200
    (envelope,) = _envelopes(tmp_path)
    assert envelope["msg"] == "boom"
    assert envelope["session"] == "s1"
