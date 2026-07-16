#!/usr/bin/env python3
"""Combat command-protocol fuzzer for Heart of Virtue (issue #291).

Drives random, seeded command sequences through
:meth:`src.api.combat_adapter.ApiCombatAdapter.process_command` -- the handler
behind ``POST /api/combat/move`` -- against a live combat session built in the
combat-testing arena style (a real player + enemies, exactly as the Flask route
would produce). Every command type is exercised with adversarial payloads:

  * ``select_move`` -- out-of-range / negative / float / None / huge / string
    move_index.
  * ``select_target`` -- unknown / duplicate / dead / player-own / ally ids,
    non-string ids.
  * ``select_direction`` -- invalid strings, casing, empty, non-string.
  * ``select_number`` -- negatives, 0, huge, non-numeric, NaN, inf, bool.
  * ``select_move_and_target`` -- unknown move names, bad target pairings.
  * ``cancel_selection`` -- at move-selection (illegal) and deeper stages.
  * unknown / missing ``type``, extra keys, empty dict, non-dict.
  * SEQUENCING abuse -- commands out of order, when not awaiting input, repeated
    selections, and commands after victory/defeat.

The security-equivalent invariants (findings here MUST be zero) are:

  * ``process_command`` never raises -- an invalid command returns a structured
    ``{"error": ...}`` dict, never a 5xx / uncaught exception.
  * After ANY command the adapter state stays coherent: ``awaiting_input`` is a
    bool, ``input_type`` is one of the known stages (or ``None``),
    ``pending_move_index`` is ``None`` or a valid in-range int, and
    ``available_options`` is a list or dict.
  * A command sent while ``awaiting_input`` is False does not mutate combat
    state (no out-of-combat mutation) and returns an ``{"error": ...}``.

Anything else -- e.g. a benign in-game rejection -- is not a breach.

Usage:
    python tools/combat_command_fuzzer.py                 # 400 iters, random seed
    python tools/combat_command_fuzzer.py --iterations 5000
    python tools/combat_command_fuzzer.py --seed 1337     # reproducible run
"""

import os
import sys
import copy
import math
import random
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Findings in these categories are genuine invariant breaches (must be zero).
# Everything else is an informational in-game rejection (not a breach).
_SECURITY_CATEGORIES = frozenset({
    "handler-raised",            # process_command raised instead of returning a dict
    "handler-returned-nondict",  # handler returned something other than a dict
    "state-incoherent",          # awaiting_input/input_type/pending/options invalid
    "out-of-combat-mutation",    # command mutated state while not awaiting input
    "harness-error",             # the fuzzer itself failed
})

_VALID_INPUT_TYPES = frozenset({
    "move_selection", "target_selection", "number_input",
    "direction_selection", None,
})

_DIRECTIONS = ["north", "south", "east", "west",
               "northeast", "northwest", "southeast", "southwest",
               "NORTH", "North", "up", "n", "", "  ", "left"]


class Finding:
    """An invariant violation, carrying enough context to reproduce it."""

    def __init__(self, seed, iteration, category, detail, command=None):
        self.seed = seed
        self.iteration = iteration
        self.category = category
        self.detail = detail
        self.command = command

    @property
    def is_security(self):
        return self.category in _SECURITY_CATEGORIES

    def __str__(self):
        tag = "SECURITY" if self.is_security else "info"
        cmd = f" cmd={self.command!r}" if self.command is not None else ""
        return (f"[{tag} seed={self.seed} iter={self.iteration} "
                f"{self.category}]{cmd} {self.detail}")


def security_findings(findings):
    """Filter to genuine invariant breaches (must be empty)."""
    return [f for f in findings if f.is_security]


def info_findings(findings):
    """Filter to informational, non-breach findings."""
    return [f for f in findings if not f.is_security]


# ---------------------------------------------------------------------------
# Live combat session construction (real player + enemies, like the route)
# ---------------------------------------------------------------------------

_app = None
_session_manager = None


def _get_app():
    """Build the Flask app + session manager once (real engine, no DB)."""
    global _app, _session_manager
    if _app is None:
        from src.api.app import create_app
        from src.api.config import TestingConfig
        _app, _ = create_app(TestingConfig)
        _session_manager = _app.session_manager
    return _app, _session_manager


