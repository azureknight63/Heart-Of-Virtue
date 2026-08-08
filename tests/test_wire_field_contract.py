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
``serialize_player_sellable`` via a real ``GameService.shop_sell`` call).

Deliberately NOT covered: the saves payload (``GameService.list_saves`` is
under concurrent revision elsewhere — encoding its shape here would just be
encoding a shape that's about to change).

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

from unittest.mock import patch

import pytest

from src.api.combat_adapter import ApiCombatAdapter
from src.api.serializers.combat import (
    CombatantSerializer,
    CombatStateSerializer,
    StateEffectSerializer,
)
from src.api.serializers.shop_serializer import ShopSerializer
from src.api.services.game_service import GameService
from src.items import Restorative
from src.moves import ShootBow
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
