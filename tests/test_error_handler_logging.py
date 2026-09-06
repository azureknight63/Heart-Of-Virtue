"""What ``src/api/handlers/error_handler.py`` does with an error: log it, and
tell the client nothing.

Two properties, one file, because they are two halves of the same handler and
they pull against each other -- the detail has to go *somewhere* useful and
*nowhere* visible:

* The traceback reaches the logging pipeline. The handlers used to call
  ``traceback.print_exc()``, which writes straight to stderr and never enters
  logging, so ``src/api/app.py``'s ``_RedactSecretsFilter`` -- installed on
  every handler the app owns precisely to keep credentials out of emitted
  tracebacks -- never saw the app's highest-volume traceback source. It also
  meant none of those tracebacks reached ``LOG_FILE``.
* The response body carries a fixed generic message. ``abort(500,
  description=...)`` and any ``HTTPException`` built with a description hand
  the handler text that a naive implementation echoes back as ``str(error)``;
  in production that text is a connection string or a server-side path.

Both sets of tests were originally written into
``tests/api/test_error_handlers.py``, which ``pytest.ini``'s ``norecursedirs``
excludes -- so they passed review and then never ran again. They live here
instead, where the suite walks. One consequence of the move is load-bearing:
``test_the_redact_filter_now_sees_the_traceback`` asserts the traceback text is
actually *present* before asserting the token is gone. That ordering is not
decoration. ``logging.Formatter.formatException`` renders through
``traceback.print_exception``, which writes with ``print``, so a fixture that
no-ops ``builtins.print`` turns every formatted traceback into the empty
string -- and every "the secret is not in the text" assertion then holds
vacuously. Asserting presence first is what makes that failure loud.
"""

import ast
import inspect
import logging

import pytest

pytest.importorskip("flask")

#: Credential-shaped, and matched by ``app._SECRET_RE``. Not a real token.
FAKE_TOKEN = "ghp_0000000000000000000000000000000000"

#: Detail of exactly the kind an ``HTTPException`` description carries in
#: production -- a credential and a server-side path. Not a real password.
LEAKY_DETAIL = "secret-db-password=hunter2 at /etc/private/config.py"

#: The pieces of :data:`LEAKY_DETAIL` that must not appear in any response.
LEAKY_FRAGMENTS = ("secret-db-password", "hunter2", "/etc/private/config.py")

LOGGER = "src.api.handlers.error_handler"


@pytest.fixture
def error_app():
    """A bare Flask app carrying only the real error handlers.

    Deliberately not ``create_app()``: the unit under test is
    ``register_error_handlers`` on its own, and building the whole app would
    drag in the universe, CORS and the security-header hook -- none of which
    can change the answer, all of which can change whether the test runs.

    The probe routes are the three shapes a 500 handler is reached by: an
    unhandled non-HTTP exception, a bare ``abort(500)``, and a 500 carrying a
    description.
    """
    from flask import Flask

    from src.api.handlers.error_handler import register_error_handlers

    app = Flask(__name__)
    app.config["TESTING"] = True
    register_error_handlers(app)

    @app.route("/boom")
    def boom():
        raise RuntimeError("token leaked: " + FAKE_TOKEN)

    @app.route("/five-hundred")
    def five_hundred():
        from flask import abort

        abort(500)

    @app.route("/five-hundred-with-detail")
    def five_hundred_with_detail():
        from werkzeug.exceptions import InternalServerError

        raise InternalServerError(description=LEAKY_DETAIL)

    # Keep the module logger from inheriting a level that would drop the
    # record before any handler saw it.
    logging.getLogger(LOGGER).setLevel(logging.NOTSET)
    return app


