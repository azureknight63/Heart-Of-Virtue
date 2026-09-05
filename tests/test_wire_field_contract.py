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

=== How to read a failure ===

Each contract below is a ``{field: "<component file:line> — how it's read"}``
dict, built by grepping the frontend files named in each section, not
invented. If a test here fails:

- If the serializer/GameService method genuinely renamed or dropped the
  field, either restore it (if the frontend still needs it) or update the
  frontend read and remove the field from the contract dict *with a comment
  explaining why the read is gone*.
- If the frontend simply no longer reads a field, remove it from the
  contract dict (with the same explanation).
- Never "fix" a failure by loosening the assertion to skip missing fields —
  that defeats the point of the guard.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.combat_adapter import ApiCombatAdapter
from src.api.serializers.combat import (
    CombatantSerializer,
    CombatStateSerializer,
    StateEffectSerializer,
)
from src.api.serializers.shop_serializer import ShopSerializer
from src.api.services.game_service import GameService
from src.items import IronArrow, Mace, Restorative, Shortbow
from src.moves import Attack, PowerStrike, ShootBow, Wait
from src.moves._mastery import BloodOfMartyrs
from src.npc._enemies import Slime
from src.npc._merchants import Merchant
from src.player import Player
import src.states as states
from tests._gs_fixtures import GRID_3X3
from src.narration import capture_narration
from src.combatant import wire_handle


def _assert_contract(payload: dict, contract: dict, label: str):
    """Assert every field the frontend reads is present in the real payload.

    Failure message names the missing fields, what read them, and what to do —
    this is the guard's entire value, so the message has to be actionable
    without the reader re-deriving the citation trail themselves.
    """
    missing = {field: why for field, why in contract.items() if field not in payload}
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
# useApi.js's transformCombatData(data) becomes the client-side `combat`
# object: `{...data.battle_state, log, beat_states, end_state, combat_active,
# suggested_moves, suggestions_loading, events_triggered, last_move_outcome,
# last_move_name, last_move_target_id}`. Fields NOT in that explicit whitelist
# and NOT inside battle_state are silently dropped by the spread — that is
# exactly how `combat_id` disappeared in bug #1 (frontend/src/hooks/useApi.js).

# Fields useApi.js pulls off the top-level get_combat_state() result, outside
# battle_state (frontend/src/hooks/useApi.js transformCombatData).
COMBAT_TOP_LEVEL_CONTRACT = {
    "battle_state": "useApi.js transformCombatData spreads ...data.battle_state",
    "log": "useApi.js:11 log: data.log || []",
    "combat_active": "useApi.js:13 combat_active: data.combat_active",
    "suggested_moves": "useApi.js:14 suggested_moves: data.suggested_moves || []",
    "suggestions_loading": "useApi.js:15 suggestions_loading: data.suggestions_loading || false",
    "last_move_outcome": "useApi.js:17 last_move_outcome: data.last_move_outcome || \"\"",
    "last_move_name": "useApi.js:18 last_move_name: data.last_move_name || null",
    "last_move_target_id": "useApi.js:19 last_move_target_id: data.last_move_target_id || null",
}

