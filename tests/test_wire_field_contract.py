"""Contract test: wire-field-name drift between the Python serializers and the
React client, for the combat, player, and shop payloads.

Modelled on ``tests/test_move_categories_ui_contract.py`` (same spirit: parse/derive
what one side actually does, assert the other side actually matches — no
exception lists, no mocking around the seam being tested).

=== The bug class ===

A code review of this repo found "wire-field-name drift" as the dominant defect
class: the React client reads a field name the Python serializer never emits.
Because the client reads through ``??``/``||`` fallback chains, the miss is
silently swallowed and the feature just quietly does nothing — no error, no
crash, no failing test. Four instances shipped in one branch before this guard
existed:

1. ``LeftPanel`` depended on ``combat.turn_number``/``combat.combat_id`` — the
   serializer emits ``round``/``beat`` instead.
2. A carry-capacity read used ``weight_tolerance`` — the *engine* attribute
   name, not a key either player payload serializer ever emits (they emit
   ``weight_current``/``carrying_capacity``/``max_weight``).
3. ``StatusEffectsIconPanel`` gated on ``duration_remaining`` when
   ``StateEffectSerializer.serialize_state`` (the function that actually feeds
   this component) emits ``beats_left``.
4. ``CombatInputDialog`` rescaled ``hit_chance`` as a 0-1 fraction, when the
   engine already sends an integer percentage.

Every one of these was invisible to the existing test suite because the *test
fixtures* (mocks with hand-set attributes) encoded the same wrong field name as
the component under test — a mock cannot catch a mock agreeing with itself.
That is why this file builds real engine objects (``src.player.Player``,
``src.npc._enemies.Slime``, ``src.npc._merchants.Merchant``, real ``Move`` and
``State`` subclasses — see ``tests/test_serializers_real_engine_objects.py``
for the established pattern) and feeds them through the *real* serializer/
GameService code paths, then asserts the frontend's declared field list is a
subset of what actually comes back. Renaming or dropping a field breaks this
test with no mock to hide behind.

=== What's covered / not covered ===

Covered: combat (``battle_state`` + ``CombatantSerializer`` + state-effect +
target-selection shapes), player (``GameService.get_player_status`` /
``get_player_stats``), shop (``ShopSerializer.serialize_state`` /
``serialize_player_sellable`` via a real ``GameService.shop_sell`` call),
saves (``GameService.list_saves`` cloud-save row shape).

Not every consumer is the React client. ``damage_multiplier`` and
``tactical_mechanics`` are read by ``ai/combat_strategist.py`` when it builds
the combat LLM prompt, and they fail in the same silent way a frontend read
does — worse, actually, because both have a plausible-looking default (``1.0``
and ``""``). Rename either and the prompt keeps assembling: every telegraphed
hit is estimated at 1.0x with POTENTIALLY LETHAL never firing, and every status
effect loses its mechanics. Nothing crashes and no test fails, which is
precisely the drift class this file exists for, so both are contracted here
with a VALUE assertion beside the presence check — presence alone cannot tell a
real multiplier from the default.

=== How to read a failure ===

Each contract below is a ``{field: Read(...)}`` dict — see ``tests/_cite.py``.
A ``Read`` names the consuming file and an *anchor*: a literal string that file
is claimed to contain, normally the member expression the consumer evaluates.
The line numbers are computed when a failure is printed, so they cannot go
stale; they used to be written by hand here, and by the time anyone checked,
roughly half of them pointed at the wrong line. How many citations there are
is not restated either — ``_reads_written_in_this_file`` counts them and
``TestCitationProvenance`` asserts the scan sees every one. Where a field
genuinely has no literal to anchor to, the entry carries a ``note=`` instead
and is counted by ``TestCitationProvenance`` below. If a test here fails:

- If the serializer/GameService method genuinely renamed or dropped the
  field, either restore it (if the frontend still needs it) or update the
  frontend read and remove the field from the contract dict *with a comment
  explaining why the read is gone*.
- If the frontend simply no longer reads a field, remove it from the
  contract dict (with the same explanation).
- Never "fix" a failure by loosening the assertion to skip missing fields —
  that defeats the point of the guard.
"""

import ast
import io
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.api.combat_adapter as combat_adapter
from src.api.combat_adapter import ApiCombatAdapter
from src.api.serializers.combat import (
    CombatantSerializer,
    CombatStateSerializer,
    StateEffectSerializer,
)
from src.api.serializers.shop_serializer import ShopSerializer
from src.api.services.game_service import GameService
from src.items import IronArrow, Mace, Restorative, Shortbow
import src.journal as journal
from src.api.constants import ITEM_USE_RANGE
from src.moves import Attack, Check, PowerStrike, ShadowStep, ShootBow, Turn, Wait
from src.moves._mastery import BloodOfMartyrs
from ai.combat_strategist import CombatStrategist
from src.npc._enemies import Slime
from src.npc._merchants import Merchant
from src.player import Player
from src.universe import Universe
import src.states as states
from tests._cite import Read, unverifiable, verify
from tests._js_scan import FRONTEND_SRC, js_literal
from tests._gs_fixtures import GRID_3X3
from src.narration import capture_narration
from src.combatant import wire_handle


def _describe(why):
    """Render one contract value for a failure message.

    A ``Read`` computes its own line numbers at call time; a tuple is the
    two-consumer case (``HeroPanel.jsx`` *and* ``StatsPanel.jsx`` read
    ``player.hp``). Anything else — the odd inline ``{"current": "..."}``
    contract below — falls back to plain text.
    """
    if isinstance(why, Read):  # a NamedTuple, so this must precede the tuple case
        return why.describe()
    if isinstance(why, tuple):
        return " / ".join(_describe(part) for part in why)
    return str(why)


def _assert_contract(payload: dict, contract: dict, label: str):
    """Assert every field a declared consumer reads is present in the real payload.

    "Consumer" is usually the React client; two fields here are read by the
    combat prompt builder instead (see the module docstring).

    Failure message names the missing fields, what read them, and what to do —
    this is the guard's entire value, so the message has to be actionable
    without the reader re-deriving the citation trail themselves.
    """
    missing = {
        field: _describe(why)
        for field, why in contract.items()
        if field not in payload
    }
    assert not missing, (
        f"{label} is missing field(s) the frontend reads: {missing}. "
        "Either the serializer/service renamed or dropped the field (restore "
        "it, or update the frontend read and remove it from the contract dict "
        "in tests/test_wire_field_contract.py with a comment explaining why), "
        f"or the frontend no longer needs it (same: prune the contract). "
        f"Payload actually had: {sorted(payload.keys())}"
    )


# ============================================================================
# Combat payload
# ============================================================================
# transformCombatData(data) (frontend/src/utils/combatTransform.js) becomes the
# client-side `combat` object: `{...data.battle_state, log, beat_states,
# end_state, combat_active, suggested_moves, suggestions_loading,
# events_triggered, last_move_outcome, last_move_name, last_move_target_id}`.
# Fields NOT in that explicit whitelist and NOT inside battle_state are
# silently dropped by the spread — that is exactly how `combat_id` disappeared
# in bug #1 (when the transform still lived in frontend/src/hooks/useApi.js).

# Fields transformCombatData pulls off the top-level get_combat_state()
# result, outside battle_state (frontend/src/utils/combatTransform.js).
#
# Seven of the ten the transform copies, plus `battle_state`, which it
# SPREADS rather than copies. The other three -- `beat_states`, `end_state`,
# `events_triggered` -- are CONDITIONAL on the wire: the adapter adds them
# only for a finished or streaming fight, so a contract that required them in
# every payload would fail on the ordinary one this guard builds. The
# transform defaults each of them, which is why their absence is not a bug.
# Their SPELLING is pinned by
# ``test_the_conditional_top_level_fields_spell_what_the_client_reads`` below,
# which arranges each condition on a real adapter -- not by the whitelist test
# in frontend/src/hooks/useApi.test.js, which compares the transform against
# the client's own list and says so itself ("It cannot see the server").
COMBAT_TOP_LEVEL_CONTRACT = {
    "battle_state": Read("combatTransform.js", "data.battle_state"),
    "log": Read("combatTransform.js", "data.log"),
    "combat_active": Read("combatTransform.js", "data.combat_active"),
    "suggested_moves": Read("combatTransform.js", "data.suggested_moves"),
    "suggestions_loading": Read("combatTransform.js", "data.suggestions_loading"),
    "last_move_outcome": Read("combatTransform.js", "data.last_move_outcome"),
    "last_move_name": Read("combatTransform.js", "data.last_move_name"),
    "last_move_target_id": Read("combatTransform.js", "data.last_move_target_id"),
}

# Fields LeftPanel.jsx/CombatManager read off `combat.*`, i.e. off
# battle_state after the spread (frontend/src/components/LeftPanel.jsx).
BATTLE_STATE_CONTRACT = {
    # `[combat?.round, combat?.beat]` useEffect deps, with an explicit comment
    # that these replaced the nonexistent turn_number/combat_id (bug #1).
    "round": Read("LeftPanel.jsx", "combat?.round"),
    "beat": Read("LeftPanel.jsx", "combat?.beat"),
    # activePlayer = {...player, ...combat.player}
    "player": Read("LeftPanel.jsx", "combat.player"),
    # combat.enemies.every(e => (e.distance ?? 0) >= 20) — the canFlee check.
    "enemies": Read("LeftPanel.jsx", "combat.enemies"),
    "awaiting_input": Read("LeftPanel.jsx", "combat?.awaiting_input"),
    "input_type": Read("LeftPanel.jsx", "combat?.input_type"),
    "available_options": Read("LeftPanel.jsx", "combat?.available_options"),
    # Battlefield.jsx reads combat_id off the TOP-LEVEL combat object and passes
    # it to BattlefieldGrid as an explicit `combatId` prop, which keys the
    # camera-pan reset.
    #
    # The citation matters here. An earlier version of this entry credited the
    # read to BattlefieldGrid itself — but that component is handed a BEAT state
    # (Battlefield.jsx: `combat={displayState}`), and serialize_combat_state does
    # not emit combat_id. So the contract was guarding a surface the consumer
    # never saw, and it would not have caught the dep flipping uuid <-> undefined
    # as displayState alternated shape. Cite the component that actually reads
    # the payload, not the one that ends up using the value.
    "combat_id": Read("Battlefield.jsx", "combat?.combat_id"),
    # map_size was another instance of the drift bug, and this dict is why it
    # survived: the adapter emitted it at the TOP LEVEL, transformCombatData's
    # whitelist does not list it, and neither contract dict declared it — so
    # `combat?.map_size` was permanently undefined and BattlefieldGrid fell
    # back to deriving the arena from the bounding box of current positions.
    # It now rides in battle_state, which the spread carries.
    "map_size": Read("Battlefield.jsx", "combat?.map_size"),
}


@pytest.fixture
def real_combat_player():
    """A real Player wired up as ApiCombatAdapter.__init__ requires it."""
    player = Player()
    player.known_moves = []
    player.combat_log = []
    player.last_move_summary = ""
    player.combat_beat = 4
    player.combat_list = []
    player.combat_list_allies = [player]
    player.combat_proximity = {}
    player.in_combat = True
    return player


@pytest.fixture
def real_adapter(real_combat_player):
    # CombatStrategist spins up background AI/LLM machinery unrelated to the
    # wire shape under test; every existing adapter test patches it the same
    # way (see tests/test_beta_qa_regressions.py).
    with patch("src.api.combat_adapter.CombatStrategist"):
        yield ApiCombatAdapter(real_combat_player)


