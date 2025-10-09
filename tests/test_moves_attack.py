import math
import types
import random
import pytest

import src.items as items
import src.functions as functions
from src.player import Player
from src.moves import Attack, Move


class DummyEnemy:
    def __init__(self, name="Target", finesse=5, protection=0):
        self.name = name
        self.finesse = finesse
        self.protection = protection
        self.friend = False
        self.hp = 100
        self.maxhp = 100
        # resistance lookup; default 1.0
        self.resistance = {
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
            "pure": 1.0
        }

    def is_alive(self):
        return self.hp > 0


def get_attack_move(player: Player) -> Attack:
    for m in player.known_moves:
        if isinstance(m, Attack):
            return m
    raise AssertionError("Attack move not found in player's known moves")


def test_attack_initial_evaluate_uses_fists():
    player = Player()
    attack = get_attack_move(player)
    # Ensure initial weapon is fists
    assert player.eq_weapon.name == "fists"
    # Attack should have been evaluated in __init__
    expected_power = player.eq_weapon.damage + (player.strength * player.eq_weapon.str_mod) + \
        (player.finesse * player.eq_weapon.fin_mod)
    assert math.isclose(attack.power, expected_power)
    assert player.eq_weapon.wpnrange == attack.mvrange
    assert "fists" in attack.stage_announce[1].lower()


def test_attack_viable_re_evaluates_after_weapon_change():
    player = Player()
    attack = get_attack_move(player)
    fists_power = attack.power
    # Give player a dagger and equip it
    dagger = items.Dagger()
    dagger.isequipped = True
    player.eq_weapon = dagger
    player.inventory.append(dagger)
    # Provide an enemy within dagger range so viable() runs True path
    enemy = DummyEnemy()
    mid = sum(dagger.wpnrange) / 2
    player.combat_proximity[enemy] = mid
    # Call viable (should trigger evaluate and update internal values)
    assert attack.viable() is True
    expected_power = dagger.damage + (player.strength * dagger.str_mod) + (player.finesse * dagger.fin_mod)
    assert attack.power != fists_power
    assert math.isclose(attack.power, expected_power)
    assert attack.mvrange == dagger.wpnrange
    assert dagger.name.lower() in attack.stage_announce[1].lower()


def test_attack_execute_applies_damage(monkeypatch):
    player = Player()
    # Equip a stronger weapon to make damage assertion clearer
    hammer = items.Hammer()
    hammer.isequipped = True
    player.eq_weapon = hammer
    player.inventory.append(hammer)
    attack = get_attack_move(player)
    # Enemy in range
    enemy = DummyEnemy(finesse=0, protection=0)
    distance = sum(hammer.wpnrange) / 2
    player.combat_proximity[enemy] = distance
    attack.target = enemy
    # Force deterministic random outcomes
    monkeypatch.setattr(random, 'randint', lambda a, b: a)  # lowest possible roll => guaranteed hit
    monkeypatch.setattr(random, 'uniform', lambda a, b: 1.0)
    # Prevent parry
    monkeypatch.setattr(functions, 'check_parry', lambda tgt: False)
    # Ensure evaluate runs with new weapon
    assert attack.viable() is True
    starting_hp = enemy.hp
    # Execute stage
    attack.execute(player)
    # Calculate expected raw power and resulting integer damage (since resistance=1, protection=0, heat=1)
    expected_power = hammer.damage + (player.strength * hammer.str_mod) + (player.finesse * hammer.fin_mod)
    # Damage can be reduced to zero if negative after protection calc; here it's positive
    # Execute uses attack.power which should equal expected_power
    assert math.isclose(attack.power, expected_power)
    # Damage int cast performed inside execute
    dealt = starting_hp - enemy.hp
    assert dealt == int(expected_power)


def test_move_base_process_stage_no_errors():
    # Minimal smoke test for base Move lifecycle
    dummy_user = types.SimpleNamespace(current_move=None, speed=1)
    move = Move(name="Base", description="", xp_gain=0, current_stage=0, beats_left=0,
                stage_announce=["a", "b", "c", "d"], target=dummy_user, user=dummy_user,
                stage_beat=[0, 0, 0, 0], targeted=False)
    dummy_user.current_move = move
    # Should run prep -> execute -> recoil -> cooldown without error when advanced
    move.advance(dummy_user)  # processes all zero-beat stages
    # After cycling it should have reset current_stage to 0
    assert move.current_stage == 0


@pytest.mark.parametrize("weapon_cls", [items.Rock, items.RustedDagger, items.Dagger, items.Hammer])
def test_attack_evaluate_various_weapons(weapon_cls):
    player = Player()
    weapon = weapon_cls()
    weapon.isequipped = True
    player.eq_weapon = weapon
    player.inventory.append(weapon)
    attack = get_attack_move(player)
    # Enemy needed for viability path (range inclusive)
    mid = sum(weapon.wpnrange) / 2 if hasattr(weapon, 'wpnrange') else 1
    enemy = DummyEnemy()
    player.combat_proximity[enemy] = mid
    attack.viable()
    expected_power = weapon.damage + (player.strength * weapon.str_mod) + (player.finesse * weapon.fin_mod)
    assert math.isclose(attack.power, expected_power)
    assert attack.mvrange == weapon.wpnrange
    assert weapon.name.lower() in attack.stage_announce[1].lower()

