"""Contract test: the combat glossary's copy ↔ the engine it describes.

The glossary (issue #507, ``frontend/src/data/combatGlossary.js``) tells the
player how combat works in prose: how long a cooldown runs, where heat is
clamped, how wide the glancing-blow window is. Prose cannot be type-checked and
nobody re-reads it after a balance change, so without a guard the glossary
quietly becomes a set of confident lies — a worse outcome than the silence it
was written to fix.

Two things are pinned here:

1. **The numbers.** Every value the copy quotes is declared once, in
   ``ENGINE_CONSTANTS``, next to the engine site it came from. This file parses
   that block out of the JS and checks each entry against the real engine —
   exercising live objects where the value is observable (the heat clamp, the
   per-beat drift) and reading the literal out of the engine source where it is
   inline arithmetic (the cooldown formula, the movement cap).

2. **The words the tooltip attaches to.** ``GlossaryText`` only explains a term
   if ``splitTextByGlossaryTerms`` recognises it, which makes the *wording* of
   an engine string load-bearing UI: rename "Available in 5 beats" to
   "Ready in 5 turns" and the explainer silently stops appearing, with nothing
   failing. So the real reason strings a real ``ApiCombatAdapter`` emits are
   run against the glossary's own patterns here.

This is the same shape as ``tests/test_move_categories_ui_contract.py`` and
``tests/test_wire_field_contract.py``: parse what one side actually declares,
assert it against what the other side actually does, with no exception lists.
"""

import math
import pathlib
import re
import sys
from unittest.mock import patch

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.api import combat_adapter as combat_adapter_module
from src.api.combat_adapter import ApiCombatAdapter
from src.moves import Attack
from src.moves import _base as moves_base
from src.player import Player

_GLOSSARY_JS = _ROOT / "frontend" / "src" / "data" / "combatGlossary.js"
_MOVES_BASE_PY = _ROOT / "src" / "moves" / "_base.py"
_MOVES_MOVEMENT_PY = _ROOT / "src" / "moves" / "_movement.py"
_MOVES_UTILITY_PY = _ROOT / "src" / "moves" / "_utility.py"


def _glossary_source():
    return _GLOSSARY_JS.read_text(encoding="utf-8")


def _engine_constants():
    """Parse ENGINE_CONSTANTS out of the JS module as {name: float}."""
    match = re.search(
        r"export const ENGINE_CONSTANTS = \{(.*?)\n\}", _glossary_source(), re.DOTALL
    )
    assert match, "ENGINE_CONSTANTS block not found in combatGlossary.js"
    return {
        name: float(value)
        for name, value in re.findall(
            r"^  (\w+): ([0-9.]+),$", match.group(1), re.MULTILINE
        )
    }


def _glossary_patterns():
    """Parse each entry's `patterns` array as {entry id: [regex source]}."""
    source = _glossary_source()
    entries = re.findall(
        r"\n    id: '(\w+)',.*?\n    patterns: \[([^\]]*)\],", source, re.DOTALL
    )
    assert entries, "no glossary entries with patterns found in combatGlossary.js"
    return {entry_id: re.findall(r"'([^']+)'", body) for entry_id, body in entries}


def _matching_entry_ids(text):
    """Every glossary entry whose patterns match somewhere in `text`.

    Mirrors splitTextByGlossaryTerms' matcher: each pattern is word-bounded and
    matched case-insensitively.
    """
    matched = []
    for entry_id, patterns in _glossary_patterns().items():
        combined = r"\b(?:" + "|".join(patterns) + r")\b"
        if re.search(combined, text, re.IGNORECASE):
            matched.append(entry_id)
    return matched


CONSTANTS = _engine_constants()


def _combat_player():
    """A real Player wired up the way ApiCombatAdapter.__init__ requires."""
    player = Player()
    player.known_moves = []
    player.combat_log = []
    player.last_move_summary = ""
    player.combat_beat = 1
    player.combat_list = []
    player.combat_list_allies = [player]
    player.combat_proximity = {}
    player.in_combat = True
    return player


