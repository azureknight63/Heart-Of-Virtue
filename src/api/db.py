import logging
import os
import threading
import libsql_client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Database:
    _instance = None
    _client = None
    # Serializes the check-then-create in get_client so concurrent callers
    # (e.g. async routes running on different event loops via asgiref) can't
    # each construct a client and leak the loser of the race (issue #406).
    _client_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance

    @staticmethod
    def _close_client_quietly(client) -> None:
        """Best-effort close of a superseded client; never raises.

        The client we're replacing is usually stale precisely because its
        event loop is gone, so a clean ``await close()`` is often impossible.
        We only schedule a close when the client's own loop is still running
        (the concurrent-create case), otherwise the loop has already torn down
        its transports and there's nothing left to close.
        """
        try:
            import asyncio

            session = getattr(client, "_session", None)
            sess_loop = getattr(session, "loop", None) if session else None
            if sess_loop is not None and not sess_loop.is_closed() and sess_loop.is_running():
                asyncio.run_coroutine_threadsafe(client.close(), sess_loop)
        except Exception as exc:  # pragma: no cover - defensive cleanup
            logger.debug("Failed to close superseded db client: %s", exc)

    def get_client(self):
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        superseded = None
        with self._client_lock:
            # If client exists, check if it's usable
            if self._client is not None:
                # We need to verify if the client's loop is still active and matches
                # The http client usually has a _session.loop
                session = getattr(self._client, "_session", None)
                if session:
                    if (
                        session.closed
                        or (loop and session.loop != loop)
                        or session.loop.is_closed()
                    ):
                        # Hand the stale client off for cleanup instead of just
                        # dropping the reference (which leaks its aiohttp session).
                        superseded = self._client
                        self._client = None

            if self._client is None:
                url = os.getenv("TURSO_DATABASE_URL")
                auth_token = os.getenv("TURSO_AUTH_TOKEN")
                if not url:
                    raise ValueError("TURSO_DATABASE_URL is not set")
                self._client = libsql_client.create_client(url, auth_token=auth_token)
            client = self._client

        # Close the superseded client outside the lock (avoids holding the lock
        # across an await-scheduling call).
        if superseded is not None:
            self._close_client_quietly(superseded)
        return client

    async def execute(self, sql, params=None):
        client = self.get_client()
        return await client.execute(sql, params)

    async def batch(self, statements):
        client = self.get_client()
        return await client.batch(statements)

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None


db = Database()