class TestCombatWireContract:
    def test_top_level_get_combat_state_fields(self, real_adapter, real_combat_player):
        real_adapter.awaiting_input = True
        real_adapter.input_type = "move_selection"
        real_adapter.available_options = []

        result = real_adapter.get_combat_state()

        _assert_contract(result, COMBAT_TOP_LEVEL_CONTRACT, "get_combat_state() top level")

    def test_the_conditional_top_level_fields_spell_what_the_client_reads(
        self, real_adapter, real_combat_player
    ):
        """The three top-level keys ``COMBAT_TOP_LEVEL_CONTRACT`` cannot hold.

        ``transformCombatData`` reads ``data.beat_states``,
        ``data.end_state`` and ``data.events_triggered``
        (frontend/src/utils/combatTransform.js), each behind a default -- so a
        rename on the adapter would leave the client reading an empty list, a
        null and an empty list forever, with nothing failing. That is the
        ``combat_id`` bug exactly. Each condition is arranged here and the
        name read off a real payload.
        """
        real_adapter.awaiting_input = True
        real_adapter.input_type = "move_selection"
        real_adapter.available_options = []
        # `events_triggered` rides on the adapter's own state until a payload
        # is built, which moves it across and clears it.
        real_adapter._adapter_state()["events_triggered"] = [{"type": "tile"}]
        # `end_state` is the summary a finished fight leaves on the player.
        real_combat_player.in_combat = False
        real_combat_player.combat_end_summary = {"status": "victory"}

        result = real_adapter.get_combat_state()

        assert result["events_triggered"] == [{"type": "tile"}]
        assert result["end_state"]["status"] == "victory"

        # `beat_states` is the per-beat snapshot list. Read off the
        # terminal snapshot, which is one of its two producers; the streaming
        # one (`_execute_move_inner`) sets the same key and is not exercised
        # here.
        beats = [{"beat_index": 0}]
        assert real_adapter._terminal_state_snapshot(beats)["beat_states"] == beats

    def test_battle_state_fields(self, real_adapter, real_combat_player):
        enemy = Slime()
        real_combat_player.combat_list = [enemy]
        real_combat_player.combat_proximity = {enemy: 10}
        real_adapter.awaiting_input = True
        real_adapter.input_type = "target_selection"
        real_adapter.available_options = [
            {"id": CombatantSerializer.stream_id(enemy)}
        ]

        result = real_adapter.get_combat_state()

        _assert_contract(result["battle_state"], BATTLE_STATE_CONTRACT, "battle_state")

    def test_no_combatant_id_in_a_real_payload_carries_a_heap_address(
        self, real_adapter, real_combat_player
    ):
        """Issue #511 moved the wire-id scheme off ``id(combatant)``: heap
        addresses both leaked process layout to the client and were recycled
        onto later-spawned NPCs, silently retargeting stale client-held ids.

        Checked here on a payload built by the whole chain (adapter →
        serializer → handle), which is the only place all three run together;
        the handle's format, stability and the recycling regression are pinned
        once in tests/test_combatant_wire_handles.py rather than restated here.
        """
        enemy = Slime()
        ally = Slime()
        ally.friend = True
        real_combat_player.combat_list = [enemy]
        real_combat_player.combat_list_allies = [real_combat_player, ally]
        real_combat_player.combat_proximity = {enemy: 10, ally: 5}
        real_adapter.awaiting_input = True
        real_adapter.input_type = "move_selection"
        real_adapter.available_options = []

        battle_state = real_adapter.get_combat_state()["battle_state"]

        # `allies` excludes Jean (he ships separately under `player`), so the
        # roster is paired up by name rather than by position — a zip would
        # silently drop whichever side ran short and pass on two thirds of the
        # payload.
        assert len(battle_state["enemies"]) == 1
        assert len(battle_state["allies"]) == 1
        roster = [
            (battle_state["enemies"][0], enemy),
            (battle_state["allies"][0], ally),
            (battle_state["player"], real_combat_player),
        ]
        for entity, combatant in roster:
            assert str(id(combatant)) not in entity["id"], (
                f"{entity['id']!r} leaks {type(combatant).__name__}'s heap address"
            )

    def test_combat_id_is_stable_across_polls_but_changes_between_fights(
        self, real_adapter, real_combat_player
    ):
        """The pan-reset dep is only useful if it holds still during a fight.

        A per-call uuid would make BattlefieldGrid reset the camera on every
        status poll; an absent one (the original bug) means it never resets at
        all. Both are wrong, so pin the actual property.
        """
        with patch("src.api.combat_adapter.CombatStrategist"):
            real_adapter.initialize_combat([Slime()])
        first = real_adapter.get_combat_state()["battle_state"]["combat_id"]

        assert first, "combat_id must be populated once a combat has begun"
        # Same fight, later beat: the id must not move.
        assert real_adapter.get_combat_state()["battle_state"]["combat_id"] == first

        # A reinit (wave transition / reinforcement spawn) is the SAME fight.
        with patch("src.api.combat_adapter.CombatStrategist"):
            real_adapter.initialize_combat([Slime()], reinit=True)
        assert real_adapter.get_combat_state()["battle_state"]["combat_id"] == first

        # A genuinely new combat must mint a new id.
        with patch("src.api.combat_adapter.CombatStrategist"):
            real_adapter.initialize_combat([Slime()])
        assert real_adapter.get_combat_state()["battle_state"]["combat_id"] != first

    def test_fight_identity_and_grid_survive_adapter_replacement(
        self, real_adapter, real_combat_player
    ):
        """Both must live on the player, not the adapter instance.

        GameService.get_combat_status's deferred-level-up resume builds a
        REPLACEMENT ApiCombatAdapter mid-fight (Jean levels up on a killing
        blow, the next fight is deferred until the points are spent, then
        starts through that branch). Anything held as an instance attribute is
        silently lost there.

        For combat_id the symptom is `null` on every poll for the rest of the
        fight. For combat_grid_size it is worse now that map_size actually
        reaches the client: the fresh adapter reverts to the legacy 13x13
        default, and get_dynamic_grid_size never returns 13 — it returns 9 for
        a small fight and 18 for five combatants. At 18 the client would clip
        every combatant past index 12 out of the visible container, i.e. an
        invisible enemy in an active fight.
        """
        with patch("src.api.combat_adapter.CombatStrategist"):
            real_adapter.initialize_combat([Slime(), Slime(), Slime(), Slime()])

        before = real_adapter.get_combat_state()["battle_state"]
        assert before["combat_id"]
        assert before["map_size"] != 13, (
            "fixture should produce a dynamically-sized grid, otherwise this "
            "test cannot distinguish the bug from the default"
        )

        # Exactly what the deferred-level-up branch does: a brand-new adapter
        # over the same player, with no re-initialisation of the fight.
        with patch("src.api.combat_adapter.CombatStrategist"):
            replacement = ApiCombatAdapter(real_combat_player, session_id="s")

        after = replacement.get_combat_state()["battle_state"]
        assert after["combat_id"] == before["combat_id"]
        assert after["map_size"] == before["map_size"]

    def test_check_data_surfaces_when_a_check_move_sets_it(
        self, real_adapter, real_combat_player
    ):
        """CombatCheckDialog reads combat?.check_data — only present when a
        Check move populated it; the adapter must forward it (not drop it)."""
        real_combat_player.combat_adapter_state["check_data"] = {"prompt": "Feel for traps?"}

        result = real_adapter.get_combat_state()

        assert "check_data" in result["battle_state"]
        assert result["battle_state"]["check_data"] == {"prompt": "Feel for traps?"}


# ----------------------------------------------------------------------------
# Move payload: combat.available_options[i] (src.api.combat_adapter
# ApiCombatAdapter._get_available_moves)
# ----------------------------------------------------------------------------
# CombatMovePanel.jsx renders each move card off this shape.
MOVE_CONTRACT = {
    # move.name || move.display_name, via displayNameOf.
    "name": Read("CombatMovePanel.jsx", "move.name"),
    "display_name": Read("CombatMovePanel.jsx", "displayNameOf(move)"),
    "description": Read("CombatMovePanel.jsx", "move.description"),
    "available": Read("CombatMovePanel.jsx", "move.available"),
    # Its *wording* is load-bearing too, not just its presence: the reason line
    # renders through GlossaryText, which only attaches the "what is a beat?"
    # explainer (#507) to words combatGlossary.js recognises. Rewording
    # "Available in 5 beats" would leave this contract green while silently
    # removing the explainer -- tests/test_combat_glossary_contract.py runs the
    # real reason strings against the glossary's own patterns to catch that.
    # The read moved out of the component in the #554 fix: the panel now asks
    # moveAvailability(move) instead of reading move.available/move.reason
    # itself, so the wire field is consumed one layer down. Anchored on the
    # literal dereference rather than on "reason", which would also match the
    # function's own return shape and could therefore never fail.
    "reason": Read("combatMoveStatus.js", "move.reason"),
    "fatigue_cost": Read("CombatMovePanel.jsx", "move.fatigue_cost"),
    # These three moved together into `autoResolvedTargetId`: the panel and
    # LeftPanel each had their own copy of the three-term predicate, and a
    # drift meant the battlefield highlighted one enemy while the click
    # submitted another. Helper-plus-consumer, as with `count`/`quantity`
    # below: the helper read alone would keep passing if both surfaces
    # stopped auto-resolving targets entirely.
    "targeted": (
        Read("combatMoveStatus.js", "move.targeted"),
        Read("LeftPanel.jsx", "autoResolvedTargetId(move)"),
    ),
    "viable_targets": (
        Read("combatMoveStatus.js", "move.viable_targets"),
        Read("CombatMovePanel.jsx", "autoResolvedTargetId(move)"),
    ),
    "requires_target_selection": Read(
        "combatMoveStatus.js", "move.requires_target_selection"
    ),
    # `category` routes the move to a radial button via CATEGORY_GROUPS
    # (utils/categories.js). A category no group claims leaves the move with no
    # button at all — that is how 8 castable moves became unreachable.
    "category": (
        Read("CooldownTray.jsx", "move.category"),
        Read("BattlefieldGrid.jsx", "move.category"),
    ),
    # The commitment bar (how many beats a move locks the player out for,
    # shown BEFORE they commit) — named sub-fields, not the engine's raw
    # stage_beat list/index convention. See MOVE_STAGE_BEATS_CONTRACT below.
    #
    # CombatMovePanel renders the bar but never touches the wire field: the
    # read is in moveCommitment.js's getStageBeats, which the panel calls.
    # The old citation named the panel, which is a component this field could
    # be dropped from without anything here noticing.
    "stage_beats": Read("moveCommitment.js", "move?.stage_beats"),
}

ABORTABLE_MOVE_CONTRACT = {
    # One destructure supplies the whole control:
    #   const { name, beats_left: beatsLeft, beats_invested: invested,
    #           cooldown_beats: cooldown } = abortable;
    # so each anchor is that renaming, not an `abortable.x` expression the
    # file has never contained.
    "name": Read("AbortMoveControl.jsx", "const { name, beats_left"),
    # 'lands in N beats'
    "beats_left": Read("AbortMoveControl.jsx", "beats_left: beatsLeft"),
    # 'forfeits N beats'
    "beats_invested": Read("AbortMoveControl.jsx", "beats_invested: invested"),
    # 'then N beats cooldown'
    "cooldown_beats": Read("AbortMoveControl.jsx", "cooldown_beats: cooldown"),
    "prep_beats": Read(
        "AbortMoveControl.jsx",
        note="no consumer at all: the destructure above takes four fields and "
        "prep_beats is not one of them. Its only appearance anywhere in "
        "frontend/src is the AbortMoveControl.test.jsx fixture. The old "
        "citation claimed the component destructured it; it does not.",
    ),
}


# `getStageBeats(move)` reads `move.stage_beats` into `raw` and then names each
# stage — those four reads are the contract, and they live in the util, not in
# the panel that draws the bar.
MOVE_STAGE_BEATS_CONTRACT = {
    "prep": Read("moveCommitment.js", "prep: safeBeat(raw.prep)"),
    "execute": Read("moveCommitment.js", "execute: safeBeat(raw.execute)"),
    "recoil": Read("moveCommitment.js", "recoil: safeBeat(raw.recoil)"),
    "cooldown": Read("moveCommitment.js", "cooldown: safeBeat(raw.cooldown)"),
}


class TestMoveWireContract:
    def test_available_move_fields(self):
        player = Player()
        player.known_moves = [Attack(player)]
        player.combat_log = []
        player.last_move_summary = ""
        player.combat_beat = 1
        player.combat_list = []
        player.combat_list_allies = [player]
        player.combat_proximity = {}
        player.in_combat = True

        with patch("src.api.combat_adapter.CombatStrategist"):
            adapter = ApiCombatAdapter(player)
            move_payloads = adapter._get_available_moves()

        assert move_payloads, "expected Attack to appear in available moves"
        _assert_contract(move_payloads[0], MOVE_CONTRACT, "_get_available_moves()[0]")
        _assert_contract(
            move_payloads[0]["stage_beats"],
            MOVE_STAGE_BEATS_CONTRACT,
            "_get_available_moves()[0].stage_beats",
        )

    def test_stage_beats_are_the_real_engine_values_not_recomputed(self):
        """Guards the Architecture rule that the engine is the source of
        truth for move timing: the API layer must read Move.stage_beat, never
        hardcode or re-derive it. Attack (a 10-beat commitment) and
        BloodOfMartyrs (101 beats — prep=40, execute=1, recoil=5,
        cooldown=55) are pinned by value so a swapped index or a hardcoded
        constant in the adapter shows up immediately."""
        player = Player()
        attack = Attack(player)
        blood = BloodOfMartyrs(player)
        player.known_moves = [attack, blood]
        player.combat_log = []
        player.last_move_summary = ""
        player.combat_beat = 1
        player.combat_list = []
        player.combat_list_allies = [player]
        player.combat_proximity = {}
        player.in_combat = True

        with patch("src.api.combat_adapter.CombatStrategist"):
            adapter = ApiCombatAdapter(player)
            move_payloads = adapter._get_available_moves()

        by_name = {m["name"]: m for m in move_payloads}

        assert attack.stage_beat == [4, 1, 1, 4]  # pin the fixture's own assumption
        assert by_name["Attack"]["stage_beats"] == {
            "prep": 4,
            "execute": 1,
            "recoil": 1,
            "cooldown": 4,
        }

        assert blood.stage_beat == [40, 1, 5, 55]  # pin the fixture's own assumption
        assert by_name["Blood of Martyrs"]["stage_beats"] == {
            "prep": 40,
            "execute": 1,
            "recoil": 5,
            "cooldown": 55,
        }

    def test_stage_beats_handle_float_and_zero_values(self):
        """stage_beat entries can be floats (e.g. 3.5) and can be 0 — the
        payload must carry both through unchanged rather than truncating or
        substituting a default. Uses Wait rather than Attack: Attack.viable()
        calls evaluate(), which recomputes stage_beat from the player's
        weapon and would silently clobber this test's override; Wait's
        viable() is the unmodified Move base (no recompute)."""
        player = Player()
        move = Wait(player)
        move.stage_beat = [0, 3.5, 0, 12]
        player.known_moves = [move]
        player.combat_log = []
        player.last_move_summary = ""
        player.combat_beat = 1
        player.combat_list = []
        player.combat_list_allies = [player]
        player.combat_proximity = {}
        player.in_combat = True

        with patch("src.api.combat_adapter.CombatStrategist"):
            adapter = ApiCombatAdapter(player)
            move_payloads = adapter._get_available_moves()

        assert move_payloads[0]["stage_beats"] == {
            "prep": 0,
            "execute": 3.5,
            "recoil": 0,
            "cooldown": 12,
        }


# ----------------------------------------------------------------------------
# Combatant shape: combat.player / combat.enemies[i]
# ----------------------------------------------------------------------------
# HeroPanel.jsx reads these off `player` — which during combat IS combat.player
# (LeftPanel.jsx's activePlayer merge) — and StatusEffectsIconPanel/LeftPanel
# read the nested lists.
COMBATANT_CONTRACT = {
    # e.id — matching enemies against last_move_target_id.
    "id": Read("LeftPanel.jsx", "e.id"),
    "hp": Read("HeroPanel.jsx", "player?.hp"),
    "max_hp": Read("HeroPanel.jsx", "player?.max_hp"),
    "fatigue": Read("HeroPanel.jsx", "player?.fatigue"),
    "max_fatigue": Read("HeroPanel.jsx", "player?.max_fatigue"),
    # Both lists are read through EFFECT_GROUPS, which names the field once for
    # the desktop columns and the mobile row alike; the anchor is that name.
    "status_effects": Read("HeroPanel.jsx", "key: 'status_effects'"),
    "passives": Read("HeroPanel.jsx", "key: 'passives'"),
    # e.distance — the canFlee check on combat.enemies.
    "distance": Read("LeftPanel.jsx", "e.distance"),
    # The battlefield map is the other consumer of a serialized combatant. It
    # was reading `position`/`current_move` all along; `distance` is now shown
    # there too (token tooltip, selected-combatant panel, enemies list and the
    # off-screen edge markers), which is what the positional layer is *for*.
    "name": Read("BattlefieldGrid.jsx", "entity.name"),
    # The displaySymbol fallback chain in entitiesToRender.
    "battle_symbol": Read("BattlefieldGrid.jsx", "entity.battle_symbol"),
    # getPos(entity) -> getEntityStyle / fitBox framing.
    "position": Read("BattlefieldGrid.jsx", "entity?.position"),
    # CombatantMarker telegraph + EntityTooltip.
    "current_move": Read("BattlefieldGrid.jsx", "entity.current_move"),
    # Heat meter. This is the RAW FLOAT multiplier applied to Jean's damage
    # by src/moves/_base.py standard_execute_attack.
    #
    # battle_state carries a SECOND, different representation of the same
    # quantity under its own top-level `heat` key -- round(player.heat * 100),
    # set by ApiCombatAdapter.get_combat_state and absent from the per-beat
    # states the adapter snapshots via
    # CombatStateSerializer.serialize_combat_state. Reading that one as a
    # multiplier renders "162.00x"; reading this one is correct. The client has
    # exactly one reader and no `??` chain across the two (see the header
    # comment in frontend/src/utils/heat.js), which is the only reason the
    # duplication is survivable.
    "heat": Read("LeftPanel.jsx", "combat?.player?.heat"),
}

