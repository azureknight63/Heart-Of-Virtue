"""Each of these modules imports cleanly as the FIRST thing a process loads.

The test suite and the app always import ``src.api.services.game_service``
early, which hides an import cycle: ``combat_adapter`` importing the
``src.api.services`` package runs its ``__init__``, which imports
``game_service``, which imports ``combat_adapter`` half-loaded. Only a fresh
interpreter per module can see that.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

FIRST_IMPORTS = [
    "src.api.combat_adapter",
    "src.api.services.analytics",
    "src.api.services.analytics_report",
    "src.api.routes.admin",
]


@pytest.mark.parametrize("module", FIRST_IMPORTS)
def test_module_imports_first_in_a_fresh_interpreter(module):
    result = subprocess.run(
        [sys.executable, "-c", "import %s" % module],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
        # Blank, not removed: .env fills only absent keys (env_bootstrap).
        env={**os.environ, "TURSO_DATABASE_URL": "", "HOV_ANALYTICS_ENABLED": "0"},
    )
    assert result.returncode == 0, result.stderr.strip().splitlines()[-1:]
