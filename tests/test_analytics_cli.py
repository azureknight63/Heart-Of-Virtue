"""tools/analytics.py: prints the analytics report, its JSON, or an account id."""

import io
import json
from types import SimpleNamespace

import pytest

from src.api.services import analytics_report
from tools import analytics as cli

REPORT = {
    "window_days": 7,
    "players": {
        "total_accounts": 5,
        "new_accounts": {"1d": 0, "7d": 2, "30d": 5},
        "started_playing": 4,
        "active": {"dau": 1, "wau": 3, "mau": 4},
    },
}


@pytest.fixture
def api(monkeypatch):
    """The real report module, with only the database fetch replaced."""
    seen = {}

    def fetch(days):
        seen["days"] = days
        if "error" in seen:
            raise seen["error"]
        return REPORT

    fake = SimpleNamespace(
        **{name: getattr(analytics_report, name) for name in dir(analytics_report) if not name.startswith("__")}
    )
    fake.fetch_report = fetch
    fake.seen = seen
    monkeypatch.setattr(cli, "_load_report_api", lambda: fake)
    return fake


def run(argv):
    """(exit code, stdout); an error on stdout would corrupt --json output."""
    code, out, _err = run_split(argv)
    return code, out


def run_split(argv):
    out, err = io.StringIO(), io.StringIO()
    return cli.main(argv, out=out, err=err), out.getvalue(), err.getvalue()


def test_text_report(api):
    code, text = run(["--days", "7"])
    assert (code, api.seen["days"]) == (0, 7)
    assert "accounts 5 (new: 0 in 1d, 2 in 7d, 5 in 30d); 4 have played" in text


def test_json_report(api):
    code, text = run(["--json"])
    assert code == 0 and json.loads(text) == REPORT


def test_default_window(api):
    run([])
    assert api.seen["days"] == analytics_report.DEFAULT_WINDOW_DAYS


@pytest.mark.parametrize("days", [0, analytics_report.MAX_WINDOW_DAYS + 1])
def test_window_out_of_range_is_refused(api, days):
    with pytest.raises(SystemExit):
        run(["--days", str(days)])
    assert "days" not in api.seen


def test_configuration_errors_are_shown(api):
    from src.api.db import DatabaseNotConfigured

    api.seen["error"] = DatabaseNotConfigured("TURSO_DATABASE_URL is not set")
    code, out, err = run_split([])
    assert code == 1 and out == "" and "TURSO_DATABASE_URL is not set" in err


def test_a_driver_value_error_shows_only_its_type(api):
    # Only the not-configured error is known to be safe to print.
    api.seen["error"] = ValueError("bad url libsql://db.example?authToken=SECRET")
    code, out, err = run_split([])
    assert code == 1 and out == "" and "ValueError" in err and "SECRET" not in err


def test_other_errors_show_only_their_type(api):
    # A connection error can echo the database URL, which may carry a token.
    api.seen["error"] = ConnectionError("libsql://db.example?authToken=SECRET")
    code, out, err = run_split([])
    assert code == 1 and out == "" and "ConnectionError" in err and "SECRET" not in err


def test_whoami_queries_by_exact_username(api):
    seen = {}

    def run_query(sql, params):
        seen["query"] = (sql, params)
        return [("uuid-1",)]

    api.run_query = run_query
    code, text = run(["--whoami", "azure"])
    assert (code, text.strip()) == (0, "uuid-1")
    assert seen["query"] == ("SELECT id FROM users WHERE username = ?", ["azure"])


def test_whoami_unknown_user(api):
    api.run_query = lambda sql, params: []  # the real lookup, finding no row
    code, out, err = run_split(["--whoami", "nobody"])
    assert code == 1 and out == "" and "No account named 'nobody'" in err