# Fields LeftPanel.jsx/CombatManager read off `combat.*`, i.e. off
# battle_state after the spread (frontend/src/components/LeftPanel.jsx).
BATTLE_STATE_CONTRACT = {
    # LeftPanel.jsx:85 — `[combat?.round, combat?.beat]` useEffect deps, with
    # an explicit comment that these replaced the nonexistent turn_number/
    # combat_id (bug #1).
    "round": "LeftPanel.jsx:85 useEffect([combat?.round, combat?.beat])",
    "beat": "LeftPanel.jsx:85 useEffect([combat?.round, combat?.beat])",
    "player": "LeftPanel.jsx:134-137 activePlayer = {...player, ...combat.player}",
    "enemies": "LeftPanel.jsx:129-131 combat.enemies.every(e => (e.distance ?? 0) >= 20)",
    "awaiting_input": "LeftPanel.jsx:125 combat?.awaiting_input",
    "input_type": "LeftPanel.jsx:293/488 combat?.input_type / combat.input_type",
    "available_options": "LeftPanel.jsx:287,720 combat?.available_options",
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
    "combat_id": "Battlefield.jsx passes combat?.combat_id -> BattlefieldGrid combatId prop",
    # map_size was the sixth instance of the drift bug and this dict is why it
    # survived: the adapter emitted it at the TOP LEVEL, transformCombatData's
    # whitelist does not list it, and neither contract dict declared it — so
    # `combat?.map_size` was permanently undefined and BattlefieldGrid fell
    # back to deriving the arena from the bounding box of current positions.
    # It now rides in battle_state, which the spread carries.
    "map_size": "Battlefield.jsx passes combat?.map_size -> BattlefieldGrid mapSize prop",
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
    "name": "CombatMovePanel.jsx:75 move.name || move.display_name",
    "display_name": "CombatMovePanel.jsx:75,131 displayNameOf(move)",
    "description": "CombatMovePanel.jsx:140 move.description",
    "available": "CombatMovePanel.jsx:73 move.available !== false",
    # Its *wording* is load-bearing too, not just its presence: the reason line
    # renders through GlossaryText, which only attaches the "what is a beat?"
    # explainer (#507) to words combatGlossary.js recognises. Rewording
    # "Available in 5 beats" would leave this contract green while silently
    # removing the explainer — tests/test_combat_glossary_contract.py runs the
    # real reason strings against the glossary's own patterns to catch that.
    "reason": "CombatMovePanel.jsx move.reason (rendered by GlossaryText)",
    "fatigue_cost": "CombatMovePanel.jsx:133-137 move.fatigue_cost",
    "targeted": "CombatMovePanel.jsx:80 move.targeted",
    "viable_targets": "CombatMovePanel.jsx:79-82 move.viable_targets",
    "requires_target_selection": "CombatMovePanel.jsx:80 move.requires_target_selection",
    # `category` routes the move to a radial button via CATEGORY_GROUPS
    # (utils/categories.js). A category no group claims leaves the move with no
    # button at all — that is how 8 castable moves became unreachable.
    "category": "CooldownTray.jsx:66,100 / BattlefieldGrid.jsx:89 move.category",
    # The commitment bar (how many beats a move locks the player out for,
    # shown BEFORE they commit) — named sub-fields, not the engine's raw
    # stage_beat list/index convention. See MOVE_STAGE_BEATS_CONTRACT below.
    "stage_beats": "CombatMovePanel.jsx MoveCommitmentBar move.stage_beats",
}

ABORTABLE_MOVE_CONTRACT = {
    "name": "AbortMoveControl.jsx abortable.name",
    "beats_left": "AbortMoveControl.jsx abortable.beats_left ('lands in N beats')",
    "beats_invested": "AbortMoveControl.jsx abortable.beats_invested ('forfeits N beats')",
    "cooldown_beats": "AbortMoveControl.jsx abortable.cooldown_beats ('then N beats cooldown')",
    "prep_beats": "AbortMoveControl.jsx destructures abortable (unused today, kept on the wire)",
}