# The in-progress move hanging off a combatant (CombatantSerializer.
# _serialize_active_move). BattlefieldGrid turns this into the *only* readout
# of enemy intent on the map, so a rename here silently blanks the telegraph.
ACTIVE_MOVE_CONTRACT = {
    # displayNameOf's `value.display_name || value.name`.
    "display_name": Read("combatMoveStatus.js", "value.display_name"),
    # categoryColor/categoryGlow (utils/categories.js) keyed off move.category.
    "category": Read("BattlefieldGrid.jsx", "move.category"),
    # isMovePending() suppresses the telegraph for stages 2/3 so a spent
    # combatant stops looking like one winding up; beatsUntilResolve() renders
    # the countdown badge on the token.
    "current_stage": Read("combatMoveStatus.js", "move.current_stage"),
    # beatsUntilResolve's fallback, for stage-less payloads.
    "beats_left": Read("combatMoveStatus.js", "move.beats_left"),
    # The countdown badge renders THIS, not beats_left: the latter is beats
    # left in the current stage, which for a windup move is a much smaller
    # number than the time until the blow actually lands.
    "beats_until_resolve": Read("combatMoveStatus.js", "move.beats_until_resolve"),
    # RangeRingLayer — gradient vs hard ring.
    "falloff": Read("BattlefieldGrid.jsx", "move.falloff"),
    # Threat-line/range-ring feature: who the pending move is aimed at, and
    # how far it reaches. target_id MUST be resolved through
    # CombatantSerializer.stream_id (see _serialize_move_target_id) or the
    # frontend can never match it against a combatant's own `id` — the same
    # drift class this whole file exists to catch.
    "target_id": Read("BattlefieldGrid.jsx", "move.target_id"),  # ThreatLineLayer
    "mvrange": Read("BattlefieldGrid.jsx", "move?.mvrange"),  # RangeRingLayer
    # NOT a frontend read. ai/combat_strategist.py's _estimate_incoming_damage
    # multiplies the enemy's damage stat by this and raises POTENTIALLY LETHAL
    # off the result. Renaming Move._DAMAGE_MULTIPLIER degrades it to the 1.0
    # default rather than failing, so the value is asserted too, below.
    "damage_multiplier": Read(
        "ai/combat_strategist.py", 'get("damage_multiplier"'
    ),
}

# StatusEffectsIconPanel.jsx renders each element of status_effects/passives.
STATE_EFFECT_CONTRACT = {
    "name": Read("StatusEffectsIconPanel.jsx", "effect.name"),
    # getEffectColor(effect.type)
    "type": Read("StatusEffectsIconPanel.jsx", "effect.type"),
    "description": Read("StatusEffectsIconPanel.jsx", "effect.description"),
    # Bug #3: this component used to read `duration_remaining`, which only
    # serialize_state_with_duration (no callers) emits. The live path is
    # serialize_state -> beats_left, read as
    # `effect.beats_left ?? effect.duration_remaining`.
    "beats_left": Read("StatusEffectsIconPanel.jsx", "effect.beats_left"),
    # NOT a frontend read. ai/combat_strategist.py's _format_status_effects
    # renders this as the mechanical half of every status line in the combat
    # prompt — the engine-owned numbers the strategist deliberately stopped
    # hand-copying. It falls back to `description` when empty, so a rename
    # quietly downgrades the prompt instead of failing; the value is asserted
    # below as well.
    "tactical_mechanics": Read(
        "ai/combat_strategist.py", 'get("tactical_mechanics")'
    ),
}

# CombatInputDialog's target_selection cards (combat_adapter._get_available_targets).
TARGET_CONTRACT = {
    "id": Read("CombatInputDialog.jsx", "target.id"),
    "name": Read("CombatInputDialog.jsx", "target.name"),
    "distance": Read("CombatInputDialog.jsx", "target.distance"),
    # target.health.current / target.health.max
    "health": Read("CombatInputDialog.jsx", "const hp = target.health"),
    # Bug #4: hit_chance is an already-integer percentage (see
    # ShootBow.calculate_hit_chance) — CombatInputDialog explicitly does NOT
    # rescale it. If the engine ever starts sending a 0-1 fraction instead,
    # that comment (and this contract) goes stale silently unless something
    # asserts the magnitude, which the dedicated test below does.
    "hit_chance": Read("CombatInputDialog.jsx", "target.hit_chance"),
}