@pytest.fixture
def adapter():
    # CombatStrategist starts background AI machinery irrelevant to the wording
    # and numbers under test; every adapter test patches it the same way.
    with patch("src.api.combat_adapter.CombatStrategist"):
        yield ApiCombatAdapter(_combat_player())


class TestGlossaryNumbersMatchTheEngine:
    def test_every_declared_constant_is_checked_here(self):
        """No constant may be added to the copy without a check beside it.

        Otherwise the guard degrades into a guard over whichever values someone
        happened to remember, which is exactly how a stale glossary survives.
        """
        checked = {
            "restRecoveryFraction",
            "heatMin",
            "heatMax",
            "heatDriftPercentPerBeat",
            "cooldownWeightBase",
            "cooldownEnduranceDivisor",
            "glanceMargin",
            "meleeReachFt",
            "abortableMinPrepBeats",
            "stepMinFt",
            "stepMaxFt",
        }
        assert set(CONSTANTS) == checked, (
            "combatGlossary.js ENGINE_CONSTANTS and this test have drifted. "
            "Add a check for every new constant, and delete the check for any "
            "value the copy stopped quoting."
        )

    def test_the_copy_quotes_no_starting_fatigue_number(self):
        """The mockup's "starts 150/150" did not survive contact with the engine.

        150 is ``maxfatigue_base``; a real fresh ``Player`` opens on 190/190,
        because ``functions.refresh_stat_bonuses`` adds +2 per endurance point
        above 10 and then a further 25% for carrying under half capacity. Any
        single number here would be wrong for most players, so the entry
        describes the two forces instead of quoting a total — and this test
        stops the number from being put back.
        """
        player = Player()
        assert player.maxfatigue != player.maxfatigue_base
        assert "startingFatigue" not in CONSTANTS
        assert "start the game with" not in _glossary_source()

    def test_rest_recovers_the_fraction_the_copy_quotes(self):
        source = _MOVES_UTILITY_PY.read_text(encoding="utf-8")
        fraction = CONSTANTS["restRecoveryFraction"]
        assert re.search(rf"maxfatigue \* {fraction}\b", source), (
            f"Rest no longer restores {fraction} of maxfatigue — the Fatigue "
            "glossary entry quotes that figure."
        )

    def test_heat_is_clamped_where_the_copy_says_it_is(self):
        player = Player()
        player.heat = 1.0
        player.change_heat(mult=1000)
        assert player.heat == CONSTANTS["heatMax"]
        player.change_heat(mult=0.0001)
        assert player.heat == CONSTANTS["heatMin"]

    @pytest.mark.parametrize("start", [2.0, 0.5])
    def test_heat_closes_the_quoted_share_of_the_gap_each_beat(self, adapter, start):
        adapter.player.heat = start
        adapter._update_heat()
        closed = abs(start - adapter.player.heat) / abs(start - 1.0)
        assert closed == pytest.approx(CONSTANTS["heatDriftPercentPerBeat"] / 100)

    def test_cooldown_formula(self):
        source = _MOVES_BASE_PY.read_text(encoding="utf-8")
        base = int(CONSTANTS["cooldownWeightBase"])
        divisor = int(CONSTANTS["cooldownEnduranceDivisor"])
        assert re.search(
            rf"cooldown = int\(\({base} \+ weight\)\) - int\(endurance / {divisor}\)",
            source,
        ), (
            "the standard-attack cooldown formula moved; the Cooldown glossary "
            "entry states it in words."
        )

    def test_glance_margin(self):
        assert CONSTANTS["glanceMargin"] == moves_base.GLANCE_MARGIN

    def test_glance_margin_still_halves_the_damage_the_copy_promises(self):
        margin = int(CONSTANTS["glanceMargin"])
        inside, _ = moves_base.apply_glancing_blow(40, 60, 60 - (margin - 1))
        outside, glanced = moves_base.apply_glancing_blow(40, 60, 60 - margin)
        assert inside == 20
        assert outside == 40 and glanced is False

    def test_melee_reach_ring_threshold(self):
        assert CONSTANTS["meleeReachFt"] == combat_adapter_module.MELEE_REACH_FT

    def test_abortable_prep_threshold(self):
        assert (
            CONSTANTS["abortableMinPrepBeats"]
            == combat_adapter_module.ABORTABLE_MIN_PREP_BEATS
        )

    def test_a_beats_travel_is_clamped_to_the_quoted_range(self):
        source = _MOVES_MOVEMENT_PY.read_text(encoding="utf-8")
        low = int(CONSTANTS["stepMinFt"])
        high = int(CONSTANTS["stepMaxFt"])
        assert re.search(rf"distance_moved = max\({low}, ", source)
        assert re.search(rf"distance_moved = min\(distance_moved, {high}\)", source)


