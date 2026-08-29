"""The player-facing attack-angle label must agree with the engine's curve.

``positions.get_damage_modifier`` scores an attack in four bands -- front
(0-45, x0.85), flank (45-90, x1.15), deep flank (90-135, x1.25) and rear
(135-180, x1.40). Two display sites re-banded the same angle by hand and got a
different answer:

* ``Check._display_coordinate_info`` (both its enemy line and its duplicated
  ally line) collapsed the curve into three buckets banding at 45/90, so a
  100-degree attack -- a 1.25x *deep flank* -- was reported to the player as
  "rear", and the 45- and 90-degree boundaries were each labelled with the next
  band's name.
* ``FlankingManeuver.execute`` printed "moved to the side" for both a failed
  head-on approach (<= 45 deg, a damage *penalty*) and a genuine rear position
  (> 135 deg, the strongest band in the game).

Every expectation below is written from the geometry and from
:data:`positions.FACING_BANDS`, so the labels are checked against what the
engine scores rather than against what the display currently prints.
"""

import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import src.moves as moves  # noqa: E402
import src.positions as positions  # noqa: E402
from src.moves._movement import (  # noqa: E402
    _FLANK_OUTCOMES,
    _FLANK_OUTCOME_DEFAULT,
)
from src.narration import capture_narration  # noqa: E402
from src.positions import CombatPosition, Direction  # noqa: E402


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

#: The defender sits mid-grid looking due north; each attacker coordinate below
#: puts the attacker at an exact bearing off that guard. Verified by
#: ``TestGeometryFixture`` so a wrong coordinate can never quietly re-label a
#: case instead of failing it.
_DEFENDER_AT = (25, 25)
_ATTACKER_AT = {
    0: (25, 26),    # dead ahead of the guard
    45: (0, 50),    # the upper edge of the front quarter
    46: (0, 49),    # one degree into the flank
    90: (0, 25),    # square on the flank
    100: (2, 21),   # the headline case: a deep flank, mislabelled "rear"
    135: (0, 0),    # the upper edge of the deep flank
    136: (1, 0),    # one degree into the rear
    180: (25, 0),   # directly behind the guard
}

#: What the shared table says each of those angles is. Spelled out rather than
#: derived so this file pins the bands instead of restating whatever the code
#: happens to do.
_EXPECTED_LABEL = {
    0: "front",
    45: "front",
    46: "flank",
    90: "flank",
    100: "deep flank",
    135: "deep flank",
    136: "rear",
    180: "rear",
}


class FakeCombatant:
    """The minimum ``Check`` and ``FlankingManeuver`` read off a combatant."""

    def __init__(self, name, x, y, facing=Direction.N):
        self.name = name
        self.hp = 100
        self.combat_position = CombatPosition(x=x, y=y, facing=facing)
        self.combat_proximity = {}
        self.combat_list = []
        self.combat_list_allies = []

    def is_alive(self):
        return self.hp > 0


def _defender():
    return FakeCombatant("Enemy", *_DEFENDER_AT)


def _attacker_at(angle, name="Jean"):
    return FakeCombatant(name, *_ATTACKER_AT[angle])


class TestGeometryFixture:
    """The fixture coordinates really are the angles they claim to be."""

    @pytest.mark.parametrize("angle", sorted(_ATTACKER_AT))
    def test_coordinates_produce_the_named_angle(self, angle):
        assert (
            positions.attack_angle_diff(
                _attacker_at(angle).combat_position, _defender().combat_position
            )
            == angle
        )


# ---------------------------------------------------------------------------
# The band table itself
# ---------------------------------------------------------------------------


