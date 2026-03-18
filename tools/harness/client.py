"""GameClient: authenticated Flask test-client wrapper for gameplay simulation."""

import json
from typing import Optional


class GameClient:
    """Wraps a Flask test client with game-session convenience methods.

    Sessions are created directly via SessionManager (bypassing the async DB
    auth routes), matching the pattern used in tests/api/conftest.py.
    """

    def __init__(self, app):
        self._client = app.test_client()
        self._session_manager = app.session_manager
        self.session_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self, username: str = "harness_player") -> str:
        """Create a session directly via SessionManager."""
        session_id, _ = self._session_manager.create_session(username)
        self.session_id = session_id
        return session_id

    def destroy_session(self):
        """Expire the current session."""
        if self.session_id:
            self._session_manager.expire_session(self.session_id)
            self.session_id = None

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.session_id}"}

    def get(self, path: str, **kwargs):
        return self._client.get(path, headers=self._auth_headers(), **kwargs)

    def post(self, path: str, json=None, **kwargs):
        return self._client.post(
            path, json=json, headers=self._auth_headers(), **kwargs
        )

    def parse(self, response) -> dict:
        """Parse a JSON response body into a dict."""
        try:
            return json.loads(response.data)
        except Exception:
            return {"_raw": response.data.decode("utf-8", errors="replace")}