class TestGlossaryTermsMatchTheEngineWording:
    """The explainer only appears on words the glossary recognises.

    A reworded engine string is therefore a silent UI regression, of exactly the
    kind CLAUDE.md calls this codebase's dominant bug class — the read fails,
    nothing throws, and the feature just stops working.
    """

    def _cooldown_reason(self, adapter, beats_left):
        move = Attack(adapter.player)
        move.current_stage = 3
        move.beats_left = beats_left
        adapter.player.known_moves = [move]
        return next(
            payload["reason"]
            for payload in adapter._get_available_moves()
            if payload.get("reason")
        )

    def test_the_cooldown_reason_still_says_beats(self, adapter):
        reason = self._cooldown_reason(adapter, beats_left=4)
        # The player-facing number is one larger than the engine's stage
        # counter by design (draining to zero does not itself advance the
        # stage; the next beat does) — the glossary states the displayed one.
        assert reason == "Available in 5 beats"
        assert "beat" in _matching_entry_ids(reason)

    def test_the_last_beat_of_a_cooldown_is_explained_too(self, adapter):
        reason = self._cooldown_reason(adapter, beats_left=0)
        assert reason == "Available next beat"
        assert "beat" in _matching_entry_ids(reason)

    def test_the_out_of_fatigue_reason_reaches_the_fatigue_entry(self, adapter):
        move = Attack(adapter.player)
        move.current_stage = 0
        move.fatigue_cost = 20
        adapter.player.fatigue = 1
        adapter.player.known_moves = [move]
        reason = next(
            payload["reason"]
            for payload in adapter._get_available_moves()
            if payload.get("reason")
        )
        assert reason == "Not enough fatigue"
        assert "fatigue" in _matching_entry_ids(reason)

    def test_a_reason_with_no_glossary_term_matches_nothing(self):
        assert _matching_entry_ids("No weapon equipped") == []

    def test_the_displayed_cooldown_number_is_the_one_the_copy_describes(self, adapter):
        """cooldown_remaining = beats_left + 1, per the maintainer's ruling."""
        move = Attack(adapter.player)
        move.current_stage = 3
        move.beats_left = 4
        adapter.player.known_moves = [move]
        payload = adapter._get_available_moves()[0]
        assert payload["cooldown_remaining"] == move.beats_left + 1
        assert payload["cooldown_max"] == move.stage_beat[3] + 1


class TestGlossaryEntriesAreWellFormed:
    def test_every_entry_declares_at_least_one_pattern(self):
        patterns = _glossary_patterns()
        assert len(patterns) >= 10
        for entry_id, entry_patterns in patterns.items():
            assert entry_patterns, f"glossary entry {entry_id!r} declares no patterns"

    def test_every_pattern_compiles_as_a_regular_expression(self):
        for entry_id, entry_patterns in _glossary_patterns().items():
            for pattern in entry_patterns:
                try:
                    re.compile(pattern)
                except re.error as exc:  # pragma: no cover - the assert is the report
                    pytest.fail(f"glossary entry {entry_id!r} pattern {pattern!r}: {exc}")

    def test_rest_recovery_reads_as_a_whole_percentage_in_the_copy(self):
        # The Fatigue entry renders `restRecoveryFraction * 100` rounded; a
        # fraction that does not land on a whole percent would read oddly.
        percent = CONSTANTS["restRecoveryFraction"] * 100
        assert math.isclose(percent, round(percent))