class TestCombatantWireContract:
    def test_player_combatant_fields(self):
        player = Player()
        payload = CombatantSerializer.serialize_combatant(player)
        _assert_contract(payload, COMBATANT_CONTRACT, "serialize_combatant(player)")

    def test_enemy_combatant_fields(self):
        player = Player()
        enemy = Slime()
        payload = CombatantSerializer.serialize_combatant(enemy, reference=player)
        _assert_contract(payload, COMBATANT_CONTRACT, "serialize_combatant(enemy)")

    def test_player_heat_is_a_float_multiplier_at_wire_precision(self):
        """HeatMeter renders this number directly, so its scaling is load-bearing.

        `hit_chance` (bug #4) was this exact failure: two plausible scalings for
        one quantity, and a client that picked the wrong one showed a silently,
        wildly wrong number. Heat has the same hazard — battle_state's own
        `heat` key is round(heat * 100) — so pin the multiplier form here.

        The 2dp rounding matters too: ApiCombatAdapter._update_heat's per-beat
        decay does NOT round the way Player.change_heat does, and the client
        derives its rise/fall indicator from the difference between consecutive
        values of this field.
        """
        player = Player()
        player.change_heat(mult=1.25)
        payload = CombatantSerializer.serialize_combatant(player)
        assert payload["heat"] == pytest.approx(1.25)

        player.heat = 1.6234567891  # a value _update_heat's decay really produces
        assert CombatantSerializer.serialize_combatant(player)["heat"] == 1.62

    def test_enemy_heat_is_neutral_because_nothing_scales_npc_damage(self):
        """Enemies must not render as if they had heat of their own."""
        payload = CombatantSerializer.serialize_combatant(Slime(), reference=Player())
        assert payload["heat"] == 1.0

    @pytest.mark.parametrize(
        "heat", [0.57, 0.58, 1.13, 1.14, 1.15, 1.16, 2.01, 2.26, 1.62, 0.83]
    )
    def test_the_int_percentage_twin_rounds_rather_than_truncates(self, heat):
        """battle_state's int-percentage heat must be exactly 100x the float.

        Binary floats put 68 of the 951 two-decimal heats in [0.50, 10.00]
        just below their exact product, so the adapter's original
        ``int(heat * 100)`` disagreed with the float the client reads for
        roughly 7% of values -- ``int(1.15 * 100)`` is 114, not 115. A single
        hand-picked heat cannot see that; most of the values here are drawn
        from the mismatching set, with a couple of controls.

        Pins the RULE (round) rather than re-deriving the arithmetic: the
        serialized float is the authority, and the percentage must be its
        exact hundredfold.
        """
        player = Player()
        player.heat = heat
        serialized = CombatantSerializer.serialize_combatant(player)["heat"]
        assert round(player.heat * 100) == round(serialized * 100), (
            f"heat {heat}: the percentage twin and the float multiplier "
            "disagree; truncation is how they drift apart"
        )

    def test_battle_state_heat_percentage_agrees_with_the_player_multiplier(
        self, real_adapter, real_combat_player
    ):
        """The two representations must stay 100x apart, or one of them is a lie.

        Nothing forces them to agree — they are set in different files
        (serializers/combat.py vs combat_adapter.py get_combat_state) — so if
        either is ever rescaled independently, the client reading one of them
        starts rendering nonsense with no other test noticing.
        """
        real_combat_player.heat = 1.62
        battle_state = real_adapter.get_combat_state()["battle_state"]
        assert battle_state["player"]["heat"] == pytest.approx(1.62)
        assert battle_state["heat"] == 162

    def test_active_move_fields_on_a_real_move_in_progress(self):
        """A real move mid-cast, through the real serializer, so the fields the
        battlefield telegraph reads can't be renamed out from under it."""
        player = Player()
        move = ShootBow(player)
        move.current_stage = 0
        move.beats_left = 2
        player.current_move = move

        payload = CombatantSerializer.serialize_combatant(player)
        assert payload["current_move"], "expected the in-progress move to serialize"
        _assert_contract(
            payload["current_move"], ACTIVE_MOVE_CONTRACT, "combatant.current_move"
        )

    def test_active_move_target_id_matches_the_target_combatants_own_serialized_id(self):
        """The whole point of `target_id`: it must resolve to exactly the same
        wire id `serialize_combatant` gives the target itself, or the frontend
        can never look the target up in `combat.enemies`/`combat.allies` to
        draw the threat line — the "id schemes don't match" failure mode
        CLAUDE.md calls this repo's dominant bug class.

        Both sides are computed independently through the real serializer
        entry points (never hand-built) so a future change to either the
        active-move id logic or `stream_id` itself cannot silently drift them
        apart without breaking this test.
        """
        player = Player()
        player.known_moves = []
        player.combat_log = []
        player.last_move_summary = ""
        player.combat_beat = 1
        player.in_combat = True
        enemy = Slime()
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        player.combat_proximity = {enemy: 10}

        move = ShootBow(player)
        move.target = enemy
        move.current_stage = 0
        move.beats_left = 2
        player.current_move = move

        player_payload = CombatantSerializer.serialize_combatant(player)
        enemy_payload = CombatantSerializer.serialize_combatant(enemy, reference=player)

        assert player_payload["current_move"], "expected the in-progress move to serialize"
        assert player_payload["current_move"]["target_id"] == enemy_payload["id"], (
            "current_move.target_id must exactly match the target's own "
            "serialize_combatant() id, or BattlefieldGrid cannot resolve who "
            f"the move is aimed at. Got target_id={player_payload['current_move']['target_id']!r} "
            f"vs enemy id={enemy_payload['id']!r}"
        )

    def test_active_move_range_prefers_the_engines_effective_max(self):
        """`mvrange.max` must be the reach the engine actually uses, not the
        static tuple bound.

        Without this the "prefer get_effective_range_max" branch could quietly
        never fire — the base Move returns None, so a wrong argument or a
        swallowed exception would silently fall back to `mvrange[1]` and the
        range ring would draw the wrong radius with nothing failing. The
        expected value is computed by calling the move's own method rather
        than hardcoding a number, so the engine stays the source of truth.
        """
        player = Player()
        player.eq_weapon = Shortbow()
        move = ShootBow(player)
        move.current_stage = 0
        move.beats_left = 1
        player.current_move = move

        engine_effective_max = move.get_effective_range_max(player)
        assert engine_effective_max is not None, (
            "fixture no longer exercises the override — pick a move/weapon "
            "whose get_effective_range_max returns a value"
        )
        assert engine_effective_max != move.mvrange[1], (
            "fixture is degenerate: the effective max coincides with the "
            "static bound, so this test could pass either way"
        )

        payload = CombatantSerializer.serialize_combatant(player)
        assert payload["current_move"]["mvrange"] == {
            "min": int(move.mvrange[0]),
            "max": int(engine_effective_max),
        }

    def test_active_move_falloff_predicts_the_engines_own_hit_chance(self):
        """The falloff curve must describe the *real* accuracy decay.

        The battlefield draws a gradient from `start`/`per_ft` to show a
        decaying move dissolving toward a vanishing hit chance. If those two
        numbers don't match what `calculate_hit_chance` actually subtracts,
        the gradient is a confident-looking lie — worse than drawing nothing.

        So this doesn't just check the fields exist: it takes the serialized
        pair, predicts the hit chance at a distance past `start`, and compares
        against the engine's own calculation at that distance.
        """
        player = Player()
        player.eq_weapon = Shortbow()
        enemy = Slime()
        player.combat_list = [enemy]
        player.combat_list_allies = [player]

        move = ShootBow(player)
        move.current_stage = 0
        move.beats_left = 1
        player.current_move = move

        payload = CombatantSerializer.serialize_combatant(player)
        falloff = payload["current_move"]["falloff"]
        assert falloff, "a bow shot decays with range — expected a falloff curve"

        start = falloff["start"]
        per_ft = falloff["per_ft"]
        assert per_ft > 0

        # Baseline at the plateau edge, then a point well beyond it. Both come
        # from the engine; only the *difference* between them is predicted.
        player.combat_proximity = {enemy: int(start)}
        baseline = move.calculate_hit_chance(enemy)

        far = int(start) + 40
        player.combat_proximity = {enemy: far}
        actual = move.calculate_hit_chance(enemy)

        predicted = baseline - (far - start) * per_ft
        assert abs(actual - predicted) <= 1, (
            f"serialized falloff (start={start}, per_ft={per_ft}) predicts "
            f"{predicted:.2f}% at {far} ft but the engine computes {actual}%. "
            "The battlefield gradient would misrepresent real hit chance."
        )
        assert actual < baseline, (
            "fixture is degenerate: accuracy did not actually drop past "
            "`start`, so this test could pass with a zero falloff"
        )

    def test_falloff_still_predicts_hit_chance_once_the_arrow_is_chosen(self):
        """Same contract, but after `prep` has folded in the real ammunition.

        ShootBow picks its arrow at the end of the prep stage, and the arrow
        carries a `range_decay_modifier` (0.8-1.4). So the decay a bow reports
        while aiming is the weapon's bare rate, and the decay it reports once
        nocked is that rate scaled by the arrow. The test above only ever sees
        the first of those, which would let an arrow-scaling regression pass:
        both sides of its comparison read the same unrefreshed attribute.
        """
        player = Player()
        player.eq_weapon = Shortbow()
        arrow = IronArrow()
        arrow.count = 10
        player.inventory.append(arrow)
        enemy = Slime()
        player.combat_list = [enemy]
        player.combat_list_allies = [player]

        move = ShootBow(player)
        move.current_stage = 0
        move.beats_left = 1
        player.current_move = move
        move.prep(player)

        falloff = CombatantSerializer.serialize_combatant(player)["current_move"]["falloff"]
        start, per_ft = falloff["start"], falloff["per_ft"]

        # The arrow really did move the rate — otherwise this test is just a
        # second copy of the one above.
        assert per_ft == pytest.approx(
            player.eq_weapon.range_decay * arrow.range_decay_modifier
        )
        assert per_ft != pytest.approx(player.eq_weapon.range_decay)

        player.combat_proximity = {enemy: int(start)}
        baseline = move.calculate_hit_chance(enemy)
        far = int(start) + 40
        player.combat_proximity = {enemy: far}
        actual = move.calculate_hit_chance(enemy)

        predicted = baseline - (far - start) * per_ft
        assert abs(actual - predicted) <= 1, (
            f"serialized falloff (start={start}, per_ft={per_ft}) predicts "
            f"{predicted:.2f}% at {far} ft but the engine computes {actual}%."
        )
        assert actual < baseline

    def test_the_aim_preview_describes_the_shot_that_will_be_taken(self):
        """The falloff on the wire must not change when the shot resolves.

        `prep` runs at the *last* beat of a 10-beat aim, and it used to be the
        only place the arrow was chosen. So for the ten beats the client renders
        a range gradient -- it renders only while a move is pending -- the wire
        carried the `__init__` placeholder: 0.05 decay for a shot that resolved
        at 2.1, and a 97% hit chance for one that landed at 45%. The player
        aimed at a near-certain shot and got a coin flip.

        This asserts the two agree across the whole aim, which is the property
        the split between `_select_arrow` and `prep`'s side effects exists for.
        """
        player = Player()
        player.eq_weapon = Shortbow()
        arrow = IronArrow()
        arrow.count = 10
        player.inventory.append(arrow)
        enemy = Slime()
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        player.combat_proximity = {enemy: 45}

        move = ShootBow(player)
        move.user = player
        move.target = enemy
        player.current_move = move
        move.cast()

        def snapshot():
            payload = CombatantSerializer.serialize_combatant(player)["current_move"]
            return payload["falloff"], payload["mvrange"], move.calculate_hit_chance(enemy)

        while_aiming = []
        with capture_narration():
            while move.current_stage == 0:
                while_aiming.append(snapshot())
                move.advance(player)
            at_execute = snapshot()

        assert len(while_aiming) > 1, "fixture is degenerate: no aim to preview"
        assert while_aiming[0] == at_execute, (
            f"the aim showed {while_aiming[0]} but the shot resolved as "
            f"{at_execute} -- the preview is describing a different arrow"
        )
        assert all(beat == at_execute for beat in while_aiming), (
            "the preview changed part-way through the aim"
        )
        # An iron arrow really does move the numbers, so this is not vacuous.
        assert while_aiming[0][0]["per_ft"] == pytest.approx(
            player.eq_weapon.range_decay * arrow.range_decay_modifier
        )

    def test_no_falloff_for_a_move_whose_accuracy_does_not_decay(self):
        """Melee moves carry no decay, and must report none — the client uses
        null here to pick a hard range ring over a dissolving gradient."""
        player = Player()
        move = PowerStrike(player)
        move.current_stage = 0
        move.beats_left = 1
        player.current_move = move

        payload = CombatantSerializer.serialize_combatant(player)
        assert payload["current_move"]["falloff"] is None

    def test_active_move_range_computes_reach_from_the_moves_own_user(self):
        """An NPC's reach must come from the NPC's weapon, not the player's.

        `_serialize_move_range` passes `move.user` into the override; passing a
        fixed player reference (as combat_adapter does for its own player-only
        target list) would report Jean's bow range for a Slime's move.
        """
        player = Player()
        player.eq_weapon = Shortbow()
        enemy = Slime()
        enemy.eq_weapon = None  # a Slime has no weapon slot at all

        enemy_move = ShootBow(enemy)  # enemy has no bow equipped
        enemy_move.current_stage = 0
        enemy_move.beats_left = 1
        enemy.current_move = enemy_move

        payload = CombatantSerializer.serialize_combatant(enemy, reference=player)
        # No weapon on the Slime => the override returns None => the static
        # bound stands. If the player were used as the reference instead, the
        # Shortbow's much longer effective reach would leak in here.
        assert payload["current_move"]["mvrange"]["max"] == int(enemy_move.mvrange[1])

    def test_damage_multiplier_carries_the_moves_own_factor(self):
        """Presence is not enough: 1.0 is a valid multiplier AND the default.

        A real heavy hitter mid-cast, through the real serializer. If
        ``Move._DAMAGE_MULTIPLIER`` is ever renamed, ``getattr`` falls through
        to 1.0 and the Tactical Advisor silently estimates the game's biggest
        telegraphed attack at its user's bare damage — the exact bug the
        attribute was added to fix, restored without a single failing test.
        """
        from src.moves import SlimeVolley

        player = Player()
        enemy = Slime()
        enemy.target = player
        move = SlimeVolley(enemy)
        move.current_stage = 0
        move.beats_left = 2
        enemy.current_move = move

        payload = CombatantSerializer.serialize_combatant(enemy, reference=player)
        wire = payload["current_move"]["damage_multiplier"]
        assert wire == pytest.approx(SlimeVolley._DAMAGE_MULTIPLIER), (
            f"wire damage_multiplier is {wire} but SlimeVolley declares "
            f"{SlimeVolley._DAMAGE_MULTIPLIER}"
        )
        assert wire != pytest.approx(1.0), (
            "fixture is degenerate: this move must declare a NON-default "
            "multiplier or the test cannot distinguish carried from defaulted"
        )

    def test_tactical_mechanics_carries_the_states_own_summary(self):
        """Same shape of guard for the status half of the combat prompt.

        ``_format_status_effects`` falls back to ``description`` when this is
        empty, so a rename costs the model the engine's real numbers and
        substitutes player-facing prose — a downgrade with no symptom.
        """
        player = Player()
        state = states.Poisoned(player)
        payload = StateEffectSerializer.serialize_state(state)

        assert payload["tactical_mechanics"] == state.tactical_mechanics
        assert payload["tactical_mechanics"], (
            "Poisoned declares a tactical summary; an empty wire value means "
            "the serializer is no longer reading it"
        )
        # The interval is the part the strategist's own table used to get wrong.
        assert f"every {state.execute_on} beats" in payload["tactical_mechanics"]

    def test_status_effect_fields_on_a_real_state(self):
        player = Player()
        state = states.Poisoned(player)
        payload = StateEffectSerializer.serialize_state(state)
        _assert_contract(payload, STATE_EFFECT_CONTRACT, "StateEffectSerializer.serialize_state")

    def test_status_effects_list_on_a_real_combatant_uses_the_same_shape(self):
        """Exercise the actual call path HeroPanel's data comes through
        (CombatantSerializer._serialize_status_effects), not just the
        serializer function in isolation."""
        player = Player()
        player.states = [states.Poisoned(player)]
        payload = CombatantSerializer.serialize_combatant(player)
        assert payload["status_effects"], "expected at least one serialized state"
        _assert_contract(
            payload["status_effects"][0], STATE_EFFECT_CONTRACT, "combatant.status_effects[0]"
        )

    def test_target_selection_fields(self):
        """A real ranged move against a real enemy in range, through the real
        adapter method that builds CombatInputDialog's target cards."""
        player = Player()
        player.known_moves = []
        player.combat_log = []
        player.last_move_summary = ""
        player.combat_beat = 1
        player.in_combat = True
        enemy = Slime()
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        player.combat_proximity = {enemy: 10}  # inside ShootBow's (6, 50) range

        with patch("src.api.combat_adapter.CombatStrategist"):
            adapter = ApiCombatAdapter(player)
            move = ShootBow(player)
            targets = adapter._get_available_targets(move)

        assert targets, "expected the in-range Slime to produce a target entry"
        _assert_contract(targets[0], TARGET_CONTRACT, "_get_available_targets()[0]")
        _assert_contract(
            targets[0]["health"], {"current": "...", "max": "..."}, "target.health"
        )

    def test_hit_chance_is_an_integer_percentage_not_a_0_1_fraction(self):
        """Guards bug #4 directly: CombatInputDialog renders hit_chance as-is
        (Math.round(target.hit_chance) + '%'). If the engine ever switched to
        emitting a 0-1 fraction, every real value would collapse to 0%-1%
        except the 100% case — this pins the magnitude, not just the name."""
        player = Player()
        player.known_moves = []
        player.combat_log = []
        player.last_move_summary = ""
        player.combat_beat = 1
        player.in_combat = True
        enemy = Slime()
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        player.combat_proximity = {enemy: 10}

        with patch("src.api.combat_adapter.CombatStrategist"):
            adapter = ApiCombatAdapter(player)
            move = ShootBow(player)
            targets = adapter._get_available_targets(move)

        hit_chance = targets[0]["hit_chance"]
        # calculate_hit_chance() clamps to [2, 100] before the shared
        # facing/HauntingPresence modifiers (which can push it slightly
        # outside that band) — see the identical comment in
        # CombatInputDialog.jsx. A 0-1 fraction would fail this floor.
        assert hit_chance > 1, (
            f"hit_chance={hit_chance!r} looks like a 0-1 fraction, not the integer "
            "percentage CombatInputDialog.jsx renders unscaled"
        )

    def test_hit_chance_is_populated_for_a_non_shootbow_move(self):
        """Before Move.preview_hit_chance (src/moves/_base.py), hit_chance was
        gated on `move.verbose_targeting and hasattr(move, "calculate_hit_chance")`
        -- true for ShootBow only, so every other targeted move's target card
        silently lacked an accuracy estimate (33 of 34 targeted moves). This
        pins PowerStrike, one of those 33, as a regression guard: revert the
        adapter's preview_hit_chance wiring and this fails while the
        ShootBow-only test above keeps passing, since that one never exercised
        the gap."""
        player = Player()
        player.known_moves = []
        player.combat_log = []
        player.last_move_summary = ""
        player.combat_beat = 1
        player.in_combat = True
        player.eq_weapon = Mace()
        enemy = Slime()
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        player.combat_proximity = {enemy: 3}  # inside PowerStrike's (0, 5) range
        enemy.combat_proximity = {player: 3}

        with patch("src.api.combat_adapter.CombatStrategist"):
            adapter = ApiCombatAdapter(player)
            move = PowerStrike(player)
            move.target = enemy
            targets = adapter._get_available_targets(move)

        assert targets, "expected the in-range Slime to produce a target entry"
        assert "hit_chance" in targets[0], (
            "PowerStrike (a non-ShootBow, non-verbose_targeting move) should "
            "now expose a preview hit chance via Move.preview_hit_chance"
        )
        assert targets[0]["hit_chance"] == move.preview_hit_chance(enemy)


# ============================================================================
# Player payload
# ============================================================================
# usePlayer() (frontend/src/hooks/useApi.js) builds `player` by spreading
# `data.status` (get_player_status) then `data.stats` (get_player_stats) then
# `data.skills` (get_player_skills) — later keys win on overlap. Fields below
# are cited to the component that reads them.

# HeroPanel guards every read with `?.`; StatsPanel does not — so the same
# field has a different literal in each consumer, and both are cited.
PLAYER_STATUS_CONTRACT = {
    "hp": (Read("HeroPanel.jsx", "player?.hp"), Read("StatsPanel.jsx", "player.hp")),
    "max_hp": (
        Read("HeroPanel.jsx", "player?.max_hp"),
        Read("StatsPanel.jsx", "player.max_hp"),
    ),
    "fatigue": (
        Read("HeroPanel.jsx", "player?.fatigue"),
        Read("StatsPanel.jsx", "player.fatigue"),
    ),
    "max_fatigue": (
        Read("HeroPanel.jsx", "player?.max_fatigue"),
        Read("StatsPanel.jsx", "player.max_fatigue"),
    ),
    "level": Read("StatsPanel.jsx", "player.level"),
    "exp": Read("StatsPanel.jsx", "player.exp"),
    "max_exp": Read("StatsPanel.jsx", "player.max_exp"),
}

PLAYER_STATS_CONTRACT = {
    "protection": Read("StatsPanel.jsx", "player.protection"),
    "attack_damage_min": Read("StatsPanel.jsx", "player.attack_damage_min"),
    "attack_damage_max": Read("StatsPanel.jsx", "player.attack_damage_max"),
    "hit_accuracy": Read("StatsPanel.jsx", "player.hit_accuracy"),
    "evasion_chance": Read("StatsPanel.jsx", "player.evasion_chance"),
    "resistance": Read("StatsPanel.jsx", "player.resistance"),
    "states": Read("StatsPanel.jsx", "player.states"),
    # Bug #2: ShopDialog used to read `weight_tolerance` (the engine-side
    # attribute name) off the player payload. Neither get_player_status nor
    # get_player_stats ever emitted that key — the real keys are below
    # (see also itemUtils.js's docstring on WEIGHT_UNIT).
    "weight_current": Read("ShopDialog.jsx", "player?.weight_current"),
    "max_weight": Read("ShopDialog.jsx", "player?.max_weight"),
    # fallback for max_weight
    "carrying_capacity": Read("ShopDialog.jsx", "player?.carrying_capacity"),
}

# Each element of player.states — note this is a *different* shape from the
# combat status_effects/beats_left contract above: get_player_stats's states
# list is a plain {name, steps_left} pair, not a
# StateEffectSerializer.serialize_state() dict.
PLAYER_STATE_ITEM_CONTRACT = {
    "name": Read("StatsPanel.jsx", "state.name"),
    "steps_left": Read("StatsPanel.jsx", "state.steps_left"),
}


class TestPlayerWireContract:
    def test_get_player_status_fields(self):
        player = Player()
        gs = GameService()
        payload = gs.get_player_status(player)
        _assert_contract(payload, PLAYER_STATUS_CONTRACT, "get_player_status()")

    def test_get_player_stats_fields(self):
        player = Player()
        gs = GameService()
        payload = gs.get_player_stats(player)
        _assert_contract(payload, PLAYER_STATS_CONTRACT, "get_player_stats()")

    def test_get_player_stats_state_item_fields(self):
        """StatsPanel indexes into player.states, so an empty list would hide
        a field-name regression on the per-state shape — force a real active
        state onto the player first."""
        player = Player()
        player.states = [states.Poisoned(player)]
        gs = GameService()
        payload = gs.get_player_stats(player)
        assert payload["states"], "expected the Poisoned state to be serialized"
        _assert_contract(payload["states"][0], PLAYER_STATE_ITEM_CONTRACT, "player.states[0]")


