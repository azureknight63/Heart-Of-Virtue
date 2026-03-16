"""AgentFinding dataclass and findings management for the Inquisitor harness."""

import uuid
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Re-export BugSeverity/BugCategory/BugReport for consumers.
from tools.harness.reporter import BugReport, BugSeverity, BugCategory
from tools.harness.triage import classify


_SEVERITY_MAP = {
    "critical": BugSeverity.CRITICAL,
    "high": BugSeverity.HIGH,
    "medium": BugSeverity.MEDIUM,
    "low": BugSeverity.LOW,
}

_FINDING_TYPE_TO_SEVERITY = {
    "bug": None,          # severity provided explicitly
    "blocker": BugSeverity.HIGH,
    "chapter_complete": None,
    "observation": BugSeverity.LOW,
    "done": None,
    "stuck": BugSeverity.MEDIUM,
}


@dataclass
class AgentFinding:
    """A single finding produced by the Inquisitor agent.

    Richer than BugReport — covers chapter milestones, blockers, and observations
    in addition to bugs.  Bugs/blockers can be converted to BugReport for
    compatibility with the existing bug_hunt_prompt.txt pipeline.
    """

    mode: str                    # "happy_path" | "bug_hunt"
    layer: str                   # "api" | "browser"
    type: str                    # "bug" | "blocker" | "chapter_complete" | "observation" | "stuck" | "done"
    title: str
    description: str
    severity: Optional[str]      # "critical" | "high" | "medium" | "low" | None
    chapter: Optional[str]       # "ch01" | "ch02" | None
    step_number: int
    tool_call: str               # Name of tool that produced this finding
    tool_input: Dict[str, Any]   # Inputs passed to that tool
    tool_result: Dict[str, Any]  # Result returned from that tool
    screenshot_path: Optional[str] = None   # Browser layer only
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return asdict(self)

    def to_bug_report(self) -> Optional[BugReport]:
        """Convert to BugReport if this finding is a bug or blocker.

        Returns None for chapter_complete / observation / done findings.
        """
        if self.type not in ("bug", "blocker", "stuck"):
            return None

        sev = _SEVERITY_MAP.get(
            self.severity or "",
            BugSeverity.MEDIUM if self.type == "stuck" else BugSeverity.LOW,
        )
        cat = BugCategory.LOGIC if self.type == "blocker" else BugCategory.WRONG_RESPONSE

        report = BugReport(
            title=self.title,
            severity=sev,
            category=cat,
            scenario=f"inquisitor/{self.mode}",
            endpoint=self.tool_call,
            method="agent-tool",
            expected="Normal operation without errors",
            actual=self.description,
            request_body=self.tool_input,
            response_body=self.tool_result,
        )
        report.triage = classify(report)
        return report

    def is_reportable_bug(self) -> bool:
        """True if this finding should appear in the bug count output."""
        return self.type in ("bug", "blocker", "stuck") and self.severity in (
            "critical", "high", "medium", "low"
        )


def findings_to_bug_reports(findings: list) -> list:
    """Convert a list of AgentFinding to BugReport, skipping non-bug findings."""
    return [r for f in findings if (r := f.to_bug_report()) is not None]


def print_summary(findings: list, headless: bool = False) -> None:
    """Print a human-readable summary to stdout (or machine JSON if headless)."""
    import json

    bugs = findings_to_bug_reports(findings)

    if headless:
        print(json.dumps(
            {
                "total": len(bugs),
                "critical": sum(1 for b in bugs if b.severity == BugSeverity.CRITICAL),
                "high": sum(1 for b in bugs if b.severity == BugSeverity.HIGH),
                "bugs": [b.to_dict() for b in bugs],
                "findings": [f.to_dict() for f in findings],
            },
            indent=2,
        ))
        return

    if not findings:
        print("\n[inquisitor] No findings. Game is clean.")
        return

    chapters_done = [f for f in findings if f.type == "chapter_complete"]
    if chapters_done:
        print("\n[inquisitor] Chapters completed:")
        for f in chapters_done:
            print(f"  ✓ {f.chapter}: {f.title}")

    sev_order = [BugSeverity.CRITICAL, BugSeverity.HIGH, BugSeverity.MEDIUM, BugSeverity.LOW]
    for sev in sev_order:
        group = [b for b in bugs if b.severity == sev]
        if not group:
            continue
        print(f"\n{'='*60}")
        print(f"  {sev.value.upper()} ({len(group)})")
        print(f"{'='*60}")
        for b in group:
            print(f"  [{b.id}] [{b.triage}] {b.title}")
            print(f"         Endpoint: {b.endpoint}")
            print(f"         Actual:   {b.actual[:120]}")

    stuck = [f for f in findings if f.type == "stuck"]
    if stuck:
        print(f"\n[inquisitor] Agent reported stuck ({len(stuck)}):")
        for f in stuck:
            print(f"  - {f.description[:120]}")

    print(f"\n[inquisitor] {len(bugs)} bug(s) from {len(findings)} total finding(s).")
