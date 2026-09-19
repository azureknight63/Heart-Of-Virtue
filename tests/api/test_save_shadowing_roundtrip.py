"""A genuine save loses nothing to the #620 shadowing filter.

Lives in tests/api/ because ``Universe.build`` mutates module-level item and
merchant registries (CLAUDE.md, "Running Tests"); the per-file CI job keeps
that out of the default suite. The unit-level guards are in
``tests/test_instance_shadowing_guard.py``.
"""

import io

import src.secure_pickle as secure_pickle
from src.secure_pickle import safe_pickle_load
from tests._gs_fixtures import live_world


def test_a_real_world_save_loses_nothing():
    """The engine itself never writes a shadowing attribute, so a genuine
    save -- a whole built universe -- restores with no drop and no refusal.
    This is the check that the rule is not wider than the hole."""
    player, _map = live_world()
    player.universe.build(player)
    events = []

    loaded = safe_pickle_load(
        io.BytesIO(secure_pickle.serialize_for_save(player)), strict=True, events=events
    )

    assert isinstance(loaded, type(player))
    assert [e for e in events if e["kind"] in ("dropped", "rejected")] == []
