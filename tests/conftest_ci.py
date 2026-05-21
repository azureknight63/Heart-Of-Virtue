"""
CI-specific pytest configuration.

When running in CI (detected via CI environment variables), skip tier 3 and tier 4
tests to allow the suite to complete within timeout limits. These tests are still
run locally by developers and on main branch for final validation.
"""

import os
import pytest


def pytest_configure(config):
    """Configure pytest based on environment."""
    is_ci = os.getenv('CI') or os.getenv('GITHUB_ACTIONS') or os.getenv('CIRCLECI')
    
    if is_ci:
        # Mark tier 3 and tier 4 tests to skip in CI
        # This allows full test suite locally but fast CI for PRs
        config.addinivalue_line(
            "markers", 
            "tier3_or_higher: marks tests as tier 3 or higher (skipped in CI)"
        )
