"""Unit tests for the shared party-join helper (npc/_progression.join_party).

Issue #625 consolidated five hand-rolled copies of "flag the NPC a friend,
put it in combat_list_allies if it isn't already, level it up to Jean" into
one helper.  These tests pin the permanent-join contract, the tolerance for
allies that are not AllyProgressionMixin instances, and — the reason the
helper takes a flag rather than normalising everything — the *temporary*
ally semantics events.CombatEvent needs, which deliberately skip sync_level
and set aggro False.
"""

from unittest.mock import Mock

from src.npc._progression import join_party


class _Player:
    """Minimal player stand-in: a real list so membership is observable."""

    def __init__(self, level=1):
        self.level = level
        self.combat_list_allies = [self]


class _PlainAlly:
    """An ally with no sync_level — a Friend without a growth profile."""

    def __init__(self):
        self.friend = False
        self.aggro = True


class _Ally(_PlainAlly):
    """An ally that supports progression."""

    def __init__(self):
        super().__init__()
        self.sync_level = Mock()


# --- Permanent joins ----------------------------------------------------------


def test_join_party_flags_appends_and_levels():
    player = _Player(level=4)
    ally = _Ally()

    join_party(player, ally)

    assert ally.friend is True
    assert player.combat_list_allies == [player, ally]
    ally.sync_level.assert_called_once_with(4)


def test_join_party_does_not_duplicate_an_ally_already_in_the_party():
    player = _Player(level=2)
    ally = _Ally()
    player.combat_list_allies.append(ally)

    join_party(player, ally)

    assert player.combat_list_allies == [player, ally]
    ally.sync_level.assert_called_once_with(2)


def test_join_party_appends_behind_the_player_at_index_zero():
    player = _Player(level=1)
    first = _Ally()
    second = _Ally()

    join_party(player, first)
    join_party(player, second)

    assert player.combat_list_allies == [player, first, second]


def test_join_party_tolerates_an_ally_without_sync_level():
    """Not every ally is an AllyProgressionMixin — the guard must survive."""
    player = _Player(level=7)
    ally = _PlainAlly()

    join_party(player, ally)  # must not AttributeError

    assert ally.friend is True
    assert player.combat_list_allies == [player, ally]


def test_join_party_defaults_the_player_level_to_one():
    """Sessions early enough to have no level yet still level the ally."""

    class _Levelless:
        def __init__(self):
            self.combat_list_allies = [self]

    player = _Levelless()
    ally = _Ally()

    join_party(player, ally)

    ally.sync_level.assert_called_once_with(1)


def test_join_party_returns_the_ally():
    player = _Player()
    ally = _Ally()

    assert join_party(player, ally) is ally


def test_join_party_leaves_aggro_alone_for_a_permanent_join():
    """Only the temporary path touches aggro; a permanent join must not."""
    player = _Player()
    ally = _Ally()
    ally.aggro = True

    join_party(player, ally)

    assert ally.aggro is True
    assert getattr(ally, "event_temp_ally", None) is None


# --- Temporary (event) joins --------------------------------------------------


def test_join_party_temporary_marks_the_ally_and_clears_aggro():
    player = _Player(level=5)
    ally = _Ally()

    join_party(player, ally, temporary=True)

    assert ally.friend is True
    assert ally.aggro is False
    assert ally.event_temp_ally is True
    assert player.combat_list_allies == [player, ally]


def test_join_party_temporary_never_levels_the_ally():
    """The diverged copy in events.py skipped sync_level; #625 must not
    quietly normalise that — a one-fight ally is not a party member and
    levelling it would bank permanent growth on a throwaway spawn."""
    player = _Player(level=9)
    ally = _Ally()

    join_party(player, ally, temporary=True)

    ally.sync_level.assert_not_called()


def test_join_party_temporary_does_not_duplicate():
    player = _Player()
    ally = _Ally()
    player.combat_list_allies.append(ally)

    join_party(player, ally, temporary=True)

    assert player.combat_list_allies == [player, ally]


def test_temporary_is_keyword_only():
    """Positional truthiness must not be able to smuggle in a temp join."""
    import inspect

    sig = inspect.signature(join_party)
    assert sig.parameters["temporary"].kind is inspect.Parameter.KEYWORD_ONLY


def test_a_player_with_no_party_list_gets_one_with_the_player_first():
    """The docstring promises the ally lands behind the player at index 0;
    a player with no list yet used to depend on each caller seeding it."""
    player = _Player()
    del player.combat_list_allies
    ally = _PlainAlly()

    join_party(player, ally)

    assert player.combat_list_allies == [player, ally]

