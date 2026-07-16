"""CI regression test for the combat command-protocol fuzzer (issue #291).

Runs a small, fixed-seed slice of ``tools/combat_command_fuzzer`` against a real
combat session and asserts the security-equivalent invariants hold: no handler
ever raises / returns a non-dict, adapter protocol state stays coherent after
every command, and commands sent while not awaiting input never mutate state.

This test builds a REAL session/universe (create_session + live
ApiCombatAdapter), so per CLAUDE.md it lives under ``tests/api/`` (excluded from
the default suite) to avoid polluting module-level item/merchant registries.
"""

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

fuzzer = importlib.import_module("tools.combat_command_fuzzer")


# A handful of fixed seeds gives deterministic, reproducible coverage across the
# adversarial command space without inflating suite runtime.
_SEEDS = [1337, 1, 42, 9999]


@pytest.mark.parametrize("seed", _SEEDS)
def test_command_fuzz_no_invariant_breach(seed):
    """No command sequence may breach a security-equivalent invariant."""
    findings = fuzzer.run_fuzz(iterations=120, seed=seed)
    breaches = fuzzer.security_findings(findings)
    assert not breaches, (
        "combat command fuzzer found invariant breaches:\n"
        + "\n".join(str(f) for f in breaches[:20])
    )


def test_non_dict_command_is_rejected_not_raised():
    """A non-dict command returns a structured error rather than raising."""
    import random

    adapter, _player, _enemies = fuzzer.build_combat(random.Random(7))
    for bad in (None, [], "select_move", 42, 3.14, ()):
        result = adapter.process_command(bad)
        assert isinstance(result, dict)
        assert "error" in result


def test_bad_move_index_types_rejected():
    """Non-int / bool / float move_index values are rejected cleanly."""
    import random

    adapter, player, _enemies = fuzzer.build_combat(random.Random(11))
    assert adapter.awaiting_input is True
    assert adapter.input_type == "move_selection"

    for bad in ("attack", 1.0, [], {}, None, float("nan"), True, False):
        result = adapter.process_command(
            {"type": "select_move", "move_index": bad}
        )
        assert isinstance(result, dict)
        assert result.get("error") == "Invalid move index"
        # State stays coherent: no pending move leaked in from a bad index.
        pmi = adapter.pending_move_index
        assert pmi is None or (
            isinstance(pmi, int)
            and not isinstance(pmi, bool)
            and 0 <= pmi < len(player.known_moves)
        )
