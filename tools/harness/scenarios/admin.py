"""Admin analytics route gate (admin_bp, GET /api/admin/analytics).

The harness session is minted straight from the SessionManager with no
account behind it, exactly like /api/test/session. The route must refuse it
whatever the admin allow-list holds: admin is decided by account id
(routes/admin.py), and an account-less session has none.
"""

import os
from typing import List

from src.api.routes.admin import ADMIN_USER_IDS_ENV

from .base import Scenario
from ..client import GameClient
from ..reporter import BugCategory, BugReport, BugSeverity

PATH = "/api/admin/analytics"


class AdminScenario(Scenario):
    name = "admin"
    description = (
        "Verify the admin analytics route answers 401 without credentials and "
        "404 to non-admins, including an account-less session while the "
        "allow-list is non-empty and a bad ?days= that must not reveal the route."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        resp = client._client.get(PATH)  # no credentials at all
        bug = self._check_status(resp, 401, PATH, "GET", "Admin analytics without credentials")
        if bug:
            bugs.append(bug)

        previous = os.environ.get(ADMIN_USER_IDS_ENV)
        os.environ[ADMIN_USER_IDS_ENV] = "00000000-0000-0000-0000-000000000000"
        try:
            for path in (PATH, PATH + "?days=abc"):
                resp = client.get(path)
                if resp.status_code != 404:
                    bugs.append(self._bug(
                        title="Admin analytics answered a non-admin with something other than 404",
                        severity=BugSeverity.CRITICAL,
                        category=BugCategory.AUTH,
                        endpoint=path,
                        method="GET",
                        expected="HTTP 404 for an account-less session, before any validation",
                        actual=f"HTTP {resp.status_code}",
                        response=resp,
                    ))
        finally:
            if previous is None:
                os.environ.pop(ADMIN_USER_IDS_ENV, None)
            else:
                os.environ[ADMIN_USER_IDS_ENV] = previous

        return bugs
