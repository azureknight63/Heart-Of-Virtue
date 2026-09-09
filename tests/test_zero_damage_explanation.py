"""A fully absorbed blow must say WHY it was absorbed (#555).

Reported: four consecutive ``Jean struck Rock Rumbler Ewohoxuq but did no
damage!`` lines against an ATTRIBUTES sheet advertising
``attack_damage_min: 40, attack_damage_max: 60``.

Source-confirmed arithmetic (``RockRumbler``, ``src/npc/_enemies.py``):
``protection = 28`` and ``resistance_base["slashing"] = 0.5``, the latter
written by ``_set_damage_resistance`` in ``__init__``, which sets the live
``resistance`` dict at the same time -- so both values are in force from
construction, with no combat enrollment needed
(``tests/test_authored_resistances_are_live.py`` is the guard for that).
Through the canonical line (``src/moves/_base.resolve_damage``) a 46-power slashing hit
resolves as ``46 * 0.5 - 28 = -5`` → 0, and a 60-power one yields 2. Neither
multiplier is surfaced anywhere, so the advertised damage range does not
predict the outcome and the log never says why.

This is a legibility fix, not a balance one: no damage, resistance or
protection number changes. The engine now narrates a second line naming the
two mitigations that consumed the blow, worded so that the *existing* glossary
patterns for "resistance" and "protection" match it — which is what lets the
``?`` explainer attach to the outcome line with no frontend change.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import src.functions as functions  # noqa: E402
from _combat_fixtures import engage, make_player, seeded  # noqa: E402
from src.moves._base import mitigation_note, target_protection  # noqa: E402
from src.narration import capture_narration  # noqa: E402
from src.npc import RockRumbler, Slime  # noqa: E402

ABSORBED_LINE = "Jean struck {} but did no damage!"


def _sword_attack_on(enemy):
    """Jean, a sword, and ``enemy`` enrolled in a real fight.

    ``refresh_stat_bonuses`` is here because it is what combat start runs on
    every enemy (``ApiCombatAdapter.initialize_combat``), so the fixture
    matches production. It is NOT what makes the authored resistances live --
    an earlier version of this docstring said so and was wrong:
    ``_set_damage_resistance`` writes ``resistance`` and ``resistance_base``
    together in ``__init__``, which is exactly what the sibling guard
    ``tests/test_authored_resistances_are_live.py`` asserts. Removing the call
    would not change this test's outcome; it stays because a fixture that
    diverges from combat start is how a passing test stops predicting the game.
    """
    player = make_player(weapon="Sword")
    functions.refresh_stat_bonuses(enemy)
    engage(player, enemies=[enemy])
    move = next(m for m in player.known_moves if type(m).__name__ == "Attack")
    move.user = player
    move.target = enemy
    move.evaluate()  # resolves base_damage_type from the equipped weapon
    move.prep_colors()
    return player, move


def _absorbed_lines(move):
    with capture_narration() as messages:
        move.hit(0, False)
    return [entry.get("text", "") for entry in messages]


@pytest.fixture
def rumbler_absorb():
    """The reported encounter: a longsword blow fully absorbed by a Rumbler."""
    with seeded(7):
        enemy = RockRumbler()
        enemy.name = "Rock Rumbler Ewohoxuq"
        _player, move = _sword_attack_on(enemy)
        return enemy, move, _absorbed_lines(move)


def test_the_absorbed_line_itself_is_unchanged(rumbler_absorb):
    """Negative control, and a contract: the outcome line keeps its wording.

    ``tests/test_combat_outcome_channel.py`` pins this string because the
    adapter pairs the published ``absorb`` outcome with it. The explanation is
    an ADDITIONAL line, never a rewrite of this one.
    """
    enemy, _move, lines = rumbler_absorb
    assert lines[0] == ABSORBED_LINE.format(enemy.name)


def test_the_absorbed_blow_is_explained(rumbler_absorb):
    """A line after it must name both mitigations, with the engine's numbers."""
    enemy, move, lines = rumbler_absorb
    explanation = " ".join(lines[1:])
    assert explanation, (
        "a fully absorbed blow narrated no explanation at all; got: " f"{lines}"
    )

    resistance = functions.combat_resistance(enemy, move.base_damage_type)
    protection = target_protection(enemy)
    # Derived from the engine, not typed in: a retune of RockRumbler must not
    # be able to leave this test asserting numbers the engine no longer uses.
    assert resistance == 0.5 and protection == 28, (
        "RockRumbler's mitigation changed; the issue's arithmetic (46 x 0.5 - "
        f"28) no longer describes it: resistance={resistance}, "
        f"protection={protection}"
    )
    assert move.base_damage_type == "slashing", move.base_damage_type
    for expected in ("slashing", "0.5", "28"):
        assert expected in explanation, (
            f"{expected!r} missing from the explanation: {explanation!r}"
        )