def build_combat(rng):
    """Create a fresh session, start combat with a couple of enemies, and return
    the live :class:`ApiCombatAdapter` plus its player.

    Two enemies are placed in melee range so targeted moves reach the
    multi-target selection path; the player keeps its default move set (which
    includes Wait -> number_input and Turn -> direction_selection), so every
    handler stage is reachable.
    """
    _, session_manager = _get_app()
    session_id, _username = session_manager.create_session(
        f"fuzz_{rng.randint(0, 1 << 30)}"
    )
    player = session_manager.get_player(session_id)

    from src.npc import Slime, CaveBat

    enemies = [Slime(), CaveBat()]
    tile = player.universe.get_tile(player.location_x, player.location_y)
    if tile is not None:
        player.current_room = tile
        tile.npcs_here = list(getattr(tile, "npcs_here", [])) + enemies

    from src.api.combat_adapter import ApiCombatAdapter

    adapter = ApiCombatAdapter(player, session_id=session_id)
    adapter.initialize_combat(enemies)

    # Force melee range so targeted moves are viable and the target list is
    # populated (deterministic — independent of spawn positioning).
    player.combat_proximity = {e: 2 for e in enemies}
    for e in enemies:
        e.combat_proximity = {player: 2}

    return adapter, player, enemies


# ---------------------------------------------------------------------------
# Random command generation
# ---------------------------------------------------------------------------

def _weird_number(rng):
    return rng.choice([
        -1, 0, 1, 3, 5, 7, 999999999, -999999999, 2 ** 63,
        1.5, -2.7, float("nan"), float("inf"), float("-inf"),
        True, False, None, "5", "abc", "", [], {}, 3 + 2j,
    ])


def _weird_index(rng):
    return rng.choice([
        -1, -999, 0, 1, 2, 5, 12, 13, 999999, 2 ** 40,
        1.0, 2.5, float("inf"), float("nan"), None, "1", "attack", "",
        True, False, [], {}, 0.0,
    ])


def _target_id(rng, adapter, player, enemies):
    kind = rng.randint(0, 9)
    if kind == 0 and enemies:
        return f"enemy_{id(rng.choice(enemies))}"          # real enemy
    if kind == 1:
        return f"ally_{id(player)}"                        # player's own id
    if kind == 2:
        return "player"
    if kind == 3:
        return "enemy_0"                                   # legacy-style id
    if kind == 4:
        return "enemy_999999999"                           # unknown id
    if kind == 5 and enemies:
        return f"enemy_{id(enemies[0])}"                   # possibly-dead/dup
    if kind == 6:
        return ""
    if kind == 7:
        return None
    if kind == 8:
        return rng.choice([123, 4.5, [], {}, True])        # non-string
    return "ally_" + "".join(rng.choice("0123456789") for _ in range(6))


def _move_name(rng, player):
    kind = rng.randint(0, 5)
    if kind == 0 and player.known_moves:
        return rng.choice(player.known_moves).name          # exact
    if kind == 1 and player.known_moves:
        return rng.choice(player.known_moves).name.lower()  # case variant
    if kind == 2:
        return "Att"                                        # partial
    if kind == 3:
        return rng.choice(["", "   ", "NoSuchMove", "\x00"])
    if kind == 4:
        return rng.choice([None, 123, [], {}, True])        # non-string
    return "attack"


def random_command(rng, adapter, player, enemies):
    """Produce one adversarial command dict (or a deliberately malformed value)."""
    kind = rng.randint(0, 12)
    if kind == 0:
        return {"type": "select_move", "move_index": _weird_index(rng)}
    if kind == 1:
        return {"type": "select_target",
                "target_id": _target_id(rng, adapter, player, enemies)}
    if kind == 2:
        return {"type": "select_direction", "direction": rng.choice(_DIRECTIONS)}
    if kind == 3:
        return {"type": "select_number", "value": _weird_number(rng)}
    if kind == 4:
        return {"type": "select_move_and_target",
                "move_name": _move_name(rng, player),
                "target_id": _target_id(rng, adapter, player, enemies)}
    if kind == 5:
        return {"type": "cancel_selection"}
    if kind == 6:
        return {"type": rng.choice(["", "bogus", "SELECT_MOVE", "attack", None])}
    if kind == 7:
        return {}                                            # missing type
    if kind == 8:
        # extra keys alongside a valid-ish type
        return {"type": "select_move", "move_index": _weird_index(rng),
                "junk": [1, 2, 3], "target_id": "enemy_0", "value": "x"}
    if kind == 9:
        return rng.choice([None, [], "string", 42, 3.14])    # non-dict
    if kind == 10:
        # a *valid* move selection to reach deeper stages, then keep fuzzing
        idx = rng.randrange(len(player.known_moves)) if player.known_moves else 0
        return {"type": "select_move", "move_index": idx}
    if kind == 11:
        return {"type": "select_number"}                     # missing value
    return {"type": "select_target"}                         # missing target_id


# ---------------------------------------------------------------------------
# Invariant checks
# ---------------------------------------------------------------------------

def _snapshot(adapter):
    """A cheap, comparable snapshot of the adapter's exposed protocol state."""
    return (
        adapter.awaiting_input,
        adapter.input_type,
        adapter.pending_move_index,
        len(adapter.available_options)
        if hasattr(adapter.available_options, "__len__") else None,
    )