# ============================================================================
# Journal payload (issue #538)
# ============================================================================
# JournalDialog.jsx reads `response?.data?.journal` (GameService.get_journal ->
# Journal.to_dict) and then indexes into its three lists. The per-item shapes
# get their own contracts because an empty list would hide a rename on the
# fields the rows actually read.

JOURNAL_CONTRACT = {
    "objectives": Read("JournalDialog.jsx", "journal?.objectives"),
    "completed": Read("JournalDialog.jsx", "journal?.completed"),
    "log": Read("JournalDialog.jsx", "journal?.log"),
}

JOURNAL_OBJECTIVE_CONTRACT = {
    "key": Read("JournalDialog.jsx", "key={objective.key}"),
    "text": Read("JournalDialog.jsx", "{objective.text}"),
}

JOURNAL_SCENE_CONTRACT = {
    "title": Read("JournalDialog.jsx", "String(scene.title || '').toUpperCase()"),
    "lines": Read("JournalDialog.jsx", "(scene.lines || []).map"),
}

JOURNAL_LINE_CONTRACT = {
    "speaker": Read("JournalDialog.jsx", "{line.speaker && ("),
    "text": Read("JournalDialog.jsx", "{line.text}"),
}


class TestJournalWireContract:
    def _journal_payload(self):
        """A journal with one of everything, produced by the real engine path.

        Objectives and scenes are written through the module-level helpers the
        story files call, and read back through the service method the route
        calls -- so a rename anywhere along that chain fails here.
        """
        player = Player()
        player.universe = Universe(player)
        journal.set_objective(player, "cross_river", "Cross the river.", chapter=3)
        journal.set_objective(player, "done_one", "Already handled.", chapter=3)
        journal.complete_objective(player, "done_one")
        GameService()._record_scene(
            player,
            "Jean stopped at the edge.",
            [
                {"text": "Jean stopped at the edge.", "in_conversation": False},
                {"text": "Tents.", "speaker": "Jean", "in_conversation": True},
            ],
        )
        return GameService().get_journal(player)

    def test_journal_top_level_fields(self):
        _assert_contract(self._journal_payload(), JOURNAL_CONTRACT, "get_journal()")

    def test_journal_objective_fields(self):
        payload = self._journal_payload()
        assert payload["objectives"], "expected an active objective to serialize"
        assert payload["completed"], "expected a completed objective to serialize"
        _assert_contract(
            payload["objectives"][0], JOURNAL_OBJECTIVE_CONTRACT, "journal.objectives[0]"
        )
        _assert_contract(
            payload["completed"][0], JOURNAL_OBJECTIVE_CONTRACT, "journal.completed[0]"
        )

    def test_journal_scene_and_line_fields(self):
        payload = self._journal_payload()
        assert payload["log"], "expected the recorded scene to serialize"
        scene = payload["log"][0]
        _assert_contract(scene, JOURNAL_SCENE_CONTRACT, "journal.log[0]")
        _assert_contract(scene["lines"][0], JOURNAL_LINE_CONTRACT, "journal.log[0].lines[0]")


# ============================================================================
# Shop payload
# ============================================================================
# ShopDialog.jsx reads `shopState.*` (GameService.shop_buy/sell/get_shop_state
# -> ShopSerializer.serialize_state) and item fields off both the buy list
# (stock + buyback_items) and the sell list (serialize_player_sellable).

SHOP_STATE_CONTRACT = {
    "shop_name": Read("ShopDialog.jsx", "shopState?.shop_name"),
    "sell_modifier": Read("ShopDialog.jsx", "shopState?.sell_modifier"),
    "stock": Read("ShopDialog.jsx", "shopState.stock"),
    "buyback_items": Read("ShopDialog.jsx", "shopState.buyback_items"),
    "merchant_gold": Read("ShopDialog.jsx", "shopState?.merchant_gold"),
    "player_gold": Read("ShopDialog.jsx", "shopState?.player_gold"),
    "player_weight_current": Read(
        "ShopDialog.jsx", "shopState?.player_weight_current"
    ),
    "player_weight_max": Read("ShopDialog.jsx", "shopState?.player_weight_max"),
}

# Fields read off a buy-tab item (stock or buyback_items — both flow through
# `allBuyItems` in ShopDialog.jsx and are treated identically).
SHOP_BUY_ITEM_CONTRACT = {
    # list.find(i => i.id === selectedId)
    "id": Read("ShopDialog.jsx", "i.id === selectedId"),
    # The read moved behind stackDisplayName, which strips the stack count the
    # engine bakes into `name` (#565). Still a read of the `name` wire field --
    # anchored on the call, which is the literal the file now contains.
    "name": Read("ShopDialog.jsx", "stackDisplayName(selectedItem)"),
    "price": Read("ShopDialog.jsx", "selectedItem.price"),
    "weight": Read("ShopDialog.jsx", "selectedItem.weight"),
    # buyback effectiveQty
    "count": Read("ShopDialog.jsx", "selectedItem.count"),
    "is_buyback": Read("ShopDialog.jsx", "selectedItem?.is_buyback"),
}

# Fields read off a sell-tab item (ShopSerializer.serialize_player_sellable).
SHOP_SELL_ITEM_CONTRACT = {
    "id": Read("ShopDialog.jsx", "i.id === selectedId"),
    # The read moved behind stackDisplayName, which strips the stack count the
    # engine bakes into `name` (#565). Still a read of the `name` wire field --
    # anchored on the call, which is the literal the file now contains.
    "name": Read("ShopDialog.jsx", "stackDisplayName(selectedItem)"),
    "offer": Read("ShopDialog.jsx", "selectedItem.offer"),
    "weight": Read("ShopDialog.jsx", "selectedItem.weight"),
    # the sell quantity picker's ceiling
    "count": Read("ShopDialog.jsx", "const available = selectedItem.count"),
}


class TestShopWireContract:
    def test_shop_state_and_stock_item_fields(self):
        merchant = Merchant(
            name="Tester", description="desc", damage=1, aggro=False,
            exp_award=0, stock_count=0,
        )
        merchant.inventory = [Restorative(count=2, merchandise=True)]
        player = Player()
        player.inventory = []

        shop_state = ShopSerializer.serialize_state(merchant, player, current_game_tick=0)

        _assert_contract(shop_state, SHOP_STATE_CONTRACT, "ShopSerializer.serialize_state()")
        assert shop_state["stock"], "expected the merchandise Restorative in stock"
        _assert_contract(shop_state["stock"][0], SHOP_BUY_ITEM_CONTRACT, "shop_state.stock[0]")

    def test_sell_inventory_item_fields(self):
        player = Player()
        player.inventory = [Restorative(merchandise=False)]

        sellable = ShopSerializer.serialize_player_sellable(player, 0.5)

        assert sellable, "expected the non-merchandise Restorative to be sellable"
        _assert_contract(sellable[0], SHOP_SELL_ITEM_CONTRACT, "serialize_player_sellable()[0]")

    def test_buyback_item_fields_via_a_real_shop_sell_call(self):
        """Exercises the real GameService.shop_sell path end-to-end (not just
        the serializer helper) so the buyback ledger's real key names
        (buyback_price -> "price", etc.) are what's actually asserted.

        _find_merchant is monkeypatched to skip the universe/tile lookup
        (tile placement is not part of the wire contract under test) — the
        same pattern tests/test_merchandise_system.py uses.
        """
        merchant = Merchant(
            name="Tester", description="desc", damage=1, aggro=False,
            exp_award=0, stock_count=0,
        )
        merchant.update_goods()  # seeds merchant.inventory with Gold to pay out

        player = Player()
        player.universe = type("U", (), {"game_tick": 0})()
        item = Restorative()
        item.value = 10
        player.inventory = [item]

        gs = GameService()
        gs._find_merchant = lambda p, nid: merchant

        result = gs.shop_sell(player, "npc1", wire_handle(item), 1)

        assert result["success"], result.get("error")
        buyback_items = result["shop_state"]["buyback_items"]
        assert buyback_items, "expected the sold item to land in the buyback ledger"
        _assert_contract(buyback_items[0], SHOP_BUY_ITEM_CONTRACT, "buyback_items[0]")


# ============================================================================
# Saves payload
# ============================================================================
# MainMenuPage.jsx's fetchCloudSaves() spreads `response.data.saves` (i.e.
# GameService.list_saves(), via GET /saves) straight into `saveList` rows —
# there is no whitelist/transform step like transformCombatData's, so every
# field a component reads off `save.*` must come from list_saves() itself.
#
# Scope: cloud rows only, and now the only kind there is. Issue #489 retired
# the write-only local-autosave blob (`hov_local_autosave`, see #487) that
# MainMenuPage used to merge in as a synthetic, display-only row with its own
# client-minted `isLocal`/`timestampMs` fields never emitted by the server.
SAVES_ROW_CONTRACT = {
    # row key, load/delete target
    "id": Read("MainMenuPage.jsx", "save.id"),
    "is_autosave": Read("MainMenuPage.jsx", "save.is_autosave"),
    # Each two-consumer entry below is rendered by the page but the field is
    # read one level down, in a localSave.js formatter — cite both, formatter
    # first, or a rename in localSave.js goes unnoticed here while
    # MainMenuPage still "reads" a save field it never dereferences.
    "name": (
        Read("localSave.js", "row?.name"),
        Read("MainMenuPage.jsx", "saveDisplayName(save)"),
    ),
    "level": (
        Read("localSave.js", "row?.level"),
        Read("MainMenuPage.jsx", "saveSummaryParts(save)"),
    ),
    "map_name": (
        Read("localSave.js", "row?.map_name"),
        Read("MainMenuPage.jsx", "saveSummaryParts(save)"),
    ),
    "room_title": (
        Read("localSave.js", "row?.room_title"),
        Read("MainMenuPage.jsx", "saveSummaryParts(save)"),
    ),
    "timestamp": (
        Read("localSave.js", "row.timestamp"),
        Read("MainMenuPage.jsx", "formatSaveTimestamp(save)"),
    ),
    # This is the field the "Continue" button's recency sort now keys on
    # (localSave.js saveRowClockValue: row?.timestamp_ms ?? row?.timestamp,
    # consumed by compareSavesByRecency, which fetchSavesNewestFirst sorts
    # MainMenuPage's list with). It was
    # added alongside the display `timestamp`
    # specifically because `timestamp`'s embedded timezone abbreviation (e.g.
    # "CET") is unparseable by Date.parse for most non-US zones — losing this
    # field silently regresses "Continue" back to that timezone bug.
    "timestamp_ms": Read("localSave.js", "row?.timestamp_ms"),
}


class TestSavesWireContract:
    @pytest.mark.asyncio
    async def test_list_saves_row_fields(self):
        """A real GameService.list_saves() call, with only the DB layer
        mocked (established pattern: tests/test_game_service_tier5_coverage.py
        ::TestListSaves patches src.api.db.db the same way) — the parsing/
        key-naming logic that actually builds the row dict is exercised for
        real, not re-encoded by hand in a fixture."""
        db_mock = AsyncMock()
        result = MagicMock()
        result.rows = [
            ["save1", "MySave", "2026-01-01 12:00:00", True, 5, "Dark Grotto", "EntryHall", 300],
        ]
        db_mock.execute.return_value = result

        gs = GameService()
        with patch("src.api.db.db", db_mock):
            saves = await gs.list_saves("user123", timezone="America/New_York")

        assert saves, "expected list_saves to return the mocked row"
        _assert_contract(saves[0], SAVES_ROW_CONTRACT, "list_saves()[0]")


# =====================================================================
# Room / location payload
# ============================================================================
# useApi.js's transformLocationData(response.data.room) becomes the client-side
# `location` object. It spreads `...room` and then normalises exits/items/npcs/
# objects into fresh array references, so every other key rides through
# untouched — which is exactly why a rename here is silent.

# ----------------------------------------------------------------------------
# The /world/interact response (GameService.interact_with_target). This is a
# TOP-LEVEL response body, not a serializer output, and it is read straight off
# the axios `data` by useWorldInteract — no whitelist in between, which is why
# a rename here reaches the client silently rather than being dropped.
INTERACT_RESPONSE_CONTRACT = {
    # `if (data?.beta_end) setShowBetaEndDialog(true)` — the end-of-beta
    # dialog for the Ferry Landing (#552). Optional-chained on both sides, so
    # a rename or a drop shows as "the demo never ends", with nothing thrown.
    "beta_end": Read("GamePage.jsx", "data?.beta_end"),
    # The interaction moved the player, so the panel closes and the room is
    # re-fetched rather than patched.
    "teleported": Read("useWorldInteract.js", "data.teleported"),
    # Patched onto the selected target so "open" appears after "unlock"
    # without a re-select round trip.
    "object_state": Read("useWorldInteract.js", "data.object_state"),
    "events_triggered": Read("useWorldInteract.js", "data.events_triggered"),
    "message": Read("useWorldInteract.js", "data.message"),
    "success": Read("useWorldInteract.js", "data.success"),
}


ROOM_CONTRACT = {
    # MapGrid positions the grid on them; GamePage builds its tile cache key
    # `${location.map_name}:${location.x},${location.y}` from them.
    "x": (Read("MapGrid.jsx", "location.x"), Read("GamePage.jsx", "location.x")),
    "y": (Read("MapGrid.jsx", "location.y"), Read("GamePage.jsx", "location.y")),
    # location.name || 'Current Location'
    "name": Read("CollapsibleRoomDescription.jsx", "location.name"),
    # grid title + tile key
    "map_name": Read("MapGrid.jsx", "location.map_name"),
    "description": Read("RoomContents.jsx", "location.description"),
    # transformLocationData normalises room.exits -> [direction]
    "exits": Read("useApi.js", "room.exits"),
    "items": Read("useApi.js", "room.items"),
    "npcs": Read("useApi.js", "room.npcs"),
    "objects": Read("useApi.js", "room.objects"),
    # const track = location?.bgm || 'adventure'
    "bgm": Read("GamePage.jsx", "location?.bgm"),
}

