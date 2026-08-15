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
from src.items import Restorative, Shortbow
from src.moves import PowerStrike, ShootBow
from src.npc._enemies import Slime
from src.npc._merchants import Merchant
from src.player import Player
import src.states as states


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
        real_adapter.available_options = [{"id": f"enemy_{id(enemy)}"}]

        result = real_adapter.get_combat_state()

        _assert_contract(result["battle_state"], BATTLE_STATE_CONTRACT, "battle_state")

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

        result = gs.shop_sell(player, "npc1", str(id(item)), 1)

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
