"""Contract test tying the character sheet's Accuracy to the engine's to-hit roll.

Accuracy is not cosmetic: players compare it against enemy Evasion to judge
whether a fight is winnable, and the UI tooltip promises that relationship
explicitly. It therefore has to be computed the way combat computes it.

It previously was not. ``get_player_stats`` used ``98 + finesse`` — full weight
on finesse, intelligence ignored — while ``Move.calculate_hit_chance`` uses
``HIT_CHANCE_BASE - enemy.finesse + finesse * 0.7 + intelligence * 0.3``. The
two agreed only when a character happened to have equal finesse and
intelligence, and nothing tested it.

The base term was retuned from 98 to 85 when the to-hit roll was made
non-vestigial (at 98 a base-stat attack landed ~93% of the time and a rear
attack was an outright certainty). The expected values below moved with it;
the *property* under test -- sheet accuracy minus enemy finesse equals the
engine's roll -- did not, and is what these assertions are for.
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

    Duplicated deliberately -- including the 85 base term: if the engine's
    formula or its base changes, this test should fail loudly rather than
    silently following it. Importing ``HIT_CHANCE_BASE`` here would make the
    test agree with the engine by construction and prove nothing.
    """
    return int(85 - enemy_finesse + (user_finesse * 0.7) + (user_intelligence * 0.3))


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
    assert derive_hit_accuracy(player) == 102
    assert derive_hit_accuracy(player) != 98 + player.finesse


def test_defaults_to_the_baseline_attributes_for_a_bare_player():
    """A player object missing the attributes must not raise."""

    class _Bare:
        pass

    assert derive_hit_accuracy(_Bare()) == 95


def test_get_player_stats_publishes_the_derived_value():
    """The route payload must carry the derived number, not a second formula.

    Asserted against a *real* ``Player`` rather than a source-code grep: the
    regression this guards was a second copy of the formula living in
    ``get_player_stats``, and only a real call can prove the published key
    tracks the shared helper.
    """
    from src.player import Player
    from src.api.services.game_service import GameService

    player = Player()
    player.finesse = 20
    player.intelligence = 10

    stats = GameService().get_player_stats(player)

    assert stats["hit_accuracy"] == 102
    assert stats["hit_accuracy"] == derive_hit_accuracy(player)
    # The old naive formula would have published 118 here.
    assert stats["hit_accuracy"] != 98 + player.finesse


def test_get_player_stats_tracks_a_changed_intelligence():
    """Mutating intelligence alone must move the published accuracy."""
    from src.player import Player
    from src.api.services.game_service import GameService

    service = GameService()
    player = Player()
    player.finesse = 20
    player.intelligence = 10
    before = service.get_player_stats(player)["hit_accuracy"]

    player.intelligence = 30
    after = service.get_player_stats(player)["hit_accuracy"]

    # +20 intelligence at weight 0.3 == +6 accuracy.
    assert (before, after) == (102, 108)


@pytest.mark.parametrize(
    "finesse, expected",
    [
        (12, 12),
        (12.4, 12),
        # Python rounds half to even: 12.5 -> 12, not 13. The sheet and the
        # battlefield card must agree on that, which is why both sides call
        # int(round(...)) rather than one of them truncating.
        (12.5, 12),
        (12.6, 13),
        (13.5, 14),
        (0, 0),
    ],
)
def test_evasion_agrees_between_the_sheet_and_the_combat_card(finesse, expected):
    """``evasion_chance`` (sheet) and ``evasion`` (combat payload) are one stat."""
    from src.player import Player
    from src.api.services.game_service import GameService
    from src.api.serializers.combat import CombatantSerializer

    player = Player()
    player.finesse = finesse

    sheet = GameService().get_player_stats(player)["evasion_chance"]
    card = CombatantSerializer._serialize_combat_stats(player)["evasion"]

    assert sheet == card == expected
    assert isinstance(sheet, int) and isinstance(card, int)


def test_accuracy_agrees_between_the_sheet_and_the_combat_card():
    """The attacker half of the roll must match across the same two surfaces."""
    from src.player import Player
    from src.api.services.game_service import GameService
    from src.api.serializers.combat import CombatantSerializer

    player = Player()
    player.finesse = 30
    player.intelligence = 5

    sheet = GameService().get_player_stats(player)["hit_accuracy"]
    card = CombatantSerializer._serialize_combat_stats(player)["accuracy"]

    assert sheet == card == int(85 + 30 * 0.7 + 5 * 0.3)


def test_evasion_chance_survives_a_none_finesse():
    """A partially built player must not 500 the character sheet."""
    from src.api.services.game_service import GameService

    class _Partial:
        finesse = None
        intelligence = None

    stats = GameService().get_player_stats(_Partial())
    assert stats["evasion_chance"] == 10
    assert stats["hit_accuracy"] == 95
