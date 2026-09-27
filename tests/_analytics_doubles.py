"""Shared doubles for the analytics tests.

A real ``AnalyticsRecorder`` with a fake writer, and a decoder for what it
flushed. Tests read back flushed rows rather than spying on ``record``: a spy
would pass for a call made with the wrong session, the rows cannot.
"""

import json
from datetime import datetime

from src.api.services.analytics import _INSERT_SQL, AnalyticsRecorder, Event
from src.api.services.session_manager import Session


class FakeWriter:
    """Collects flushed batches; raises instead when ``fail`` is set."""

    def __init__(self, fail=False):
        self.batches = []
        self.fail = fail

    def __call__(self, statements):
        if self.fail:
            raise RuntimeError("turso is down")
        self.batches.append(list(statements))


class FakeClock:
    def __init__(self, now=1_800_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def enabled_recorder(writer=None, clock=None, secret="test-secret"):
    """An enabled recorder writing to ``writer`` (a new FakeWriter by default)."""
    kwargs = {"writer": writer or FakeWriter(), "secret": secret}
    if clock is not None:
        kwargs["clock"] = clock
    recorder = AnalyticsRecorder(**kwargs)
    recorder.enabled = True
    return recorder


def inserted(writer, include_heartbeats=True):
    """(event, pid, sid, props) for every row ``writer`` received, oldest first."""
    rows = []
    for batch in writer.batches:
        for sql, args in batch:
            if sql == _INSERT_SQL:
                _ts, pid, sid, event, props = args
                if include_heartbeats or event != Event.HEARTBEAT:
                    rows.append((event, pid, sid, json.loads(props)))
    return rows


def flushed(recorder, writer, include_heartbeats=False):
    """Flush ``recorder`` and return (event, props) pairs; heartbeats only if asked."""
    recorder.flush()
    return [(event, props) for event, _, _, props in inserted(writer, include_heartbeats)]


def real_session(db_user_id="db_user_1", session_id="sid_1", **attrs):
    """A real ``Session`` with an account, as sign-in leaves it."""
    session = Session(session_id, "player_1", "jean_claire", datetime.now())
    if db_user_id is not None:
        session.db_user_id = db_user_id
    for name, value in attrs.items():
        setattr(session, name, value)
    return session
