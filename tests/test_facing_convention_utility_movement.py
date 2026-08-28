"""Facing-convention regressions for ``src/moves/_utility.py`` and
``src/moves/_movement.py``.

The engine scored attack angles with the arguments reversed:
``angle_to_target(attacker_pos, defender_pos)`` is the bearing from the
*attacker* toward the defender, which is the exact 180-degree opposite of the
question the facing system asks. The correct question -- owned by
``positions.attack_angle_diff(attacker_pos, defender_pos)`` -- is the bearing
from the *defender* toward the attacker, measured against the defender's own
facing:

* 0 deg   -- the defender is looking straight at the attacker (frontal)
* 90 deg  -- the attacker is on the defender's flank
* 180 deg -- the attacker is at the defender's back (rear)

Every case below is built by construction: the defender is given an explicit
facing and the attacker is placed at an explicit bearing from it, so the
expected label follows from the geometry rather than from what the code
currently prints. Each also fails under the inverted read -- the boundary
cases for ``FlankingManeuver`` are chosen specifically because the flank band
``45 < diff <= 135`` is otherwise nearly symmetric under ``diff -> 180 - diff``
and so hides the inversion everywhere except at its two edges.
"""

import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import src.functions as functions  # noqa: E402
import src.moves as moves  # noqa: E402
from src.narration import capture_narration  # noqa: E402
from src.positions import CombatPosition, Direction  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

RESISTANCE = {
    "piercing": 1.0,
    "slashing": 1.0,
    "crushing": 1.0,
    "fire": 1.0,
    "ice": 1.0,
    "shock": 1.0,
    "earth": 1.0,
    "light": 1.0,
    "dark": 1.0,
    "spiritual": 1.0,
    "pure": 1.0,
}


class FakeWeapon:
    def __init__(self):
        self.name = "Broadsword"
        self.subtype = "Sword"
        self.type = "Weapon"
        self.damage = 20
        self.str_mod = 0.5
        self.fin_mod = 0.5
        self.weight = 3.0
        self.wpnrange = (0, 5)
        self.isequipped = True


class FakeCombatant:
    """Enough of a combatant for the display and hand-rolled damage paths."""

    def __init__(self, name, x, y, facing, hp=1000, protection=0):
        self.name = name
        self.x = x
        self.y = y
        self.hp = hp
        self.maxhp = hp
        self.protection = protection
        self.strength = 12
        self.finesse = 8
        self.speed = 10
        self.endurance = 10
        self.intelligence = 10
        self.charisma = 10
        self.faith = 10
        self.fatigue = 200
        self.maxfatigue = 200
        self.heat = 1.0
        self.friend = False
        self.in_combat = True
        self.states = []
        self.known_moves = []
        self.combat_list = []
        self.combat_list_allies = []
        self.combat_proximity = {}
        self.combat_exp = {"Basic": 0, "Sword": 0}
        self.skill_exp = {"Basic": 0, "Sword": 0}
        self.resistance = dict(RESISTANCE)
        self.status_resistance = {"generic": 0.0, "stun": 0.0}
        self.current_move = None
        self.eq_weapon = FakeWeapon()
        self.inventory = []
        self.pronouns = {"subject": "he", "object": "him", "possessive": "his"}
        self.combat_position = CombatPosition(x=x, y=y, facing=facing)

    def is_alive(self):
        return self.hp > 0

    def change_heat(self, amount):  # pragma: no cover - not exercised here
        pass


#: Positions at these bearings *from the defender* (which faces north) land in
#: each labelled band. ``Check``'s display buckets are <45 front, <90 flank,
#: else rear.
_DEFENDER_AT = (5, 5)
_BEARING_FROM_DEFENDER = {
    "front": (5, 10),   # due north of it -- it is looking right at us: 0 deg
    "flank": (7, 6),    # off its right shoulder: 63 deg
    "rear": (5, 0),     # due south of it -- at its back: 180 deg
}


def _defender(facing=Direction.N, **kwargs):
    return FakeCombatant("Enemy", _DEFENDER_AT[0], _DEFENDER_AT[1], facing, **kwargs)


def _attacker_at(band, name="Jean"):
    x, y = _BEARING_FROM_DEFENDER[band]
    return FakeCombatant(name, x, y, Direction.N)


# ---------------------------------------------------------------------------
# Check._display_coordinate_info -- the enemy line
# ---------------------------------------------------------------------------


