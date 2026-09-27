"""Secret redaction for log records, with no dependency beyond the stdlib.

Split out of :mod:`src.api.structured_log` (issue #741) so the gunicorn
*master* can load it: ``deploy/gunicorn.conf.py`` runs there before any worker
forks, and importing ``structured_log`` would drag in Flask and the request
middleware pre-fork. ``structured_log`` re-exports the names the tree already
imports from it.

A record gets redacted in one of two places:

* **On a handler** — ``structured_log.configure_logging`` puts
  :class:`_RedactSecretsFilter` on every handler it installs (#698).
* **On a logger** — :func:`redact_logger`, for loggers whose *library*
  installs handlers of its own, which ``configure_logging`` never sees. A
  logger-level filter runs in ``Logger.handle`` before the record reaches any
  handler at all: the library's own, one added later, or the root handlers the
  record propagates to. So it holds whichever order the library and
  ``configure_logging`` run in, and whatever handler the library picks. Its
  one limit: a logger's filters see only records created *on that logger*,
  not ones propagating up from a child. Every library in
  :data:`SELF_HANDLING_LOGGERS` logs through exactly the logger named there.
"""

import logging
import re

# Blunt scrub for credential-shaped substrings on their way into any log
# handler. Nothing in the tree is known to log a secret in a
# message (checked deliberately: the LLM client logs bool(api_key), never the
# value) — but provider-SDK tracebacks are not written by this tree, and this
# repo has shipped a live GITHUB_TOKEN in ``.env``, so the scrub covers the
# credential families actually present here rather than only the OpenAI shape:
#   sk-…            OpenAI / OpenRouter / Anthropic-style API keys
#   gsk_…           Groq
#   ghp_/gho_/…     GitHub OAuth + classic PATs
#   github_pat_…    GitHub fine-grained PATs
#   discord webhook the provider digest's Discord sink URL (the path IS the
#                   credential)
#   eyJ….….         JWTs, which is how the Turso/libSQL auth token is shaped
#   Bearer …        anything already framed as a bearer credential
_SECRET_RE = re.compile(
    r"""
      sk-[A-Za-z0-9_\-]{8,}
    | gsk_[A-Za-z0-9_\-]{8,}
    | gh[pousr]_[A-Za-z0-9_\-]{8,}
    | github_pat_[A-Za-z0-9_\-]{8,}
    | https://(?:\w+\.)*discord(?:app)?\.com/api/webhooks/\S+
    | eyJ[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]*
    | Bearer\s+[A-Za-z0-9._\-]{8,}
    """,
    re.VERBOSE,
)

# Used to render ``record.exc_info`` for scrubbing before any handler formats
# it. A bare Formatter's ``formatException`` is exactly what the real handlers
# would call, so the text this filter rewrites is the text they will emit.
_EXC_FORMATTER = logging.Formatter()

# Stamped on a LogRecord once _RedactSecretsFilter has scrubbed it.
_REDACTED_MARKER = "_hov_redacted"

# What every credential-shaped substring is replaced with.
_REDACTION = "[REDACTED]"


def _scrub(text):
    """``text`` with every ``_SECRET_RE`` match replaced by ``_REDACTION``."""
    return _SECRET_RE.sub(_REDACTION, text)


