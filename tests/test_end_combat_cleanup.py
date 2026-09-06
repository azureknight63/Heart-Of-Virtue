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

import ast
from pathlib import Path

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


#: The two modules a combat exit can live in.
_EXIT_MODULES = ("src/api/combat_adapter.py", "src/api/services/game_service.py")


def _clears_player_in_combat(node):
    """True if ``node`` assigns ``False`` to the PLAYER's ``in_combat``.

    ``ally.in_combat = False`` and ``each_enemy.in_combat = False`` appear in
    the same functions and are not exits, so the owner is checked rather than
    just the attribute name.
    """
    if not isinstance(node, ast.Assign):
        return False
    if not (isinstance(node.value, ast.Constant) and node.value.value is False):
        return False
    for target in node.targets:
        if not isinstance(target, ast.Attribute) or target.attr != "in_combat":
            continue
        owner = target.value
        if isinstance(owner, ast.Name) and owner.id == "player":
            return True
        if (
            isinstance(owner, ast.Attribute)
            and owner.attr == "player"
            and isinstance(owner.value, ast.Name)
            and owner.value.id == "self"
        ):
            return True
    return False


def _calls(func_node, name):
    """True if ``name`` is called anywhere inside ``func_node``."""
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue
        called = node.func
        if isinstance(called, ast.Name) and called.id == name:
            return True
        if isinstance(called, ast.Attribute) and called.attr == name:
            return True
    return False


def _combat_exits():
    """Every function that takes the player out of combat, found by scanning.

    DERIVED, not listed. The previous version of this guard hand-listed the
    exits it knew about -- and there were four, not the three it named. It
    also checked by reading each FILE for the substring ``end_combat_cleanup``,
    which fails open two ways: ``game_service.py`` line 10 IMPORTS the name, so
    both of its call sites could be deleted with the test still green; and
    ``combat_adapter.py`` contains the name at the victory exit, so the defeat
    exit's omission was invisible in the same file.

    "Takes the player out of combat" is something the code says out loud, so
    it can be scanned for. A fifth exit written tomorrow is covered the day it
    is written, which is the only way this stays true.
    """
    found = {}
    for path in _EXIT_MODULES:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(_clears_player_in_combat(n) for n in ast.walk(node)):
                found["%s::%s" % (path, node.name)] = node
    return found


class TestEveryExitPathCallsIt:
    """A correct helper nobody calls is what the victory path already had --
    and then the defeat path had it too, for a whole review round, because the
    guard written to prevent exactly that could not see it."""

    def test_the_scan_finds_the_exits(self):
        """Non-vacuity. A scan that matches nothing approves of everything.

        Four today: victory and defeat in the adapter, flee and load-mid-fight
        in the service.
        """
        exits = _combat_exits()
        assert len(exits) >= 4, sorted(exits)

    def test_every_exit_strips_departed_states(self):
        """The rule the helper exists for."""
        missing = sorted(
            name
            for name, node in _combat_exits().items()
            if not _calls(node, "end_combat_cleanup")
        )
        assert missing == [], (
            "these functions take the player out of combat without calling "
            "functions.end_combat_cleanup, so a combat-only state's stat "
            "delta stays baked into the live stat with nothing to remove it: "
            "%s" % ", ".join(missing)
        )

    def test_every_exit_recharges_single_use_equipment(self):
        """The step that went missing from exactly one exit.

        Victory and load recharged; flee did not, so a player who burned a
        single-use equip state (``PhoenixRevive``) and then FLED lost it until
        he won a fight or reloaded. The teardown being written out once per
        exit is why one step could go missing from one of them.

        If an exit ever SHOULD skip this, that belongs here as a named
        exception with the reason -- not as an absence.
        """
        missing = sorted(
            name
            for name, node in _combat_exits().items()
            if not _calls(node, "recharge_equip_states")
        )
        assert missing == [], (
            "these combat exits do not recharge single-use equip states, so a "
            "consumed PhoenixRevive stays consumed: %s" % ", ".join(missing)
        )

    def test_no_exit_path_still_rebinds_the_list_by_hand(self):
        """The shape that caused it, banned rather than its instances.

        Detected structurally: an assignment to ``<x>.states`` whose value
        mentions ``persistent``. The previous version matched the literal text
        ``getattr(s`` on one line, so ``getattr(state, "persistent", ...)`` --
        the spelling ``functions.py`` itself uses -- and the plain
        ``s.persistent`` attribute access both walked straight past it.
        """
        offenders = []
        for path in _EXIT_MODULES:
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                if not any(
                    isinstance(t, ast.Attribute) and t.attr == "states"
                    for t in node.targets
                ):
                    continue
                mentions = any(
                    (isinstance(n, ast.Constant) and n.value == "persistent")
                    or (isinstance(n, ast.Attribute) and n.attr == "persistent")
                    for n in ast.walk(node.value)
                )
                if mentions:
                    offenders.append("%s:%d" % (path, node.lineno))
        assert offenders == [], (
            "these sites filter player.states on `persistent` by hand instead "
            "of calling functions.end_combat_cleanup, which skips "
            "refresh_stat_bonuses and leaves the stat delta baked in: %s"
            % ", ".join(offenders)
        )

    def test_the_ban_would_catch_the_original_shape(self):
        """Guard-the-guard: the banned pattern, in all three spellings it has
        actually been written in, must be recognised by the same predicate the
        test above uses."""
        for source in (
            'player.states = [s for s in player.states if getattr(s, "persistent", True)]',
            "player.states = [s for s in player.states if s.persistent]",
            'self.player.states = [x for x in self.player.states'
            ' if getattr(x, "persistent", False)]',
        ):
            tree = ast.parse(source)
            assign = tree.body[0]
            assert any(
                isinstance(t, ast.Attribute) and t.attr == "states"
                for t in assign.targets
            ), source
            assert any(
                (isinstance(n, ast.Constant) and n.value == "persistent")
                or (isinstance(n, ast.Attribute) and n.attr == "persistent")
                for n in ast.walk(assign.value)
            ), source
