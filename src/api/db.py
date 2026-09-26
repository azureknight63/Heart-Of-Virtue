import asyncio
import logging
import os
import threading
import libsql_client

from src.env_bootstrap import load_project_env

# Not a bare ``load_dotenv()``. That resolves ``.env`` through ``find_dotenv()``,
# which walks up from the *working directory*, so a process started anywhere but
# the project root loads nothing at all and boots with none of the project's
# settings — no error, no log line. ``load_project_env`` resolves from
# ``__file__`` and cannot miss.
#
# This module in particular: ``create_app()`` -> routes -> auth_service -> db
# makes it the first ``.env`` load in almost every process that is not one of
# the two entry points, the test suite included. That is why ``tests/conftest.py``
# has to blank the provider credentials and ``LOG_LEVEL`` before importing it.
load_project_env()

logger = logging.getLogger(__name__)


class Database:
    """The process's one Turso client, running on ONE event loop of its own.

    Every request's async view runs through ``asgiref.async_to_sync``, which
    gives it its own event loop, and an aiohttp-backed libsql client is bound
    to the loop it was built on. This used to keep one client and replace it
    whenever the calling loop differed -- closing it under whichever request
    was still awaiting a query on it. On production two concurrent calls were
    enough for one to fail (2026-09-26: 2 concurrent calls under eventlet lost
    1; 16 on threads lost 15, Python 3.12 and 3.13 alike), and every replaced
    session was dropped unclosed (#728).

    Now the client lives on a dedicated loop in a daemon thread, created on
    first use, and every query is submitted to that loop. Callers keep the
    ``async`` API: they await a future that the database loop resolves, so any
    number of request loops share one client and one connection pool.
    """

    _instance = None
    # Instance attributes once set; these are the unset defaults. Guarded by
    # _client_lock: the check-then-create must not race (issue #406).
    _client = None
    _loop = None
    _loop_thread = None
    _client_lock = threading.Lock()
    #: How long a request waits, holding _client_lock, for the database loop to
    #: build the client. Building is object construction with no I/O, so this
    #: only fires if the loop is wedged -- and then it must fail the request
    #: rather than queue every other one behind the lock forever.
    _BUILD_TIMEOUT_SECONDS = 30

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance

    def _db_loop(self) -> asyncio.AbstractEventLoop:
        """The database loop, started on first use. Call with _client_lock held."""
        if self._loop is None or self._loop.is_closed() or not self._loop_thread.is_alive():
            loop = asyncio.new_event_loop()
            thread = threading.Thread(target=loop.run_forever, name="hov-db-loop", daemon=True)
            thread.start()
            self._loop, self._loop_thread = loop, thread
            self._client = None  # a client is bound to the loop it was built on
        return self._loop

    def get_client(self):
        """The shared client, built on first use.

        Raises ValueError("TURSO_DATABASE_URL is not set") when unconfigured:
        routes/saves.py and services/auth_service.py catch exactly that.
        """
        return self._client_and_loop()[0]

    def _client_and_loop(self):
        with self._client_lock:
            loop = self._db_loop()
            if self._client is None:
                url = os.getenv("TURSO_DATABASE_URL")
                auth_token = os.getenv("TURSO_AUTH_TOKEN")
                if not url:
                    raise ValueError("TURSO_DATABASE_URL is not set")

                async def build():
                    # Built on the database loop, so its session binds there.
                    return libsql_client.create_client(url, auth_token=auth_token)

                self._client = asyncio.run_coroutine_threadsafe(build(), loop).result(
                    timeout=self._BUILD_TIMEOUT_SECONDS
                )
            return self._client, loop

    async def _on_db_loop(self, call):
        client, loop = self._client_and_loop()
        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(call(client), loop))

    async def execute(self, sql, params=None):
        return await self._on_db_loop(lambda client: client.execute(sql, params))

    async def batch(self, statements):
        return await self._on_db_loop(lambda client: client.batch(statements))

    async def close(self):
        """Close the client; the next query reconnects. The loop thread stays."""
        with self._client_lock:
            client, loop = self._client, self._loop
            self._client = None
        if client is not None and loop is not None and not loop.is_closed():
            await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(client.close(), loop))


db = Database()
