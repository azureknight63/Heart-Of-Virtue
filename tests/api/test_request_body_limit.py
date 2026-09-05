"""The API bounds the size of a request body, and says so with a 413.

Nothing bounded it before. The two routes that matter are the two an
unauthenticated client can reach — ``POST /api/logs/browser`` (the frontend
logger posts there without a session, including via ``sendBeacon``) and
``POST /api/auth/register`` — and this deployment runs a single gunicorn
worker with nothing in front of it (``src/api/rate_limiter.py`` documents the
absent proxy), so an arbitrarily large body had nowhere to be stopped.

Two mechanisms, tested separately below because only one of them is enough on
its own:

* ``Config.MAX_CONTENT_LENGTH`` makes Werkzeug refuse to *read* past the cap.
  That is what stops the buffering, and it is not enough by itself: Werkzeug
  signals the refusal by raising ``RequestEntityTooLarge`` where the body is
  read, which for every route in this API is inside a ``try:`` whose
  ``except Exception`` answers with that route's own 500.
* ``_register_request_limits`` in ``src/api/app.py`` checks the declared
  ``Content-Length`` in a ``before_request``, so the refusal happens ahead of
  the view function and reaches the client as a 413 with this API's error
  shape.
"""

import pytest

from src.api.config import Config

_LOGS = "/api/logs/browser"
_REGISTER = "/api/auth/register"

#: Bodies at these sizes, relative to the limit, must be treated differently.
#: The under-limit case is the control: a guard that refused everything would
#: satisfy every "is it rejected?" assertion in this file while breaking the
#: endpoint it protects.
_OVER = 64 * 1024


@pytest.fixture(autouse=True)
def _clear_browser_log_limiter():
    """Keep the (module-level, process-wide) browser-log throttle out of it.

    ``POST /api/logs/browser`` is rate limited at 60/minute per source, and
    every test in this process shares one limiter and one client address. A
    429 here would look like a body-size failure.
    """
    from src.api.routes import logs as logs_module

    if logs_module._browser_log_limiter is not None:
        logs_module._browser_log_limiter.clear_all()
    yield
    if logs_module._browser_log_limiter is not None:
        logs_module._browser_log_limiter.clear_all()


def _body_of_size(nbytes):
    """A syntactically valid browser-log payload of roughly ``nbytes`` bytes."""
    overhead = len('{"session_id": "size-probe", "logs": [{"message": ""}]}')
    filler = "x" * max(nbytes - overhead, 0)
    return (
        '{"session_id": "size-probe", "logs": [{"message": "%s"}]}' % filler
    ).encode("utf-8")


class TestTheLimitIsConfigured:
    def test_the_app_carries_a_body_limit(self, app):
        assert app.config["MAX_CONTENT_LENGTH"] == Config.MAX_CONTENT_LENGTH

    def test_the_limit_is_a_megabyte(self):
        """Pinned, because the number is argued rather than arbitrary — see the
        rationale beside it in ``src/api/config.py``. Changing it should be a
        deliberate edit in two places, not a drift in one."""
        assert Config.MAX_CONTENT_LENGTH == 1024 * 1024


class TestAnOversizedBodyIsRefused:
    @pytest.mark.parametrize("path", [_LOGS, _REGISTER])
    def test_it_is_a_413_on_the_unauthenticated_routes(self, client, path):
        """Both routes reachable with no credentials at all, and both of them
        used to answer 500 (having declined to read the body, but only after
        the route's own exception handler had relabelled the refusal)."""
        body = _body_of_size(Config.MAX_CONTENT_LENGTH + _OVER)
        rv = client.post(path, data=body, content_type="application/json")
        assert rv.status_code == 413

    def test_the_refusal_uses_this_api_s_error_shape(self, client):
        body = _body_of_size(Config.MAX_CONTENT_LENGTH + _OVER)
        rv = client.post(_LOGS, data=body, content_type="application/json")
        payload = rv.get_json()
        assert payload["success"] is False
        assert payload["error"] == "payload_too_large"
        # A machine token in `error` is only legible to a person when `message`
        # accompanies it — the rule `MACHINE_TOKEN_ERROR` states and
        # tests/test_rate_limiter.py scans for.
        assert payload["message"].strip()

    def test_the_view_never_runs(self, client, monkeypatch):
        """The point of checking in ``before_request``: no route code executes,
        so no route's ``except Exception`` can turn the refusal into a 500 and
        no log file is opened for a body that was never accepted."""
        from src.api.routes import logs as logs_module

        opened = []
        monkeypatch.setattr(
            logs_module,
            "_maybe_cleanup",
            lambda: opened.append("cleanup"),
        )
        real_open = open

        def _spy_open(path, *args, **kwargs):
            opened.append(str(path))
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr("builtins.open", _spy_open)
        body = _body_of_size(Config.MAX_CONTENT_LENGTH + _OVER)
        rv = client.post(_LOGS, data=body, content_type="application/json")
        assert rv.status_code == 413
        assert opened == []


class TestTheHandlerBehindTheHook:
    """``handlers/error_handler.py``'s own rule is that a
    registered-but-unreachable handler is worse than none, so the 413 handler
    is exercised rather than assumed.

    It covers the case the ``before_request`` hook structurally cannot: a
    chunked body carries no ``Content-Length``, so its size is unknown until
    Werkzeug reads it and raises ``RequestEntityTooLarge`` from inside the
    view. Dispatched here the same way Flask dispatches it — a route that lets
    the exception escape — because the test client cannot easily send a
    genuinely chunked request.
    """

    def test_a_request_entity_too_large_is_answered_as_413_json(self, app):
        from werkzeug.exceptions import RequestEntityTooLarge

        with app.test_request_context(_LOGS, method="POST"):
            response = app.make_response(
                app.handle_user_exception(RequestEntityTooLarge())
            )
        assert response.status_code == 413
        payload = response.get_json()
        assert payload["error"] == "payload_too_large"
        assert payload["message"].strip()


class TestALegitimateBodyStillPasses:
    """The control. Every assertion above is satisfied by a server that
    refuses everything."""

    def test_a_body_just_under_the_limit_is_accepted(self, client, tmp_path):
        from unittest.mock import patch

        body = _body_of_size(Config.MAX_CONTENT_LENGTH - _OVER)
        with patch("src.api.routes.logs.LOGS_DIR", tmp_path):
            rv = client.post(_LOGS, data=body, content_type="application/json")
        assert rv.status_code == 200
        assert "1 log" in rv.get_json()["message"]

    def test_an_ordinary_batch_is_accepted(self, client, tmp_path):
        from unittest.mock import patch

        payload = {
            "session_id": "ordinary",
            "logs": [
                {
                    "timestamp": "2026-01-01T00:00:00Z",
                    "level": "LOG",
                    "message": "hello",
                    "url": "http://localhost:3000/",
                }
            ],
        }
        with patch("src.api.routes.logs.LOGS_DIR", tmp_path):
            rv = client.post(_LOGS, json=payload)
        assert rv.status_code == 200