class TestTracebacksGoThroughLogging:
    LOGGER = LOGGER
    FAKE_TOKEN = FAKE_TOKEN

    def test_an_unhandled_exception_is_logged_not_printed(self, error_app, caplog):
        with caplog.at_level(logging.ERROR, logger=self.LOGGER):
            assert error_app.test_client().get("/boom").status_code == 500

        records = [r for r in caplog.records if r.name == self.LOGGER]
        assert records, "the handler emitted no log record at all"
        # exc_info is the whole point: without it there is no traceback for
        # the redactor to scrub or the log file to keep.
        assert records[0].exc_info is not None
        assert records[0].levelno == logging.ERROR

    def test_a_500_is_logged_not_printed(self, error_app, caplog):
        with caplog.at_level(logging.ERROR, logger=self.LOGGER):
            assert error_app.test_client().get("/five-hundred").status_code == 500

        records = [r for r in caplog.records if r.name == self.LOGGER]
        assert records
        assert records[0].exc_info is not None

    def test_the_log_line_names_the_request(self, error_app, caplog):
        """``print_exc`` gave a traceback and nothing else, so a 500 in the
        log could not be tied to the call that produced it.

        Filtered by logger name like its two siblings: a stray warning from
        any other logger would otherwise land at index 0 and fail this on
        grounds that have nothing to do with what it checks.
        """
        with caplog.at_level(logging.ERROR, logger=self.LOGGER):
            error_app.test_client().get("/boom")

        records = [r for r in caplog.records if r.name == self.LOGGER]
        assert records, "the handler emitted no log record at all"
        message = records[0].getMessage()
        assert "GET" in message
        assert "/boom" in message

    def test_the_redact_filter_now_sees_the_traceback(self, error_app):
        """The bypass this closes, asserted end to end: a credential in the
        traceback text must come out ``[REDACTED]`` once the record travels
        through a handler carrying the filter."""
        from src.api.app import _RedactSecretsFilter

        emitted = []

        class _Capture(logging.Handler):
            def emit(self, record):
                emitted.append(self.format(record))

        handler = _Capture()
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler.addFilter(_RedactSecretsFilter())

        logger = logging.getLogger(self.LOGGER)
        logger.addHandler(handler)
        try:
            error_app.test_client().get("/boom")
        finally:
            logger.removeHandler(handler)

        assert emitted, "no record reached the filtered handler"
        text = "\n".join(emitted)
        # Assert the traceback is here BEFORE asserting the token is not: if
        # something ever nulls ``print`` for this directory, formatException
        # yields "" and every later assertion would hold vacuously.
        assert "Traceback (most recent call last)" in text
        assert self.FAKE_TOKEN not in text
        assert "[REDACTED]" in text

    def test_no_handler_prints_a_traceback_to_stderr(self):
        """Structural guard. A future edit that reintroduces
        ``traceback.print_exc()`` puts the app's busiest traceback source back
        outside the redactor, and no response-shape assertion would notice.

        Parsed rather than grepped: the module comment deliberately names the
        call it replaced, and a substring scan cannot tell prose from code.
        """
        from src.api.handlers import error_handler

        tree = ast.parse(inspect.getsource(error_handler))
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert "print_exc" not in called
        assert "exception" in called, "nothing logs the traceback at all"
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert "traceback" not in imported


class TestTheClientIsToldNothing:
    """The other half: what the handler logged must not be in the body.

    This is the only place in the suite that asserts it. The assertion existed
    before, in ``tests/api/test_error_handlers.py`` -- a directory
    ``norecursedirs`` skips, so for as long as it lived there it was a security
    claim nothing checked. ``InternalServerError`` still appears in no other
    test module.
    """

    def test_a_500_description_does_not_reach_the_client(self, error_app):
        """``abort(500, description=...)`` and any hand-built
        ``InternalServerError`` hand the handler text that ``str(error)`` would
        echo -- Werkzeug's own default error page prints it verbatim, and the
        first draft of a JSON handler usually copies that.

        Asserted over the whole serialised body, not just ``message``: a
        handler that moved the detail into ``error``, or added a ``detail``
        key, would still have leaked it, and a field-scoped assertion would
        have called that a pass.
        """
        response = error_app.test_client().get("/five-hundred-with-detail")
        assert response.status_code == 500

        body = response.get_data(as_text=True)
        # Non-vacuity: an empty or unrendered body satisfies every "not in"
        # below without the handler having done anything right.
        assert "Internal server error" in body
        for fragment in LEAKY_FRAGMENTS:
            assert fragment not in body, (
                "the 500 handler echoed the exception description to the "
                f"client: {fragment!r} is in the response body"
            )

        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "Internal server error"
        assert data["message"] == "An unexpected error occurred"

    def test_an_unhandled_exceptions_text_does_not_reach_the_client(self, error_app):
        """The same property on the other handler. ``/boom`` raises a
        ``RuntimeError`` whose message carries a credential-shaped token, which
        is what an exception raised near a config load actually looks like."""
        response = error_app.test_client().get("/boom")
        assert response.status_code == 500

        body = response.get_data(as_text=True)
        assert "Internal server error" in body
        assert FAKE_TOKEN not in body
        assert "token leaked" not in body

    def test_every_error_response_carries_a_string_message(self, error_app):
        """The frontend renders ``message`` directly, so a handler that omitted
        it -- or set it to a dict -- puts ``undefined`` on screen."""
        client = error_app.test_client()
        for path in ("/no-such-route", "/five-hundred", "/boom"):
            data = client.get(path).get_json()
            assert isinstance(data.get("message"), str) and data["message"], path
