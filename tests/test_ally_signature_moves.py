"""Unit tests for ally signature moves (Seismic Slam, Stone Bulwark,
Marked Quarry, Twin Fangs) and their skill-schedule grants.

Kit design: docs/development/ally-progression-design.md (signature notes).
"""

import moves
import states
from npc._base import NPC
from npc._friends import Gorran, Mara


def _gorran(level=1):
    g = Gorran()
    g.current_room = None
    g.player_ref = None
    if level > 1:
        g.sync_level(level)
    return g


def _mara(level=1):
    m = Mara()
    m.current_room = None
    m.player_ref = None
    if level > 1:
        m.sync_level(level)
    return m


def _dummy_enemy(protection=0, finesse=10, maxhp=500):
    e = NPC(
        name="Target",
        description="test target",
        damage=1,
        aggro=True,
        exp_award=0,
        maxhp=maxhp,
        protection=protection,
        finesse=finesse,
    )
    e.in_combat = True
    return e


# --- Schedule grants ------------------------------------------------------------


def test_gorran_learns_signatures_at_9_and_12():
    g = _gorran(12)
    names = [m.name for m in g.known_moves]
    assert "Seismic Slam" in names
    assert "Stone Bulwark" in names


def test_mara_learns_signatures_at_9_and_12():
    m = _mara(12)
    names = [mv.name for mv in m.known_moves]
    assert "Marked Quarry" in names
    assert "Twin Fangs" in names


def test_signature_moves_appear_in_chat_knowledge():
    from npc._chat_llm import HumanNPCLLMMixin

    m = _mara(12)
    block = HumanNPCLLMMixin._build_combat_knowledge_block(m)
    assert "Marked Quarry" in block
    assert "Twin Fangs" in block


# --- Marked Quarry ----------------------------------------------------------------


def test_marked_quarry_reduces_target_protection():
    m = _mara(9)
    enemy = _dummy_enemy(protection=12)
    m.target = enemy
    move = next(mv for mv in m.known_moves if mv.name == "Marked Quarry")
    move.target = enemy
    move.execute(m)
    assert any(isinstance(s, states.Quarried) for s in enemy.states)
    assert enemy.protection == 12 - int(12 * 0.25)


def test_marked_quarry_not_viable_when_already_marked():
    m = _mara(9)
    enemy = _dummy_enemy(protection=12)
    m.target = enemy
    m.combat_proximity = {enemy: 10}
    move = next(mv for mv in m.known_moves if mv.name == "Marked Quarry")
    assert move.viable()
    move.target = enemy
    move.execute(m)
    assert not move.viable()  # already Quarried


# --- Twin Fangs --------------------------------------------------------------------


def test_twin_fangs_hits_harder_against_quarried_target(monkeypatch):
    monkeypatch.setattr("moves._npc.random.randint", lambda a, b: 0)  # always hit, no glance

    m = _mara(12)
    move = next(mv for mv in m.known_moves if mv.name == "Twin Fangs")

    plain = _dummy_enemy()
    move.target = plain
    move.evaluate()
    move.execute(m)
    plain_damage = plain.maxhp - plain.hp
    assert plain_damage > 0

    marked = _dummy_enemy()
    marked.states.append(states.Quarried(marked))
    m.fatigue = m.maxfatigue
    move.target = marked
    move.execute(m)
    marked_damage = marked.maxhp - marked.hp
    assert marked_damage == int(plain_damage * move._QUARRY_BONUS)


def test_twin_fangs_viable_only_in_close_range():
    m = _mara(12)
    enemy = _dummy_enemy()
    m.target = enemy
    move = next(mv for mv in m.known_moves if mv.name == "Twin Fangs")
    m.combat_proximity = {enemy: 2}
    move.target = enemy
    assert move.viable()
    m.combat_proximity = {enemy: 10}
    assert not move.viable()


# --- Seismic Slam --------------------------------------------------------------------