class TestCheckEnemyBracket:
    """The front/flank/rear bracket ``Check`` prints for each enemy."""

    @pytest.mark.parametrize(
        "band, expected_color",
        [("front", "red"), ("flank", "yellow"), ("rear", "green")],
    )
    def test_bracket_matches_constructed_geometry(self, band, expected_color):
        player = _attacker_at(band)
        enemy = _defender()
        player.combat_proximity = {enemy: 5}
        move = moves.Check(player)

        with capture_narration() as messages:
            move._display_coordinate_info(player)

        assert [(m["text"], m["color"]) for m in messages] == [
            (f"Enemy at (5, 5) facing N is 5 ft away ({band}, N-facing)",
             expected_color)
        ]

    def test_standing_behind_a_north_facing_enemy_reads_rear(self):
        """The headline case: an enemy looking north, Jean at its back.

        Under the inverted read this printed "front" -- it told the player
        their genuine rear position was the one angle that carries a damage
        *penalty*.
        """
        player = _attacker_at("rear")
        enemy = _defender()
        player.combat_proximity = {enemy: 5}

        with capture_narration() as messages:
            moves.Check(player)._display_coordinate_info(player)

        assert "(rear, N-facing)" in messages[0]["text"]
        assert "front" not in messages[0]["text"]


# ---------------------------------------------------------------------------
# Check._display_coordinate_info -- the ally line
# ---------------------------------------------------------------------------


class TestCheckAllyBracket:
    """The bracket ``Check`` prints for each ally, relative to each enemy."""

    @pytest.mark.parametrize("band", ["front", "flank", "rear"])
    def test_ally_bracket_matches_constructed_geometry(self, band):
        # Jean stands due west of the enemy -- a different bearing from the
        # ally's in every row -- so an ally line computed from the *player's*
        # angle instead of the ally's would fail here.
        player = FakeCombatant("Jean", 0, 5, Direction.N)
        enemy = _defender()
        player.combat_proximity = {enemy: 5}

        ally = _attacker_at(band, name="Gorran")
        ally.combat_proximity = {enemy: 4}
        player.combat_list_allies = [ally]

        with capture_narration() as messages:
            moves.Check(player)._display_coordinate_info(player)

        ally_line = messages[1]["text"]
        assert ally_line == (
            f"  → Gorran at ({ally.combat_position.x}, "
            f"{ally.combat_position.y}) is 4 ft away ({band}-facing)"
        )


# ---------------------------------------------------------------------------
# FlankingManeuver.execute -- the "+15-25% damage bonus" claim
# ---------------------------------------------------------------------------


_FLANK_SUCCESS = "successfully positioned to flank"


def _flank_execute(attacker_xy, defender_facing=Direction.N):
    player = FakeCombatant("Jean", attacker_xy[0], attacker_xy[1], Direction.N)
    enemy = _defender(facing=defender_facing)
    player.combat_proximity = {enemy: 8}
    move = moves.FlankingManeuver(player)
    move.target = enemy
    with capture_narration() as messages:
        move.execute(player)
    return " ".join(m["text"] for m in messages)


class TestFlankingManeuverSuccessMessage:
    """``FlankingManeuver`` promises a damage bonus it can only deliver when
    the player is genuinely off the target's guard.

    The flank band the message gates on (``45 < diff <= 135``) is symmetric
    about 90 deg, so the 180-deg inversion is invisible except exactly at its
    two edges -- which is why both edges are pinned here.
    """

    def test_deep_flank_at_135_degrees_announces_the_bonus(self):
        """South-east of a north-facing target: 135 deg, a 1.25x deep flank.

        The inverted read scored this as 45 deg and stayed silent -- the
        player earned the bonus and was never told.
        """
        out = _flank_execute((10, 0))
        assert _FLANK_SUCCESS in out

    def test_front_quarter_at_45_degrees_stays_silent(self):
        """North-east of a north-facing target: 45 deg, inside its front
        quarter, where the curve is a 0.85x *penalty*.

        The inverted read scored this as 135 deg and congratulated the player
        on a flank they had not achieved.
        """
        out = _flank_execute((10, 10))
        assert _FLANK_SUCCESS not in out
        assert "moved to the side" in out

    def test_head_on_stays_silent(self):
        out = _flank_execute(_BEARING_FROM_DEFENDER["front"])
        assert _FLANK_SUCCESS not in out

    def test_true_flank_announces_the_bonus(self):
        out = _flank_execute(_BEARING_FROM_DEFENDER["flank"])
        assert _FLANK_SUCCESS in out

    def test_directly_behind_is_not_reported_as_a_flank(self):
        """180 deg is the rear, not a flank: the move's own band excludes it."""
        out = _flank_execute(_BEARING_FROM_DEFENDER["rear"])
        assert _FLANK_SUCCESS not in out


# ---------------------------------------------------------------------------
# Facing damage on the hand-rolled attacks in _utility.py
# ---------------------------------------------------------------------------


