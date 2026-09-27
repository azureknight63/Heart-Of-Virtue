"""Issue #741: log sinks that libraries install for themselves are redacted too.

``configure_logging`` puts ``_RedactSecretsFilter`` on every handler *it*
installs (#698). These tests cover the handlers it does not install:

* werkzeug attaches an unfiltered ``_ColorStreamHandler`` to the ``werkzeug``
  logger the first time it logs, when no handler in the chain accepts INFO --
  which is the default arrangement (root console at WARNING). Its
  "Error on request" traceback then reaches stderr raw.
* python-engineio / python-socketio attach an unfiltered ``StreamHandler`` to
  ``engineio.server`` / ``socketio.server`` whenever that logger's level is
  unset -- in production too (``logger=False`` still adds it, at ERROR).
* gunicorn writes ``gunicorn.error`` / ``gunicorn.access`` through its own
  handlers (``--error-logfile`` / ``--access-logfile``). Production closes
  that in ``deploy/gunicorn.conf.py``, loaded by the unit's ``-c`` flag.

Every case emits a real record through the real library path and asserts on
what reaches the stream, not on which filters are attached.
"""

import contextlib
import io
import logging
import re
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from src.api.structured_log import configure_logging

_ROOT = Path(__file__).resolve().parent.parent
_GUNICORN_CONF = _ROOT / "deploy" / "gunicorn.conf.py"

#: OpenRouter-shaped, which is the key this game actually ships with.
_SECRET = "sk-or-v1-0123456789abcdef0123456789abcdef"


def _snapshot(name):
    logger = logging.getLogger(name)
    return logger, list(logger.handlers), list(logger.filters), logger.level


def _restore(snapshot):
    logger, handlers, filters, level = snapshot
    logger.handlers[:] = handlers
    logger.filters[:] = filters
    logger.setLevel(level)


@contextlib.contextmanager
def _production_like_root():
    """Root with only configure_logging's own console, at the default WARNING.

    Under pytest root carries capture handlers at level 0, which would satisfy
    werkzeug's "is anything listening at INFO?" check and hide the leak. They
    are set aside and put back afterwards. A context manager used inside the
    test body rather than a fixture: pytest attaches its per-phase capture
    handlers to root *after* fixture setup, so a fixture could not clear them.
    """
    names = ("", "werkzeug", "engineio.server", "socketio.server")
    snapshots = [_snapshot(name) for name in names]
    import werkzeug._internal as wz_internal

    saved_wz_logger = wz_internal._logger
    root = logging.getLogger()
    root.handlers[:] = []
    for name in names[1:]:
        logger = logging.getLogger(name)
        logger.handlers[:] = []
        logger.filters[:] = []
        logger.setLevel(logging.NOTSET)
    wz_internal._logger = None
    try:
        # StreamHandler() binds sys.stderr at construction -- capsys's stream.
        configure_logging(env={"LOG_LEVEL": "WARNING"})
        yield
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
            handler.close()
        wz_internal._logger = saved_wz_logger
        for snapshot in snapshots:
            _restore(snapshot)


def test_a_werkzeug_error_on_request_never_reaches_stderr_raw(capsys):
    from werkzeug._internal import _log

    with _production_like_root():
        try:
            raise RuntimeError(f"upstream said: Authorization: {_SECRET}")
        except RuntimeError:
            # What werkzeug.serving.WSGIRequestHandler.log_error sends.
            _log("error", "Error on request:\n%s", f"Traceback ... key={_SECRET}", exc_info=True)
        # Proves the leak's precondition rather than assuming it: werkzeug
        # judged nothing in the chain to be listening at INFO.
        wz_handlers = list(logging.getLogger("werkzeug").handlers)

    err = capsys.readouterr().err
    assert "Error on request" in err, "the record never reached stderr at all"
    assert _SECRET not in err
    assert "sk-or-v1" not in err
    assert wz_handlers, "werkzeug attached no handler of its own; test is vacuous"