class TestFacingBandTable:
    """``FACING_BANDS`` is the one place the boundaries are written down."""

    def test_modifiers_are_unchanged_across_every_integer_angle(self):
        """The table-driven lookup reproduces the original if/elif ladder.

        Transcribed from the pre-refactor bodies of ``get_damage_modifier`` and
        ``get_accuracy_modifier``; if sharing the table with the labels shifted
        a single boundary, the combat curve would have moved silently.
        """

        def historical_damage(angle):
            if 0 <= angle <= 45:
                return 0.85
            elif 45 < angle <= 90:
                return 1.15
            elif 90 < angle <= 135:
                return 1.25
            else:
                return 1.40

        def historical_accuracy(angle):
            if 0 <= angle <= 45:
                return 0.95
            elif 45 < angle <= 90:
                return 1.10
            elif 90 < angle <= 135:
                return 1.20
            else:
                return 1.30

        for angle in range(0, 181):
            assert positions.get_damage_modifier(angle) == historical_damage(angle)
            assert positions.get_accuracy_modifier(angle) == historical_accuracy(angle)

    def test_out_of_range_angles_still_fall_back_to_rear(self):
        """The original ``else`` caught negatives and angles past 180."""
        for angle in (-1, -90, 181, 360):
            assert positions.get_damage_modifier(angle) == 1.40
            assert positions.get_accuracy_modifier(angle) == 1.30
            assert positions.facing_band_label(angle) == "rear"

    def test_each_band_has_a_distinct_label_and_colour(self):
        labels = [band.label for band in positions.FACING_BANDS]
        colors = [band.color for band in positions.FACING_BANDS]
        assert labels == ["front", "flank", "deep flank", "rear"]
        assert len(set(colors)) == len(colors)

    @pytest.mark.parametrize("angle, expected", sorted(_EXPECTED_LABEL.items()))
    def test_label_matches_the_expected_band(self, angle, expected):
        assert positions.facing_band_label(angle) == expected

    @pytest.mark.parametrize("angle", range(0, 181))
    def test_label_and_multiplier_never_disagree(self, angle):
        """Whatever band the label names is the band whose multiplier applies."""
        band = positions.facing_band(angle)
        assert band.label == positions.facing_band_label(angle)
        assert band.damage_modifier == positions.get_damage_modifier(angle)
        assert band.accuracy_modifier == positions.get_accuracy_modifier(angle)

    def test_damage_percent_label_matches_the_multiplier(self):
        assert [b.damage_percent_label for b in positions.FACING_BANDS] == [
            "-15%",
            "+15%",
            "+25%",
            "+40%",
        ]


# ---------------------------------------------------------------------------
# Check._display_coordinate_info
# ---------------------------------------------------------------------------


def _check_lines(player):
    with capture_narration() as messages:
        moves.Check(player)._display_coordinate_info(player)
    return messages


class TestCheckEnemyLabel:
    @pytest.mark.parametrize("angle, expected", sorted(_EXPECTED_LABEL.items()))
    def test_enemy_line_names_the_engine_band(self, angle, expected):
        player = _attacker_at(angle)
        enemy = _defender()
        player.combat_proximity = {enemy: 5}

        messages = _check_lines(player)

        assert messages[0]["text"] == (
            "Enemy at (25, 25) facing N is 5 ft away "
            f"({expected}, N-facing)"
        )
        assert messages[0]["color"] == positions.facing_band(angle).color

    def test_a_hundred_degree_attack_is_not_called_rear(self):
        """The headline defect: 100 deg is a 1.25x deep flank, not the rear.

        Calling it "rear" told the player they had the game's strongest band
        (x1.40) when the engine was paying them x1.25.
        """
        player = _attacker_at(100)
        enemy = _defender()
        player.combat_proximity = {enemy: 5}

        text = _check_lines(player)[0]["text"]

        assert "rear" not in text
        assert "deep flank" in text
        assert positions.get_damage_modifier(100) == 1.25

    def test_boundary_angles_are_labelled_by_the_engine_bands(self):
        """45 deg is still the front and 90 deg is still the flank.

        The hand-rolled ladder used ``< 45`` / ``< 90`` where the engine uses
        ``<= 45`` / ``<= 90``, so both boundaries were reported one band too
        generous.
        """
        for angle, expected in ((45, "front"), (90, "flank")):
            player = _attacker_at(angle)
            enemy = _defender()
            player.combat_proximity = {enemy: 5}
            assert f"({expected}, N-facing)" in _check_lines(player)[0]["text"]

    def test_all_four_bands_are_reachable_and_distinct(self):
        seen = []
        for angle in (0, 46, 100, 180):
            player = _attacker_at(angle)
            enemy = _defender()
            player.combat_proximity = {enemy: 5}
            line = _check_lines(player)[0]["text"]
            seen.append(line.split("(")[-1].split(",")[0])
        assert seen == ["front", "flank", "deep flank", "rear"]


