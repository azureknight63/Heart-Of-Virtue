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
import src.items as items
from src.moves import Attack
from src.moves import _base as moves_base
from src.player import Player

_GLOSSARY_JS = _ROOT / "frontend" / "src" / "data" / "combatGlossary.js"
_HEAT_JS = _ROOT / "frontend" / "src" / "utils" / "heat.js"
_MOVE_PANEL_JSX = _ROOT / "frontend" / "src" / "components" / "CombatMovePanel.jsx"
_MOVES_BASE_PY = _ROOT / "src" / "moves" / "_base.py"
_MOVES_MOVEMENT_PY = _ROOT / "src" / "moves" / "_movement.py"
_MOVES_UTILITY_PY = _ROOT / "src" / "moves" / "_utility.py"
_THIS_FILE = pathlib.Path(__file__)


def _glossary_source():
    return _GLOSSARY_JS.read_text(encoding="utf-8")


def _js_number_exports(path):
    """`export const NAME = <number>` declarations in a JS module."""
    return {
        name: float(value)
        for name, value in re.findall(
            r"^export const (\w+) = ([0-9.]+)$",
            path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    }


def _resolve_constant(expression, symbols):
    """A number, an imported constant, or a product of those.

    ENGINE_CONSTANTS re-exports the heat figures from utils/heat.js rather than
    re-typing them, so the values are no longer all literals. Deliberately tiny:
    anything this cannot resolve fails loudly instead of being skipped, which is
    the whole point of the block being machine-checked.
    """
    value = 1.0
    for token in (part.strip() for part in expression.split("*")):
        if re.fullmatch(r"[0-9.]+", token):
            value *= float(token)
        else:
            assert token in symbols, (
                f"ENGINE_CONSTANTS refers to {token!r}, which is not a numeric "
                "export of frontend/src/utils/heat.js. Add it there, or inline "
                "the number with its engine citation."
            )
            value *= symbols[token]
    return value


def _engine_constants():
    """Parse ENGINE_CONSTANTS out of the JS module as {name: float}."""
    match = re.search(
        r"export const ENGINE_CONSTANTS = \{(.*?)\n\}", _glossary_source(), re.DOTALL
    )
    assert match, "ENGINE_CONSTANTS block not found in combatGlossary.js"
    symbols = _js_number_exports(_HEAT_JS)
    return {
        name: _resolve_constant(expression, symbols)
        for name, expression in re.findall(
            r"^  (\w+): ([^,]+),$", match.group(1), re.MULTILINE
        )
    }


def _entry_blocks():
    """Each GLOSSARY_ENTRIES element as {entry id: its source text}.

    Split on the element boundary rather than pattern-matched with one DOTALL
    regex over the whole file. The old shape (`id: …` bridged to `patterns: …`
    by `.*?`) could silently pair an id with the NEXT entry's patterns, and
    dropped any entry whose formatting it did not expect — a fail-open parser
    behind an assertion that only checked a floor.
    """
    array = re.search(
        r"export const GLOSSARY_ENTRIES = \[\n(.*?)\n\]\n", _glossary_source(), re.DOTALL
    )
    assert array, "GLOSSARY_ENTRIES block not found in combatGlossary.js"
    body = array.group(1)

    blocks = {}
    for block in re.split(r"\n(?=  \{\n)", body):
        match = re.search(r"^    id: '(\w+)',$", block, re.MULTILINE)
        assert match, f"could not read an entry id out of block: {block[:80]!r}"
        blocks[match.group(1)] = block

    # The ids, found independently of the block split. If the two disagree the
    # split lost an entry, and every check built on it was silently narrower
    # than its name claims.
    declared = re.findall(r"^    id: '(\w+)',$", body, re.MULTILINE)
    assert sorted(declared) == sorted(blocks), (
        "the GLOSSARY_ENTRIES parser did not see every entry: "
        f"ids {sorted(declared)} vs blocks {sorted(blocks)}"
    )
    return blocks


def _glossary_patterns():
    """Parse each entry's `patterns` array as {entry id: [regex source]}."""
    return {
        entry_id: re.findall(
            r"'([^']+)'",
            (re.search(r"^    patterns: \[([^\]]*)\],$", block, re.MULTILINE) or _NoPatterns).group(1),
        )
        for entry_id, block in ENTRY_BLOCKS.items()
    }


class _NoPatterns:
    """Stand-in so a `patterns:` line the parser cannot see yields [] — which
    ``test_every_entry_declares_at_least_one_pattern`` then reports by name —
    rather than raising an AttributeError that names no entry."""

    @staticmethod
    def group(_index):
        return ""


def _entry_text(entry_id):
    """The player-visible copy of one entry: its short, body and tell."""
    block = ENTRY_BLOCKS[entry_id]
    return "\n".join(
        re.findall(r"^\s*(?:short|tell): (.*)$", block, re.MULTILINE)
        + re.findall(r"^      ['`](.*)$", block, re.MULTILINE)
    )


def _constants_referenced_in_class(class_name):
    """Every `CONSTANTS[...]` name this test file reads inside `class_name`."""
    source = _THIS_FILE.read_text(encoding="utf-8")
    match = re.search(rf"\nclass {class_name}\b.*?(?=\nclass |\Z)", source, re.DOTALL)
    assert match, f"class {class_name} not found in {_THIS_FILE.name}"
    # This helper is module-level, so its own regex literal is never inside the
    # class body it scans — and it would not match itself anyway (the literal
    # reads `CONSTANTS\[`, with a backslash the pattern does not allow).
    return set(re.findall(r'CONSTANTS\["(\w+)"\]', match.group(0)))


def _python_class_body(source, class_name):
    """One class's source out of a module, so a search cannot stray into another.

    Advance and Withdraw both contain a line starting `distance_moved = max(1, `
    and both cap it — at different numbers. A file-wide search for either
    substring therefore passes on Advance's copy while saying nothing at all
    about Withdraw, which is exactly how the copy came to quote a 3 ft cap for a
    move that stops at 2.
    """
    match = re.search(rf"\nclass {class_name}\(.*?(?=\nclass |\Z)", source, re.DOTALL)
    assert match, f"class {class_name} not found in the movement module"
    return match.group(0)


def _matching_entry_ids(text):
    """Every glossary entry whose patterns match somewhere in `text`.

    Mirrors splitTextByGlossaryTerms' matcher: each pattern is word-bounded and
    matched case-insensitively.
    """
    matched = []
    for entry_id, patterns in PATTERNS.items():
        combined = r"\b(?:" + "|".join(patterns) + r")\b"
        if re.search(combined, text, re.IGNORECASE):
            matched.append(entry_id)
    return matched


# Parsed once, beside CONSTANTS: _glossary_patterns() re-read and re-parsed the
# whole JS module on every call, including once per entry inside
# _matching_entry_ids.
CONSTANTS = _engine_constants()
ENTRY_BLOCKS = _entry_blocks()
PATTERNS = _glossary_patterns()


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

        The set of checked names is READ OUT of this class rather than typed
        below it. Hand-listing them made this test pass for a constant that had
        been added to the list and never actually asserted against the engine —
        the precise degradation the paragraph above warns about, reintroduced by
        the guard against it.
        """
        checked = _constants_referenced_in_class(type(self).__name__)
        assert set(CONSTANTS) == checked, (
            "combatGlossary.js ENGINE_CONSTANTS and this class have drifted. "
            "Every declared constant needs a test in this class that reads it "
            "out of CONSTANTS and checks it against the engine; delete the "
            "check for any value the copy stopped quoting."
        )

    def test_the_copy_quotes_no_starting_fatigue_number(self):
        """The mockup's "starts 150/150" did not survive contact with the engine.

        150 is ``maxfatigue_base``; a real fresh ``Player`` opens on 190/190,
        because ``functions.refresh_stat_bonuses`` adds +2 per endurance point
        above 10 and then a further 25% for carrying under half capacity. Any
        single number here would be wrong for most players, so the entry
        describes the two forces instead of quoting a total — and this test
        stops the number from being put back.

        Checking for one banned phrase let every other phrasing of the same
        mistake through ("Jean opens a fight at 190/190" passed), so the real
        assertion is over the fatigue entry's own copy: no `NNN/NNN` total.
        """
        player = Player()
        assert player.maxfatigue != player.maxfatigue_base
        assert "startingFatigue" not in CONSTANTS
        assert "start the game with" not in _glossary_source()

        fatigue_copy = _entry_text("fatigue")
        assert fatigue_copy, "the fatigue entry's copy could not be read"
        quoted_total = re.search(r"\b\d{2,4}\s*/\s*\d{2,4}\b", fatigue_copy)
        assert not quoted_total, (
            "the Fatigue entry quotes a starting-fatigue total "
            f"({quoted_total.group(0) if quoted_total else ''}). There is no "
            "single right number: maxfatigue depends on endurance and carried "
            "weight. Describe the two forces instead."
        )

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

    @pytest.mark.parametrize(
        "move_class, cap_constant",
        [("Advance", "advanceStepMaxFt"), ("Withdraw", "withdrawStepMaxFt")],
    )
    def test_a_beats_travel_is_clamped_to_the_quoted_range(
        self, move_class, cap_constant
    ):
        """Each mover's cap, checked against ITS OWN class body.

        Searching the whole module for `distance_moved = min(distance_moved, 3)`
        found Advance's line and passed — while Withdraw, two hundred lines
        further down, capped at 2 and the copy said 3 for both. A file-wide
        search over a file with six independent implementations of the same
        idea asserts nothing about any particular one of them.
        """
        source = _MOVES_MOVEMENT_PY.read_text(encoding="utf-8")
        body = _python_class_body(source, move_class)
        low = int(CONSTANTS["stepMinFt"])
        cap = int(CONSTANTS[cap_constant])
        assert re.search(rf"distance_moved = max\({low}, ", body), (
            f"{move_class} no longer floors a beat's travel at {low} ft; the "
            "Distance & reach glossary entry quotes that floor."
        )
        assert re.search(rf"distance_moved = min\(distance_moved, {cap}\)", body), (
            f"{move_class} no longer caps a beat's travel at {cap} ft; the "
            "Distance & reach glossary entry quotes that cap."
        )

    def test_the_two_movers_do_not_share_a_cap(self):
        """The caps differ, and the copy is only correct while they do.

        Stated as its own assertion because the parametrized test above passes
        just as happily if the two constants are made equal — and "roughly 1 to
        3 feet per beat" covering both moves is precisely the false claim that
        shipped.
        """
        assert CONSTANTS["advanceStepMaxFt"] != CONSTANTS["withdrawStepMaxFt"], (
            "Advance and Withdraw now share a per-beat cap. The Distance & "
            "reach entry states them separately — collapse it back into one "
            "range if that is deliberate."
        )


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
        """cooldown_remaining = beats_left + 1, per the maintainer's ruling.

        The name promises the ADAPTER and the COPY agree, so both halves are
        asserted: previously the body only restated the adapter's arithmetic
        back to itself and never opened the glossary at all, which would have
        stayed green through any rewording of the entry.
        """
        move = Attack(adapter.player)
        move.current_stage = 3
        move.beats_left = 4
        adapter.player.known_moves = [move]
        payload = adapter._get_available_moves()[0]
        assert payload["cooldown_remaining"] == move.beats_left + 1
        assert payload["cooldown_max"] == move.stage_beat[3] + 1

        # The reason string the card shows for that same move, verbatim in the
        # Cooldown entry — the copy's whole point is that the greyed-out card
        # is not a lockout, and it makes that point by quoting the card.
        reason = payload["reason"]
        assert reason == f"Available in {payload['cooldown_remaining']} beats"
        assert f'"{reason}"' in _entry_text("cooldown"), (
            "the Cooldown entry quotes a card string the adapter no longer "
            f"emits; it now says {reason!r}."
        )


    @pytest.mark.parametrize(
        "long_reach, expected",
        [(False, "Enemy out of range (too far)"), (True, "No valid target in range")],
    )
    def test_both_out_of_range_reasons_reach_the_distance_entry(
        self, adapter, long_reach, expected
    ):
        """A move out of range emits one of TWO strings, not one.

        The adapter only says "Enemy out of range (too far)" when
        ``range_max <= 5``; anything reaching past that — spear, bow, polearm —
        says "No valid target in range". The Distance & reach entry quoted the
        first flatly, as though it were what every long-reach move shows.

        Driven through a real ``Spear`` rather than by assigning ``mvrange``:
        ``Attack`` recomputes its band from the equipped weapon's ``wpnrange``
        on every availability pass, so a hand-set band is silently overwritten
        and the test would only ever exercise the unarmed branch.
        """
        if long_reach:
            adapter.player.eq_weapon = items.Spear()
        move = Attack(adapter.player)
        move.current_stage = 0
        move.fatigue_cost = 0
        adapter.player.combat_proximity = {object(): 80}
        adapter.player.known_moves = [move]
        reason = next(
            payload["reason"]
            for payload in adapter._get_available_moves()
            if payload.get("reason")
        )
        assert reason == expected
        assert "distance" in _matching_entry_ids(reason)

    def test_the_range_string_the_copy_quotes_is_one_the_engine_emits(self):
        """Any engine string the copy puts in quotation marks is pinned here.

        The copy hedges it as "a range reason such as …" precisely because it is
        one of two; that hedge is only honest while the quoted half is real.
        """
        quoted = re.findall(r'\\"([^"]+)\\"|"([^"]+)"', _entry_text("distance"))
        quoted = {a or b for a, b in quoted}
        adapter_source = (
            _ROOT / "src" / "api" / "combat_adapter.py"
        ).read_text(encoding="utf-8")
        for phrase in quoted:
            if "range" not in phrase.lower():
                continue
            assert f'"{phrase}"' in adapter_source, (
                f"the Distance & reach entry quotes {phrase!r}, which "
                "src/api/combat_adapter.py no longer emits."
            )


class TestGlossaryEntriesAreWellFormed:
    def test_every_entry_declares_at_least_one_pattern(self):
        # Equality, not a floor: `>= 10` passed while the fail-open parser was
        # dropping entries it could not see.
        assert set(PATTERNS) == set(ENTRY_BLOCKS)
        for entry_id, entry_patterns in PATTERNS.items():
            assert entry_patterns, f"glossary entry {entry_id!r} declares no patterns"

    def test_every_pattern_compiles_as_a_regular_expression(self):
        for entry_id, entry_patterns in PATTERNS.items():
            for pattern in entry_patterns:
                try:
                    re.compile(pattern)
                except re.error as exc:  # pragma: no cover - the assert is the report
                    pytest.fail(f"glossary entry {entry_id!r} pattern {pattern!r}: {exc}")

    def test_no_pattern_opens_a_capturing_group(self):
        """MATCHER's whole attribution scheme rests on this.

        `splitTextByGlossaryTerms` wraps each ENTRY in exactly one group and
        reads the entry back off the group NUMBER that matched. A capturing
        group inside any pattern renumbers every entry after it: the wrong
        tooltip opens, or the index runs off the end of GLOSSARY_ENTRIES —
        inside a render that runs on every unavailability reason of every
        combat poll. `break(?:ing)? off` is non-capturing for this reason.
        """
        for entry_id, entry_patterns in PATTERNS.items():
            for pattern in entry_patterns:
                assert re.compile(pattern).groups == 0, (
                    f"glossary entry {entry_id!r} pattern {pattern!r} opens a "
                    "capturing group. Use (?:…) — see the patterns note in "
                    "combatGlossary.js."
                )

    def test_the_stages_entry_names_the_stages_the_move_card_labels(self):
        """The four stage names have one on-screen source: STAGE_LABELS.

        The entry hand-copied them. It is not exported, so this reads the map
        out of the component rather than the component importing the entry.
        """
        labels = re.search(
            r"const STAGE_LABELS = \{(.*?)\};", _MOVE_PANEL_JSX.read_text(encoding="utf-8"),
            re.DOTALL,
        )
        assert labels, "STAGE_LABELS not found in CombatMovePanel.jsx"
        values = re.findall(r": '([^']+)',", labels.group(1))
        assert len(values) == 4, f"expected four stage labels, found {values}"
        body = _entry_text("stages")
        for value in values:
            assert value in body, (
                f"CombatMovePanel labels a stage {value!r}, which the four-stages "
                "glossary entry does not name."
            )

    def test_rest_recovery_reads_as_a_whole_percentage_in_the_copy(self):
        # The Fatigue entry renders `restRecoveryFraction * 100` rounded; a
        # fraction that does not land on a whole percent would read oddly.
        percent = CONSTANTS["restRecoveryFraction"] * 100
        assert math.isclose(percent, round(percent))
