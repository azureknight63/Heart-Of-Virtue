"""Unit tests for ally NPC static progression (npc/_progression.py).

Covers the AllyProgressionMixin contract: exp curve parity with the player
formula, level cap at Jean's level, catch-up multiplier, deterministic stat
growth (recompute-from-spawn), skill schedule grants, sync_level, legacy-save
backfill, and pickle round-trip.
"""

import pickle
from types import SimpleNamespace

import moves
from npc._base import Friend
from npc._friends import Gorran
from npc._progression import CATCH_UP_MULTIPLIER, LEVEL_CAP


def _gorran():
    g = Gorran()
    # Detach from world lookups (name property probes current_room/universe)
    g.current_room = None
    g.player_ref = None
    return g


def _plain_friend():
    return Friend(
        name="Extra",
        description="A friend with no growth profile.",
        damage=10,
        aggro=False,
        exp_award=0,
    )


# --- Opt-in and defaults ------------------------------------------------------


def test_friend_defaults_inert_without_growth_profile():
    f = _plain_friend()
    assert f.growth_profile is None
    assert f.level == 1
    assert f.exp == 0
    events = f.gain_exp(10_000, player_level=50)
    assert events == []
    assert f.level == 1


def test_sync_level_noop_without_growth_profile():
    f = _plain_friend()
    f.sync_level(10)
    assert f.level == 1


# --- Exp curve ----------------------------------------------------------------


def test_exp_curve_matches_player_formula():
    g = _gorran()
    # Player formula: level * max(1, 165 - intelligence); Gorran int is 10.
    assert g.exp_to_level == 1 * (165 - g.intelligence)
    g.level = 7
    assert g.exp_to_level == 7 * (165 - g.intelligence)


def test_gain_exp_banks_and_levels():
    g = _gorran()
    need = g.exp_to_level
    events = g.gain_exp(need - 1, player_level=2)
    assert events == []
    assert g.exp == need - 1
    events = g.gain_exp(1, player_level=2)
    assert len(events) == 1
    assert events[0]["old_level"] == 1
    assert events[0]["new_level"] == 2
    assert g.level == 2
    assert g.exp == 0


def test_level_capped_at_player_level_and_exp_banked():
    g = _gorran()
    events = g.gain_exp(1_000_000, player_level=3)
    assert g.level == 3
    assert len(events) == 2
    assert g.exp > 0  # overflow retained
    # Once Jean levels, the banked exp resolves on the next award (the
    # million-exp bank always covers the level-4 threshold).
    g.gain_exp(1, player_level=4)
    assert g.level == 4


def test_catch_up_multiplier_when_two_levels_behind():
    g = _gorran()
    g.gain_exp(100, player_level=5)  # level 1 vs 5 → catch-up zone
    assert g.exp == int(100 * CATCH_UP_MULTIPLIER)


def test_no_catch_up_within_one_level():
    g = _gorran()
    g.sync_level(4)
    g.gain_exp(100, player_level=5)  # exactly one behind → no multiplier
    assert g.exp == 100


def test_level_hard_cap_100():
    g = _gorran()
    g.sync_level(LEVEL_CAP + 50)
    assert g.level == LEVEL_CAP


# --- Deterministic stat growth --------------------------------------------------


def test_growth_recomputes_from_spawn_bases():
    g = _gorran()
    spawn_maxhp = g.maxhp_base
    spawn_damage = g.damage_base
    spawn_speed = g.speed_base
    g.sync_level(5)
    assert g.maxhp_base == spawn_maxhp + 14 * 4
    assert g.damage_base == spawn_damage + 3 * 4
    assert g.protection_base == int(0.5 * 4)  # +1 every 2 levels
    assert g.speed_base == spawn_speed + int(0.25 * 4)
    # Live stats track base (no equipment/states on a fresh Gorran)
    assert g.maxhp == g.maxhp_base
    assert g.damage == g.damage_base


