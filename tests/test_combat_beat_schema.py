"""Contract + builder tests for the combat beat protocol (issue #436).

Covers the pure Python builders/validators and asserts the frontend JS mirror
(frontend/src/utils/combatBeatSchema.js) stays in parity with the Python source
of truth (src/api/schemas/combat_beat.py).
"""

import re
from pathlib import Path

from src.api.schemas import combat_beat as cb

_ROOT = Path(__file__).resolve().parents[1]
_MIRROR_JS = _ROOT / "frontend" / "src" / "utils" / "combatBeatSchema.js"


# ── JS-mirror parity ────────────────────────────────────────────────────────

def _js_string_array(name):
    """Parse `export const NAME = [ 'a', 'b', ... ];` out of the JS mirror."""
    source = _MIRROR_JS.read_text(encoding="utf-8")
    match = re.search(
        rf"export const {name} = \[(.*?)\];", source, re.DOTALL
    )
    assert match, f"{name} array not found in combatBeatSchema.js"
    return tuple(re.findall(r"'([^']+)'", match.group(1)))


def _js_string_const(name):
    source = _MIRROR_JS.read_text(encoding="utf-8")
    match = re.search(rf"export const {name} = '([^']+)';", source)
    assert match, f"{name} const not found in combatBeatSchema.js"
    return match.group(1)


def test_beat_fields_parity():
    assert _js_string_array("BEAT_FIELDS") == cb.BEAT_FIELDS


def test_outcomes_parity():
    assert _js_string_array("OUTCOMES") == cb.OUTCOMES


def test_sfx_kinds_parity():
    assert _js_string_array("SFX_KINDS") == cb.SFX_KINDS


def test_departure_reasons_parity():
    assert _js_string_array("DEPARTURE_REASONS") == cb.DEPARTURE_REASONS


def test_event_name_parity():
    assert _js_string_const("BEAT_EVENT") == cb.BEAT_EVENT
    assert _js_string_const("RESOLVED_EVENT") == cb.RESOLVED_EVENT
    assert _js_string_const("ENDED_EVENT") == cb.ENDED_EVENT
    assert _js_string_const("SUGGESTIONS_EVENT") == cb.SUGGESTIONS_EVENT


# ── build_beat ──────────────────────────────────────────────────────────────

def test_build_beat_is_valid_and_has_all_fields():
    beat = cb.build_beat(
        seq=1,
        actor_id="player",
        target_id="enemy_9",
        web_animation="pierce",
        outcome="hit",
        hp_changes=[{"id": "enemy_9", "delta": -14}],
        log_line="Jean pierces the Slime for 14.",
    )
    assert cb.validate_beat(beat) == []
    assert set(beat) == set(cb.BEAT_FIELDS)
    assert beat["hp_changes"] == [{"id": "enemy_9", "delta": -14}]


def test_build_beat_defaults_empty_collections():
    beat = cb.build_beat(1, "player", None, "pulse", "hit")
    assert beat["hp_changes"] == []
    assert beat["killed"] == []
    assert beat["departed"] == []
    assert beat["status_changes"] == []


def test_build_beat_with_departed_is_valid():
    beat = cb.build_beat(
        1,
        "enemy_3",
        None,
        "pulse",
        "miss",
        departed=[{"id": "enemy_3", "reason": "fled"}],
    )
    assert cb.validate_beat(beat) == []
    assert beat["departed"] == [{"id": "enemy_3", "reason": "fled"}]
    # An alive-exit is NOT a death: no death SFX kind.
    assert "death" not in [e["kind"] for e in beat["sfx"]]


def test_validate_beat_flags_bad_departure_reason():
    beat = cb.build_beat(1, "player", "enemy_9", "pierce", "hit")
    beat["departed"] = [{"id": "enemy_9", "reason": "vaporized"}]
    problems = cb.validate_beat(beat)
    assert any("invalid departure reason" in p for p in problems)


# ── SFX chain ordering / indices ────────────────────────────────────────────

def test_sfx_chain_basic_hit_is_swing_then_impact():
    chain = cb.build_sfx_chain("hit")
    kinds = [e["kind"] for e in chain]
    assert kinds == ["swing", "impact"]
    assert [e["index"] for e in chain] == [0, 1]
    assert chain[1]["outcome"] == "hit"


def test_sfx_chain_miss_still_has_impact():
    chain = cb.build_sfx_chain("miss")
    assert [e["kind"] for e in chain] == ["swing", "impact"]
    assert chain[1]["outcome"] == "miss"


def test_sfx_chain_without_swing():
    chain = cb.build_sfx_chain("hit", has_swing=False)
    assert [e["kind"] for e in chain] == ["impact"]
    assert chain[0]["index"] == 0


def test_sfx_chain_lifesteal_kill_and_status_order_and_indices():
    # A poisoned, killing lifesteal strike: target -14, actor +4.
    chain = cb.build_sfx_chain(
        "hit",
        hp_changes=[{"id": "enemy_9", "delta": -14}, {"id": "player", "delta": 4}],
        killed=["enemy_9"],
        status_changes=[{"id": "enemy_9", "status": "poison"}],
        actor_id="player",
    )
    assert [e["kind"] for e in chain] == [
        "swing",
        "impact",
        "status",
        "heal",
        "death",
    ]
    assert [e["index"] for e in chain] == [0, 1, 2, 3, 4]
    status_emission = next(e for e in chain if e["kind"] == "status")
    assert status_emission["status"] == "poison"


