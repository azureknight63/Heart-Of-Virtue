"""Inquisitor — AI-driven game testing harness for Heart of Virtue.

Two modes:
  happy-path  Claude plays the game chapter-by-chapter, reporting blockers.
  bug-hunt    Claude adversarially probes user-accessible paths for bugs.

Two layers:
  api         In-process Flask test client (fast, no browser required).
  browser     Playwright driving localhost:3000 + localhost:5000 (catches UI bugs).

Usage:
    python tools/inquisitor.py --mode bug-hunt --max-turns 30
    python tools/inquisitor.py --mode happy-path --chapter ch01
    python tools/inquisitor.py --mode bug-hunt --browser
    python tools/inquisitor.py --mode bug-hunt --headless --output findings.json
"""
