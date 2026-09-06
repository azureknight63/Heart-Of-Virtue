"""The level-up attribute vocabulary is the engine's, and is spelled once.

``src/player/_leveling.py`` distributes level-up bonuses across seven named
``*_base`` attributes. That list was written out THREE times: once in the
engine, and twice more in ``GameService.allocate_level_up_points`` -- as the
set of keys the route accepts, and as the list it randomises over.

The architecture rule is that the engine is the source of truth and the API
adapts. Three copies meant an eighth attribute added to the engine would be
silently refused by the API with "Invalid attribute" -- the rule failing in the
direction that is hardest to notice, because nothing errors and no test that
exercises the seven existing attributes can see it.
"""

import ast
from pathlib import Path

import pytest

from src.player._leveling import LEVEL_UP_ATTRIBUTE_NAMES, LEVEL_UP_ATTRIBUTES

#: Where a re-typed copy would go. ``src/player/`` is excluded: that is where
#: the authority lives and where the names are legitimately spelled.
_API_ROOT = Path("src/api")


class TestTheEngineOwnsTheVocabulary:
    def test_the_authority_is_populated(self):
        """Non-vacuity. An empty tuple makes every ban below hold trivially."""
        assert len(LEVEL_UP_ATTRIBUTES) >= 7
        assert all(
            name.endswith("_base") for name in LEVEL_UP_ATTRIBUTE_NAMES
        ), LEVEL_UP_ATTRIBUTE_NAMES

    def test_the_names_and_labels_stay_paired(self):
        """The labels are half the authority -- a name without one renders as
        nothing in the level-up screen."""
        assert all(
            isinstance(name, str) and isinstance(label, str) and name and label
            for name, label in LEVEL_UP_ATTRIBUTES
        ), LEVEL_UP_ATTRIBUTES
        assert len(set(LEVEL_UP_ATTRIBUTE_NAMES)) == len(LEVEL_UP_ATTRIBUTES)

    def test_every_name_exists_on_a_real_player(self):
        """The authority is checked against the thing it describes, not just
        against itself. This is what would have caught a typo'd or renamed
        attribute -- the same shape as `player.equipped`, which no Player has
        ever had."""
        from src.player import Player

        player = Player()
        missing = [n for n in LEVEL_UP_ATTRIBUTE_NAMES if not hasattr(player, n)]
        assert missing == [], missing

    def test_the_api_accepts_exactly_the_engine_vocabulary(self):
        """Computed live from both sides rather than compared to a list here,
        so this cannot drift into being one more copy."""
        import inspect

        from src.api.services.game_service import GameService

        source = inspect.getsource(GameService.allocate_level_up_points)
        assert "LEVEL_UP_ATTRIBUTE_NAMES" in source, (
            "allocate_level_up_points no longer derives its accepted "
            "attributes from the engine"
        )

    def test_no_api_module_rebuilds_the_vocabulary(self):
        """The ban, over the whole API layer.

        A COLLECTION of these names is a copy of the vocabulary; a single one
        is a reference to one attribute. The first is what drifts when an
        eighth is added, and the second is legitimate -- `combat_adapter` and
        `session_manager` both read individual `*_base` values for reasons
        that have nothing to do with level-up allocation, and banning those
        would make this rule unusable and get it deleted.

        Two or more in one literal collection is the line, and it is where the
        three real copies sat.
        """
        offenders = []
        for path in sorted(_API_ROOT.rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:  # pragma: no cover
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Set, ast.List, ast.Tuple)):
                    continue
                names = {
                    el.value
                    for el in node.elts
                    if isinstance(el, ast.Constant)
                    and isinstance(el.value, str)
                    and el.value in LEVEL_UP_ATTRIBUTE_NAMES
                }
                if len(names) >= 2:
                    offenders.append(
                        "%s:%d (%s)"
                        % (path.as_posix(), node.lineno, ", ".join(sorted(names)))
                    )
        assert offenders == [], (
            "these API sites rebuild the level-up attribute vocabulary as a "
            "literal collection instead of reading LEVEL_UP_ATTRIBUTE_NAMES "
            "from the engine, so an attribute added to the engine would be "
            "silently refused here: %s" % ", ".join(offenders)
        )

    def test_the_scan_would_catch_a_retyped_copy(self):
        """Guard-the-guard, against the exact shape that was there."""
        source = 'allowed = {"strength_base", "finesse_base", "randomize"}'
        tree = ast.parse(source)
        collections_with_two = [
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.Set, ast.List, ast.Tuple))
            and len(
                {
                    el.value
                    for el in n.elts
                    if isinstance(el, ast.Constant)
                    and isinstance(el.value, str)
                    and el.value in LEVEL_UP_ATTRIBUTE_NAMES
                }
            )
            >= 2
        ]
        assert len(collections_with_two) == 1

    def test_the_scan_leaves_an_unrelated_string_alone(self):
        """The control: a ban that fired on ordinary strings would be deleted
        within a week."""
        # A single reference, and an unrelated collection. Neither is a copy
        # of the vocabulary, and flagging either would break real code.
        for source in (
            'v = getattr(player, "strength_base", 0)',
            'x = ["randomize", "strength"]',
        ):
            tree = ast.parse(source)
            flagged = [
                n
                for n in ast.walk(tree)
                if isinstance(n, (ast.Set, ast.List, ast.Tuple))
                and len(
                    {
                        el.value
                        for el in n.elts
                        if isinstance(el, ast.Constant)
                        and isinstance(el.value, str)
                        and el.value in LEVEL_UP_ATTRIBUTE_NAMES
                    }
                )
                >= 2
            ]
            assert flagged == [], source


class TestAFailedRefreshIsNotReportedAsSuccess:
    """`refresh_stat_bonuses` is what makes spent points count.

    Its failure was caught by `except Exception: pass`, and the route then
    answered `success: True` with a `stats` block computed from a player whose
    bonuses had not been recomputed -- the allocation accepted, the numbers
    unchanged, nothing said. Same mechanism as the combat-exit bug: skip the
    refresh and the stat stays wrong with nothing to put it right.
    """

    def _player_with_points(self):
        from src.player import Player

        player = Player()
        player.pending_attribute_points = 3
        return player

    def test_a_failing_refresh_answers_failure(self, monkeypatch):
        from src import functions
        from src.api.services.game_service import GameService

        def _boom(_player):
            raise RuntimeError("recompute failed")

        # Built BEFORE the patch: `Player.__init__` itself calls
        # `refresh_stat_bonuses`, so constructing under the patch made the
        # fixture explode rather than the code under test.
        player = self._player_with_points()
        monkeypatch.setattr(functions, "refresh_stat_bonuses", _boom)
        result = GameService().allocate_level_up_points(
            player, "strength_base", 1
        )
        assert result["success"] is False
        assert "stats" not in result

    def test_an_ordinary_allocation_still_succeeds(self):
        """The control. A guard that failed every allocation would satisfy the
        test above and break levelling up entirely."""
        from src.api.services.game_service import GameService

        player = self._player_with_points()
        before = player.strength_base
        result = GameService().allocate_level_up_points(player, "strength_base", 1)
        assert result["success"] is True, result
        assert player.strength_base == before + 1
        assert result["remaining_points"] == 2