def test_sfx_chain_heal_only_when_actor_gains_hp():
    # A positive delta on the TARGET (ally heal) is not an actor heal SFX.
    chain = cb.build_sfx_chain(
        "hit",
        hp_changes=[{"id": "ally_2", "delta": 10}],
        actor_id="player",
    )
    assert "heal" not in [e["kind"] for e in chain]


def test_build_beat_embeds_sfx_chain():
    beat = cb.build_beat(
        7,
        "player",
        "enemy_9",
        "pierce",
        "hit",
        hp_changes=[{"id": "enemy_9", "delta": -14}, {"id": "player", "delta": 4}],
        killed=["enemy_9"],
        status_changes=[{"id": "enemy_9", "status": "poison"}],
    )
    assert [e["kind"] for e in beat["sfx"]] == [
        "swing",
        "impact",
        "status",
        "heal",
        "death",
    ]


# ── validate_beat negative cases ────────────────────────────────────────────

def test_validate_beat_flags_bad_outcome():
    beat = cb.build_beat(1, "player", "enemy_9", "pierce", "hit")
    beat["outcome"] = "obliterated"
    problems = cb.validate_beat(beat)
    assert any("invalid outcome" in p for p in problems)


def test_validate_beat_flags_missing_field():
    beat = cb.build_beat(1, "player", "enemy_9", "pierce", "hit")
    del beat["log_line"]
    problems = cb.validate_beat(beat)
    assert any("missing field: log_line" in p for p in problems)


def test_validate_beat_flags_non_monotonic_sfx_index():
    beat = cb.build_beat(1, "player", "enemy_9", "pierce", "hit")
    beat["sfx"][0]["index"] = 5
    problems = cb.validate_beat(beat)
    assert any("sfx index" in p for p in problems)


# ── diff_combatants ─────────────────────────────────────────────────────────

def _combatant(cid, hp, statuses=None):
    return {
        "id": cid,
        "hp": hp,
        "status_effects": [{"name": n} for n in (statuses or [])],
    }


def test_diff_damage_only():
    prev = [_combatant("enemy_9", 30)]
    curr = [_combatant("enemy_9", 16)]
    hp_changes, killed, status_changes = cb.diff_combatants(prev, curr)
    assert hp_changes == [{"id": "enemy_9", "delta": -14}]
    assert killed == []
    assert status_changes == []


def test_diff_lifesteal_two_subjects():
    prev = [_combatant("enemy_9", 30), _combatant("player", 50)]
    curr = [_combatant("enemy_9", 16), _combatant("player", 54)]
    hp_changes, killed, _ = cb.diff_combatants(prev, curr)
    assert {"id": "enemy_9", "delta": -14} in hp_changes
    assert {"id": "player", "delta": 4} in hp_changes
    assert killed == []


def test_diff_kill_detected_on_crossing_zero():
    prev = [_combatant("enemy_9", 5)]
    curr = [_combatant("enemy_9", 0)]
    _, killed, _ = cb.diff_combatants(prev, curr)
    assert killed == ["enemy_9"]


def test_diff_no_kill_when_already_dead():
    prev = [_combatant("enemy_9", 0)]
    curr = [_combatant("enemy_9", 0)]
    hp_changes, killed, _ = cb.diff_combatants(prev, curr)
    assert killed == []
    assert hp_changes == []


def test_diff_new_status_attributed():
    prev = [_combatant("enemy_9", 30, [])]
    curr = [_combatant("enemy_9", 28, ["poison"])]
    _, _, status_changes = cb.diff_combatants(prev, curr)
    assert status_changes == [{"id": "enemy_9", "status": "poison"}]


def test_diff_existing_status_not_reported():
    prev = [_combatant("enemy_9", 30, ["poison"])]
    curr = [_combatant("enemy_9", 28, ["poison"])]
    _, _, status_changes = cb.diff_combatants(prev, curr)
    assert status_changes == []


def test_diff_reinforcement_has_no_baseline():
    prev = [_combatant("enemy_9", 30)]
    curr = [_combatant("enemy_9", 30), _combatant("enemy_new", 40)]
    hp_changes, killed, _ = cb.diff_combatants(prev, curr)
    assert hp_changes == []
    assert killed == []


def test_diff_ignores_absent_combatants():
    # Absence alone can't distinguish death from an alive-exit, so the pure diff
    # does NOT classify a removed combatant (the caller resolves it by reason).
    prev = [_combatant("enemy_9", 12), _combatant("player", 40)]
    curr = [_combatant("player", 40)]
    hp_changes, killed, _ = cb.diff_combatants(prev, curr)
    assert killed == []
    assert hp_changes == []


def test_diff_transient_dip_ending_alive_is_not_a_death():
    # Snapshot diff only sees net start->end; ending above 0 is not a kill.
    prev = [_combatant("enemy_9", 30)]
    curr = [_combatant("enemy_9", 5)]
    hp_changes, killed, _ = cb.diff_combatants(prev, curr)
    assert killed == []
    assert hp_changes == [{"id": "enemy_9", "delta": -25}]
