#!/usr/bin/env python
"""Heart of Virtue — game exploration harness and bug hunt runner.

Option A (manual sessions):
    python tools/bug_hunt.py
    python tools/bug_hunt.py --scenario combat
    python tools/bug_hunt.py --output /tmp/bugs.json

Option B (GitHub Actions / headless CI):
    python tools/bug_hunt.py --headless --output /tmp/bugs.json
    (The GH Actions workflow then feeds the JSON to a Claude Code invocation.)

Exit codes:
    0  — no CRITICAL or HIGH bugs found
    1  — one or more CRITICAL or HIGH bugs found
    2  — harness setup failed
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: sys.path + game-engine module shims.
# Mirrors tests/api/conftest.py so the engine loads cleanly without pytest.
# NOTE: we do NOT install a synchronized import hook here — it causes a
# KeyError when the Flask src.api package is later imported.
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(1, str(SRC_DIR))

# Silence Mynx LLM calls during harness runs.
os.environ.setdefault("MYNX_LLM_ENABLED", "0")
os.environ.setdefault("MYNX_FALLBACK_DELAY", "0")
os.environ.setdefault("MYNX_LLM_PROVIDER", "none")

# Shim core game-engine modules so bare imports (e.g. `import functions`)
# resolve to the same objects as `src.*` imports.
# functions must come first — everything else depends on it.
try:
    import src.functions as _functions_mod
    sys.modules["functions"] = _functions_mod
except Exception as _e:
    print(f"[bug_hunt] WARNING: could not shim 'functions': {_e}", file=sys.stderr)

_CORE_MODULES = [
    "animations", "genericng", "items", "states", "enchant_tables",
    "objects", "loot_tables", "actions", "tiles", "universe", "positions",
    "moves", "combatant", "npc", "skilltree", "switch", "player",
]
for _name in _CORE_MODULES:
    if _name not in sys.modules:
        try:
            _mod = __import__(f"src.{_name}", fromlist=["*"])
            sys.modules[_name] = _mod
            sys.modules[f"src.{_name}"] = _mod
        except Exception:
            pass

for _name in ("combat", "events", "shop_conditions"):
    if _name not in sys.modules:
        try:
            sys.modules[_name] = __import__(f"src.{_name}", fromlist=["*"])
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Now safe to import project modules.
# ---------------------------------------------------------------------------

try:
    from src.api.app import create_app
    from src.api.config import TestingConfig
except Exception as exc:
    print(f"[bug_hunt] FATAL: could not import Flask app — {exc}", file=sys.stderr)
    sys.exit(2)

from tools.harness.client import GameClient
from tools.harness.reporter import BugReport, BugSeverity
from tools.harness.triage import classify
from tools.harness.scenarios import get_scenarios


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _print_summary(bugs: list[BugReport], headless: bool) -> None:
    if headless:
        # Machine-readable: one JSON blob to stdout.
        print(json.dumps(
            {
                "total": len(bugs),
                "critical": sum(1 for b in bugs if b.severity == BugSeverity.CRITICAL),
                "high": sum(1 for b in bugs if b.severity == BugSeverity.HIGH),
                "bugs": [b.to_dict() for b in bugs],
            },
            indent=2,
        ))
        return

    if not bugs:
        print("\n[bug_hunt] No bugs found. Impressive.")
        return

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
            print(f"         Scenario: {b.scenario}  |  {b.method} {b.endpoint}")
            print(f"         Expected: {b.expected}")
            print(f"         Actual:   {b.actual}")

    print(f"\n[bug_hunt] Total: {len(bugs)} bug(s) found.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Heart of Virtue game exploration harness."
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Output machine-readable JSON (for CI / Option B).",
    )
    parser.add_argument(
        "--scenario", metavar="NAME",
        help="Run only the named scenario (health, auth, world, combat, inventory).",
    )
    parser.add_argument(
        "--output", metavar="FILE",
        help="Write JSON bug report to FILE.",
    )
    args = parser.parse_args()

    # Create the Flask app (TestingConfig: no real DB, no external calls).
    try:
        app, _ = create_app(TestingConfig)
    except Exception as exc:
        print(f"[bug_hunt] FATAL: create_app failed — {exc}", file=sys.stderr)
        return 2

    client = GameClient(app)

    # Select scenarios.
    scenarios = get_scenarios(name=args.scenario)
    if not scenarios:
        print(f"[bug_hunt] Unknown scenario: {args.scenario!r}", file=sys.stderr)
        return 2

    # Run scenarios.
    all_bugs: list[BugReport] = []
    for scenario in scenarios:
        if not args.headless:
            print(f"[bug_hunt] Running scenario: {scenario.name} — {scenario.description}")

        client.create_session(f"harness_{scenario.name}")
        try:
            bugs = scenario.run(client)
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            bugs = [BugReport(
                title=f"Scenario '{scenario.name}' raised an unhandled exception",
                severity=BugSeverity.CRITICAL,
                category=__import__(
                    "tools.harness.reporter", fromlist=["BugCategory"]
                ).BugCategory.CRASH,
                scenario=scenario.name,
                endpoint="(harness)",
                method="(harness)",
                expected="Scenario completes without exception",
                actual=str(exc),
                traceback=tb,
            )]
        finally:
            client.destroy_session()

        # Annotate triage decision onto each bug.
        for bug in bugs:
            bug.triage = classify(bug)

        all_bugs.extend(bugs)
        if not args.headless:
            status = "OK" if not bugs else f"{len(bugs)} bug(s)"
            print(f"         >> {status}")

    # Write JSON report if requested.
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w") as f:
            json.dump([b.to_dict() for b in all_bugs], f, indent=2)
        if not args.headless:
            print(f"\n[bug_hunt] Report written to {out_path}")

    _print_summary(all_bugs, args.headless)

    # Non-zero exit if any CRITICAL or HIGH bugs found (useful in CI).
    critical_or_high = [
        b for b in all_bugs
        if b.severity in (BugSeverity.CRITICAL, BugSeverity.HIGH)
    ]
    return 1 if critical_or_high else 0


if __name__ == "__main__":
    sys.exit(main())