@pytest.mark.parametrize(
    "factory, logger_name",
    [
        ("engineio", "engineio.server"),
        ("socketio", "socketio.server"),
    ],
)
def test_the_socket_servers_own_stderr_handlers_are_redacted(
    capsys, factory, logger_name
):
    with _production_like_root():
        if factory == "engineio":
            import engineio

            engineio.Server(async_mode="threading", logger=False)
        else:
            import socketio

            socketio.Server(async_mode="threading", logger=False)

        library_handlers = list(logging.getLogger(logger_name).handlers)
        assert library_handlers, (
            f"{factory} no longer installs its own handler on {logger_name}; "
            "this test is now vacuous -- revisit the enumeration in log_redaction"
        )
        logging.getLogger(logger_name).error("post request handler error: %s", _SECRET)

    err = capsys.readouterr().err
    assert "post request handler error" in err
    assert _SECRET not in err


def _gunicorn_command_lines():
    unit = (_ROOT / "deploy" / "heart-of-virtue.service").read_text(encoding="utf-8")
    unit_command = " ".join(
        ln.rstrip("\\").strip()
        for ln in unit.splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    )
    procfile = (_ROOT / "Procfile").read_text(encoding="utf-8")
    return {"deploy/heart-of-virtue.service": unit_command, "Procfile": procfile}


@pytest.mark.parametrize("source", ["deploy/heart-of-virtue.service", "Procfile"])
def test_production_gunicorn_loads_the_redacting_config(source):
    command = _gunicorn_command_lines()[source]
    assert re.search(r"(?:-c|--config)[ =]deploy/gunicorn\.conf\.py\b", command), (
        f"{source} does not pass -c deploy/gunicorn.conf.py, so gunicorn's "
        "error/access logs are written unredacted"
    )


@pytest.fixture
def gunicorn_loggers():
    snapshots = [_snapshot(n) for n in ("gunicorn.error", "gunicorn.access")]
    # Start bare, so a pass proves the config file installed the filter rather
    # than an earlier load in the same process.
    for logger, *_ in snapshots:
        logger.filters[:] = []
    try:
        yield
    finally:
        for snapshot in snapshots:
            _restore(snapshot)


@pytest.mark.parametrize("logger_name", ["gunicorn.error", "gunicorn.access"])
def test_a_secret_logged_by_gunicorn_is_redacted_after_the_config_loads(
    gunicorn_loggers, logger_name
):
    runpy.run_path(str(_GUNICORN_CONF))

    # Stand-in for the FileHandler gunicorn's Logger.setup() attaches for
    # --error-logfile / --access-logfile: it attaches handlers only, so a
    # logger-level filter installed here is still in front of them.
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger(logger_name)
    logger.propagate = False
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        try:
            raise RuntimeError(f"engineio middleware blew up with {_SECRET}")
        except RuntimeError:
            logger.exception("Error handling request %s", f"/socket.io/?key={_SECRET}")
    finally:
        logger.removeHandler(handler)
        logger.propagate = True

    written = stream.getvalue()
    assert "Error handling request" in written
    assert "RuntimeError" in written, "the traceback was dropped, not redacted"
    assert _SECRET not in written


def test_the_gunicorn_config_does_not_import_the_app_in_the_master():
    """gunicorn execs the config in the master before forking. Importing the
    app there would load db.py's client and the LLM modules pre-fork, which is
    the one-loop-per-process trap behind #726."""
    probe = (
        "import runpy, sys; runpy.run_path(sys.argv[1]); "
        "bad = sorted(m for m in sys.modules if m == 'flask' or m.startswith(('flask.', 'src.api.app', 'src.api.db'))); "
        "print(bad); sys.exit(1 if bad else 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe, str(_GUNICORN_CONF)],
        capture_output=True,
        text=True,
        cwd=str(_ROOT),
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
