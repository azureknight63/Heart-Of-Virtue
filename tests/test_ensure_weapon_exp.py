import types
import pytest

from src.moves import _ensure_weapon_exp, Attack
from src.player import Player
import src.items as items


class DummyWeapon:
    def __init__(self, subtype='TestBlade'):
        self.subtype = subtype
        self.name = 'UnitTest ' + subtype
        self.damage = 7
        self.str_mod = 1.5
        self.fin_mod = 0.5
        self.weight = 2
        self.wpnrange = (0, 5)


class DummyNoSubtypeWeapon:
    def __init__(self):
        self.name = 'Mystery Object'
        self.damage = 1
        self.str_mod = 1
        self.fin_mod = 1
        self.weight = 0
        self.wpnrange = (0, 1)


class DummyTarget:
    def __init__(self):
        self.name = 'Target'
        self.finesse = 0
        self.protection = 0
        self.hp = 100
        self.maxhp = 100
        self.friend = False
        self.resistance = {k: 1.0 for k in (
            'piercing','slashing','crushing','fire','ice','shock','earth','light','dark','spiritual','pure'
        )}

    def is_alive(self):
        return self.hp > 0


def test_ensure_weapon_exp_adds_missing_keys():
    user = types.SimpleNamespace()
    user.eq_weapon = DummyWeapon(subtype='TestSubtype')
    user.combat_exp = {'Basic': 0}
    user.skill_exp = {'Basic': 0}
    _ensure_weapon_exp(user)
    assert 'TestSubtype' in user.combat_exp and user.combat_exp['TestSubtype'] == 0
    assert 'TestSubtype' in user.skill_exp and user.skill_exp['TestSubtype'] == 0


def test_ensure_weapon_exp_idempotent_and_preserves_existing():
    user = types.SimpleNamespace()
    user.eq_weapon = DummyWeapon(subtype='Blade')
    user.combat_exp = {'Basic': 0, 'Blade': 42}
    user.skill_exp = {'Basic': 0, 'Blade': 99}
    _ensure_weapon_exp(user)
    assert user.combat_exp['Blade'] == 42
    assert user.skill_exp['Blade'] == 99
    # Call again to ensure no change
    _ensure_weapon_exp(user)
    assert user.combat_exp['Blade'] == 42
    assert user.skill_exp['Blade'] == 99


def test_ensure_weapon_exp_no_skill_exp_attribute():
    user = types.SimpleNamespace()
    user.eq_weapon = DummyWeapon(subtype='Novel')
    user.combat_exp = {'Basic': 0}
    # Deliberately no skill_exp
    _ensure_weapon_exp(user)
    assert 'Novel' in user.combat_exp


def test_ensure_weapon_exp_no_combat_exp_attribute():
    user = types.SimpleNamespace()
    user.eq_weapon = DummyWeapon(subtype='Ghost')
    # No combat_exp; should silently return without raising
    _ensure_weapon_exp(user)  # Should not raise
    assert not hasattr(user, 'skill_exp')  # ensure it didn't create unrelated attributes


def test_ensure_weapon_exp_weapon_without_subtype():
    user = types.SimpleNamespace()
    user.eq_weapon = DummyNoSubtypeWeapon()  # no subtype attr
    user.combat_exp = {'Basic': 0}
    user.skill_exp = {'Basic': 0}
    _ensure_weapon_exp(user)  # Should not add anything new
    assert set(user.combat_exp.keys()) == {'Basic'}
    assert set(user.skill_exp.keys()) == {'Basic'}


def test_attack_integration_creates_exp_entries(monkeypatch):
    player = Player()
    # Assign a unique subtype unlikely to exist already
    custom_subtype = 'UltraEdge'
    custom_weapon = DummyWeapon(subtype=custom_subtype)
    player.eq_weapon = custom_weapon
    # Remove key if the skilltree added it (defensive)
    player.combat_exp.pop(custom_subtype, None)
    player.skill_exp.pop(custom_subtype, None)
    # Build attack and enemy in range
    attack = None
    for mv in player.known_moves:
        if isinstance(mv, Attack):
            attack = mv
            break
    assert attack is not None
    enemy = DummyTarget()
    mid = sum(custom_weapon.wpnrange)/2
    player.combat_proximity[enemy] = mid
    attack.target = enemy
    # Force deterministic roll (guaranteed hit)
    monkeypatch.setattr('random.randint', lambda a,b: a)
    monkeypatch.setattr('random.uniform', lambda a,b: 1.0)
    # Execute viability (triggers evaluate) then attack.hit via execute path
    assert attack.viable() is True
    start_hp = enemy.hp
    attack.execute(player)
    # Keys should exist now
    assert custom_subtype in player.combat_exp
    assert custom_subtype in player.skill_exp
    # Damage applied
    assert enemy.hp < start_hp


def test_attack_hit_direct_invocation_triggers_helper(monkeypatch):
    player = Player()
    new_subtype = 'EdgeCase'
    player.eq_weapon = DummyWeapon(subtype=new_subtype)
    player.combat_exp.pop(new_subtype, None)
    player.skill_exp.pop(new_subtype, None)
    # Acquire attack move
    attack = next(m for m in player.known_moves if isinstance(m, Attack))
    tgt = DummyTarget()
    player.combat_proximity[tgt] = 1
    attack.target = tgt
    # Monkeypatch randomness to stable values
    monkeypatch.setattr('random.randint', lambda a,b: a)
    monkeypatch.setattr('random.uniform', lambda a,b: 1.0)
    # Manually call hit to isolate helper (simulate positive damage)
    attack.prep_colors()
    damage = 10
    attack.hit(damage, glance=False)
    assert new_subtype in player.combat_exp and new_subtype in player.skill_exp


def test_no_eq_weapon_attribute_graceful():
    user = types.SimpleNamespace()
    user.combat_exp = {'Basic': 0}
    _ensure_weapon_exp(user)  # Should not raise
    assert user.combat_exp == {'Basic': 0}


def test_eq_weapon_none_graceful():
    user = types.SimpleNamespace()
    user.eq_weapon = None
    user.combat_exp = {'Basic': 0}
    user.skill_exp = {'Basic': 0}
    _ensure_weapon_exp(user)
    assert user.combat_exp == {'Basic': 0}
    assert user.skill_exp == {'Basic': 0}

