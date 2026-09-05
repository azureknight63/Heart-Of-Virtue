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
  That is what stops the buffering, and it is not enough by itself. What it
  does when the cap is hit depends on how the size was declared, and neither
  answer is a 413 on its own:

  - with a ``Content-Length``, ``get_input_stream`` raises
    ``RequestEntityTooLarge`` where the body is read, which for every route in
    this API is inside a ``try:`` whose ``except Exception`` answers with that
    route's own 500;
  - without one (a chunked body), it raises nothing at all.
    ``LimitedStream.readall`` stops at the cap and returns the truncated
    bytes, so the route sees the first megabyte of a ten-megabyte body and
    answers 400 "malformed". This file used to assert the opposite via a
    hand-dispatched exception, which is why it never noticed.

* ``_register_request_limits`` in ``src/api/app.py`` covers both: the declared
  length in front of the view function, and the streamed one by reading the
  (already-bounded) body itself and refusing it if it reached the cap. Either
  way the client gets a 413 in this API's error shape.
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


def _post_chunked(client, path, body):
    """POST ``body`` the way a chunked client does: no usable Content-Length.

    ``Transfer-Encoding: chunked`` is what makes ``request.content_length``
    None (``werkzeug.sansio.utils.get_content_length`` returns None whenever
    that header says chunked, regardless of CONTENT_LENGTH), and
    ``wsgi.input_terminated`` is the flag a server sets to say it has framed
    the stream itself — Werkzeug's own dev server sets exactly this pair for a
    chunked request, and gunicorn sets the flag for every request. Without the
    flag Werkzeug hands the app an empty stream and there is no body to bound,
    which is why the environ override is part of the fixture rather than
    incidental to it.
    """
    return client.post(
        path,
        data=body,
        content_type="application/json",
        headers={"Transfer-Encoding": "chunked"},
        environ_overrides={"wsgi.input_terminated": True},
    )


class TestAChunkedBodyIsRefusedToo:
    """The half ``Content-Length`` cannot cover, driven through a real route.

    Werkzeug raises nothing here — it truncates — so before this was bounded,
    an unbounded chunked POST reached the view as a mangled megabyte and was
    answered 400 "No logs provided". These tests send a genuinely
    length-less body to the real endpoints; nothing is dispatched by hand.
    """

    @pytest.mark.parametrize("path", [_LOGS, _REGISTER])
    def test_it_is_a_413_on_the_unauthenticated_routes(self, client, path):
        rv = _post_chunked(
            client, path, _body_of_size(Config.MAX_CONTENT_LENGTH + _OVER)
        )
        assert rv.status_code == 413
        payload = rv.get_json()
        assert payload["success"] is False
        assert payload["error"] == "payload_too_large"
        assert payload["message"].strip()

    def test_the_view_never_runs(self, client, monkeypatch):
        from src.api.routes import logs as logs_module

        opened = []
        real_open = open
        monkeypatch.setattr(
            logs_module, "_maybe_cleanup", lambda: opened.append("cleanup")
        )
        monkeypatch.setattr(
            "builtins.open",
            lambda path, *a, **kw: (
                opened.append(str(path)),
                real_open(path, *a, **kw),
            )[1],
        )
        rv = _post_chunked(
            client, _LOGS, _body_of_size(Config.MAX_CONTENT_LENGTH + _OVER)
        )
        assert rv.status_code == 413
        assert opened == []

    def test_the_body_is_not_buffered_past_the_cap(self, client, monkeypatch):
        """The DoS half, asserted rather than assumed.

        A hook that read the whole stream to measure it would answer 413 and
        satisfy every test above while doing the exact thing the cap exists to
        prevent. ``request.stream`` is the one place the bytes can arrive, so
        count them there.
        """
        from werkzeug.wrappers import Request

        read_total = []
        real_get_data = Request.get_data

        def _counting_get_data(self, *args, **kwargs):
            rv = real_get_data(self, *args, **kwargs)
            read_total.append(len(rv))
            return rv

        monkeypatch.setattr(Request, "get_data", _counting_get_data)
        rv = _post_chunked(
            client, _LOGS, _body_of_size(Config.MAX_CONTENT_LENGTH * 4)
        )
        assert rv.status_code == 413
        assert read_total, "the hook never read the body"
        assert max(read_total) <= Config.MAX_CONTENT_LENGTH


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

    def test_a_chunked_body_under_the_limit_is_accepted(self, client, tmp_path):
        """The control for the chunked branch specifically.

        That branch reads the body itself, so "refuse every request with no
        Content-Length" would pass every 413 assertion in this file. A chunked
        POST under the cap has to still reach the view *and* still parse there
        — which is also the proof that pre-reading with ``cache=True`` leaves
        the route's own ``get_json`` a body to find."""
        from unittest.mock import patch

        body = _body_of_size(Config.MAX_CONTENT_LENGTH - _OVER)
        with patch("src.api.routes.logs.LOGS_DIR", tmp_path):
            rv = _post_chunked(client, _LOGS, body)
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