def test_growth_is_deterministic_and_drift_free():
    a, b = _gorran(), _gorran()
    a.sync_level(9)
    # Reaching 9 one level at a time must produce identical stats.
    for target in range(2, 10):
        b.sync_level(target)
    assert a.maxhp_base == b.maxhp_base
    assert a.damage_base == b.damage_base
    assert a.protection_base == b.protection_base
    assert a.speed_base == b.speed_base


def test_level_up_raises_current_hp_by_maxhp_delta():
    g = _gorran()
    g.hp = 50  # wounded
    g.gain_exp(g.exp_to_level, player_level=2)
    assert g.level == 2
    assert g.hp == 50 + 14  # topped up by the maxhp delta, not fully healed
    assert g.hp < g.maxhp


# --- Skill schedule -------------------------------------------------------------


def test_skill_schedule_weight_up_and_new_move():
    g = _gorran()
    g.sync_level(5)
    parry = next(m for m in g.known_moves if m.name == "Parry")
    assert parry.weight == 3  # L3 grant
    bull = next((m for m in g.known_moves if m.name == "Bull Charge"), None)
    assert bull is not None  # L5 grant
    assert bull.weight == 2


def test_skill_schedule_class_selector_hits_gorran_club_only():
    g = _gorran()
    g.sync_level(7)
    club = next(m for m in g.known_moves if isinstance(m, moves.GorranClub))
    basic = next(m for m in g.known_moves if isinstance(m, moves.NpcAttack))
    assert club.weight == 4  # L7 grant targets the class, not the shared name
    assert basic.weight == 4  # unchanged (spawn weight)


def test_new_move_grant_is_idempotent():
    g = _gorran()
    g.sync_level(5)
    count = len(g.known_moves)
    learned = g._apply_skill_schedule()  # re-apply the level-5 grants
    assert learned == []
    assert len(g.known_moves) == count


def test_level_up_event_reports_learned_skills():
    g = _gorran()
    g.sync_level(4)
    events = g.gain_exp(g.exp_to_level, player_level=6)
    level5 = [e for e in events if e["new_level"] == 5]
    assert level5 and level5[0]["skills_learned"] == ["Bull Charge"]


# --- sync_level -----------------------------------------------------------------


def test_sync_level_matches_player_and_keeps_exp_clean():
    g = _gorran()
    g.sync_level(6)
    assert g.level == 6
    assert g.exp >= 0


def test_sync_level_never_lowers():
    g = _gorran()
    g.sync_level(6)
    g.sync_level(3)
    assert g.level == 6


# --- Persistence / legacy saves ---------------------------------------------------


def test_legacy_save_backfill():
    g = _gorran()
    del g.level
    del g.exp
    events = g.gain_exp(10, player_level=3)
    assert events == []
    assert g.level == 1
    assert g.exp == int(10 * CATCH_UP_MULTIPLIER)


def test_pickle_roundtrip_preserves_progression():
    g = _gorran()
    g.sync_level(5)
    clone = pickle.loads(pickle.dumps(g))
    assert clone.level == 5
    assert clone.maxhp_base == g.maxhp_base
    assert any(m.name == "Bull Charge" for m in clone.known_moves)
    # Progression continues on the restored instance
    clone.gain_exp(1_000_000, player_level=6)
    assert clone.level == 6


# --- LLM chat surface --------------------------------------------------------------


def test_combat_knowledge_block_empty_without_profile():
    from npc._chat_llm import HumanNPCLLMMixin

    bare = SimpleNamespace()
    assert HumanNPCLLMMixin._build_combat_knowledge_block(bare) == ""


def test_combat_knowledge_block_describes_techniques():
    from npc._chat_llm import HumanNPCLLMMixin
    from npc._friends import Mara

    mara = Mara()
    mara.sync_level(5)
    block = HumanNPCLLMMixin._build_combat_knowledge_block(mara)
    assert "COMBAT SELF-KNOWLEDGE" in block
    assert "seasoned" in block
    assert "Dodge" in block
    assert "Tactical Retreat" in block  # L5 grant
    assert "NPC_Attack" not in block  # internal names filtered
