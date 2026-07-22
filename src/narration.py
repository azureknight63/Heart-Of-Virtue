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
import logging
import re

from neotermcolor import colored as _neo_colored

logger = logging.getLogger(__name__)

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
# Live callbacks invoked with each structured entry as it is emitted. Used by the
# combat adapter to attribute animations to the active entity in real time.
_listeners: "contextvars.ContextVar[tuple]" = contextvars.ContextVar(
    "narration_listeners", default=()
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
    if clean.strip():
        entry = {"text": clean, "type": mtype}
        if color:
            entry["color"] = color
        if attrs:
            entry["attrs"] = list(attrs)
        if meta:
            entry.update(meta)
        buf = _buffer.get()
        if buf is not None:
            buf.append(entry)
        for cb in _listeners.get():
            try:
                cb(entry)
            except Exception:
                logger.exception(
                    "narration listener %r raised while handling entry %r", cb, entry
                )
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


# --- Staged conversation authoring ------------------------------------------
# The event-dialog "conversation mode" renders character portraits next to prose.
# Authors tag spoken beats with a speaker + emotion and stage characters in/out;
# the API layer (game_service) reads these structured entries to build a
# ``segments`` array and a ``conversation`` roster for the frontend. None of this
# affects plain ``narrate``/``cprint`` output, so untagged events render as before.

#: The fixed portrait emotion vocabulary. Unknown values normalize to "neutral".
EMOTIONS = ("neutral", "happy", "sad", "angry", "surprised", "skeptical", "concerned", "curious")


def _norm_emotion(emotion):
    """Coerce an emotion to one of :data:`EMOTIONS`, defaulting to ``"neutral"``."""
    e = (emotion or "neutral").strip().lower()
    return e if e in EMOTIONS else "neutral"


def _emit_control(entry):
    """Append a pre-built structured entry directly to the active capture buffer.

    Unlike :func:`narrate`, this does not require display ``text``, so it suits
    stage/control messages (conversation begin/end, character enter/exit). It
    never echoes to stdout.
    """
    buf = _buffer.get()
    if buf is not None:
        buf.append(entry)
    for cb in _listeners.get():
        try:
            cb(entry)
        except Exception:
            logger.exception(
                "narration listener %r raised while handling control entry %r", cb, entry
            )


def say(
    text,
    speaker,
    emotion="neutral",
    *,
    reactions=None,
    enter=None,
    leave=None,
    thought=False,
    color=None,
    attrs=None,
    **meta,
):
    """Emit a spoken dialogue beat attributed to ``speaker`` with an ``emotion``.

    :param reactions: optional ``{char_id: emotion}`` applied to listening
        characters on this beat (their faces persist until changed again). Works
        the same whether the beat is spoken or a ``thought`` — pass it whenever a
        strong-emotion thought should visibly land on another character's face;
        omit it (the default) for a private thought no one reacts to.
    :param enter: optional stage-enter op(s) attached to this beat — a dict (or
        list of dicts) shaped like :func:`enter_character`'s entry.
    :param leave: optional stage-exit op(s) attached to this beat; maps to the
        wire field ``exit`` (a dict or list of dicts like :func:`exit_character`).
    :param thought: when ``True``, marks this beat as ``speaker``'s internal
        thought rather than spoken dialogue — the client renders it italicized
        without quote marks while the speaker's portrait stays fully active.
    """
    extra = {"speaker": speaker, "emotion": _norm_emotion(emotion)}
    if reactions:
        extra["reactions"] = {k: _norm_emotion(v) for k, v in reactions.items()}
    if enter:
        extra["enter"] = enter if isinstance(enter, list) else [enter]
    if leave:
        extra["exit"] = leave if isinstance(leave, list) else [leave]
    if thought:
        extra["thought"] = True
    extra.update(meta)
    narrate(text, color=color, attrs=attrs, mtype="dialogue", **extra)


def begin_conversation(cast):
    """Open a staged conversation with an initial cast roster.

    :param cast: iterable of members, each either an ``(id, side, emotion)``
        tuple or a dict with keys ``id``/``speaker``, ``side``, ``emotion``,
        ``name``. ``side`` may be ``"left"``/``"right"`` or ``None`` to defer to
        the party-rule default (party → left, non-party → right) resolved by the
        API layer.
    """
    roster = []
    for member in cast:
        if isinstance(member, dict):
            cid = member.get("id") or member.get("speaker")
            roster.append(
                {
                    "id": cid,
                    "name": member.get("name") or cid,
                    "side": member.get("side"),
                    "emotion": _norm_emotion(member.get("emotion")),
                }
            )
        else:
            cid = member[0]
            side = member[1] if len(member) > 1 else None
            emotion = member[2] if len(member) > 2 else "neutral"
            roster.append(
                {
                    "id": cid,
                    "name": cid,
                    "side": side,
                    "emotion": _norm_emotion(emotion),
                }
            )
    _emit_control({"type": "conversation_begin", "cast": roster})


def enter_op(speaker, side=None, emotion="neutral", transition="fade", name=None):
    """Build a stage-enter op dict without emitting it.

    Use this to construct the ``enter=`` argument to :func:`say` (attaching the
    entrance to a spoken/thought beat) instead of hand-writing the dict literal.
    For a standalone entrance not tied to a beat, call :func:`enter_character`,
    which emits this same shape immediately.

    :param side: ``"left"``/``"right"`` or ``None`` to defer to the party-rule
        default resolved by the API layer.
    :param transition: ``"fade"`` (default) or ``"instant"``.
    """
    return {
        "id": speaker,
        "name": name or speaker,
        "side": side,
        "emotion": _norm_emotion(emotion),
        "transition": transition,
    }


def exit_op(speaker, transition="fade", span=None):
    """Build a stage-exit op dict without emitting it.

    Use this to construct the ``leave=`` argument to :func:`say` (attaching the
    exit to a spoken/thought beat) instead of hand-writing the dict literal.
    For a standalone exit not tied to a beat, call :func:`exit_character`, which
    emits this same shape immediately.

    :param transition: ``"fade"`` (default) or ``"instant"``.
    :param span: optional number of subsequent advances over which a ``fade``
        steps out; omit for a fixed-duration fade.
    """
    entry = {"id": speaker, "transition": transition}
    if span is not None:
        entry["span"] = span
    return entry


def enter_character(
    speaker, side=None, emotion="neutral", transition="fade", name=None
):
    """Bring a character onto the conversation stage mid-scene.

    :param side: ``"left"``/``"right"`` or ``None`` to defer to the party-rule
        default resolved by the API layer.
    :param transition: ``"fade"`` (default) or ``"instant"``.
    """
    _emit_control({"type": "stage_enter", **enter_op(speaker, side, emotion, transition, name)})


def exit_character(speaker, transition="fade", span=None):
    """Remove a character from the conversation stage mid-scene.

    :param transition: ``"fade"`` (default) or ``"instant"``.
    :param span: optional number of subsequent advances over which a ``fade``
        steps out; omit for a fixed-duration fade.
    """
    _emit_control({"type": "stage_exit", **exit_op(speaker, transition, span)})


def end_conversation():
    """Close the staged conversation; subsequent beats render without the stage."""
    _emit_control({"type": "conversation_end"})


class capture_narration:
    """Context manager that collects narration into a fresh buffer.

    Suppresses the stdout echo by default so the API receives only structured
    messages. Pass ``echo=True`` to also keep mirroring to stdout.

    Usage::

        with capture_narration() as messages:
            player.do_something()
        # messages is a list of structured dicts
    """

    def __init__(self, echo=False, listener=None):
        self._echo = echo
        self._listener = listener
        self._buf = None
        self._buf_token = None
        self._echo_token = None
        self._listener_token = None

    def __enter__(self):
        self._buf = []
        self._buf_token = _buffer.set(self._buf)
        self._echo_token = _echo_stdout.set(self._echo)
        if self._listener is not None:
            self._listener_token = _listeners.set(_listeners.get() + (self._listener,))
        return self._buf

    def __exit__(self, *exc):
        if self._listener_token is not None:
            _listeners.reset(self._listener_token)
        _echo_stdout.reset(self._echo_token)
        _buffer.reset(self._buf_token)
        return False


def collect():
    """Return a copy of the active buffer's messages (empty list if none active)."""
    buf = _buffer.get()
    return list(buf) if buf is not None else []