def _damage_from(move_cls, band, monkeypatch, distance=2):
    """Resolve one guaranteed, non-glancing hit.

    Returns ``(damage_dealt, unscaled_power)``.
    """
    player = _attacker_at(band)
    enemy = _defender(hp=100000)
    player.combat_list = [enemy]
    player.combat_proximity = {enemy: distance}
    enemy.combat_list = [player]
    enemy.combat_proximity = {player: distance}

    move = move_cls(player)
    move.target = enemy

    recorded = []
    monkeypatch.setattr(move, "hit", lambda damage, glance: recorded.append(damage))
    # Pin the dice: uniform() at 1.0 removes the +/-20% damage spread, and a
    # roll of 0 both guarantees the hit and keeps it outside the glancing
    # window (hit_chance - roll >= 10).
    monkeypatch.setattr("src.moves._utility.random.uniform", lambda a, b: 1.0)
    monkeypatch.setattr("src.moves._utility.random.randint", lambda a, b: 0)
    monkeypatch.setattr(functions, "check_parry", lambda target: False)

    with capture_narration():
        move.execute(player)

    assert recorded, f"{move_cls.__name__} did not resolve a hit"
    return recorded[0], move.power


@pytest.mark.parametrize("move_cls", [moves.Attack, moves.Disrupt])
class TestHandRolledAttacksHonourFacingDamage:
    """``Attack`` and ``Disrupt`` compute damage in their own ``execute()``
    rather than through ``standard_execute_attack``, so the shared facing
    curve (issue #394) has to be applied explicitly or these two moves
    silently opt out of the whole positioning system.

    Protection is 0 and every resistance is 1.0 here, so the damage that
    reaches ``hit()`` is the facing-scaled power itself -- which makes the
    curve's shape (0.85 front / 1.15 flank / 1.40 rear) directly observable.
    """

    def test_rear_beats_flank_beats_front(self, move_cls, monkeypatch):
        front, _ = _damage_from(move_cls, "front", monkeypatch)
        flank, _ = _damage_from(move_cls, "flank", monkeypatch)
        rear, _ = _damage_from(move_cls, "rear", monkeypatch)
        assert front < flank < rear

    @pytest.mark.parametrize(
        "band, expected_multiplier",
        [("front", 0.85), ("flank", 1.15), ("rear", 1.40)],
    )
    def test_damage_equals_the_shared_curve_applied_to_power(
        self, move_cls, band, expected_multiplier, monkeypatch
    ):
        """Pinned to the exact band value in positions.get_damage_modifier.

        Protection is 0 and every resistance is 1.0, so the number reaching
        hit() is the facing-scaled power itself. A facing-blind execute()
        returns the raw power for all three bands and fails two of them.
        """
        damage, power = _damage_from(move_cls, band, monkeypatch)
        assert damage == max(1, int(power * expected_multiplier))

    def test_facing_curve_applies_before_protection(self, move_cls, monkeypatch):
        """Armour keeps its full bite from every angle.

        ``apply_facing_damage`` scales *power*, not the post-protection
        result, so a rear strike against an armoured target loses exactly the
        same flat protection as a frontal one -- the bonus does not get
        multiplied through the subtraction.
        """
        bare, _ = _damage_from(move_cls, "rear", monkeypatch)

        player = _attacker_at("rear")
        armoured = _defender(hp=100000, protection=10)
        player.combat_list = [armoured]
        player.combat_proximity = {armoured: 2}
        armoured.combat_list = [player]
        armoured.combat_proximity = {player: 2}
        move = move_cls(player)
        move.target = armoured
        recorded = []
        monkeypatch.setattr(move, "hit", lambda damage, glance: recorded.append(damage))
        monkeypatch.setattr("src.moves._utility.random.uniform", lambda a, b: 1.0)
        monkeypatch.setattr("src.moves._utility.random.randint", lambda a, b: 0)
        monkeypatch.setattr(functions, "check_parry", lambda target: False)
        with capture_narration():
            move.execute(player)

        assert recorded
        assert bare - recorded[0] == pytest.approx(10, abs=1)

    def test_no_positions_leaves_damage_untouched(self, move_cls, monkeypatch):
        """The facing system is a no-op when the 2D grid is not in play."""
        with_positions, _ = _damage_from(move_cls, "flank", monkeypatch)

        player = _attacker_at("flank")
        enemy = _defender(hp=100000)
        player.combat_position = None
        enemy.combat_position = None
        player.combat_list = [enemy]
        player.combat_proximity = {enemy: 2}
        enemy.combat_list = [player]
        enemy.combat_proximity = {player: 2}
        move = move_cls(player)
        move.target = enemy
        recorded = []
        monkeypatch.setattr(move, "hit", lambda damage, glance: recorded.append(damage))
        monkeypatch.setattr("src.moves._utility.random.uniform", lambda a, b: 1.0)
        monkeypatch.setattr("src.moves._utility.random.randint", lambda a, b: 0)
        monkeypatch.setattr(functions, "check_parry", lambda target: False)
        with capture_narration():
            move.execute(player)

        assert recorded
        # 1.15x flank bonus applied above, none applied here.
        assert recorded[0] < with_positions