class _RedactSecretsFilter(logging.Filter):
    """Replace anything credential-shaped with ``[REDACTED]``.

    Installed two ways. On **every** handler
    :func:`src.api.structured_log.configure_logging` owns — console, LOG_FILE
    and JSONL alike — and, through :func:`redact_logger`, on the loggers
    whose libraries attach handlers of their own
    (:data:`SELF_HANDLING_LOGGERS`, :data:`GUNICORN_LOGGERS`). Handler filters
    run per handler, in handler order, so a
    filter missing from any one handler emits the unredacted record through
    it before the redacting one ever runs. That is not hypothetical: it is
    issue #698, where a second, unfiltered handler set installed at import
    time printed every line raw ahead of the redacted copy.

    Three payloads are scrubbed, because they travel by different routes:

    * ``record.msg`` (with ``record.args`` dropped, as they have already been
      merged in by ``getMessage()``).
    * ``record.msg`` and ``record.args`` *separately*, as text, when the args
      do not fit the format string: ``getMessage()`` raises, and
      ``Handler.handleError`` then prints the raw msg and args to stderr.
    * ``record.exc_text`` — the formatted traceback. This is the one that
      matters most. Every ``logger.exception`` / ``exc_info=True`` call under
      ``src/`` and ``ai/`` feeds it — dozens of sites across the tree, so no
      list of them written here would stay true — and the largest single
      contributor is not any route module but
      ``src/api/handlers/error_handler.py``, the app-wide 500 handler that
      every unhandled exception passes through. Any of them can surface a
      provider-SDK traceback whose frame locals or request repr carry the API
      key, and that text is rendered by ``Formatter.format`` *after* every
      filter has run. Rendering it here and caching the redacted result in
      ``exc_text`` (which ``Formatter.format`` reuses verbatim when set) is
      what puts it inside the scrub. ``stack_info`` gets the same treatment
      for the same reason.

    The ``exc_text`` cache is written only when the scrub actually changed
    something. That reuse cuts both ways: a non-empty ``exc_text`` freezes the
    traceback for *every* handler on root, so writing it unconditionally would
    take ``formatException`` away from handlers that render it differently —
    caplog's, and :class:`src.api.structured_log.JsonlFormatter`.

    Mutating the record makes it scrubbed for every handler that formats it
    afterwards as well — the safe direction to be wrong in — which is why the
    record is stamped (``_REDACTED_MARKER``) after its first pass and later
    handlers' filters skip it.
    """

    def filter(self, record):
        # One record passes this filter once per handler; after the first pass
        # it is already scrubbed. Stamped only once the scrub has finished.
        if getattr(record, _REDACTED_MARKER, False):
            return True
        try:
            message = record.getMessage()
        except Exception:
            # Bad %-format args. ``Handler.handleError`` prints the raw msg and
            # args to stderr for exactly this record, so scrub both as text.
            record.msg = _scrub(str(record.msg))
            args = record.args if isinstance(record.args, tuple) else (record.args,)
            record.args = tuple(_scrub(repr(a)) for a in args)
            message = None
        if message is not None and _SECRET_RE.search(message):
            record.msg = _scrub(message)
            record.args = ()
        self._redact_traceback(record)
        setattr(record, _REDACTED_MARKER, True)
        return True

    @staticmethod
    def _redact_traceback(record):
        """Scrub (and, if needed, materialise) the record's traceback text."""
        text = getattr(record, "exc_text", None)
        if not text and record.exc_info:
            try:
                text = _EXC_FORMATTER.formatException(record.exc_info)
            except Exception:  # pragma: no cover - defensive
                text = None
        if text:
            redacted = _scrub(text)
            if redacted != text:
                record.exc_text = redacted

        # ``stack_info`` is appended verbatim by every formatter rather than
        # cached, so an unconditional write costs nothing and hides nothing.
        stack = getattr(record, "stack_info", None)
        if stack:
            record.stack_info = _scrub(stack)


#: Loggers whose libraries attach an unfiltered handler of their own (#741).
#: Enumerated from the installed packages' ``addHandler`` call sites, not
#: guessed; re-check them when one of these dependencies changes major version:
#:
#: * ``werkzeug`` — ``werkzeug._internal._log`` adds a ``_ColorStreamHandler``
#:   (stderr) on first use when no handler in the chain accepts the logger's
#:   effective level (INFO). With the root console at the default WARNING and
#:   no LOG_JSONL_DIR, nothing does, so the dev server's "Error on request"
#:   tracebacks went to stderr raw. Dev server only.
#: * ``engineio.server`` / ``socketio.server`` — ``BaseServer.__init__`` adds a
#:   ``StreamHandler`` (stderr) whenever the logger's level is unset, at ERROR
#:   when ``logger=False``. That is production: create_app passes
#:   ``logger=app.debug``, and a gunicorn worker's stderr is the journal.
#: * ``engineio.client`` / ``socketio.client`` — the same code in the client
#:   classes. Nothing in the tree builds a client today; listed so one that
#:   does is covered.
#:
#: Checked and **not** a sink: Flask's ``default_handler`` (create_app removes
#: it, #734); urllib3 and requests (``NullHandler``); charset_normalizer (a
#: stream handler only under ``explain=True``); aiohttp and openai (CLI entry
#: points only). gunicorn's handlers belong to the master's configuration,
#: not the app's — see :data:`GUNICORN_LOGGERS`.
SELF_HANDLING_LOGGERS = (
    "werkzeug",
    "engineio.server",
    "engineio.client",
    "socketio.server",
    "socketio.client",
)

#: gunicorn's own loggers, written through ``--error-logfile`` and
#: ``--access-logfile`` by handlers gunicorn attaches. Redacted by
#: ``deploy/gunicorn.conf.py``, which the unit and the Procfile load with -c.
GUNICORN_LOGGERS = ("gunicorn.error", "gunicorn.access")


def redact_logger(logger):
    """Put :class:`_RedactSecretsFilter` on ``logger`` itself. Idempotent.

    ``logger`` is a name or a ``Logger``; the ``Logger`` is returned. See the
    module docstring for why this is a *logger* filter, not a handler filter.
    """
    if not isinstance(logger, logging.Logger):
        logger = logging.getLogger(logger)
    if not any(isinstance(f, _RedactSecretsFilter) for f in logger.filters):
        logger.addFilter(_RedactSecretsFilter())
    return logger
