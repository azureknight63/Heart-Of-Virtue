"""Structured narration sink — the engine's player-facing message channel.

This module replaces direct terminal output (``neotermcolor`` ``print``/``cprint``).
Engine code calls :func:`narrate` / :func:`cprint`; each message is recorded as a
structured dict into a context-local buffer that the web API reads directly — no
more scraping ``stdout`` or parsing ANSI text back into JSON.

When no capture context is active (e.g. unit tests, or ad-hoc debugging), messages
also echo to ``stdout`` so existing ``capsys``-based assertions keep working. The
API wraps engine calls in :class:`capture_narration`, which collects structured
messages and suppresses the stdout echo.
"""

import contextvars
import re

from neotermcolor import colored as _neo_colored

# Strips ANSI escape codes so the structured ``text`` field is clean.
_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Context-local buffer of message dicts. ``None`` means "no active capture".
_buffer: "contextvars.ContextVar[list | None]" = contextvars.ContextVar(
    "narration_buffer", default=None
)
# Whether to also echo plain text to stdout. Disabled inside capture_narration.
_echo_stdout: "contextvars.ContextVar[bool]" = contextvars.ContextVar(
    "narration_echo_stdout", default=True
)


def colored(text, color=None, on_color=None, attrs=None):
    """Compatibility shim for ``neotermcolor.colored`` (returns ANSI-wrapped str).

    Inline ``colored(...)`` calls inside larger strings keep rendering as before;
    :func:`narrate` strips the ANSI when recording the structured ``text`` field.
    """
    return _neo_colored(str(text), color, on_color, attrs)


def narrate(*parts, color=None, attrs=None, mtype="narration", sep=" ", **meta):
    """Emit a narration message.

    Accepts one or more positional parts which are joined like :func:`print`
    (with ``sep``), so converted ``print(a, b)`` calls behave as before. Records a
    structured ``{"text", "type", ...}`` entry into the active capture buffer (if
    any) and/or echoes to stdout when no capture is active.

    :param parts: message text fragment(s); joined with ``sep``. Fragments may
        contain inline ANSI from :func:`colored`.
    :param color: optional top-level color name for the whole message.
    :param attrs: optional list of style attributes (e.g. ``["bold"]``).
    :param mtype: message category (``"narration"``, ``"combat"``, ...).
    :param meta: extra structured fields merged into the entry.
    """
    raw = sep.join("" if p is None else str(p) for p in parts)
    clean = _ANSI_ESCAPE.sub("", raw)
    buf = _buffer.get()
    if buf is not None and clean.strip():
        entry = {"text": clean, "type": mtype}
        if color:
            entry["color"] = color
        if attrs:
            entry["attrs"] = list(attrs)
        if meta:
            entry.update(meta)
        buf.append(entry)
    if _echo_stdout.get():
        # Mirror to stdout for non-API contexts (unit tests / debugging).
        if color and clean.strip():
            print(_neo_colored(clean, color, attrs=attrs))
        else:
            print(raw)


def cprint(text="", color=None, on_color=None, attrs=None, **kwargs):
    """Drop-in for ``neotermcolor.cprint``, routed through the narration sink."""
    narrate(text, color=color, attrs=attrs)


def emit(text="", color=None, **meta):
    """Alias for :func:`narrate` for callers that prefer a non-print-style name."""
    narrate(text, color=color, **meta)


class capture_narration:
    """Context manager that collects narration into a fresh buffer.

    Suppresses the stdout echo by default so the API receives only structured
    messages. Pass ``echo=True`` to also keep mirroring to stdout.

    Usage::

        with capture_narration() as messages:
            player.do_something()
        # messages is a list of structured dicts
    """

    def __init__(self, echo=False):
        self._echo = echo
        self._buf = None
        self._buf_token = None
        self._echo_token = None

    def __enter__(self):
        self._buf = []
        self._buf_token = _buffer.set(self._buf)
        self._echo_token = _echo_stdout.set(self._echo)
        return self._buf

    def __exit__(self, *exc):
        _buffer.reset(self._buf_token)
        _echo_stdout.reset(self._echo_token)
        return False


def collect():
    """Return a copy of the active buffer's messages (empty list if none active)."""
    buf = _buffer.get()
    return list(buf) if buf is not None else []