# Room items flow through ItemSerializer.serialize_list -> RoomContents /
# InteractPanel target cards.
ROOM_ITEM_CONTRACT = {
    "id": (
        Read("RoomContents.jsx", "id: item.id"),
        Read("InteractPanel.jsx", "takeOne(item.id"),
    ),
    "name": Read("RoomContents.jsx", "item.name"),
    # item.announce || `There is a ${item.name} here.`
    "announce": Read("RoomContents.jsx", "item.announce"),
    # The read moved behind `stackSize`, which resolves `count ?? quantity`
    # once so no call site re-picks the spelling:
    #   stackSize = (item) => Number(item?.count ?? item?.quantity ?? 1)
    # Anchored on the HELPER *and* on a consumer's call, deliberately. The
    # helper alone would attest only that the serializer emits the key -- it
    # would keep passing if every list stopped rendering counts entirely,
    # which is exactly the regression this entry exists to catch.
    "count": (
        Read("utils/stackName.js", "item?.count"),
        Read("InteractPanel.jsx", "stackSize(selectedTarget)"),
    ),
    # allTargets.filter(t => !t.hidden)
    "hidden": Read("InteractPanel.jsx", "t.hidden"),
    # selectedTarget.keywords.length > 0
    "keywords": Read("InteractPanel.jsx", "selectedTarget.keywords"),
}

# Room NPCs flow through NPCSerializer.serialize_list.
ROOM_NPC_CONTRACT = {
    # key={`${target.id}-${idx}`}
    "id": Read("InteractPanel.jsx", "target.id"),
    "name": Read("RoomContents.jsx", "entity.name"),
    # npc_class: n.type -> NpcChatPanel npcId
    "type": Read("InteractPanel.jsx", "n.type"),
    # NPCs and objects describe themselves identically (an `idle_message`
    # or nothing), so `pushIdleLines` reads BOTH shapes -- which is why
    # this anchor and the object contract's are the same literal.
    "idle_message": Read("RoomContents.jsx", "entity.idle_message"),
    "llm_chat_enabled": Read("InteractPanel.jsx", "selectedTarget?.llm_chat_enabled"),
    "loquacity_available": Read(
        "InteractPanel.jsx", "selectedTarget?.loquacity_available"
    ),
}

# Room objects flow through ObjectSerializer.serialize_list.
ROOM_OBJECT_CONTRACT = {
    "id": Read("InteractPanel.jsx", "target.id"),
    "name": Read("RoomContents.jsx", "entity.name"),
    "idle_message": Read("RoomContents.jsx", "entity.idle_message"),
    # objectState.keywords ?? prev.keywords
    "keywords": Read("InteractPanel.jsx", "objectState.keywords"),
}


class TestRoomWireContract:
    """`GameService.get_current_room` against a real Player/Universe/MapTile.

    ``live_world`` builds the world graph by hand rather than via
    ``Universe.build()``, so no module-level item/merchant registry is mutated
    and this stays safe for the default suite (see CLAUDE.md, Running Tests).
    """

    @staticmethod
    def _populated_room():
        from src.items import Longsword
        from src.objects import Container
        from tests._gs_fixtures import live_world

        player, game_map = live_world(coords=GRID_3X3, start=(0, 0))
        tile = game_map[(0, 0)]
        tile.items_here = [Longsword()]
        tile.npcs_here = [Slime()]
        tile.objects_here = [Container(name="Chest", inventory=[Longsword()])]
        return player, tile

    def test_room_fields(self):
        player, _ = self._populated_room()

        room = GameService().get_current_room(player)

        _assert_contract(room, ROOM_CONTRACT, "get_current_room()")

    def test_interact_response_fields(self):
        """The /world/interact body, built from a real interaction.

        `beta_end` shipped as a new top-level field of this response with no
        entry here, which is the omission `.claude/rules/api-layer.md` names
        this file the registry against: the client reads it as
        `data?.beta_end`, so a rename would read as "the demo never ends" and
        nothing would throw.
        """
        player, tile = self._populated_room()
        from src.combatant import wire_handle

        # The container, with a verb it implements: an unimplemented verb
        # returns the in-fiction refusal shape instead of the full body, so it
        # would exercise none of these fields.
        result = GameService().interact_with_target(
            player, wire_handle(tile.objects_here[0]), "look", session_data={}
        )

        _assert_contract(
            result, INTERACT_RESPONSE_CONTRACT, "interact_with_target()"
        )

    def test_exits_is_a_direction_keyed_mapping_the_client_can_take_keys_of(self):
        """transformLocationData calls `Object.keys(room.exits)`. If the server
        ever switched to a list of dicts the client would render `["0","1"]`
        as its compass directions — no error, just wrong exits."""
        player, _ = self._populated_room()

        exits = GameService().get_current_room(player)["exits"]

        assert isinstance(exits, dict)
        assert "north" in exits and "southwest" in exits
        assert set(exits["north"]) == {"x", "y"}

    def test_room_item_fields(self):
        player, _ = self._populated_room()

        items = GameService().get_current_room(player)["items"]

        assert items, "expected the Longsword on the tile"
        _assert_contract(items[0], ROOM_ITEM_CONTRACT, "get_current_room()['items'][0]")

    def test_room_npc_fields(self):
        player, _ = self._populated_room()

        npcs = GameService().get_current_room(player)["npcs"]

        assert npcs, "expected the Slime on the tile"
        _assert_contract(npcs[0], ROOM_NPC_CONTRACT, "get_current_room()['npcs'][0]")

    def test_room_object_fields(self):
        player, _ = self._populated_room()

        objects = GameService().get_current_room(player)["objects"]

        assert objects, "expected the Container on the tile"
        _assert_contract(
            objects[0], ROOM_OBJECT_CONTRACT, "get_current_room()['objects'][0]"
        )


# ============================================================================
# Inventory payload
# ============================================================================
# useApi.js:59 — `inventory: data.inventory?.items || []`. Each entry is an
# InventoryItemSerializer.serialize() dict, read by InventoryDialog (list rows)
# and ItemDetailDialog (detail pane).

INVENTORY_ITEM_CONTRACT = {
    "id": (
        Read("InventoryDialog.jsx", "key={item.id}"),
        Read("ItemDetailDialog.jsx", "item_id: item.id"),
    ),
    "name": Read("InventoryDialog.jsx", "item.name"),
    "type": Read("ItemDetailDialog.jsx", "item.type"),
    # slot grouping
    "maintype": (
        Read("InventoryDialog.jsx", "item.maintype"),
        Read("ItemDetailDialog.jsx", "item.maintype"),
    ),
    "subtype": (
        Read("InventoryDialog.jsx", "item.subtype"),
        Read("ItemDetailDialog.jsx", "item.subtype"),
    ),
    # The stack count badge, moved behind `stackSize` for the same reason
    # `count`'s read was. Helper plus one consumer, as there -- see the note
    # on `count` for why the helper alone is not enough.
    "quantity": (
        Read("utils/stackName.js", "item?.quantity"),
        Read("InventoryDialog.jsx", "stackSize(item)"),
    ),
    # row colour
    "rarity": Read("InventoryDialog.jsx", "item.rarity"),
    "weight": Read("InventoryDialog.jsx", "item.weight"),
    "value": Read("InventoryDialog.jsx", "item.value"),
    "is_equipped": (
        Read("InventoryDialog.jsx", "item.is_equipped"),
        Read("ItemDetailDialog.jsx", "item.is_equipped"),
    ),
    "is_merchandise": Read("ItemDetailDialog.jsx", "item.is_merchandise"),
    "description": Read("ItemDetailDialog.jsx", "item.description"),
    # the four button gates
    "can_equip": Read("ItemDetailDialog.jsx", "item.can_equip"),
    "can_use": Read("ItemDetailDialog.jsx", "item.can_use"),
    "can_read": Read("ItemDetailDialog.jsx", "item.can_read"),
    "can_drop": Read("ItemDetailDialog.jsx", "item.can_drop"),
}


class TestInventoryWireContract:
    def test_inventory_envelope_and_item_fields(self):
        from src.api.serializers.inventory import InventorySerializer
        from src.items import Longsword

        player = Player()
        player.inventory = [Longsword()]

        payload = InventorySerializer.serialize(player)

        # useApi.js reads `data.inventory?.items`; anything else is invisible.
        assert "items" in payload
        _assert_contract(
            payload["items"][0], INVENTORY_ITEM_CONTRACT, "inventory.items[0]"
        )

    def test_weapon_rows_carry_the_weapon_stat_block(self):
        from src.api.serializers.inventory import InventoryItemSerializer
        from src.items import Longsword

        row = InventoryItemSerializer.serialize(Longsword(), 0)

        # ItemStatGrid renders damage/damage_type for weapons.
        assert row["damage"] == 30
        assert row["damage_type"] == "slashing"

    def test_armor_rows_carry_protection(self):
        from src.api.serializers.inventory import InventoryItemSerializer
        from src.items import IronCuirass

        row = InventoryItemSerializer.serialize(IronCuirass(), 0)

        assert row["protection"] == 14

    def test_comparison_block_shape_for_an_equippable_candidate(self):
        """ItemDetailDialog renders `item.comparison.differences.*`."""
        from src.api.serializers.inventory import InventoryItemSerializer
        from src.items import Shortsword, Longsword

        equipped = Shortsword()
        equipped.isequipped = True
        candidate = Longsword()
        player = Player()
        player.inventory = [equipped, candidate]

        row = InventoryItemSerializer.serialize(candidate, 1, player)

        comparison = row["comparison"]
        assert comparison["comparison_type"] == "item_to_item"
        assert set(comparison) >= {"current", "candidate", "differences",
                                   "recommendation", "reason"}
        assert set(comparison["differences"]) >= {
            "damage_diff", "protection_diff", "weight_diff", "value_diff",
            "bonus_diffs", "resistance_diffs", "status_resistance_diffs",
        }


# ============================================================================
# Skills payload
# ============================================================================
# GET /player/skills -> GameService.get_player_skills(). SkillsPanel.jsx reads
# `skills.skill_tree` / `skills.skill_exp`; CombatMovePanel / CooldownTray /
# BattlefieldGrid read the move dicts.

SKILLS_CONTRACT = {
    "known_moves": Read(
        "SkillsPanel.jsx",
        note="no literal read anywhere in frontend/src: `known_moves` appears "
        "only in test/payloads.js. The old citation named CombatMovePanel, "
        "but that panel's list is LeftPanel's `movesForButtons`, which comes "
        "from combat.available_options, not from get_player_skills(). Kept in "
        "the contract because the endpoint still emits it.",
    ),
    "skill_tree": Read("SkillsPanel.jsx", "skills.skill_tree"),
    "skill_exp": Read("SkillsPanel.jsx", "skills.skill_exp"),
}

# The skills panel's move list is a DIFFERENT payload from the combat move list
# above: get_player_skills() emits the at-a-glance fields (xp_gain, beats_left),
# while _get_available_moves() emits the per-beat combat gating fields
# (available/reason/targeted/stage_beats). Keeping one name for both let the
# later definition shadow the earlier one, so whichever test ran against the
# survivor was silently asserting the wrong contract.
KNOWN_MOVE_CONTRACT = {
    "name": Read("CombatMovePanel.jsx", "move.name"),
    "display_name": Read("CombatMovePanel.jsx", "move.display_name"),
    # `category` routes the move to a radial button via CATEGORY_GROUPS
    # (utils/categories.js). A category no group claims leaves the move with no
    # button at all — that is how 8 castable moves became unreachable.
    "category": (
        Read("CooldownTray.jsx", "move.category"),
        Read("BattlefieldGrid.jsx", "move.category"),
    ),
    # move tooltip
    "description": Read("CombatMovePanel.jsx", "move.description"),
    # move.fatigue_cost > 0
    "fatigue_cost": Read("CombatMovePanel.jsx", "move.fatigue_cost"),
    "beats_left": Read(
        "CooldownTray.jsx",
        note="the tray's countdown reads cooldown_remaining/cooldown_max, not "
        "beats_left, and its `moves` prop is LeftPanel's combat move list "
        "rather than this payload. Nothing in frontend/src reads "
        "known_moves[i].beats_left.",
    ),
    "xp_gain": Read(
        "SkillsPanel.jsx",
        note="no literal read anywhere in frontend/src; `xp_gain` appears only "
        "in test/payloads.js. Neither SkillsPanel nor CombatMovePanel renders "
        "an xp figure per move.",
    ),
}

SKILL_TREE_ENTRY_CONTRACT = {
    # handleLearn(skill.name, selectedCategory)
    "name": Read("SkillsPanel.jsx", "skill.name"),
    # the card title, via displayNameOf's `display_name || name`
    "display_name": Read("SkillsPanel.jsx", "displayNameOf(skill)"),
    "description": Read("SkillsPanel.jsx", "skill.description"),
    # LEARN ({skill.required_exp})
    "required_exp": Read("SkillsPanel.jsx", "skill.required_exp"),
    "is_known": Read("SkillsPanel.jsx", "skill.is_known"),
    "can_learn": Read("SkillsPanel.jsx", "skill.can_learn"),
}


class TestSkillsWireContract:
    def test_skills_envelope_fields(self):
        payload = GameService().get_player_skills(Player())

        _assert_contract(payload, SKILLS_CONTRACT, "get_player_skills()")

    def test_known_move_fields_on_a_real_move(self):
        player = Player()
        player.known_moves = [ShootBow(player)]

        payload = GameService().get_player_skills(player)

        assert payload["known_moves"], "expected the ShootBow in known_moves"
        _assert_contract(
            payload["known_moves"][0],
            KNOWN_MOVE_CONTRACT,
            "get_player_skills().known_moves[0]",
        )

    def test_move_category_is_one_the_ui_routes(self):
        """A category string CATEGORY_GROUPS does not claim means no button."""
        player = Player()
        player.known_moves = [ShootBow(player)]

        move = GameService().get_player_skills(player)["known_moves"][0]

        assert move["category"] == ShootBow(player).category
        assert isinstance(move["category"], str) and move["category"]

    def test_skill_tree_entry_fields(self):
        payload = GameService().get_player_skills(Player())

        entries = [e for cat in payload["skill_tree"].values() for e in cat]
        assert entries, "expected the real skill tree to offer at least one skill"
        _assert_contract(
            entries[0], SKILL_TREE_ENTRY_CONTRACT, "skill_tree[category][0]"
        )