class TestCheckAllyLabel:
    """The ally line carried its own copy of the same three-bucket ladder."""

    @pytest.mark.parametrize("angle, expected", sorted(_EXPECTED_LABEL.items()))
    def test_ally_line_names_the_engine_band(self, angle, expected):
        # Jean stands square on the enemy's flank; the ally is the one whose
        # bearing varies, so a line computed from Jean's angle fails here.
        player = FakeCombatant("Jean", *_ATTACKER_AT[90])
        enemy = _defender()
        player.combat_proximity = {enemy: 5}

        ally = _attacker_at(angle, name="Gorran")
        ally.combat_proximity = {enemy: 4}
        player.combat_list_allies = [ally]

        ally_line = _check_lines(player)[1]["text"]

        assert ally_line == (
            f"  → Gorran at ({ally.combat_position.x}, "
            f"{ally.combat_position.y}) is 4 ft away ({expected}-facing)"
        )

    def test_ally_at_a_hundred_degrees_is_not_called_rear(self):
        player = FakeCombatant("Jean", *_ATTACKER_AT[90])
        enemy = _defender()
        player.combat_proximity = {enemy: 5}

        ally = _attacker_at(100, name="Gorran")
        ally.combat_proximity = {enemy: 4}
        player.combat_list_allies = [ally]

        assert "(deep flank-facing)" in _check_lines(player)[1]["text"]


# ---------------------------------------------------------------------------
# FlankingManeuver.execute
# ---------------------------------------------------------------------------


def _flank_message(angle):
    player = _attacker_at(angle)
    enemy = _defender()
    player.combat_proximity = {enemy: 8}
    move = moves.FlankingManeuver(player)
    move.target = enemy
    with capture_narration() as messages:
        move.execute(player)
    return " ".join(m["text"] for m in messages)


class TestFlankingManeuverOutcome:
    def test_head_on_failure_and_genuine_rear_no_longer_share_a_message(self):
        """The defect: both printed "moved to the side of Enemy!".

        0 deg is a failed maneuver carrying a x0.85 penalty; 180 deg is the
        best result the move can produce, x1.40. Reporting them identically
        told the player nothing about which had happened.
        """
        head_on = _flank_message(0)
        rear = _flank_message(180)

        assert head_on != rear
        assert "-15%" in head_on
        assert "+40%" in rear

    @pytest.mark.parametrize("angle", sorted(_EXPECTED_LABEL))
    def test_message_quotes_the_band_the_engine_will_pay(self, angle):
        band = positions.facing_band(angle)
        assert f"({band.damage_percent_label} damage)" in _flank_message(angle)

    def test_each_band_produces_its_own_message(self):
        messages = [_flank_message(angle) for angle in (0, 46, 100, 180)]
        assert len(set(messages)) == 4

    def test_flank_and_deep_flank_still_announce_a_flank(self):
        for angle in (46, 90, 100, 135):
            assert "successfully positioned to flank" in _flank_message(angle)

    def test_failed_and_rear_outcomes_are_not_announced_as_flanks(self):
        for angle in (0, 45, 136, 180):
            assert "successfully positioned to flank" not in _flank_message(angle)

    def test_every_band_has_its_own_outcome_line(self):
        """No band may fall through to the generic default at runtime."""
        assert set(_FLANK_OUTCOMES) == {b.label for b in positions.FACING_BANDS}
        assert _FLANK_OUTCOME_DEFAULT not in _FLANK_OUTCOMES.values()
