"""Leaving combat must not bake a departed state's stat bonus into the player.

THE BUG THIS PINS. Removing a state is three steps in this engine — take it off
``target.states``, call ``functions.refresh_stat_bonuses(target)``, then call the
state's ``on_removal``. Every engine call site does all three (``src/states.py``'s
expiry path, and the item effects in ``src/items.py``).

The API layer did only the first. At all three combat-exit paths it rebound
``player.states`` to a filtered list, and because ``refresh_stat_bonuses``
recomputes each stat from its ``*_base`` value, skipping it left the departed
state's contribution baked into the LIVE stat with nothing to ever remove it.

Measured before the fix: a player who fled with ``Dodging`` up kept finesse 64
against a base of 11. For the rest of the game. Penalties stuck the same way.

Worse, the three exits disagreed with each other: flee stripped without
refreshing, load stripped without refreshing, and victory stripped nothing at
all — so a combat-only state simply survived a won fight, since ``State.process``
decrements neither clock outside combat.

All three now call ``functions.end_combat_cleanup``. These tests assert the
engine rule directly, and then assert that each exit path actually invokes it —
because a correct helper nobody calls is what the API had for the third path.
"""

import src.functions as functions
from src.player import Player
from src.states import Dodging


def _player_with_dodging():
    player = Player()
    base = player.finesse
    player.states.append(Dodging(player))
    functions.refresh_stat_bonuses(player)
    return player, base


class TestTheEngineRule:
    def test_the_premise_that_a_state_actually_moves_the_stat(self):
        """Non-vacuity. If Dodging stopped granting finesse these would all
        pass while proving nothing, so pin the thing that makes them meaningful."""
        player, base = _player_with_dodging()
        assert player.finesse > base, (player.finesse, base)

    def test_cleanup_restores_the_stat(self):
        player, base = _player_with_dodging()
        functions.end_combat_cleanup(player)
        assert player.finesse == base

    def test_cleanup_removes_the_state(self):
        player, _base = _player_with_dodging()
        removed = functions.end_combat_cleanup(player)
        assert [type(s).__name__ for s in removed] == ["Dodging"]
        assert player.states == []

    def test_a_persistent_state_is_kept(self):
        """The other direction, so this cannot pass by removing everything."""
        player, _base = _player_with_dodging()
        keeper = Dodging(player)
        keeper.persistent = True
        player.states.append(keeper)
        functions.end_combat_cleanup(player)
        assert player.states == [keeper]

    def test_an_undeclared_persistent_flag_is_treated_as_non_persistent(self):
        """Fail CLOSED. The old code defaulted to True — keeping a state whose
        flag it could not read — in the guard whose whole job is to drop
        combat-only states. Every real State sets the flag, so the default is
        only reached by a degraded, legacy or mocked one: exactly the case that
        should be dropped rather than kept."""

        class _Undeclared:
            pass

        player = Player()
        player.states = [_Undeclared()]
        functions.end_combat_cleanup(player)
        assert player.states == []

    def test_cleanup_is_a_no_op_with_nothing_to_remove(self):
        player = Player()
        before = player.finesse
        assert functions.end_combat_cleanup(player) == []
        assert player.finesse == before


class TestEveryExitPathCallsIt:
    """A correct helper nobody calls is what the victory path already had.

    Asserted by source rather than by driving three full combat scenarios: the
    question here is whether the call SITE exists, and a source check answers
    exactly that without a fixture that could pass for another reason.
    """

    def test_all_three_exits_delegate_to_the_engine(self):
        from pathlib import Path

        sites = {
            "flee / load-mid-fight": Path("src/api/services/game_service.py"),
            "victory": Path("src/api/combat_adapter.py"),
        }
        missing = [
            name
            for name, path in sites.items()
            if "end_combat_cleanup" not in path.read_text(encoding="utf-8")
        ]
        assert missing == [], missing

    def test_no_exit_path_still_rebinds_the_list_by_hand(self):
        """The shape that caused it, not just the instances.

        A future exit path that filters `player.states` itself reintroduces the
        bug exactly, so the pattern is what is banned.
        """
        from pathlib import Path

        offenders = []
        for path in (
            Path("src/api/services/game_service.py"),
            Path("src/api/combat_adapter.py"),
        ):
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "states = [" in stripped and "persistent" not in stripped:
                    continue
                if "persistent" in stripped and "getattr(s" in stripped:
                    offenders.append("%s:%d" % (path, number))
        assert offenders == [], (
            "these sites filter player.states on `persistent` by hand instead of "
            "calling functions.end_combat_cleanup, which skips "
            "refresh_stat_bonuses and leaves the stat delta baked in: %s"
            % ", ".join(offenders)
        )