class TestAbortableMoveWireContract:
    """`battle_state.abortable_move` is what the abort control renders.

    It is published inside battle_state, never at the top level, because
    transformCombatData whitelists top-level keys and silently drops the rest —
    the drop-trap CLAUDE.md records as having shipped twice.
    """

    def _adapter_mid_prep(self):
        from src.api.combat_adapter import ApiCombatAdapter
        from src.items import Crossbow, IronArrow
        from src.moves import AimedShot, Wait
        from src.narration import capture_narration

        player = Player()
        player.eq_weapon = Crossbow()
        arrow = IronArrow()
        arrow.count = 30
        player.inventory.append(arrow)
        player.combat_exp.setdefault("Crossbow", 0)
        player.known_moves = [AimedShot(player), Wait(player)]
        for move in player.known_moves:
            move.user = player

        enemy = Slime()
        adapter = ApiCombatAdapter(player)
        with capture_narration():
            adapter.initialize_combat([enemy])
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        player.combat_proximity = {enemy: 20}
        with capture_narration():
            adapter._handle_move_selection(0)
        return adapter

    def test_abortable_move_fields_match_what_the_control_reads(self):
        adapter = self._adapter_mid_prep()
        state = adapter.get_combat_state()
        assert "abortable_move" not in state, (
            "abortable_move must live inside battle_state — transformCombatData "
            "drops unknown top-level keys"
        )
        abortable = state["battle_state"]["abortable_move"]
        assert abortable is not None, "fixture: expected a move mid-prep"

        missing = set(ABORTABLE_MOVE_CONTRACT) - set(abortable)
        assert not missing, (
            f"AbortMoveControl reads fields the serializer never emits: {missing}"
        )

    def test_abortable_move_is_null_when_nothing_is_in_flight(self):
        from src.api.combat_adapter import ApiCombatAdapter

        player = Player()
        player.known_moves = []
        player.combat_log = []
        player.combat_beat = 1
        adapter = ApiCombatAdapter(player)
        state = adapter.get_combat_state()
        assert state["battle_state"]["abortable_move"] is None


# ============================================================================
# Wire id round-trip
# ============================================================================
# Every `id` above is only useful if the endpoint that *consumes* it accepts
# the same string back. That pairing is a wire contract exactly like a field
# name, and it broke the same silent way: issue #518 moved the serializers to
# opaque handles (src.combatant.wire_handle) while the lookups still compared
# str(id(...)), so `interact_with_target` answered "Target not found." for
# every object in the room — no error, no exception, just a dead UI.
#
# These tests deliberately never construct an id. They take the one the real
# serializer emitted for a real engine object and feed it to the real resolver,
# so a future change that moves one side has nowhere to hide: a mock id fed to
# a mock lookup would agree with itself forever (CLAUDE.md, wire-field drift).

#: An id must be opaque. A decimal string is a CPython heap address — the
#: scheme #511/#518 removed — so its reappearance anywhere is a regression.
#: The check itself lives in ``tests/_gs_fixtures`` so this file and
#: ``test_entity_wire_handles`` make the SAME check rather than two different
#: partial ones.
from tests._gs_fixtures import assert_opaque_wire_id as _assert_opaque  # noqa: E402


class TestWireIdRoundTrip:
    """The id a serializer emits is the id its resolver accepts."""

    @staticmethod
    def _room():
        from src.items import Longsword
        from src.objects import Container
        from tests._gs_fixtures import live_world

        player, game_map = live_world(coords=GRID_3X3, start=(0, 0))
        tile = game_map[(0, 0)]
        tile.items_here = [Longsword()]
        tile.npcs_here = [Slime()]
        chest = Container(name="Chest", inventory=[Longsword()])
        chest.state = "opened"
        tile.objects_here = [chest]
        return player, tile

    @pytest.mark.parametrize("payload_key", ["npcs", "items", "objects"])
    def test_a_room_entity_id_resolves_back_through_interact_with_target(
        self, payload_key
    ):
        """Every room list: the id ``get_current_room`` published resolves.

        One parametrised body rather than three copies differing only in the
        dict key — the container-contents case below stays separate because it
        reads a *nested* id (``objects[0].contents[0]``) and a different branch
        of ``interact_with_target`` resolves it.
        """
        player, _ = self._room()
        gs = GameService()

        entity_id = gs.get_current_room(player)[payload_key][0]["id"]
        _assert_opaque(entity_id, f"room {payload_key}[0].id")

        result = gs.interact_with_target(player, entity_id, "look")

        assert result["message"] != "Target not found.", (
            f"the id get_current_room published for {payload_key} did not resolve"
        )

    def test_a_room_npc_id_is_what_start_combat_matches_on(self):
        """InteractPanel's Attack button posts the room id to /combat/start."""
        player, tile = self._room()
        gs = GameService()

        npc_id = gs.get_current_room(player)["npcs"][0]["id"]
        with capture_narration():
            result = gs.start_combat(player, npc_id)

        assert "error" not in result, result

    def test_a_container_content_id_resolves_back_through_interact_with_target(self):
        """Chest contents are serialized by ItemSerializer inside the object
        payload and resolved by a *separate* branch of interact_with_target."""
        player, tile = self._room()
        gs = GameService()

        room_chest = gs.get_current_room(player)["objects"][0]
        content_id = room_chest["contents"][0]["id"]
        _assert_opaque(content_id, "room objects[0].contents[0].id")

        result = gs.interact_with_target(player, content_id, "look")

        assert result["message"] != "Target not found."

    def test_a_search_result_id_resolves_back_through_interact_with_target(self):
        """`search` mints its own found-entry ids, a fourth site that has to
        agree with the room scheme — the client's very next click after a
        successful search posts one of these back to /interact.

        A hidden *NPC* rather than a hidden item: an item with hide_factor 0 is
        auto-taken into the pack by `search`, so it is no longer on the tile for
        interact_with_target to resolve.
        """
        from tests._gs_fixtures import live_world

        player, game_map = live_world(coords=GRID_3X3, start=(0, 0))
        tile = game_map[(0, 0)]
        lurker = Slime()
        lurker.hidden = True
        lurker.hide_factor = 0
        tile.npcs_here = [lurker]
        gs = GameService()

        found = gs.search(player)["found"]

        assert found, "fixture: expected the hidden Slime to be uncovered"
        _assert_opaque(found[0]["id"], "search()['found'][0].id")

        result = gs.interact_with_target(player, found[0]["id"], "look")

        assert result["message"] != "Target not found.", (
            "the id search() published did not resolve"
        )

    def test_an_inventory_row_id_resolves_back_through_get_item_and_index(self):
        from src.api.routes.inventory import get_item_and_index
        from src.api.serializers.inventory import InventorySerializer
        from src.items import Longsword

        player = Player()
        sword = Longsword()
        player.inventory = [Restorative(), sword]

        rows = InventorySerializer.serialize(player)["items"]
        row = next(r for r in rows if r["name"] == "Longsword")
        _assert_opaque(row["id"], "inventory.items[].id")

        item, index = get_item_and_index(player, item_id=row["id"])

        assert item is sword
        assert index == row["index"]

    def test_an_unknown_inventory_id_resolves_to_nothing(self):
        """Negative control — the lookup must not fall through to item 0."""
        from src.api.routes.inventory import get_item_and_index
        from src.items import Longsword

        player = Player()
        player.inventory = [Longsword()]

        assert get_item_and_index(player, item_id="no-such-handle") == (None, None)

    def test_the_shop_npc_id_resolves_back_through_find_merchant(self):
        from tests._gs_fixtures import live_shop

        player, _, merchant = live_shop(
            coords=GRID_3X3, stock=[Restorative(count=2, merchandise=True)]
        )
        gs = GameService()

        npc_id = ShopSerializer.serialize_state(merchant, player, 0)["npc_id"]
        _assert_opaque(npc_id, "shop_state.npc_id")

        assert gs._find_merchant(player, npc_id) is merchant

    def test_a_stock_item_id_is_what_shop_buy_matches_on(self):
        from tests._gs_fixtures import live_shop

        stock = Restorative(count=2, merchandise=True)
        player, _, merchant = live_shop(
            coords=GRID_3X3, stock=[stock], player_gold=500
        )
        gs = GameService()

        state = ShopSerializer.serialize_state(merchant, player, 0)
        item_id = state["stock"][0]["id"]
        _assert_opaque(item_id, "shop_state.stock[0].id")

        result = gs.shop_buy(player, state["npc_id"], item_id, 1)

        assert result["success"], result.get("error")

    def test_a_sell_row_id_is_what_shop_sell_matches_on(self):
        from tests._gs_fixtures import live_shop

        player, _, merchant = live_shop(coords=GRID_3X3)
        goods = Restorative()
        goods.value = 10
        player.inventory = [goods]
        merchant.update_goods()
        gs = GameService()

        state = ShopSerializer.serialize_state(merchant, player, 0)
        sellable = ShopSerializer.serialize_player_sellable(
            player, state["sell_modifier"]
        )
        row = next(r for r in sellable if r["name"] == "Restorative")
        _assert_opaque(row["id"], "sell_inventory[].id")

        result = gs.shop_sell(player, state["npc_id"], row["id"], 1)

        assert result["success"], result.get("error")

    def test_a_buyback_entry_id_is_what_shop_buyback_matches_on(self):
        """The buyback id is the one wire id that is *persisted* (on the
        merchant, into saves), so its round trip spans a sell and a repurchase
        rather than a single request."""
        from tests._gs_fixtures import live_shop

        player, _, merchant = live_shop(coords=GRID_3X3, player_gold=500)
        goods = Restorative()
        goods.value = 10
        player.inventory.append(goods)
        merchant.update_goods()
        gs = GameService()

        npc_id = ShopSerializer.serialize_state(merchant, player, 0)["npc_id"]
        sold = gs.shop_sell(player, npc_id, wire_handle(goods), 1)
        assert sold["success"], sold.get("error")

        buyback = sold["shop_state"]["buyback_items"]
        assert buyback, "fixture: expected the sale to land in the ledger"
        _assert_opaque(buyback[0]["id"], "shop_state.buyback_items[0].id")

        result = gs.shop_buyback(player, npc_id, buyback[0]["id"])

        assert result["success"], result.get("error")

    def test_no_room_payload_id_is_a_heap_address(self):
        player, _ = self._room()

        room = GameService().get_current_room(player)

        for key in ("npcs", "items", "objects"):
            for entry in room[key]:
                _assert_opaque(entry["id"], f"room {key}[].id")


# The citations themselves
# ============================================================================
# Everything above asserts that the SERIALIZER still emits what the client
# reads. Nothing above notices the other direction: a component that stopped
# reading a field, or a file that was renamed or deleted. A hand-written
# `File.jsx:123` could not catch that — a stale number still renders as a
# plausible reference — which is why the citations below name an anchor
# instead. These tests close the loop.

#: Every contract dict above, found rather than listed. A hand-maintained
#: roster is a second place to forget: dropping a name from it would remove
#: that dict's citations from both guards below with nothing failing, and the
#: roster and the dicts would still look consistent to a reader.
ALL_CONTRACTS = tuple(
    value
    for name, value in sorted(globals().items())
    if name.endswith("_CONTRACT") and isinstance(value, dict)
)


def _source() -> str:
    with io.open(__file__, encoding="utf-8") as handle:
        return handle.read()


def _reads_written_in_this_file() -> int:
    """How many ``Read(...)`` calls this file's own source contains.

    The floor on the INCREMENT, not just the base. ``ALL_CONTRACTS`` scans
    globals, so a dict renamed out of the ``*_CONTRACT`` shape — or one built
    somewhere the scan cannot see — would drop out silently while its Reads
    stayed in the file. Parsed rather than counted with ``str.count`` so the
    ``Read(...)`` in the module docstring above is not mistaken for one.
    """
    return sum(
        1
        for node in ast.walk(ast.parse(_source()))
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Read"
    )


def _all_reads():
    """Every Read in every contract above, two-consumer tuples flattened.

    Strict on purpose: a plain string slipped back into a contract would be
    skipped silently by both guards below, which is exactly the hole this
    file was converted to close.
    """
    for contract in ALL_CONTRACTS:
        for field, why in contract.items():
            multi = isinstance(why, tuple) and not isinstance(why, Read)
            for part in (why if multi else (why,)):
                if not isinstance(part, Read):
                    raise TypeError(
                        f"contract entry {field!r} is {part!r}, not a Read — "
                        "provenance in this file is derived, not written; see "
                        "tests/_cite.py"
                    )
                yield part


ALL_READS = tuple(_all_reads())

# Citations that carry a `note=` instead of an anchor, i.e. the fields this
# file cannot check a consumer for. An unchecked citation is acceptable — some
# fields genuinely have no consumer to point at. An UNCOUNTED one is not: a
# citation nobody is counting is precisely how the defect class this file was
# converted to close got started. Change this number only alongside the note
# that justifies it.
EXPECTED_UNVERIFIABLE = 4


def _citation_count_mismatch(reached: int, written: int) -> str:
    """Why the two ``Read`` counts disagree -- which depends on the direction.

    The assertion they feed is an equality, so it fires both ways, and the two
    ways have opposite causes and opposite fixes. Describing only one of them
    left the other rendered as its own mirror image ("5 Read(...) calls are
    written in this file but only 30 reached the guards"), which is nonsense at
    the moment somebody most needs the message to be readable.
    """
    if written > reached:
        return (
            f"{written} Read(...) calls are written in this file but only "
            f"{reached} reached the guards. A citation that is not in a "
            "module-level `*_CONTRACT` dict is checked by nothing."
        )
    return (
        f"{reached} Read(...) citations reached the guards but only {written} "
        "Read(...) call(s) are written in this file. "
        "`_reads_written_in_this_file` counts call SITES, so one site "
        "standing for many citations lands here: a Read built inside a loop, a "
        "comprehension or a helper that a contract dict then spreads. Write "
        "the citations out one per field -- a generated citation names "
        "whatever the generator was handed rather than a consumer somebody "
        "checked -- or teach that counter to see the construct and say here "
        "why it is trustworthy."
    )


def _contracts_declared_in_this_file():
    """The ``*_CONTRACT = {...}`` names this file's own source assigns."""
    return {
        target.id
        for node in ast.parse(_source()).body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id.endswith("_CONTRACT")
    }