def test_the_explanation_uses_the_words_the_glossary_already_explains(
    rumbler_absorb,
):
    """The ``?`` explainer attaches by word match, so the wording is load-bearing.

    ``frontend/src/data/combatGlossary.js`` already carries a
    ``Protection & resistance`` entry whose patterns are ``protections?`` and
    ``resistances?``, and ``GlossaryText`` attaches its explainer by matching
    those patterns against rendered text.

    This pins the BACKEND half. ``GlossaryText`` presently wraps
    ``CombatMovePanel`` only — not ``CombatLog`` — so the tooltip does not yet
    appear on this line; wrapping the log is the frontend half, and this test
    is what guarantees the words will be there when it lands. No new wire
    field is involved either way.
    """
    from test_combat_glossary_contract import _matching_entry_ids

    _enemy, _move, lines = rumbler_absorb
    explanation = " ".join(lines[1:])
    assert "protection" in _matching_entry_ids(explanation), (
        "the explanation does not match the glossary's protection/resistance "
        f"patterns, so the ? explainer will not attach: {explanation!r}"
    )


def test_an_unmitigated_absorb_claims_no_mitigation():
    """No resistance and no armour: the line must not invent a reason.

    A Slime has neither, so a zero here came from the power/heat/variance
    product rather than from mitigation. Claiming armour that is not there
    would be a worse lie than the silence this fix replaces.
    """
    with seeded(11):
        slime = Slime()
        slime.name = "Slime Xoq"
        _player, move = _sword_attack_on(slime)
        assert functions.combat_resistance(slime, move.base_damage_type) == 1.0
        assert target_protection(slime) == 0
        lines = _absorbed_lines(move)
        explanation = " ".join(lines[1:])
        assert "protection" not in explanation.lower(), explanation
        assert "resistance" not in explanation.lower(), explanation


def test_a_vulnerability_is_never_offered_as_the_reason():
    """A resistance above neutral did not consume the blow — don't name it.

    The Rumbler takes 1.5x from crushing, so a crushing blow that still landed
    for nothing was stopped by armour alone. Naming a vulnerability as the
    reason for zero damage reads as nonsense.
    """
    enemy = RockRumbler()
    enemy.name = "Rock Rumbler Ewohoxuq"
    functions.refresh_stat_bonuses(enemy)
    assert functions.combat_resistance(enemy, "crushing") > 1.0
    note = mitigation_note(enemy, "crushing")
    assert "protection" in note, note
    assert "resistance" not in note, note


def test_an_npc_swing_names_protection_only():
    """The hostile-NPC damage line applies protection and NO resistance.

    ``_npc._npc_flat_damage`` is ``power - protection``; the resistance
    multiplier never enters it. The note stays honest about that because those
    moves declare no ``base_damage_type`` — a pairing this test exists to pin,
    so that adding one to an NPC move without also moving it onto
    ``resolve_damage`` fails here instead of shipping a note crediting a
    resistance the swing never scored.
    """
    import src.moves as moves

    slime = Slime()
    jean = make_player()
    swing = moves.NpcAttack(slime)
    assert getattr(swing, "base_damage_type", None) is None, (
        "an NPC attack now declares a damage type; check whether its damage "
        "line applies resistance before trusting mitigation_note here"
    )
    note = mitigation_note(jean, getattr(swing, "base_damage_type", None))
    assert "resistance" not in note, note
    assert "protection" in note, note


def test_the_note_is_silent_when_nothing_mitigated():
    """No armour, no resistance: "" rather than an invented reason."""
    bare = make_player()
    bare.protection = 0
    assert mitigation_note(bare, "slashing") == ""
