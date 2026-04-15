"""Bug report data structures and formatting."""

import uuid
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict


class BugSeverity(str, Enum):
    CRITICAL = "critical"  # crash / unplayable / data loss
    HIGH = "high"          # major feature broken
    MEDIUM = "medium"      # wrong behaviour, playable
    LOW = "low"            # cosmetic


class BugCategory(str, Enum):
    CRASH = "crash"              # 5xx / unhandled exception
    WRONG_RESPONSE = "wrong"     # bad shape or wrong field values
    LOGIC = "logic"              # game logic incorrect
    AUTH = "auth"                # session / auth failures
    MISSING_FIELD = "missing"    # required field absent from response
    UI = "ui"                    # browser/rendering/JS error


@dataclass
class BugReport:
    title: str
    severity: BugSeverity
    category: BugCategory
    scenario: str
    endpoint: str
    method: str
    expected: str
    actual: str
    request_body: Dict[str, Any] = field(default_factory=dict)
    response_status: int = 0
    response_body: Dict[str, Any] = field(default_factory=dict)
    traceback: str = ""
    triage: str = ""  # populated by triage.classify()
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["category"] = self.category.value
        return d

    def to_github_issue_title(self) -> str:
        return f"[BUG][{self.severity.value.upper()}] {self.title}"

    def to_github_issue_body(self) -> str:
        req = json.dumps(self.request_body, indent=2) if self.request_body else "(none)"
        resp = json.dumps(self.response_body, indent=2) if self.response_body else "(none)"
        lines = [
            f"## Bug Report `{self.id}`",
            f"",
            f"| Field | Value |",
            f"|---|---|",
            f"| **Scenario** | `{self.scenario}` |",
            f"| **Severity** | `{self.severity.value}` |",
            f"| **Category** | `{self.category.value}` |",
            f"| **Endpoint** | `{self.method} {self.endpoint}` |",
            f"| **HTTP status** | `{self.response_status}` |",
            f"| **Triage** | `{self.triage}` |",
            f"",
            f"## Steps to Reproduce",
            f"",
            f"1. Create an authenticated game session.",
            f"2. Call `{self.method} {self.endpoint}` with:",
            f"   ```json",
            f"   {req}",
            f"   ```",
            f"",
            f"## Expected",
            f"",
            self.expected,
            f"",
            f"## Actual",
            f"",
            self.actual,
            f"",
            f"## Response Body",
            f"",
            f"```json",
            resp,
            f"```",
        ]
        if self.traceback:
            lines += [
                f"",
                f"## Traceback",
                f"",
                f"```",
                self.traceback,
                f"```",
            ]
        lines += [
            f"",
            f"---",
            f"*Discovered by the bug-hunt harness at `{self.timestamp}`.*",
            f"*Auto-generated — verify before closing.*",
        ]
        return "\n".join(lines)
