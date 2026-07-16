"""Fuzz test for the hardened API serializers (issue #295).

Drives tools/serializer_fuzzer.py, which feeds plausible-but-degraded engine
objects (real Player/NPC/Item/State/Move/Object/Event instances with a random
subset of attributes deleted, set to None, or swapped to a wrong type, plus
``_legacy_placeholder`` shapes) into every serializer entry point and asserts
the CLAUDE.md serializer contract: a serializer never raises on a degraded
object, and its output is always JSON-serializable. Any finding (crash or
JSON-leak) fails the test.

The fuzzer operates on pure in-memory engine objects — no Flask app/session — so
this lives under tests/ (see CLAUDE.md: only real-session integration tests
belong in tests/api/). The fuzzer module is loaded by file path, matching
tests/test_save_fuzz.py.
"""

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _load_fuzzer():
    path = _ROOT / "tools" / "serializer_fuzzer.py"
    spec = importlib.util.spec_from_file_location("_serializer_fuzzer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fuzzer = _load_fuzzer()


@pytest.mark.parametrize("seed", [1, 1337, 42, 20240101])
def test_serializers_never_crash_or_leak(seed):
    findings = fuzzer.run_fuzz(iterations=600, seed=seed)
    assert not findings, "\n".join(str(f) for f in findings[:40])


def test_degraded_player_serializes_to_json_safe_dict():
    """A Player with None/wrong-type core fields still serializes cleanly."""
    import json

    from src.player import Player
    from src.api.serializers.combat import CombatantSerializer

    p = Player()
    p.hp = None
    p.maxhp = float("nan")
    p.states = "not-a-list"
    p.resistance = {1, 2, 3}          # a set where a dict is expected
    out = CombatantSerializer.serialize_combatant(p)
    assert isinstance(out, dict)
    json.dumps(out)                   # must be JSON-serializable


def test_legacy_placeholder_serializes_without_raising():
    """A secure_pickle legacy placeholder (the shape a legacy save yields)."""
    import json

    from src import secure_pickle as sp
    from src.api.serializers.item_serializer import ItemSerializer

    placeholder = sp._make_legacy_placeholder("items", "Widget") \
        if hasattr(sp, "_make_legacy_placeholder") else object()
    out = ItemSerializer.serialize(placeholder)
    assert isinstance(out, dict)
    json.dumps(out)
