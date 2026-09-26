"""Concurrent requests must not break each other's database calls.

Every async route runs through ``asgiref.async_to_sync``, which gives each
request its own event loop. ``Database`` used to keep ONE client and replace it
whenever the calling loop differed from the client's, closing the old one --
while another request was still awaiting a query on it. On production
(2026-09-26, read-only probe, ``SELECT 1``): 2 concurrent calls under eventlet
-> 1 failed with RuntimeError; 16 concurrent calls on threads -> 15 failed with
CancelledError, on Python 3.12 and 3.13 alike. Two players saving at the same
moment was enough.

The fake client below fails a query whose client was closed under it, which is
what aiohttp does to an in-flight request when its session closes.
"""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from asgiref.sync import async_to_sync

import src.api.db as db_module
from src.api.db import Database

CALLERS = 8


class _Session:
    def __init__(self):
        self.closed = False


class _FakeLibsqlClient:
    created = []

    def __init__(self):
        self._session = _Session()
        _FakeLibsqlClient.created.append(self)

    async def execute(self, sql, params=None):
        await asyncio.sleep(0.05)  # a network round trip, long enough to overlap
        if self._session.closed:
            raise RuntimeError("Session is closed")
        return ("rows-for", sql)

    async def batch(self, statements):
        await asyncio.sleep(0.01)
        if self._session.closed:
            raise RuntimeError("Session is closed")
        return list(statements)

    async def close(self):
        self._session.closed = True


@pytest.fixture
def fresh_db(monkeypatch):
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://fake.invalid")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "")
    _FakeLibsqlClient.created = []
    monkeypatch.setattr(db_module.libsql_client, "create_client", lambda url, auth_token=None: _FakeLibsqlClient())
    # A private instance: the module singleton is shared with every other test.
    return object.__new__(Database)


def _sync(make_coroutine):
    """``async_to_sync`` over a real coroutine function, as a view is."""
    async def view():
        return await make_coroutine()
    return async_to_sync(view)


def _concurrently(fn, n=CALLERS):
    start = threading.Barrier(n)

    def call(_):
        start.wait()
        try:
            return ("ok", fn())
        except BaseException as exc:  # CancelledError is a BaseException
            return (type(exc).__name__, str(exc))

    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(call, range(n)))


def test_concurrent_requests_on_their_own_loops_all_succeed(fresh_db):
    results = _concurrently(_sync(lambda: fresh_db.execute("SELECT 1")))

    assert results == [("ok", ("rows-for", "SELECT 1"))] * CALLERS, results


def test_concurrent_requests_share_one_client(fresh_db):
    # One client is also one connection pool: rebuilding per request paid a
    # fresh TLS handshake to Turso every time and dropped the old session
    # unclosed ("Unclosed client session", #728).
    _concurrently(_sync(lambda: fresh_db.execute("SELECT 1")))
    _concurrently(_sync(lambda: fresh_db.batch(["SELECT 1"])))

    assert len(_FakeLibsqlClient.created) == 1
    assert not _FakeLibsqlClient.created[0]._session.closed


def test_close_closes_the_client_and_the_next_call_reconnects(fresh_db):
    async def first():
        await fresh_db.execute("SELECT 1")
        await fresh_db.close()

    async_to_sync(first)()
    assert _FakeLibsqlClient.created[0]._session.closed

    assert _sync(lambda: fresh_db.execute("SELECT 2"))() == ("rows-for", "SELECT 2")
    assert len(_FakeLibsqlClient.created) == 2


def test_an_unset_url_still_raises_value_error(monkeypatch):
    # routes/saves.py and auth_service.py catch exactly this.
    monkeypatch.setenv("TURSO_DATABASE_URL", "")
    with pytest.raises(ValueError, match="TURSO_DATABASE_URL is not set"):
        _sync(lambda: object.__new__(Database).execute("SELECT 1"))()