class TestCitationProvenance:
    def test_the_scan_sees_every_contract_and_every_citation(self):
        """Guard the guards: both of the tests below take a SET as input.

        ``verify([])`` is ``[]`` and ``unverifiable([])`` is ``[]``, so an
        input set that quietly emptied would leave both passing while checking
        nothing. Neither half of the size is written down here — the contract
        roster is compared against the dicts this file declares, and the
        citation count against the ``Read(...)`` calls it contains — so the
        floor cannot go stale the way a literal number would.
        """
        declared = _contracts_declared_in_this_file()
        assert declared, "parsed no contract dicts out of this file's source"
        assert len(ALL_CONTRACTS) == len(declared), (
            f"{len(ALL_CONTRACTS)} contract dict(s) reached the citation scan "
            f"but {len(declared)} are declared here ({sorted(declared)}) — a "
            "contract built somewhere the globals scan cannot see contributes "
            "no citations to either guard below."
        )
        written = _reads_written_in_this_file()
        assert len(ALL_READS) == written, _citation_count_mismatch(
            len(ALL_READS), written
        )

    def test_every_anchored_citation_still_finds_its_anchor(self):
        broken = verify(ALL_READS)
        assert not broken, (
            "Contract citations point at reads that no longer exist:\n  "
            + "\n  ".join(broken)
            + "\n\nEither the consumer stopped reading the field (drop the "
            "field from its contract dict, with a comment saying why), or the "
            "read moved/was renamed (update the anchor to the literal the "
            "file now contains). Never widen the anchor to something that "
            "happens to match — an anchor that cannot fail is not a citation."
        )

    def test_the_unverifiable_set_is_bounded_and_named(self):
        loose = unverifiable(ALL_READS)
        listing = "\n  ".join(f"{r.file}: {r.note}" for r in loose)
        assert len(loose) == EXPECTED_UNVERIFIABLE, (
            f"{len(loose)} citation(s) carry a note instead of an anchor, "
            f"expected {EXPECTED_UNVERIFIABLE}:\n  {listing}\n\n"
            "If you added one, prefer finding the real literal the file "
            "contains (often the destructured name). If there genuinely isn't "
            "one, say so in `note=` and raise EXPECTED_UNVERIFIABLE in the "
            "same commit. If you removed one, lower it."
        )


# ----------------------------------------------------------------------------
# The payloads.js builders and exported constants held to the wire
# ----------------------------------------------------------------------------
_PAYLOADS_JS = FRONTEND_SRC / "test" / "payloads.js"


def _js_builder_keys(path, name):
    """The top-level keys of the object literal a ``payloads.js`` builder
    passes to ``merge(`` -- ``key: value`` and shorthand ``key,`` alike.
    Nested objects and arrays are stripped first, so only the builder's own
    keys remain.

    What this reader assumes of the builder, each checked rather than hoped:

    * its FIRST ``merge(`` is the object literal -- the search is bounded at
      the next ``export function``, so a builder that stops calling ``merge(``
      raises here instead of silently reading the NEXT builder's object;
    * that literal's braces balance inside the builder -- a ``{`` in a default
      string value would break the depth walk, so an unbalanced walk raises;
    * it names at least one key -- an empty read would otherwise be reported
      as "the wire sent keys the fixture is missing", blaming the fixture for
      a parser miss.

    What it cannot see: a spread (``...base``) contributes no key here, and a
    multi-line call inside the literal can yield phantom shorthand keys from
    its argument lines. Both would show up as a mismatch, not as a false pass.

    ``//`` comments are stripped before the walk. Prose is not JS, and these
    literals are heavily commented: a comment line ending in ``, never`` read
    as a key named ``never`` and failed the guard. No string value in this
    file contains ``//``, which is what makes the blunt strip safe -- if one
    ever does, this drops the rest of that line and the key count changes,
    which fails here rather than passing quietly.
    """
    source = path.read_text(encoding="utf-8")
    start = source.index(f"export function {name}(")
    next_builder = source.find("export function ", start + 1)
    limit = len(source) if next_builder == -1 else next_builder
    merge_at = source.index("merge(", start)
    assert merge_at < limit, f"{name} has no merge( call of its own"
    open_brace = source.index("{", merge_at)
    depth = 0
    for end in range(open_brace, limit):
        depth += {"{": 1, "}": -1}.get(source[end], 0)
        if depth == 0:
            break
    else:
        raise AssertionError(f"{name}: the braces after merge( never balance")
    body = re.sub(r"(?m)//.*$", "", source[open_brace + 1:end])
    previous = None
    while previous != body:
        previous, body = body, re.sub(r"\{[^{}]*\}|\[[^\[\]]*\]", "", body)
    # ``(?:^|,)`` and not just ``^``: two keys on one line are legal JS, and
    # anchoring to the line start would hide the second -- the direction an
    # invented field would travel.
    keys = set(re.findall(r"(?m)(?:^|,)\s*(\w+)\s*(?::|,|$)", body))
    assert keys, f"{name}: no keys read out of the object literal"
    return keys


def _assert_builder_matches_the_wire(builder, wire_entry, emitter):
    """``builder``'s keys in ``payloads.js`` are exactly ``wire_entry``'s."""
    fixture_keys = _js_builder_keys(_PAYLOADS_JS, builder)
    wire_keys = set(wire_entry)
    assert fixture_keys == wire_keys, (
        f"missing from {builder}: {sorted(wire_keys - fixture_keys)}; "
        f"not sent by {emitter}: {sorted(fixture_keys - wire_keys)}"
    )


class TestThePayloadBuildersMatchTheWire:
    """The ``payloads.js`` fixtures the frontend's combat tests are built from.

    A key the adapter always sends and a builder omits sends every test built
    on it down a fallback no real payload takes: a fixture agreeing with
    itself, which this module exists to stop. So each builder's KEYS -- the
    move card, its ``viable_targets`` entry, a passive icon, a check row --
    are held to the real emitter's own output, in both directions: a field the
    fixture invents fails here too.

    Where the fixture is a constant rather than a builder, it is held by
    VALUE: the two input prompts and the two unavailability reasons land on
    the wire verbatim and the client renders them, and the default enemy's
    distance carries a claim about reach that its key set cannot see. Those
    also pin the emitter's own side, so the constants stay the thing the
    adapter actually sends.
    """

    def test_the_move_fixture_carries_exactly_the_keys_the_adapter_emits(
        self, real_adapter, real_combat_player
    ):
        real_combat_player.known_moves = [Attack(real_combat_player)]
        [move] = real_adapter._get_available_moves()

        _assert_builder_matches_the_wire("makeAvailableOption", move, "_get_available_moves")

    def test_the_target_fixture_carries_exactly_the_keys_of_a_target_in_reach(
        self, real_adapter, real_combat_player
    ):
        # In reach, as a viable target always is: an out-of-reach entry
        # omits hit_chance, which the fixture carries.
        attack = Attack(real_combat_player)
        enemy = Slime()
        _range_min, range_max = real_adapter._move_range(attack)
        real_combat_player.known_moves = [attack]
        real_combat_player.combat_list = [enemy]
        real_combat_player.combat_proximity = {enemy: range_max}

        [target] = real_adapter._get_available_moves()[0]["viable_targets"]

        _assert_builder_matches_the_wire("makeTargetOption", target, "_build_target_entry")

    def test_the_check_fixture_carries_exactly_the_keys_the_move_emits(
        self, real_combat_player
    ):
        """A combatant with no coordinate position and no move in progress --
        the row ``makeCheckEntry`` describes. One mid-move carries three more
        keys, which a test that wants them adds."""
        enemy = Slime()
        real_combat_player.combat_list = [enemy]
        real_combat_player.combat_proximity = {enemy: 5}
        real_combat_player.combat_adapter_state = {}

        Check(real_combat_player)._generate_api_check_data(real_combat_player)
        [row] = real_combat_player.combat_adapter_state["check_data"]

        _assert_builder_matches_the_wire(
            "makeCheckEntry", row, "Check._generate_api_check_data"
        )

    def test_the_suggestion_fixture_carries_exactly_the_keys_the_strategist_emits(
        self, real_adapter, real_combat_player
    ):
        """``combat.suggested_moves``, scored off a real move card.

        The heuristic path, not the LLM one: ``get_suggestions`` either
        returns the model's rows or falls back here, and both go through the
        same four keys -- but only this one runs without a network call. A
        client is passed so the constructor does not reach for
        ``CombatLLMAdapter``; ``_get_fallback_suggestions`` never touches it.

        The enemy is load-bearing, not scenery: with an empty ``combat_list``
        Attack is not viable, its card arrives ``available: False``,
        ``_offerable_moves`` drops it and the strategist returns its hardcoded
        "no moves available" row instead -- the same four keys, so the guard
        would pass while the SCORED branch it means to pin never ran.
        """
        enemy = Slime()
        real_combat_player.known_moves = [Attack(real_combat_player)]
        real_combat_player.combat_list = [enemy]
        real_combat_player.combat_proximity = {enemy: 5}
        [card] = real_adapter._get_available_moves()
        assert card["available"], card["reason"]
        context = {"available_moves": [card]}

        [suggestion] = CombatStrategist(client=object())._get_fallback_suggestions(
            context, max_suggestions=1
        )

        _assert_builder_matches_the_wire(
            "makeSuggestedMove", suggestion, "_get_fallback_suggestions"
        )

    def test_the_combatant_fixture_carries_exactly_the_keys_the_serializer_emits(
        self, real_combat_player
    ):
        """``makeCombatant`` -- the builder this branch changed most, and the
        one every combat fixture is built on. A `reference` is passed because
        that is what a real payload has: without one the serializer short-
        circuits ``in_range`` to True and never reads a distance."""
        enemy = Slime()
        real_combat_player.combat_proximity = {enemy: 5}
        enemy.combat_proximity = {real_combat_player: 5}

        combatant = CombatantSerializer.serialize_combatant(enemy, real_combat_player)

        _assert_builder_matches_the_wire(
            "makeCombatant", combatant, "serialize_combatant"
        )

    @pytest.mark.parametrize(
        "name, read",
        [
            # The card `_get_available_moves` builds, off a move Jean holds now.
            ("ATTACK_CARD_FATIGUE_COST", lambda player: Attack(player).fatigue_cost),
            # The row `get_player_skills` builds, off the move `Player.__init__`
            # constructed before endurance and carry weight settled. Nothing
            # re-evaluates it until Jean swings, which is why the two differ.
            (
                "ATTACK_DECLARED_FATIGUE_COST",
                lambda player: next(
                    m.fatigue_cost for m in player.known_moves if m.name == "Attack"
                ),
            ),
        ],
    )
    def test_the_fixture_fatigue_costs_are_what_the_engine_computes(self, name, read):
        """Two numbers a key-set guard cannot see.

        ``payloads.js`` carries a fatigue cost in two builders, and both are
        the kind of invented-looking literal this module exists to stop: a
        wrong one describes a card no adapter can send, and every test built
        on it agrees with the fixture rather than the engine. Held to a real
        ``Player`` -- a fresh one, because both readings depend on the state
        Jean starts with.
        """
        assert js_literal(_PAYLOADS_JS, name) == read(Player())

    def test_the_passive_fixture_carries_exactly_the_keys_the_serializer_emits(self):
        player = Player()
        player.known_moves = [ShadowStep(player)]

        [passive] = CombatantSerializer._serialize_passives(player)

        _assert_builder_matches_the_wire("makePassive", passive, "_serialize_passives")

    @pytest.mark.parametrize(
        "name, emitted",
        [
            ("TURN_DIRECTIONS", combat_adapter.TURN_DIRECTIONS),
            ("WAIT_DURATION_PROMPT", combat_adapter.WAIT_DURATION_PROMPT),
            ("TOO_FAR_REASON", combat_adapter.TOO_FAR_REASON),
            ("NOT_ENOUGH_FATIGUE_REASON", combat_adapter.NOT_ENOUGH_FATIGUE_REASON),
        ],
    )
    def test_the_wire_string_fixtures_are_what_the_adapter_sends(self, name, emitted):
        """The adapter puts these on the wire verbatim -- the two input
        prompts in ``available_options``, the two reasons in a move card's
        ``reason`` -- and the client renders them. A fixture that merely
        looked like them let a renamed key, a moved bound or a reworded
        sentence pass on both sides."""
        assert emitted, name
        assert js_literal(_PAYLOADS_JS, name) == emitted

    @pytest.mark.parametrize(
        "move_class, expected",
        [
            (Wait, combat_adapter.WAIT_DURATION_PROMPT),
            (Turn, combat_adapter.TURN_DIRECTIONS),
        ],
    )
    def test_the_adapter_really_offers_the_constants_it_names(
        self, real_adapter, real_combat_player, move_class, expected
    ):
        """The other half of the pin above: the constants are only worth
        holding the fixtures to if ``_handle_move_selection`` is what puts
        them on the wire. Re-inlining either literal fails here."""
        # A placed fight: Turn is viable only in coordinate-based combat, so
        # the adapter has to have positioned the combatants.
        real_adapter.initialize_combat([Slime()])
        move = move_class(real_combat_player)
        assert move.viable(), f"{move.name} is not selectable in this fixture"
        real_combat_player.known_moves = [move]
        real_adapter.input_type = "move_selection"

        assert "error" not in real_adapter._handle_move_selection(0)

        # Off the WIRE, not off the attribute: what the client renders is
        # what `get_combat_state` put in the response.
        offered = real_adapter.get_combat_state()["battle_state"]["available_options"]
        assert offered == expected
        # A copy, not the module constant: a client-driven mutation of the
        # offered options must not edit the next fight's prompt.
        assert real_adapter.available_options is not expected

    def test_the_default_enemy_stands_where_its_target_card_is_viable(
        self, real_adapter, real_combat_player
    ):
        """``DEFAULT_ENEMY_DISTANCE`` carries a claim the key-only tests
        cannot see: the fixture enemy is in reach of the default move, which
        is what makes its card carry a hit chance and a damage preview, and
        makes ``in_range`` true on the combatant. Held to the two reaches the
        engine actually applies -- and since ``makeCombatant`` now DERIVES
        ``in_range`` from the item-use range rather than defaulting it, that
        threshold is held to the engine's constant here too."""
        assert js_literal(_PAYLOADS_JS, "ITEM_USE_RANGE") == ITEM_USE_RANGE
        distance = js_literal(_PAYLOADS_JS, "DEFAULT_ENEMY_DISTANCE")
        reach_min, reach_max = real_adapter._move_range(Attack(real_combat_player))

        # The REACH, which makeTargetOption derives `in_range` and
        # `shortfall_ft` from. Held separately from the distance above: the
        # two are equal today, and deriving one from the other would make this
        # a tautology that could not see the reach move.
        assert js_literal(_PAYLOADS_JS, "DEFAULT_MOVE_REACH_FT") == reach_max

        # Both ends: `_build_target_entry` reads the band as
        # ``range_min <= distance <= range_max``, and several weapons in
        # src/items.py open at 1, 2 or 3 feet rather than 0.
        assert reach_min <= distance <= reach_max, (reach_min, distance, reach_max)
        assert distance <= ITEM_USE_RANGE, (distance, ITEM_USE_RANGE)
