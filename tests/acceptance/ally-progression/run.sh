#!/bin/bash
# Ally progression acceptance test — in-process, no servers or browser needed.
set -e
cd "$(dirname "$0")/../../.."

echo "=== Ally progression unit tests ==="
python -m pytest tests/test_ally_progression.py -q

echo ""
echo "=== Ally progression harness scenario (end-to-end via Flask test client) ==="
CONFIG_FILE=tests/acceptance/ally-progression/config.ini \
  python tools/bug_hunt.py --scenario ally_progression
