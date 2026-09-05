"""Contract + builder tests for the combat beat protocol (issue #436).

Covers the pure Python builders/validators and asserts the frontend JS mirror
(frontend/src/utils/combatBeatSchema.js) stays in parity with the Python source
of truth (src/api/schemas/combat_beat.py).
"""

import ast
import re
from pathlib import Path

from src.api.schemas import combat_beat as cb

_ROOT = Path(__file__).resolve().parents[1]
_MIRROR_JS = _ROOT / "frontend" / "src" / "utils" / "combatBeatSchema.js"
_SOURCE_PY = _ROOT / "src" / "api" / "schemas" / "combat_beat.py"


# ── JS-mirror parity ────────────────────────────────────────────────────────
#
# Parity is DERIVED, not enumerated (issue #521). The previous version of this
# file called the parsers below from a hand-maintained list of names, which
# caught *value* drift but not *addition* drift: a constant added on the Python
# side and forgotten in the JS mirror failed nothing unless someone also
# remembered to edit this test. That hole was already real --
# ``MAX_BEAT_RESOLUTIONS`` shipped mirrored in the JS with a "Keep the two
# values identical" comment and no test asserting it.
#
# So instead: walk every module-level UPPERCASE constant in combat_beat.py and
# require a matching ``export const`` in the mirror. A name that is genuinely
# Python-only must be listed in ``_PY_ONLY_CONSTANTS`` below, which makes the
# omission a deliberate, reviewed act rather than an accident.
#
# Drift here is not cosmetic. The error codes are the sharpest case: if the JS
# constant stops matching what the server emits, ``ERROR_SESSION_INVALID`` stops
# being recognised and a genuinely dead session leaves the socket retrying
# forever, while ``ERROR_SESSION_MISSING`` stops being recognised and a
# handshake that simply lost its cookie falls through to "unknown code" and
# never retries. CLAUDE.md names mirrored-literal drift across this boundary as
# a recurring failure mode of this codebase.

#: Module-level constants that deliberately do NOT appear in the JS mirror,
#: each with the reason it stays Python-side. Anything not listed here MUST be
#: mirrored.
_PY_ONLY_CONSTANTS = {
    # Server-side substitutions: the API layer picks these when a move declares
    # no ``web_animation`` of its own, so the client only ever receives the
    # resulting concrete value on the wire and never needs the name. Their
    # values are contract-checked against the frontend's ANIMATION_CONFIGS keys
    # by tests/test_move_web_animations.py instead.
    "DEFAULT_ANIMATION",
    "DEFAULT_DAMAGE_ANIMATION",
    # Server-only event names: nothing in frontend/src emits or listens for any
    # of these, so a JS mirror would be an export with no consumer -- exactly
    # the client-only accumulation the reverse test below exists to prevent.
    # They are defined Python-side anyway so combat_beat.py holds the WHOLE
    # socket vocabulary; a subset would imply this guard covers more than it
    # does. Mirror one and drop it from here the moment a client consumes it.
    "STARTED_EVENT",   # emitted at combat start; the client re-fetches instead
    "LOG_EVENT",       # legacy per-entry log push
    "TURN_EVENT",      # legacy awaiting-input notification
    "LEAVE_EVENT",     # handler; the client just disconnects
    "LEFT_EVENT",      # ack for the above
    "PING_EVENT",      # test-only liveness probe
    "PONG_EVENT",      # ack for the above
}

#: The same exemption in the other direction: names the JS mirror exports that
#: ``combat_beat.py`` does not define. Empty on purpose -- a constant in the
#: mirror with no Python counterpart is the exact shape of CLAUDE.md's dominant
#: bug class (the client keying off a name the server never emits), so it has to
#: be argued for here rather than merely appearing.
_JS_ONLY_CONSTANTS = set()


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


def _js_int_const(name):
    source = _MIRROR_JS.read_text(encoding="utf-8")
    match = re.search(rf"export const {name} = (-?\d+);", source)
    assert match, f"{name} const not found in combatBeatSchema.js"
    return int(match.group(1))


def _js_exported_constants():
    """Every ``export const NAME`` in the JS mirror, as a set of names.

    Whitespace-tolerant on purpose. This scan fails OPEN -- a name it does not
    see is simply absent from the reverse-direction check, with nothing to say
    so -- and the previous pattern required the exact byte sequence
    ``export const NAME = ``. Two spaces, a line-wrapped assignment or a
    Prettier pass would each have silently dropped an export out of the guard.
    """
    source = _MIRROR_JS.read_text(encoding="utf-8")
    return set(
        re.findall(r"^export\s+const\s+([A-Za-z_$][\w$]*)\s*=", source, re.M)
    )


#: Statement types that open a new scope. A binding inside one of these is a
#: local, not a module constant, so the scan below stops at their boundary --
#: everything else at module level does bind a module attribute, however deeply
#: it is nested in ``if`` / ``try`` / ``with`` blocks.
_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _bound_names(target):
    """Yield every ``ast.Name`` an assignment target binds, unpacking included."""
    if isinstance(target, ast.Name):
        yield target
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            yield from _bound_names(element)
    elif isinstance(target, ast.Starred):
        yield from _bound_names(target.value)


