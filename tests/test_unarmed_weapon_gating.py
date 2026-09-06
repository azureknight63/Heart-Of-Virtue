"""Unarmed moves must read the user's *current* weapon, not one cached at build time.

``Jab`` and ``PowerStrike`` both stashed ``user.eq_weapon`` in ``__init__`` and
then consulted that reference forever, even though a move outlives any number
of equip/unequip cycles and ``evaluate()``'s documented job is to "adjust the
move's attributes to match the current game state".

Two player-visible consequences motivated these tests:

* **Jab reported two different power values for the same named move.** Taken
  from ``player.skilltree`` — built during ``Player.__init__``, when Jean is
  bare-handed — it cached ``Fists`` and computed fist damage forever. Built
  through ``functions.learn_all_skills_from_skilltree`` (the ``learn_all_skills``
  config flag and the Adjutant in the combat testing arena) while a Longsword
  was equipped, it cached the Longsword and computed sword damage forever. The
  arena was therefore balancing a version of Jab that no player can ever get.
  Compounding this, ``standard_viability_attack`` skips its weapon check
  entirely whenever ``"Unarmed"`` is among the allowed subtypes, so Jab was
  castable *with a sword in hand*. The project decision is fists-only, always.

* **PowerStrike was unusable for real players.** Its ``viable()`` tested the
  cached weapon's subtype against ``"Bludgeon"``. Acquired bare-handed (the
  skill-tree path every player takes) it cached ``Fists``/``Unarmed`` and stayed
  un-castable no matter what mace Jean picked up; built while holding a mace it
  stayed castable after the mace came off.
"""

import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import src.items as items  # noqa: E402
import src.npc as npc  # noqa: E402
from src.moves import Jab, PowerStrike  # noqa: E402
from src.player import Player  # noqa: E402


def _player_in_combat():
    """A player with one hostile adjacent, so range checks pass and only the
    weapon half of viability is under test."""
    player = Player()
    enemy = npc.Slime()
    player.combat_proximity = {enemy: 1}
    player.combat_list = [enemy]
    enemy.combat_proximity = {player: 1}
    enemy.combat_list = [player]
    return player


def _skilltree_move(player, name):
    """The move instance the skill tree holds — built during ``Player.__init__``."""
    for skills in player.skilltree.subtypes.values():
        for move in skills:
            if move.name == name:
                return move
    pytest.fail(f"{name} not found in the player's skill tree")


def _bare_handed(player):
    """Put the player back to fists, the way ``unequip_item`` does."""
    player.eq_weapon = player.fists


class TestJabIsFistsOnly:
    def test_viable_when_bare_handed(self):
        player = _player_in_combat()
        _bare_handed(player)
        assert Jab(player).viable() is True

    def test_viable_when_the_user_has_no_eq_weapon_at_all(self):
        """NPCs and degraded users model unarmed as ``eq_weapon = None``."""
        player = _player_in_combat()
        player.eq_weapon = None
        assert Jab(player).viable() is True

    @pytest.mark.parametrize(
        "weapon_factory", [items.Longsword, items.RustedIronMace, items.Rock]
    )
    def test_not_viable_while_holding_a_weapon(self, weapon_factory):
        player = _player_in_combat()
        player.eq_weapon = weapon_factory()
        assert Jab(player).viable() is False

    def test_availability_tracks_equipment_changes_after_acquisition(self):
        """Acquiring Jab does not freeze its availability.

        The whole bug was that ``__init__`` decided this once and forever.
        """
        player = _player_in_combat()
        _bare_handed(player)
        jab = Jab(player)
        assert jab.viable() is True

        player.eq_weapon = items.Longsword()
        assert jab.viable() is False, "equipping a sword must retire the fists-only Jab"

        _bare_handed(player)
        assert jab.viable() is True, "dropping the sword must bring Jab back"

    def test_power_always_derives_from_fists(self):
        """Even mid-swap, Jab's numbers are fist numbers — never sword-scaled."""
        player = _player_in_combat()
        _bare_handed(player)
        jab = Jab(player)
        jab.evaluate()
        unarmed_power = jab.power

        player.eq_weapon = items.Longsword()
        jab.evaluate()

        assert jab.weapon.subtype == "Unarmed"
        assert jab.power == unarmed_power, (
            "Jab is fists-only; equipping a weapon must not change its damage"
        )

    def test_skilltree_instance_and_fresh_instance_agree(self):
        """The two acquisition paths must produce the same move.

        ``player.skilltree`` is built during ``Player.__init__`` (bare-handed);
        ``functions.learn_all_skills_from_skilltree`` builds a second
        ``Skilltree`` later, whenever the player happens to be equipped.
        """
        player = _player_in_combat()

        for weapon in (player.fists, items.Longsword()):
            player.eq_weapon = weapon
            tree_jab = _skilltree_move(player, "Jab")
            fresh_jab = Jab(player)
            tree_jab.evaluate()
            fresh_jab.evaluate()

            assert tree_jab.power == fresh_jab.power
            assert tree_jab.fatigue_cost == fresh_jab.fatigue_cost
            assert tree_jab.stage_beat == fresh_jab.stage_beat
            assert tree_jab.viable() == fresh_jab.viable()

    def test_keeps_its_quick_and_cheap_identity(self):
        """"A quick unarmed attack that causes little damage but has a very low
        fatigue cost and zero cooldown" — the skill tree's own description."""
        player = _player_in_combat()
        _bare_handed(player)
        jab = Jab(player)
        jab.evaluate()

        prep, execute, recoil, cooldown = jab.stage_beat
        assert cooldown == 0, "Jab is documented as having zero cooldown"
        assert prep == 0 and recoil == 0, "Jab is documented as a quick strike"
        assert execute == 1
        assert 0 < jab.power, "Jab must still do some damage"
        assert jab.fatigue_cost <= 50, "Jab is documented as very low fatigue cost"


class TestPowerStrikeReadsTheCurrentWeapon:
    def test_becomes_viable_once_a_bludgeon_is_equipped(self):
        """The regression that made PowerStrike dead on arrival for players."""
        player = _player_in_combat()
        _bare_handed(player)
        strike = PowerStrike(player)
        assert strike.viable() is False, "no bludgeon in hand yet"

        player.eq_weapon = items.RustedIronMace()
        assert strike.viable() is True, (
            "PowerStrike acquired bare-handed must become castable once a "
            "bludgeon is equipped"
        )

    def test_stops_being_viable_when_the_bludgeon_comes_off(self):
        player = _player_in_combat()
        player.eq_weapon = items.RustedIronMace()
        strike = PowerStrike(player)
        assert strike.viable() is True

        _bare_handed(player)
        assert strike.viable() is False

    def test_not_viable_with_a_non_bludgeon_weapon(self):
        player = _player_in_combat()
        player.eq_weapon = items.Longsword()
        assert PowerStrike(player).viable() is False

    def test_announcement_names_the_current_weapon(self):
        """``refresh_announcements`` reads ``self.weapon``; a stale cache made it
        narrate the wrong weapon."""
        player = _player_in_combat()
        _bare_handed(player)
        strike = PowerStrike(player)

        mace = items.RustedIronMace()
        player.eq_weapon = mace
        strike.evaluate()

        assert strike.weapon is mace
        assert mace.name in strike.stage_announce[1]
