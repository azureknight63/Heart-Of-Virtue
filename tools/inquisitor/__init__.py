"""Inquisitor — game testing harness for Heart of Virtue.

Runs a deterministic probe sequence across all eight bug-hunt categories.

Two layers:
  browser     Playwright driving localhost:3000 + localhost:5000 (default).
              Catches JS errors and rendering bugs the API layer can't see.
  api         In-process Flask test client — faster, no servers needed.
              Pass --no-browser when you just want a quick smoke-test.

Usage:
    python tools/inquisitor.py
    python tools/inquisitor.py --no-browser
    python tools/inquisitor.py --headless --output findings.json
"""
