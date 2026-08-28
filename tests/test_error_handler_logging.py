"""The error handlers must log tracebacks, not print them.

``src/api/handlers/error_handler.py``'s 500 and unhandled-exception handlers
used to call ``traceback.print_exc()``. That writes straight to stderr and
never enters the logging pipeline, so ``src/api/app.py``'s
``_RedactSecretsFilter`` -- installed on every handler the app owns precisely
to keep credentials out of emitted tracebacks -- never saw the app's
highest-volume traceback source. It also meant none of those tracebacks
reached ``LOG_FILE``.

These tests were originally written into ``tests/api/test_error_handlers.py``,
which ``pytest.ini``'s ``norecursedirs`` excludes -- so they would have passed
review and never run again. They live here instead, where the suite walks.
Two consequences of the move are load-bearing:

* ``tests/api/conftest.py`` has an autouse fixture that no-ops
  ``builtins.print`` so Windows consoles don't choke on the engine's
  box-drawing output. ``logging.Formatter.formatException`` renders through
  ``traceback.print_exception``, which writes with ``print``, so under that
  fixture every formatted traceback comes out as the empty string and any
  assertion about traceback text passes vacuously. ``tests/conftest.py`` does
  not patch ``print``, so no workaround is needed here.
* ``test_the_redact_filter_now_sees_the_traceback`` asserts the traceback text
  is actually present before asserting the token is gone. That ordering is
  what keeps the test honest if a print-nulling fixture ever arrives here.
"""

import ast
import inspect
import logging

import pytest

pytest.importorskip("flask")


class TestTracebacksGoThroughLogging:
    LOGGER = "src.api.handlers.error_handler"

    #: Credential-shaped, and matched by ``app._SECRET_RE``. Not a real token.
    FAKE_TOKEN = "ghp_0000000000000000000000000000000000"

    @pytest.fixture
    def app(self):
        from flask import Flask

        from src.api.handlers.error_handler import register_error_handlers

        app = Flask(__name__)
        app.config["TESTING"] = True
        register_error_handlers(app)

        @app.route("/boom")
        def boom():
            raise RuntimeError("token leaked: " + self.FAKE_TOKEN)

        @app.route("/five-hundred")
        def five_hundred():
            from flask import abort

            abort(500)

        # Keep the module logger from inheriting a level that would drop the
        # record before any handler saw it.
        logging.getLogger(self.LOGGER).setLevel(logging.NOTSET)
        return app

    def test_an_unhandled_exception_is_logged_not_printed(self, app, caplog):
        with caplog.at_level(logging.ERROR, logger=self.LOGGER):
            assert app.test_client().get("/boom").status_code == 500

        records = [r for r in caplog.records if r.name == self.LOGGER]
        assert records, "the handler emitted no log record at all"
        # exc_info is the whole point: without it there is no traceback for
        # the redactor to scrub or the log file to keep.
        assert records[0].exc_info is not None
        assert records[0].levelno == logging.ERROR

    def test_a_500_is_logged_not_printed(self, app, caplog):
        with caplog.at_level(logging.ERROR, logger=self.LOGGER):
            assert app.test_client().get("/five-hundred").status_code == 500

        records = [r for r in caplog.records if r.name == self.LOGGER]
        assert records
        assert records[0].exc_info is not None

    def test_the_log_line_names_the_request(self, app, caplog):
        """``print_exc`` gave a traceback and nothing else, so a 500 in the
        log could not be tied to the call that produced it."""
        with caplog.at_level(logging.ERROR, logger=self.LOGGER):
            app.test_client().get("/boom")

        message = caplog.records[0].getMessage()
        assert "GET" in message
        assert "/boom" in message

    def test_the_redact_filter_now_sees_the_traceback(self, app):
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
            app.test_client().get("/boom")
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