def _module_level_constant_names(node):
    """Recursively collect UPPERCASE names bound at module level.

    This scan fails OPEN, which is why it is written to be exhaustive rather
    than convenient: a constant it does not see is simply not required to have
    a JS mirror, and nothing reports the omission. The previous version walked
    ``tree.body`` alone and matched only ``ast.Name`` targets, so BOTH
    ``BEAT_EVENT, RESOLVED_EVENT = "combat:beat", "combat:resolved"`` and a
    constant defined inside a module-level ``if`` / ``try`` / ``with`` block
    escaped it silently -- while the guard's own docstring claimed to cover
    "every module-level UPPERCASE constant".

    "Bound" means bound, not merely assigned: ``for`` targets and ``with ... as``
    targets are collected too. They are far-fetched shapes for a constant, but
    an exhaustiveness claim that quietly excludes some binding forms is the
    same overclaim this function was written to remove.
    """
    names = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _SCOPE_NODES):
            continue
        if isinstance(child, ast.Assign):
            targets = child.targets
        elif isinstance(child, ast.AnnAssign):
            targets = [child.target]
        elif isinstance(child, (ast.For, ast.AsyncFor)):
            # The loop variable binds too, and then the body still needs
            # walking -- so this branch does both rather than `continue`.
            targets = [child.target]
            names.extend(_module_level_constant_names(child))
        elif isinstance(child, (ast.With, ast.AsyncWith)):
            targets = [i.optional_vars for i in child.items if i.optional_vars]
            names.extend(_module_level_constant_names(child))
        else:
            names.extend(_module_level_constant_names(child))
            continue
        for target in targets:
            for name in _bound_names(target):
                if re.fullmatch(r"[A-Z][A-Z0-9_]*", name.id):
                    names.append(name.id)
    return names


def _python_constants():
    """Every module-level UPPERCASE constant in combat_beat.py, name -> value.

    AST-parsed rather than read off ``vars(cb)`` so that names the module
    merely *imports* can never be mistaken for constants it defines.
    """
    tree = ast.parse(_SOURCE_PY.read_text(encoding="utf-8"))
    return {
        name: getattr(cb, name) for name in _module_level_constant_names(tree)
    }


def test_python_constants_are_all_mirrored_in_js():
    """Every constant combat_beat.py defines exists, with the same value, in JS.

    This is the addition-drift guard: adding a constant to the Python schema
    without mirroring it fails HERE, with no edit to this test required.
    """
    constants = _python_constants()
    # Sanity-check the scan itself: a parser that silently found nothing would
    # make this whole test vacuously green.
    assert len(constants) >= 10, (
        f"only found {sorted(constants)} -- the AST scan is broken"
    )

    for name, value in sorted(constants.items()):
        if name in _PY_ONLY_CONSTANTS:
            continue
        if isinstance(value, tuple):
            assert _js_string_array(name) == value, f"{name} drifted"
        elif isinstance(value, str):
            assert _js_string_const(name) == value, f"{name} drifted"
        elif isinstance(value, int) and not isinstance(value, bool):
            assert _js_int_const(name) == value, f"{name} drifted"
        else:
            raise AssertionError(
                f"{name} is a {type(value).__name__}, which this parity guard "
                "cannot compare across the boundary. Teach the _js_* parsers "
                "to read it, or add it to _PY_ONLY_CONSTANTS with a reason."
            )


def test_js_constants_all_exist_on_the_python_side():
    """Nothing is exported from the mirror that the Python schema never defines.

    The companion to the test above, and not redundant with it: that one walks
    Python -> JS, so a name invented (or left behind) on the JS side alone is
    invisible to it. A client constant with no server counterpart is precisely
    the failure CLAUDE.md calls this codebase's dominant bug class -- reads sit
    behind ``??``/``||`` chains, so the miss is swallowed and the feature just
    quietly does nothing.
    """
    exported = _js_exported_constants()
    # Same vacuity guard as above: a regex that matched nothing would make this
    # trivially green.
    assert len(exported) >= 10, (
        f"only found {sorted(exported)} -- the JS export scan is broken"
    )
    orphans = sorted(
        exported - set(_python_constants()) - _JS_ONLY_CONSTANTS
    )
    assert not orphans, (
        f"{orphans} are exported by combatBeatSchema.js but combat_beat.py "
        "defines no such constant. Define them Python-side, delete them, or "
        "add them to _JS_ONLY_CONSTANTS with the reason they are client-only"
    )


def test_python_only_exclusions_are_still_accurate():
    """``_PY_ONLY_CONSTANTS`` may not go stale in either direction."""
    constants = _python_constants()
    stale = sorted(set(_PY_ONLY_CONSTANTS) - set(constants))
    assert not stale, (
        f"{stale} listed as Python-only but combat_beat.py no longer defines "
        "them -- drop them from _PY_ONLY_CONSTANTS"
    )

    source = _MIRROR_JS.read_text(encoding="utf-8")
    now_mirrored = sorted(
        name for name in _PY_ONLY_CONSTANTS
        if re.search(rf"export const {name}\b", source)
    )
    assert not now_mirrored, (
        f"{now_mirrored} are excluded as Python-only but the JS mirror now "
        "exports them -- drop them from _PY_ONLY_CONSTANTS so parity is checked"
    )


def test_error_codes_are_distinct():
    assert cb.ERROR_SESSION_MISSING != cb.ERROR_SESSION_INVALID


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