def test_seismic_slam_hits_all_hostiles_in_radius(monkeypatch):
    monkeypatch.setattr("moves._npc.random.randint", lambda a, b: 0)  # always hit

    g = _gorran(9)
    near = _dummy_enemy()
    far = _dummy_enemy()
    friend = Gorran()  # same side — must not be hit
    friend.current_room = None
    g.combat_proximity = {near: 4, far: 30, friend: 2}
    move = next(mv for mv in g.known_moves if mv.name == "Seismic Slam")
    move.evaluate()
    assert move.viable()
    move.execute(g)
    assert near.hp < near.maxhp
    assert far.hp == far.maxhp  # out of radius
    assert friend.hp == friend.maxhp  # same side


def test_seismic_slam_not_viable_without_hostiles_in_radius():
    g = _gorran(9)
    far = _dummy_enemy()
    g.combat_proximity = {far: 30}
    move = next(mv for mv in g.known_moves if mv.name == "Seismic Slam")
    assert not move.viable()


def test_seismic_slam_never_hits_the_player(monkeypatch, player):
    """Regression: coordinate proximity sync puts Jean in every ally's
    combat_proximity dict, and ally.player_ref is never assigned — the
    side check must recognize the player by his missing `friend` attribute,
    not via player_ref, or Gorran's slam friendly-fires Jean."""
    monkeypatch.setattr("moves._npc.random.randint", lambda a, b: 0)  # always hit

    g = _gorran(9)
    assert g.player_ref is None  # the trap this test guards against
    enemy = _dummy_enemy()
    g.combat_proximity = {player: 1, enemy: 4}

    move = next(mv for mv in g.known_moves if mv.name == "Seismic Slam")
    move.evaluate()
    move.execute(g)
    assert player.hp == player.maxhp  # Jean untouched
    assert enemy.hp < enemy.maxhp

    # Jean alone in range must not make the slam viable either.
    g.combat_proximity = {player: 1}
    assert not move.viable()


def test_hostile_to_side_classification(player):
    from moves._npc import _hostile_to

    ally = _gorran(1)  # friend=True
    enemy = _dummy_enemy()  # friend=False
    assert not _hostile_to(ally, player)  # ally never hostile to Jean
    assert _hostile_to(enemy, player)  # enemy is hostile to Jean
    assert _hostile_to(ally, enemy) and _hostile_to(enemy, ally)
    assert not _hostile_to(enemy, _dummy_enemy())  # same side


# --- Stone Bulwark -----------------------------------------------------------------


def test_stone_bulwark_buffs_whole_party():
    g = _gorran(12)
    m = _mara(1)
    g.combat_list_allies = [m, g]
    g.in_combat = True
    m.in_combat = True
    enemy = _dummy_enemy()
    g.combat_proximity = {enemy: 5}

    move = next(mv for mv in g.known_moves if mv.name == "Stone Bulwark")
    assert move.viable()

    base_m, base_g = m.protection, g.protection
    move.execute(g)
    amount = 6 + int(g.protection_base * 0.5)
    assert any(isinstance(s, states.StoneBulwarkState) for s in m.states)
    assert any(isinstance(s, states.StoneBulwarkState) for s in g.states)
    assert m.protection == base_m + amount

    # Won't recast while the ward is up on anyone.
    assert not move.viable()


def test_stone_bulwark_not_viable_out_of_combat():
    g = _gorran(12)
    g.in_combat = False
    move = next(mv for mv in g.known_moves if mv.name == "Stone Bulwark")
    assert not move.viable()


def test_stone_bulwark_full_stage_cycle_applies_ward():
    """Drive the move through the real advance() stage machinery (as the
    combat adapter does per beat), not just a direct execute() call."""
    g = _gorran(12)
    m = _mara(1)
    g.combat_list_allies = [m, g]
    g.in_combat = True
    m.in_combat = True
    enemy = _dummy_enemy()
    g.combat_proximity = {enemy: 5}

    move = next(mv for mv in g.known_moves if mv.name == "Stone Bulwark")
    move.current_stage = 0
    move.beats_left = move.stage_beat[0]
    g.current_move = move
    for _ in range(12):  # prep 3 + execute 1 + recoil 2, with margin
        move.advance(g)
        if any(isinstance(s, states.StoneBulwarkState) for s in m.states):
            break
    assert any(isinstance(s, states.StoneBulwarkState) for s in m.states)
    assert any(isinstance(s, states.StoneBulwarkState) for s in g.states)
