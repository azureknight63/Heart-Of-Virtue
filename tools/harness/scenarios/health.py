"""Health and API-info endpoint checks."""

from typing import List

from src.api.app import session_gauge_visible

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory


class HealthScenario(Scenario):
    name = "health"
    description = "Verify /health and /api/info respond with expected shapes."

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # /health -----------------------------------------------------------
        resp = client.get("/health")
        bug = self._check_status(
            resp, 200, "/health", "GET", "Health check",
            severity=BugSeverity.CRITICAL,
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            # `sessions` is published only for a non-production config — it is
            # an unauthenticated occupancy oracle otherwise. Asked of the same
            # predicate the route uses, rather than hard-required here: this
            # list used to name it unconditionally, which is right only for the
            # config the harness happens to build and reports a phantom missing
            # field against any other.
            expected = ["status"]
            if session_gauge_visible(client.app_config):
                expected.append("sessions")
            bugs += self._check_fields(
                data, expected, "/health", "GET", "Health check", resp
            )
            if data.get("status") != "healthy":
                bugs.append(self._bug(
                    title='Health check: status field is not "healthy"',
                    severity=BugSeverity.HIGH,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/health",
                    method="GET",
                    expected='"status": "healthy"',
                    actual=f'"status": {data.get("status")!r}',
                    response=resp,
                ))

        # /api/info ---------------------------------------------------------
        resp = client.get("/api/info")
        bug = self._check_status(resp, 200, "/api/info", "GET", "API info")
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["name", "version"], "/api/info", "GET", "API info", resp
            )

        return bugs
