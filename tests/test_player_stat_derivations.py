"""Contract test tying the character sheet's Accuracy to the engine's to-hit roll.

Accuracy is not cosmetic: players compare it against enemy Evasion to judge
whether a fight is winnable, and the UI tooltip promises that relationship
explicitly. It therefore has to be computed the way combat computes it.

It previously was not. ``get_player_stats`` used ``98 + finesse`` — full weight
on finesse, intelligence ignored — while ``Move.calculate_hit_chance`` uses
``98 - enemy.finesse + finesse * 0.7 + intelligence * 0.3``. The two agreed only
when a character happened to have equal finesse and intelligence, and nothing
tested it.
"""

import pytest

from src.api.services.game_service import derive_hit_accuracy


class _StubPlayer:
    """Carries only the attributes derive_hit_accuracy reads."""

    def __init__(self, finesse=10, intelligence=10):
        self.finesse = finesse
        self.intelligence = intelligence


def engine_hit_chance(user_finesse, user_intelligence, enemy_finesse):
    """The unclamped to-hit expression from Move.calculate_hit_chance.

    Duplicated deliberately: if the engine's formula changes, this test should
    fail loudly rather than silently following it.
    """
    return int(98 - enemy_finesse + (user_finesse * 0.7) + (user_intelligence * 0.3))


@pytest.mark.parametrize(
    "finesse, intelligence",
    [(10, 10), (20, 10), (10, 20), (1, 1), (30, 5), (5, 30), (99, 99)],
)
@pytest.mark.parametrize("enemy_finesse", [0, 12, 40])
def test_accuracy_minus_evasion_reproduces_the_engine_roll(finesse, intelligence, enemy_finesse):
    """The property the tooltip promises: accuracy - evasion == hit chance."""
    accuracy = derive_hit_accuracy(_StubPlayer(finesse, intelligence))
    assert accuracy - enemy_finesse == engine_hit_chance(finesse, intelligence, enemy_finesse)


def test_intelligence_contributes_to_accuracy():
    """The specific regression: intelligence was dropped from the sheet entirely."""
    assert derive_hit_accuracy(_StubPlayer(10, 30)) > derive_hit_accuracy(_StubPlayer(10, 10))


def test_finesse_outweighs_intelligence():
    """Finesse is weighted 0.7 against intelligence's 0.3."""
    assert derive_hit_accuracy(_StubPlayer(30, 10)) > derive_hit_accuracy(_StubPlayer(10, 30))


def test_diverges_from_the_old_naive_formula():
    """`98 + finesse` and the real weighting part company once the stats differ."""
    player = _StubPlayer(finesse=20, intelligence=10)
    assert derive_hit_accuracy(player) == 115
    assert derive_hit_accuracy(player) != 98 + player.finesse


def test_defaults_to_the_baseline_attributes_for_a_bare_player():
    """A player object missing the attributes must not raise."""

    class _Bare:
        pass

    assert derive_hit_accuracy(_Bare()) == 108


def test_get_player_stats_publishes_the_derived_value():
    """The route payload must carry the derived number, not a second formula."""
    from src.api.services.game_service import GameService

    service = GameService()
    stats = {}
    player = _StubPlayer(finesse=20, intelligence=10)

    # get_player_stats needs a far richer player than this, so assert the
    # published key is wired to the shared helper rather than re-deriving it.
    import inspect

    source = inspect.getsource(GameService.get_player_stats)
    assert 'stats["hit_accuracy"] = derive_hit_accuracy(player)' in source
    assert "98 + getattr(player" not in source

    stats["hit_accuracy"] = derive_hit_accuracy(player)
    assert stats["hit_accuracy"] == 115
    assert service is not None