MOVE_STAGE_BEATS_CONTRACT = {
    "prep": "CombatMovePanel.jsx MoveCommitmentBar stageBeats.prep",
    "execute": "CombatMovePanel.jsx MoveCommitmentBar stageBeats.execute",
    "recoil": "CombatMovePanel.jsx MoveCommitmentBar stageBeats.recoil",
    "cooldown": "CombatMovePanel.jsx MoveCommitmentBar stageBeats.cooldown",
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
    "id": "LeftPanel.jsx:768,773 e.id (matching enemies against last_move_target_id)",
    "hp": "HeroPanel.jsx:33 player?.hp",
    "max_hp": "HeroPanel.jsx:34 player?.max_hp",
    "fatigue": "HeroPanel.jsx:37 player?.fatigue",
    "max_fatigue": "HeroPanel.jsx:38 player?.max_fatigue",
    "status_effects": "HeroPanel.jsx:130-133,338-341 player?.status_effects",
    "passives": "HeroPanel.jsx:109-113,332-336 player?.passives",
    "distance": "LeftPanel.jsx:131 e.distance (canFlee check on combat.enemies)",
    # The battlefield map is the other consumer of a serialized combatant. It
    # was reading `position`/`current_move` all along; `distance` is now shown
    # there too (token tooltip, selected-combatant panel, enemies list and the
    # off-screen edge markers), which is what the positional layer is *for*.
    "name": "BattlefieldGrid.jsx EntityTooltip / EnemiesList entity.name",
    "battle_symbol": "BattlefieldGrid.jsx entitiesToRender displaySymbol fallback chain",
    "position": "BattlefieldGrid.jsx getPos(entity) -> getEntityStyle / fitBox framing",
    "current_move": "BattlefieldGrid.jsx CombatantMarker telegraph + EntityTooltip",
    # Heat meter. This is the RAW FLOAT multiplier applied to Jean's damage
    # by src/moves/_base.py standard_execute_attack.
    #
    # battle_state carries a SECOND, different representation of the same
    # quantity under its own top-level `heat` key — int(player.heat * 100), set
    # by ApiCombatAdapter.get_combat_state and absent from the per-beat states
    # the adapter serializes at combat_adapter.py:1338. Reading that one as a
    # multiplier renders "162.00x"; reading this one is correct. The client has
    # exactly one reader and no `??` chain across the two (see the header
    # comment in frontend/src/utils/heat.js), which is the only reason the
    # duplication is survivable.
    "heat": "LeftPanel.jsx combat?.player?.heat -> HeatMeter (utils/heat.js)",
}

# The in-progress move hanging off a combatant (CombatantSerializer.
# _serialize_active_move). BattlefieldGrid turns this into the *only* readout
# of enemy intent on the map, so a rename here silently blanks the telegraph.
ACTIVE_MOVE_CONTRACT = {
    "display_name": "combatMoveStatus.js displayNameOf(move)",
    "category": "BattlefieldGrid.jsx MOVE_CATEGORY_GLOW/_COLOR[move.category]",
    # isMovePending() suppresses the telegraph for stages 2/3 so a spent
    # combatant stops looking like one winding up; beatsUntilResolve() renders
    # the countdown badge on the token.
    "current_stage": "combatMoveStatus.js isMovePending / formatCombatMoveStatus",
    "beats_left": "combatMoveStatus.js beatsUntilResolve fallback (stage-less payloads)",
    # The countdown badge renders THIS, not beats_left: the latter is beats
    # left in the current stage, which for a windup move is a much smaller
    # number than the time until the blow actually lands.
    "beats_until_resolve": "combatMoveStatus.js beatsUntilResolve -> countdown badge",
    "falloff": "BattlefieldGrid.jsx RangeRingLayer — gradient vs hard ring",
    # Threat-line/range-ring feature: who the pending move is aimed at, and
    # how far it reaches. target_id MUST be resolved through
    # CombatantSerializer.stream_id (see _serialize_move_target_id) or the
    # frontend can never match it against a combatant's own `id` — the same
    # drift class this whole file exists to catch.
    "target_id": "BattlefieldGrid.jsx ThreatLineLayer entity.current_move.target_id",
    "mvrange": "BattlefieldGrid.jsx RangeRingLayer entity.current_move.mvrange",
}

# StatusEffectsIconPanel.jsx renders each element of status_effects/passives.
STATE_EFFECT_CONTRACT = {
    "name": "StatusEffectsIconPanel.jsx:48,98 effect.name",
    "type": "StatusEffectsIconPanel.jsx:26-33,55 getEffectColor(effect.type)",
    "description": "StatusEffectsIconPanel.jsx:101 effect.description",
    # Bug #3: this component used to read `duration_remaining`, which only
    # serialize_state_with_duration (no callers) emits. The live path is
    # serialize_state -> beats_left (StatusEffectsIconPanel.jsx:103-107).
    "beats_left": "StatusEffectsIconPanel.jsx:107,115 effect.beats_left ?? effect.duration_remaining",
}