def _check_state_coherent(adapter, player, seed, i, command):
    findings = []
    ai = adapter.awaiting_input
    if not isinstance(ai, bool):
        findings.append(Finding(seed, i, "state-incoherent",
                                f"awaiting_input is {type(ai).__name__}: {ai!r}",
                                command))
    it = adapter.input_type
    if it not in _VALID_INPUT_TYPES:
        findings.append(Finding(seed, i, "state-incoherent",
                                f"input_type not a known stage: {it!r}", command))
    pmi = adapter.pending_move_index
    if pmi is not None:
        if not isinstance(pmi, int) or isinstance(pmi, bool):
            findings.append(Finding(seed, i, "state-incoherent",
                                    f"pending_move_index not int/None: {pmi!r}",
                                    command))
        elif pmi < 0 or pmi >= len(player.known_moves):
            findings.append(Finding(seed, i, "state-incoherent",
                                    f"pending_move_index out of range: {pmi!r}",
                                    command))
    opts = adapter.available_options
    if not isinstance(opts, (list, dict)):
        findings.append(Finding(seed, i, "state-incoherent",
                                f"available_options not list/dict: "
                                f"{type(opts).__name__}", command))
    return findings


def _run_one_command(adapter, player, enemies, command, seed, i):
    """Invoke process_command once and validate every hard invariant."""
    findings = []
    awaiting_before = adapter.awaiting_input
    state_before = _snapshot(adapter)

    try:
        result = adapter.process_command(command)
    except Exception as exc:  # noqa: BLE001 — any raise is a breach
        import traceback
        findings.append(Finding(
            seed, i, "handler-raised",
            f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}", command))
        return findings, False

    if not isinstance(result, dict):
        findings.append(Finding(seed, i, "handler-returned-nondict",
                                f"returned {type(result).__name__}: {result!r}",
                                command))

    findings.extend(_check_state_coherent(adapter, player, seed, i, command))

    # Out-of-combat mutation: if we were NOT awaiting input, the command must be
    # rejected and must not have changed the protocol state.
    if not awaiting_before:
        if isinstance(result, dict) and "error" not in result:
            findings.append(Finding(seed, i, "out-of-combat-mutation",
                                    "command accepted while not awaiting input "
                                    f"(no error): {result!r}", command))
        if _snapshot(adapter) != state_before:
            findings.append(Finding(seed, i, "out-of-combat-mutation",
                                    f"state changed while not awaiting input: "
                                    f"{state_before} -> {_snapshot(adapter)}",
                                    command))

    return findings, adapter.awaiting_input


# ---------------------------------------------------------------------------
# Fuzz driver
# ---------------------------------------------------------------------------

def run_fuzz(iterations=400, seed=None, sequence_len=12):
    """Run the fuzzer and return a list of :class:`Finding` (empty == clean)."""
    if seed is None:
        seed = random.randrange(2 ** 32)
    rng = random.Random(seed)
    findings = []

    i = 0
    while i < iterations:
        try:
            adapter, player, enemies = build_combat(rng)
        except Exception as exc:  # noqa: BLE001
            import traceback
            findings.append(Finding(seed, i, "harness-error",
                                    f"session build failed: {exc}\n"
                                    f"{traceback.format_exc()}"))
            break

        # Drive a random-length sequence of commands against this one battle.
        for _ in range(sequence_len):
            if i >= iterations:
                break
            command = random_command(rng, adapter, player, enemies)
            # process_command mutates the command dict path only via .get(); pass a
            # deep copy so a finding's recorded command reflects the input as sent.
            try:
                sent = copy.deepcopy(command)
            except Exception:  # noqa: BLE001 — unpicklable junk: send as-is
                sent = command
            try:
                got, _awaiting = _run_one_command(
                    adapter, player, enemies, sent, seed, i)
                findings.extend(got)
            except Exception as exc:  # noqa: BLE001 — harness must not die
                import traceback
                findings.append(Finding(seed, i, "harness-error",
                                        f"{type(exc).__name__}: {exc}\n"
                                        f"{traceback.format_exc()}", command))
            i += 1

    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=400)
    parser.add_argument("--seed", type=int, default=None,
                        help="Fix the RNG seed for a reproducible run.")
    args = parser.parse_args(argv)

    findings = run_fuzz(args.iterations, args.seed)
    security = security_findings(findings)
    info = info_findings(findings)

    if info:
        # Informational findings should be rare here; surface a few for tuning.
        print(f"NOTE: {len(info)} informational finding(s):")
        seen = set()
        for f in info:
            if f.detail not in seen:
                seen.add(f.detail)
                print("  " + str(f))

    if security:
        print(f"FAIL: {len(security)} invariant violation(s):")
        for f in security[:50]:
            print("  " + str(f))
        return 1
    print(f"OK: {args.iterations} iterations, no invariant violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
