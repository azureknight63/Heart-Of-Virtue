"""Verify that all major authenticated endpoints return 401 (not 500) with no auth.

One representative endpoint per blueprint is probed without an Authorization
header.  Any 5xx is a bug (the auth check itself crashed).  Any 2xx is flagged
MEDIUM (the endpoint skipped authentication entirely).
"""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory

# (method, path) — one per blueprint
_PROTECTED = [
    ("GET",  "/api/status"),            # player_bp
    ("GET",  "/api/stats"),             # player_bp
    ("GET",  "/api/world"),             # world_bp
    ("GET",  "/api/inventory"),         # inventory_bp
    ("GET",  "/api/equipment"),         # equipment_bp
    ("GET",  "/api/combat/status"),     # combat_bp
    ("GET",  "/api/combat/log"),        # combat_bp
    ("GET",  "/api/auth/validate"),     # auth_bp
    ("GET",  "/api/reputation/player"), # reputation_bp
    ("GET",  "/api/npc/quests/active"), # npc_bp
    ("GET",  "/api/quests/progression"),       # quest_rewards_bp
    ("GET",  "/api/quest-chains/progress"),    # quest_chains_bp
    ("GET",  "/api/npcs/probe/status"),        # npc_availability_bp
    ("GET",  "/api/dialogue/node/probe"),      # dialogue_context_bp
]


class NoAuthScenario(Scenario):
    name = "no_auth"
    description = (
        "Verify all authenticated endpoints reject requests with no Authorization "
        "header (expect 401, never 500 or 200)."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []
        raw = client._client  # Flask test client, no auth headers

        for method, path in _PROTECTED:
            if method == "GET":
                resp = raw.get(path)
            else:
                resp = raw.post(path, json={},
                                content_type="application/json")

            if resp.status_code >= 500:
                bugs.append(self._bug(
                    title=f"No-auth {method} {path} crashed (HTTP {resp.status_code})",
                    severity=BugSeverity.HIGH,
                    category=BugCategory.CRASH,
                    endpoint=path,
                    method=method,
                    expected="HTTP 401 (auth rejected before processing)",
                    actual=f"HTTP {resp.status_code} (server error)",
                    response=resp,
                ))
            elif resp.status_code == 200:
                bugs.append(self._bug(
                    title=f"No-auth {method} {path} returned 200 — endpoint unprotected",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.AUTH,
                    endpoint=path,
                    method=method,
                    expected="HTTP 401",
                    actual="HTTP 200 (no auth required)",
                    response=resp,
                ))
            # 401 / 403 / 404 are all acceptable

        return bugs