# CombatInputDialog's target_selection cards (combat_adapter._get_available_targets).
TARGET_CONTRACT = {
    "id": "CombatInputDialog.jsx:46,60 target.id",
    "name": "CombatInputDialog.jsx:63 target.name",
    "distance": "CombatInputDialog.jsx:64-68 target.distance",
    "health": "CombatInputDialog.jsx:72-82 target.health.current / target.health.max",
    # Bug #4: hit_chance is an already-integer percentage (see
    # ShootBow.calculate_hit_chance) — CombatInputDialog.jsx:86-92 explicitly
    # does NOT rescale it. If the engine ever starts sending a 0-1 fraction
    # instead, that comment (and this contract) goes stale silently unless
    # something asserts the magnitude, which the dedicated test below does.
    "hit_chance": "CombatInputDialog.jsx:83-92 target.hit_chance (used unscaled)",
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
        `heat` key is int(heat * 100) — so pin the multiplier form here.

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

PLAYER_STATUS_CONTRACT = {
    "hp": "HeroPanel.jsx:33 / StatsPanel.jsx:37 player.hp",
    "max_hp": "HeroPanel.jsx:34 / StatsPanel.jsx:37 player.max_hp",
    "fatigue": "HeroPanel.jsx:37 / StatsPanel.jsx:38 player.fatigue",
    "max_fatigue": "HeroPanel.jsx:38 / StatsPanel.jsx:38 player.max_fatigue",
    "level": "StatsPanel.jsx:40 player.level",
    "exp": "StatsPanel.jsx:114,120,127 player.exp",
    "max_exp": "StatsPanel.jsx:109,114,120,127 player.max_exp",
}

PLAYER_STATS_CONTRACT = {
    "protection": "StatsPanel.jsx:39 player.protection",
    "attack_damage_min": "StatsPanel.jsx:41 player.attack_damage_min",
    "attack_damage_max": "StatsPanel.jsx:41 player.attack_damage_max",
    "hit_accuracy": "StatsPanel.jsx:34,47,51 player.hit_accuracy",
    "evasion_chance": "StatsPanel.jsx:56 player.evasion_chance",
    "resistance": "StatsPanel.jsx:29 player.resistance",
    "states": "StatsPanel.jsx:30,205-217 player.states",
    # Bug #2: ShopDialog used to read `weight_tolerance` (the engine-side
    # attribute name) off the player payload. Neither get_player_status nor
    # get_player_stats ever emitted that key — the real keys are below
    # (ShopDialog.jsx:308-314, itemUtils.js docstring on WEIGHT_UNIT).
    "weight_current": "ShopDialog.jsx:308 player?.weight_current",
    "max_weight": "ShopDialog.jsx:313 player?.max_weight",
    "carrying_capacity": "ShopDialog.jsx:314 player?.carrying_capacity (fallback)",
}

# Each element of player.states (StatsPanel.jsx:215 state.steps_left) — note
# this is a *different* shape from the combat status_effects/beats_left
# contract above: get_player_stats's states list is a plain
# {name, steps_left} pair, not a StateEffectSerializer.serialize_state() dict.
PLAYER_STATE_ITEM_CONTRACT = {
    "name": "StatsPanel.jsx:214 state.name",
    "steps_left": "StatsPanel.jsx:215 state.steps_left",
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
# Shop payload
# ============================================================================
# ShopDialog.jsx reads `shopState.*` (GameService.shop_buy/sell/get_shop_state
# -> ShopSerializer.serialize_state) and item fields off both the buy list
# (stock + buyback_items) and the sell list (serialize_player_sellable).

SHOP_STATE_CONTRACT = {
    "shop_name": "ShopDialog.jsx:402 shopState?.shop_name",
    "sell_modifier": "ShopDialog.jsx:711 shopState?.sell_modifier",
    "stock": "ShopDialog.jsx:282,406 shopState.stock",
    "buyback_items": "ShopDialog.jsx:282,405,578 shopState.buyback_items",
    "merchant_gold": "ShopDialog.jsx:317 shopState?.merchant_gold",
    "player_gold": "ShopDialog.jsx:308 shopState?.player_gold",
    "player_weight_current": "ShopDialog.jsx:309 shopState?.player_weight_current",
    "player_weight_max": "ShopDialog.jsx:313 shopState?.player_weight_max",
}

# Fields read off a buy-tab item (stock or buyback_items — both flow through
# `allBuyItems` in ShopDialog.jsx and are treated identically).
SHOP_BUY_ITEM_CONTRACT = {
    "id": "ShopDialog.jsx:288 list.find(i => i.id === selectedId)",
    "name": "ShopDialog.jsx (item cards render selectedItem.name)",
    "price": "ShopDialog.jsx:322 selectedItem.price",
    "weight": "ShopDialog.jsx:299 selectedItem.weight",
    "count": "ShopDialog.jsx:292 selectedItem.count (buyback effectiveQty)",
    "is_buyback": "ShopDialog.jsx:292 selectedItem?.is_buyback",
}

# Fields read off a sell-tab item (ShopSerializer.serialize_player_sellable).
SHOP_SELL_ITEM_CONTRACT = {
    "id": "ShopDialog.jsx:288 list.find(i => i.id === selectedId)",
    "name": "ShopDialog.jsx (item cards render selectedItem.name)",
    "offer": "ShopDialog.jsx:326 selectedItem.offer",
    "weight": "ShopDialog.jsx:299 selectedItem.weight",
    "count": "ShopDialog.jsx sell quantity picker",
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
    "id": "MainMenuPage.jsx:405,408,412,454 save.id (row key, load/delete target)",
    "name": "MainMenuPage.jsx:440 save.name || 'Untitled Save'",
    "is_autosave": "MainMenuPage.jsx:442 save.is_autosave && <(Autosave)>",
    "level": "MainMenuPage.jsx:447 Lvl {save.level}",
    "map_name": "MainMenuPage.jsx:447 save.map_name",
    "room_title": "MainMenuPage.jsx:447 save.room_title",
    "timestamp": "MainMenuPage.jsx:450 formatSaveTimestamp(save)",
    # This is the field the "Continue" button's recency sort now keys on
    # (localSave.js saveRowClockValue: row?.timestamp_ms ?? row?.timestamp,
    # consumed by compareSavesByRecency at MainMenuPage.jsx:88,93). It was
    # added alongside the display `timestamp`
    # specifically because `timestamp`'s embedded timezone abbreviation (e.g.
    # "CET") is unparseable by Date.parse for most non-US zones — losing this
    # field silently regresses "Continue" back to that timezone bug.
    "timestamp_ms": "localSave.js:52 saveRowClockValue: row?.timestamp_ms",
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

ROOM_CONTRACT = {
    "x": "MapGrid.jsx:93,98,208 location.x; GamePage.jsx:190 tile cache key",
    "y": "MapGrid.jsx:94,98,209 location.y; GamePage.jsx:190 tile cache key",
    "name": "CollapsibleRoomDescription.jsx:56 location.name || 'Current Location'",
    "map_name": "MapGrid.jsx:97,188 location.map_name (grid title + tile key)",
    "description": "RoomContents.jsx:61 location.description",
    "exits": "useApi.js:28-30 transformLocationData normalises room.exits -> [direction]",
    "items": "useApi.js:31 items: room.items ? [...room.items] : []",
    "npcs": "useApi.js:32 npcs: room.npcs ? [...room.npcs] : []",
    "objects": "useApi.js:33 objects: room.objects ? [...room.objects] : []",
    "bgm": "GamePage.jsx:423 const track = location?.bgm || 'adventure'",
}

# Room items flow through ItemSerializer.serialize_list -> RoomContents /
# InteractPanel target cards.
ROOM_ITEM_CONTRACT = {
    "id": "RoomContents.jsx:44 id: item.id; InteractPanel.jsx:491 takeOne(item.id, …)",
    "name": "RoomContents.jsx:38,42 item.name",
    "announce": "RoomContents.jsx:38 item.announce || `There is a ${item.name} here.`",
    "count": "InteractPanel.jsx:486 item.count > 1 ? `x${item.count}` : ''",
    "hidden": "InteractPanel.jsx:83 allTargets.filter(t => !t.hidden)",
    "keywords": "InteractPanel.jsx:512 selectedTarget.keywords.length > 0",
}

# Room NPCs flow through NPCSerializer.serialize_list.
ROOM_NPC_CONTRACT = {
    "id": "InteractPanel.jsx:339 key={`${target.id}-${idx}`}",
    "name": "RoomContents.jsx:28 name: npc.name",
    "type": "InteractPanel.jsx:78 npc_class: n.type -> NpcChatPanel npcId",
    "idle_message": "RoomContents.jsx:24,27 if (npc.idle_message) …",
    "llm_chat_enabled": "InteractPanel.jsx:192 selectedTarget?.llm_chat_enabled",
    "loquacity_available": "InteractPanel.jsx:193 selectedTarget?.loquacity_available !== false",
}

# Room objects flow through ObjectSerializer.serialize_list.
ROOM_OBJECT_CONTRACT = {
    "id": "InteractPanel.jsx:339 key={`${target.id}-${idx}`}",
    "name": "RoomContents.jsx:54 name: obj.name",
    "idle_message": "RoomContents.jsx:50,53 if (obj.idle_message) …",
    "keywords": "InteractPanel.jsx:62,512 objectState.keywords ?? prev.keywords",
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
    "id": "InventoryDialog.jsx:258,280 key={item.id}; ItemDetailDialog.jsx:104 item_id",
    "name": "InventoryDialog.jsx:407 {item.name}",
    "type": "ItemDetailDialog.jsx item.type",
    "maintype": "InventoryDialog.jsx / ItemDetailDialog.jsx item.maintype (slot grouping)",
    "subtype": "InventoryDialog.jsx / ItemDetailDialog.jsx item.subtype",
    "quantity": "InventoryDialog.jsx item.quantity (stack count badge)",
    "rarity": "InventoryDialog.jsx item.rarity (row colour)",
    "weight": "InventoryDialog.jsx item.weight",
    "value": "InventoryDialog.jsx item.value",
    "is_equipped": "InventoryDialog.jsx item.is_equipped; ItemDetailDialog.jsx:159",
    "is_merchandise": "ItemDetailDialog.jsx item.is_merchandise",
    "description": "ItemDetailDialog.jsx:489,502 item.description",
    "can_equip": "ItemDetailDialog.jsx item.can_equip (Equip button gate)",
    "can_use": "ItemDetailDialog.jsx item.can_use (Use button gate)",
    "can_read": "ItemDetailDialog.jsx item.can_read (Read button gate)",
    "can_drop": "ItemDetailDialog.jsx item.can_drop (Drop button gate)",
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
    "known_moves": "CombatMovePanel.jsx move list source",
    "skill_tree": "SkillsPanel.jsx:31,85,149 skills.skill_tree",
    "skill_exp": "SkillsPanel.jsx:32,86,135 skills.skill_exp",
}

# The skills panel's move list is a DIFFERENT payload from the combat move list
# above: get_player_skills() emits the at-a-glance fields (xp_gain, beats_left),
# while _get_available_moves() emits the per-beat combat gating fields
# (available/reason/targeted/stage_beats). Keeping one name for both let the
# later definition shadow the earlier one, so whichever test ran against the
# survivor was silently asserting the wrong contract.
KNOWN_MOVE_CONTRACT = {
    "name": "CombatMovePanel.jsx:75 move.name || move.display_name",
    "display_name": "CombatMovePanel.jsx:75 move.display_name",
    # `category` routes the move to a radial button via CATEGORY_GROUPS
    # (utils/categories.js). A category no group claims leaves the move with no
    # button at all — that is how 8 castable moves became unreachable.
    "category": "CooldownTray.jsx:66,100 / BattlefieldGrid.jsx:89 move.category",
    "description": "CombatMovePanel.jsx move tooltip",
    "fatigue_cost": "CombatMovePanel.jsx:133-135 move.fatigue_cost > 0",
    "beats_left": "CooldownTray.jsx cooldown countdown",
    "xp_gain": "SkillsPanel/CombatMovePanel move xp readout",
}

SKILL_TREE_ENTRY_CONTRACT = {
    "name": "SkillsPanel.jsx:175 handleLearn(skill.name, selectedCategory)",
    "display_name": "SkillsPanel.jsx skill card title",
    "description": "SkillsPanel.jsx:186 {skill.description}",
    "required_exp": "SkillsPanel.jsx:180,191 LEARN ({skill.required_exp})",
    "is_known": "SkillsPanel.jsx:151,161,167,173 skill.is_known",
    "can_learn": "SkillsPanel.jsx:176,177,189 skill.can_learn",
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
def _assert_opaque(wire_id, label):
    assert wire_id, f"{label} emitted an empty id"
    assert not str(wire_id).isdigit(), (
        f"{label} emitted {wire_id!r} — a decimal heap address. Wire ids are "
        "opaque handles (src.combatant.wire_handle); see issue #518."
    )


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

    def test_a_room_npc_id_resolves_back_through_interact_with_target(self):
        player, _ = self._room()
        gs = GameService()

        npc_id = gs.get_current_room(player)["npcs"][0]["id"]
        _assert_opaque(npc_id, "room npcs[0].id")

        result = gs.interact_with_target(player, npc_id, "look")

        assert result["message"] != "Target not found.", (
            "the id get_current_room published did not resolve"
        )

    def test_a_room_npc_id_is_what_start_combat_matches_on(self):
        """InteractPanel's Attack button posts the room id to /combat/start."""
        player, tile = self._room()
        gs = GameService()

        npc_id = gs.get_current_room(player)["npcs"][0]["id"]
        with capture_narration():
            result = gs.start_combat(player, npc_id)

        assert "error" not in result, result

    def test_a_room_object_id_resolves_back_through_interact_with_target(self):
        player, _ = self._room()
        gs = GameService()

        obj_id = gs.get_current_room(player)["objects"][0]["id"]
        _assert_opaque(obj_id, "room objects[0].id")

        result = gs.interact_with_target(player, obj_id, "look")

        assert result["message"] != "Target not found."

    def test_a_floor_item_id_resolves_back_through_interact_with_target(self):
        player, _ = self._room()
        gs = GameService()

        item_id = gs.get_current_room(player)["items"][0]["id"]
        _assert_opaque(item_id, "room items[0].id")

        result = gs.interact_with_target(player, item_id, "look")

        assert result["message"] != "Target not found."

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
        from tests._gs_fixtures import live_world

        player, game_map = live_world(coords=GRID_3X3, start=(0, 0))
        merchant = Merchant(
            name="Tester", description="desc", damage=1, aggro=False,
            exp_award=0, stock_count=0,
        )
        merchant.inventory = [Restorative(count=2, merchandise=True)]
        game_map[(0, 0)].npcs_here = [merchant]
        gs = GameService()

        npc_id = ShopSerializer.serialize_state(merchant, player, 0)["npc_id"]
        _assert_opaque(npc_id, "shop_state.npc_id")

        assert gs._find_merchant(player, npc_id) is merchant

    def test_a_stock_item_id_is_what_shop_buy_matches_on(self):
        from tests._gs_fixtures import live_world, set_player_gold

        player, game_map = live_world(coords=GRID_3X3, start=(0, 0))
        set_player_gold(player, 500)
        merchant = Merchant(
            name="Tester", description="desc", damage=1, aggro=False,
            exp_award=0, stock_count=0,
        )
        stock = Restorative(count=2, merchandise=True)
        merchant.inventory = [stock]
        game_map[(0, 0)].npcs_here = [merchant]
        gs = GameService()

        state = ShopSerializer.serialize_state(merchant, player, 0)
        item_id = state["stock"][0]["id"]
        _assert_opaque(item_id, "shop_state.stock[0].id")

        result = gs.shop_buy(player, state["npc_id"], item_id, 1)

        assert result["success"], result.get("error")

    def test_a_sell_row_id_is_what_shop_sell_matches_on(self):
        from tests._gs_fixtures import live_world

        player, game_map = live_world(coords=GRID_3X3, start=(0, 0))
        goods = Restorative()
        goods.value = 10
        player.inventory = [goods]
        merchant = Merchant(
            name="Tester", description="desc", damage=1, aggro=False,
            exp_award=0, stock_count=0,
        )
        merchant.update_goods()
        game_map[(0, 0)].npcs_here = [merchant]
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
        from tests._gs_fixtures import live_world, set_player_gold

        player, game_map = live_world(coords=GRID_3X3, start=(0, 0))
        set_player_gold(player, 500)
        goods = Restorative()
        goods.value = 10
        player.inventory.append(goods)
        merchant = Merchant(
            name="Tester", description="desc", damage=1, aggro=False,
            exp_award=0, stock_count=0,
        )
        merchant.update_goods()
        game_map[(0, 0)].npcs_here = [merchant]
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
