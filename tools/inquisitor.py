#!/usr/bin/env python
"""Inquisitor — AI-driven game testing harness for Heart of Virtue.

Usage:
    # API layer (no servers needed)
    python tools/inquisitor.py --mode bug-hunt --max-turns 30
    python tools/inquisitor.py --mode happy-path --chapter ch01
    python tools/inquisitor.py --mode happy-path

    # Browser layer (auto-starts Flask + Vite)
    python tools/inquisitor.py --mode bug-hunt --browser
    python tools/inquisitor.py --mode happy-path --browser --headless

    # Machine-readable output (compatible with bug_hunt_prompt.txt pipeline)
    python tools/inquisitor.py --mode bug-hunt --headless --output findings.json

Exit codes:
    0  — no CRITICAL or HIGH findings
    1  — one or more CRITICAL or HIGH findings found
    2  — setup failed (missing API key, import error, server startup failure)

Required environment variable:
    ANTHROPIC_API_KEY   Your Anthropic API key

Optional environment variables (email report):
    INQUISITOR_REPORT_EMAIL   Recipient email address
    INQUISITOR_FROM_EMAIL     Sender address (default: inquisitor@heart-of-virtue.local)
    INQUISITOR_SMTP_HOST      SMTP host (default: localhost)
    INQUISITOR_SMTP_PORT      SMTP port (default: 587)
    INQUISITOR_SMTP_USER      SMTP username
    INQUISITOR_SMTP_PASSWORD  SMTP password
    INQUISITOR_SMTP_TLS       Use STARTTLS: "1" (default) or "0"
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: sys.path + game-engine module shims.
# Mirrors tools/bug_hunt.py so the engine loads cleanly without pytest.
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

# ---------------------------------------------------------------------------
# Headless tkinter stub.
#
# combat_battlefield.py imports tkinter for its ASCII-art window, which is
# unavailable in headless CI environments.  We inject a lightweight stub so
# that create_app() can load without a display server.  The combat_battlefield
# module is only used by the terminal game loop; the web API never calls it.
# ---------------------------------------------------------------------------
if "tkinter" not in sys.modules:
    import types as _types

    _tk_stub = _types.ModuleType("tkinter")
    _tk_stub.Tk = type("Tk", (), {"__init__": lambda s, *a, **k: None,
                                   "title": lambda s, *a: None,
                                   "geometry": lambda s, *a: None,
                                   "resizable": lambda s, *a: None,
                                   "configure": lambda s, *a, **k: None,
                                   "after": lambda s, *a: None,
                                   "destroy": lambda s: None,
                                   "mainloop": lambda s: None})
    _tk_stub.Canvas = type("Canvas", (), {"__init__": lambda s, *a, **k: None,
                                           "pack": lambda s, *a, **k: None,
                                           "delete": lambda s, *a: None,
                                           "create_text": lambda s, *a, **k: None,
                                           "create_rectangle": lambda s, *a, **k: None})
    _tk_stub.font = _types.ModuleType("tkinter.font")
    _tk_stub.font.Font = type("Font", (), {"__init__": lambda s, *a, **k: None,
                                            "measure": lambda s, *a: 8})
    _tk_stub.END = "end"
    sys.modules["tkinter"] = _tk_stub
    sys.modules["tkinter.font"] = _tk_stub.font

# Shim core game-engine modules so bare imports resolve correctly.
try:
    import src.functions as _functions_mod
    sys.modules["functions"] = _functions_mod
except Exception as _e:
    print(f"[inquisitor] WARNING: could not shim 'functions': {_e}", file=sys.stderr)

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
    print(f"[inquisitor] FATAL: could not import Flask app — {exc}", file=sys.stderr)
    sys.exit(2)

from tools.inquisitor.modes import get_mode
from tools.inquisitor.reporter import (
    print_summary, findings_to_bug_reports, BugSeverity
)
from tools.inquisitor.email_reporter import send_report


def _check_api_key() -> bool:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print(
            "[inquisitor] FATAL: ANTHROPIC_API_KEY is not set.\n"
            "Export your key before running:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...",
            file=sys.stderr,
        )
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inquisitor — AI-driven game testing harness.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["happy-path", "bug-hunt"],
        help="Testing mode.",
    )
    parser.add_argument(
        "--chapter",
        metavar="CH",
        default=None,
        help="(happy-path only) Limit run to a single chapter, e.g. 'ch01'.",
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Use Playwright browser layer (auto-starts Flask + Vite).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Headless mode: JSON output only (no human-readable summary).",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Write JSON findings to FILE.",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=100,
        metavar="N",
        help="Maximum number of Claude API round-trips (default: 100).",
    )
    args = parser.parse_args()

    if not _check_api_key():
        return 2

    # ------------------------------------------------------------------
    # Resolve mode
    # ------------------------------------------------------------------
    try:
        mode = get_mode(args.mode, chapter_filter=args.chapter)
    except ValueError as exc:
        print(f"[inquisitor] {exc}", file=sys.stderr)
        return 2

    if not args.headless:
        print(f"[inquisitor] Mode: {mode.display_name}")
        if args.chapter:
            print(f"[inquisitor] Chapter filter: {args.chapter}")
        print(f"[inquisitor] Layer: {'browser' if args.browser else 'api'}")
        print(f"[inquisitor] Max turns: {args.max_turns}")

    # ------------------------------------------------------------------
    # Build the layer
    # ------------------------------------------------------------------
    layer = None
    try:
        if args.browser:
            from tools.inquisitor.browser_layer import BrowserLayer
            if not args.headless:
                print("[inquisitor] Starting servers and browser…")
            layer = BrowserLayer(mode_name=mode.name, headless=args.headless)
        else:
            from tools.inquisitor.api_layer import ApiLayer
            app, _ = create_app(TestingConfig)
            layer = ApiLayer(app=app, mode_name=mode.name)
    except Exception as exc:
        print(f"[inquisitor] FATAL: layer initialisation failed — {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 2

    # ------------------------------------------------------------------
    # Run the agent
    # ------------------------------------------------------------------
    from tools.inquisitor.agent import Inquisitor

    try:
        agent = Inquisitor(
            mode=mode,
            layer=layer,
            max_turns=args.max_turns,
            chapter_filter=args.chapter,
        )
        findings = agent.run()
    except EnvironmentError as exc:
        print(f"[inquisitor] FATAL: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        import traceback
        print(f"[inquisitor] FATAL: unhandled error — {exc}", file=sys.stderr)
        traceback.print_exc()
        return 2
    finally:
        if layer is not None:
            try:
                layer.teardown()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Write JSON output
    # ------------------------------------------------------------------
    output_path = args.output
    if output_path:
        bugs = findings_to_bug_reports(findings)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            json.dump(
                {
                    "total": len(bugs),
                    "critical": sum(1 for b in bugs if b.severity == BugSeverity.CRITICAL),
                    "high": sum(1 for b in bugs if b.severity == BugSeverity.HIGH),
                    "bugs": [b.to_dict() for b in bugs],
                    "findings": [f.to_dict() for f in findings],
                },
                fh,
                indent=2,
            )
        if not args.headless:
            print(f"[inquisitor] Report written to {out}")

    # ------------------------------------------------------------------
    # Email report
    # ------------------------------------------------------------------
    layer_name = "browser" if args.browser else "api"
    send_report(
        findings=findings,
        mode=mode.display_name,
        layer=layer_name,
        output_path=output_path,
    )

    # ------------------------------------------------------------------
    # Print summary
    # ------------------------------------------------------------------
    print_summary(findings, headless=args.headless)

    # ------------------------------------------------------------------
    # Exit code
    # ------------------------------------------------------------------
    bugs = findings_to_bug_reports(findings)
    critical_or_high = [
        b for b in bugs
        if b.severity in (BugSeverity.CRITICAL, BugSeverity.HIGH)
    ]
    return 1 if critical_or_high else 0


if __name__ == "__main__":
    sys.exit(main())
