"""Base class for all exploration scenarios."""

import json
from abc import ABC, abstractmethod
from typing import List, Optional

from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory


class Scenario(ABC):
    name: str = "base"
    description: str = ""

    @abstractmethod
    def run(self, client: GameClient) -> List[BugReport]:
        """Run this scenario and return any bugs found."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _bug(
        self,
        title: str,
        severity: BugSeverity,
        category: BugCategory,
        endpoint: str,
        method: str,
        expected: str,
        actual: str,
        response=None,
        request_body: dict = None,
        traceback: str = "",
    ) -> BugReport:
        status = 0
        body = {}
        if response is not None:
            status = response.status_code
            try:
                body = json.loads(response.data)
            except Exception:
                body = {"_raw": response.data.decode("utf-8", errors="replace")}
        return BugReport(
            title=title,
            severity=severity,
            category=category,
            scenario=self.name,
            endpoint=endpoint,
            method=method,
            expected=expected,
            actual=actual,
            request_body=request_body or {},
            response_status=status,
            response_body=body,
            traceback=traceback,
        )

    def _check_status(
        self,
        response,
        expected_status: int,
        endpoint: str,
        method: str,
        context: str,
        request_body: dict = None,
        severity: BugSeverity = BugSeverity.HIGH,
    ) -> Optional[BugReport]:
        """Return a BugReport if the response status doesn't match."""
        if response.status_code == expected_status:
            return None
        if response.status_code >= 500:
            category = BugCategory.CRASH
            severity = BugSeverity.CRITICAL
        elif response.status_code in (401, 403):
            category = BugCategory.AUTH
        else:
            category = BugCategory.WRONG_RESPONSE
        return self._bug(
            title=f"{context}: expected HTTP {expected_status}, got {response.status_code}",
            severity=severity,
            category=category,
            endpoint=endpoint,
            method=method,
            expected=f"HTTP {expected_status}",
            actual=f"HTTP {response.status_code}",
            response=response,
            request_body=request_body,
        )

    def _check_no_crash(
        self,
        response,
        endpoint: str,
        method: str,
        context: str,
        request_body: dict = None,
    ) -> Optional[BugReport]:
        """Return a HIGH BugReport if the response is a 5xx server crash.

        Use this for endpoints where any non-5xx response (including 400/404)
        is acceptable — the only bug we're hunting is an unhandled exception.
        """
        if response.status_code < 500:
            return None
        try:
            body = json.loads(response.data)
        except Exception:
            body = {"_raw": response.data.decode("utf-8", errors="replace")}
        return BugReport(
            title=f"{context}: server crash (HTTP {response.status_code})",
            severity=BugSeverity.HIGH,
            category=BugCategory.CRASH,
            scenario=self.name,
            endpoint=endpoint,
            method=method,
            expected="HTTP 4xx (graceful rejection)",
            actual=f"HTTP {response.status_code} (server error)",
            request_body=request_body or {},
            response_status=response.status_code,
            response_body=body,
        )

    def _check_fields(
        self,
        data: dict,
        required_fields: List[str],
        endpoint: str,
        method: str,
        context: str,
        response=None,
    ) -> List[BugReport]:
        """Return BugReports for any missing required fields."""
        bugs = []
        for f in required_fields:
            if f not in data:
                bugs.append(
                    self._bug(
                        title=f"{context}: missing field '{f}'",
                        severity=BugSeverity.MEDIUM,
                        category=BugCategory.MISSING_FIELD,
                        endpoint=endpoint,
                        method=method,
                        expected=f"Response includes '{f}'",
                        actual=f"'{f}' absent. Keys present: {sorted(data.keys())}",
                        response=response,
                    )
                )
        return bugs
