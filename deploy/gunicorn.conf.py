"""gunicorn configuration for production: redact secrets in gunicorn's own logs.

Loaded with ``-c deploy/gunicorn.conf.py`` by the systemd unit
(``deploy/heart-of-virtue.service``) and the Procfile, which
tests/test_log_redaction_foreign_sinks.py holds to it. Every other setting
stays on the command line, where tests/test_npc_chat_turn_budget.py reads it.

Why (issue #741): ``--error-logfile`` and ``--access-logfile`` are written by
handlers gunicorn attaches to ``gunicorn.error`` / ``gunicorn.access``, not by
anything ``src.api.structured_log.configure_logging`` installs, so they sat
outside the secret-redaction filter. An exception that escapes the Flask app
-- in engineio's middleware, say -- is logged by the worker as "Error handling
request" with its full traceback, straight into error.log.

How: the filter goes on the two *loggers*, not on gunicorn's handlers.
gunicorn's ``Logger.setup()`` (re)attaches handlers only -- at boot and again
on every HUP -- and never touches logger filters, so a logger filter stays in
front of whichever file, stream or syslog handler it picks. Deliberately not
``logconfig_dict``: any dictConfig there reconfigures ``gunicorn.error`` with
its own handler list, replacing the ``--error-logfile`` handler, so the log
paths would have to move out of the unit and into this file.

This file runs in the gunicorn *master*, before workers fork, and workers
inherit the filtered loggers. It must therefore stay light: it imports
``src.api.log_redaction`` (stdlib only), never ``src.api.app`` or anything that
loads Flask, the database client or the LLM modules pre-fork.
"""

import sys
from pathlib import Path

# gunicorn puts its chdir (the unit's WorkingDirectory) on sys.path before it
# loads this file; this makes the import independent of that detail.
_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.api.log_redaction import GUNICORN_LOGGERS, redact_logger  # noqa: E402

for _name in GUNICORN_LOGGERS:
    redact_logger(_name)