class TestTheSocketIOHalf:
    """``/socket.io/*`` is bounded separately, because it is not bounded here.

    ``flask_socketio`` sets itself as ``app.wsgi_app`` and answers those paths
    inside the middleware, so Flask's request dispatch -- and every
    ``before_request`` with it, including the one above -- never runs for them.
    That is a real hole in the claim "this API bounds request bodies", and the
    thing that closes it is ``max_http_buffer_size`` on the Engine.IO server.
    """

    def test_the_socketio_buffer_is_pinned_to_the_same_limit(self, app):
        assert (
            app.socketio.server.eio.max_http_buffer_size
            == Config.MAX_CONTENT_LENGTH
        )

    def test_the_before_request_hook_really_is_bypassed(self, app):
        """The documented reason the pin above has to exist.

        If a ``/socket.io/`` request did reach Flask, an over-limit
        Content-Length would come back as this API's 413 -- and the comment in
        ``_init_socketio`` would be describing a hazard that isn't there. It
        does not, so it isn't a comment, it's a finding.
        """
        oversized = {"CONTENT_LENGTH": str(Config.MAX_CONTENT_LENGTH * 2)}
        client = app.test_client()

        # Control: the same oversized declaration on an ordinary route.
        assert client.post(_LOGS, environ_overrides=oversized).status_code == 413

        rv = client.post(
            "/socket.io/?EIO=4&transport=polling", environ_overrides=oversized
        )
        assert rv.status_code != 413
        body = rv.get_data(as_text=True)
        assert "payload_too_large" not in body


class TestABodylessPostIsNotRead:
    """The hook must not touch the stream of a request that has no body.

    The chunked branch is gated on ``Transfer-Encoding: chunked`` rather than
    on "no Content-Length", and those are not the same condition: a request
    carrying neither header has no body at all. Reading such a request's stream
    is how a WSGI server whose length-less body reader waits for EOF blocks on
    a POST that already finished arriving -- a hang, in production, on a code
    path this repo cannot exercise from a test client. Hence a test that the
    read does not happen, rather than a comment saying it must not.
    """

    @staticmethod
    def _bodyless_post(path):
        """A POST with no Content-Length, no Transfer-Encoding, and a server
        that says it framed the stream (which gunicorn says for everything).

        Built by hand and fed to the WSGI callable directly, because the test
        client cannot express it: ``Client.open`` rebuilds whatever environ it
        is handed through ``EnvironBuilder``, which restores ``CONTENT_LENGTH``
        (as 0) and drops ``wsgi.input_terminated``. The first version of this
        test went through the client and passed with the guard deleted -- a
        test that could not fail, which is the defect this whole file is a
        correction for.
        """
        from werkzeug.test import EnvironBuilder

        environ = EnvironBuilder(path, method="POST").get_environ()
        environ.pop("CONTENT_LENGTH", None)
        environ.pop("CONTENT_TYPE", None)
        environ["wsgi.input_terminated"] = True
        return environ

    def test_the_environ_is_the_one_being_claimed(self, app):
        """Non-vacuity for the fixture above: if any of these three came back,
        the branch under test would not be the branch reached."""
        from flask import request

        environ = self._bodyless_post(_LOGS)
        with app.request_context(environ):
            assert request.content_length is None
            assert request.headers.get("Transfer-Encoding") is None
            assert "wsgi.input_terminated" in request.environ

    def test_the_stream_is_never_touched(self, app, monkeypatch):
        from werkzeug.test import run_wsgi_app
        from werkzeug.wrappers import Request

        reads = []
        real_get_data = Request.get_data

        def _spy_get_data(self, *args, **kwargs):
            reads.append(self.path)
            return real_get_data(self, *args, **kwargs)

        monkeypatch.setattr(Request, "get_data", _spy_get_data)
        _body, status, _headers = run_wsgi_app(app, self._bodyless_post(_LOGS))

        # The route answers on its own terms (no logs in an empty body).
        assert status.startswith("400")
        assert reads == []
