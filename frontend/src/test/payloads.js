/**
 * Shared realistic API payload fixtures.
 *
 * === Why this module exists ===
 *
 * CLAUDE.md names *wire-field-name drift* as this codebase's dominant bug
 * class: the client reads a field name the Python serializer never emits.
 * Because reads sit behind `??`/`||` chains, the miss is swallowed silently
 * and the feature just quietly does nothing. Six have shipped
 * (`turn_number`, `combat_id`, `weight_tolerance`, `duration_remaining`,
 * `hit_chance` rescaled as a fraction, and `map_size`).
 *
 * > Every one was invisible to the suite because the test fixtures encoded
 * > the same wrong field name as the component — a mock cannot catch a mock
 * > agreeing with itself.
 *
 * A component test that hand-writes `{ battle_state: { turn: 1 } }` and then
 * asserts `combat.turn === 1` cannot fail, however wrong the component is:
 * `turn` is not a key any serializer emits. The fix is for every test that
 * consumes an API payload to derive its fixture from *one* module that
 * mirrors what the backend actually sends. Then one field rename breaks many
 * tests at once, which is the point.
 *
 * === Provenance ===
 *
 * Every shape below was captured by running the real serializer against real
 * engine objects, not written from memory. To re-derive after a serializer
 * change:
 *
 *   python -c "
 *   import json
 *   from unittest.mock import patch
 *   from src.player import Player
 *   from src.npc._enemies import Slime
 *   from src.api.combat_adapter import ApiCombatAdapter
 *   p = Player(); p.known_moves=[]; p.combat_log=[]; p.last_move_summary=''
 *   p.combat_beat=1; p.combat_list=[]; p.combat_list_allies=[p]
 *   p.combat_proximity={}; p.in_combat=True
 *   e = Slime()
 *   with patch('src.api.combat_adapter.CombatStrategist'):
 *       a = ApiCombatAdapter(p); a.initialize_combat([e])
 *   p.combat_list=[e]; p.combat_proximity={e:10}
 *   print(json.dumps(a.get_combat_state(), indent=1, default=str))"
 *
 * The Python-side guard that these names still exist is
 * tests/test_wire_field_contract.py — it builds the same real objects and
 * asserts the frontend's declared field list is a subset of what actually
 * comes back. This module is its client-side counterpart: the contract test
 * proves the *server* emits the names, this module makes the *tests* use them.
 *
 * === Usage ===
 *
 * Every factory takes an `overrides` object merged shallowly over the
 * realistic default, so a test states only the field it cares about:
 *
 *   makeBattleState({ awaiting_input: true, input_type: 'target_selection' })
 *
 * Do NOT add a field here that no serializer emits. If a component needs one,
 * either the serializer gains it (and this module follows) or the component
 * read is wrong.
 */

/** Shallow merge that keeps the factory call sites terse. */
const merge = (base, overrides) => ({ ...base, ...overrides })

// ---------------------------------------------------------------------------
// Status effects — CombatantSerializer._serialize_status_effects
//                  -> StateEffectSerializer.serialize_state
// ---------------------------------------------------------------------------
// NOTE the field is `beats_left`. `duration_remaining` comes from
// serialize_state_with_duration, which has no live callers — a fixture using
// it is the drift bug, not a legacy shape worth exercising.
export function makeStatusEffect(overrides = {}) {
  return merge(
    {
      name: 'Poisoned',
      type: 'ailment',
      description: 'Deals escalating HP damage every few beats. Worsens if reapplied.',
      severity: 'severe',
      beats_left: 127,
    },
    overrides
  )
}

// ---------------------------------------------------------------------------
// Combatant — CombatantSerializer.serialize_combatant
// ---------------------------------------------------------------------------
const RESISTANCES = Object.freeze({
  fire: 1.0, ice: 1.0, shock: 1.0, earth: 1.0, light: 1.0, dark: 1.0,
  piercing: 1.0, slashing: 1.0, crushing: 1.0, spiritual: 1.0, pure: 1.0,
})

export function makeCombatant(overrides = {}) {
  return merge(
    {
      id: 'player',
      in_range: true,
      name: 'Jean',
      battle_symbol: null,
      type: 'player',
      level: 1,
      health: { current: 100, max: 100 },
      hp: 100,
      max_hp: 100,
      fatigue: 190,
      max_fatigue: 190,
      maxfatigue: 190,
      heat: 1.0,
      stats: { damage: 1, speed: 10, accuracy: 108, evasion: 11, defense: 4, attack_power: 22 },
      attributes: {
        strength: 10, finesse: 11, speed: 10,
        endurance: 11, intelligence: 10, charisma: 9,
      },
      status_effects: [],
      passives: [],
      equipment: {
        weapon: { name: 'fists', damage: 1, damage_type: 'pure' },
        armor: { name: 'Tattered Cloth', protection: 1 },
        resistances: { ...RESISTANCES },
      },
      distance: 0,
      position: { x: 0, y: 3, facing: 'N' },
      current_move: null,
      move_in_process: null,
    },
    overrides
  )
}

/** An enemy combatant (same serializer, `type: 'npc'` and an `enemy_<id>` id). */
export function makeEnemy(overrides = {}) {
  return makeCombatant(
    merge(
      {
        id: 'enemy_1',
        name: 'Slime Ernerouchu',
        type: 'npc',
        health: { current: 20, max: 20 },
        hp: 20,
        max_hp: 20,
        fatigue: 100,
        max_fatigue: 100,
        maxfatigue: 100,
        stats: { damage: 26, speed: 10, accuracy: 108, evasion: 10, defense: 0, attack_power: 26 },
        attributes: {
          strength: 10, finesse: 10, speed: 10,
          endurance: 10, intelligence: 10, charisma: 10,
        },
        equipment: { weapon: null, armor: null, resistances: { ...RESISTANCES } },
        distance: 10,
        position: { x: 6, y: 3, facing: 'S' },
      },
      overrides
    )
  )
}

// ---------------------------------------------------------------------------
// battle_state — ApiCombatAdapter.get_combat_state()["battle_state"]
// ---------------------------------------------------------------------------
// Everything here reaches the client, because transformCombatData SPREADS
// battle_state. That is why new per-poll combat fields belong in here rather
// than at the top level (see COMBAT_TOP_LEVEL_WHITELIST below).
export function makeBattleState(overrides = {}) {
  const player = overrides.player ?? makeCombatant()
  const enemies = overrides.enemies ?? [makeEnemy()]
  return merge(
    {
      status: 'active',
      round: 1,
      beat: 1,
      current_turn_index: 0,
      turn_order: [player.id, enemies[0]?.id].filter(Boolean),
      combatants: [player, ...enemies],
      player,
      enemies,
      allies: [],
      heat: 100,
      awaiting_input: false,
      input_type: null,
      available_options: [],
      // `combat_id` identifies a FIGHT, not a call: it survives a reinit
      // (wave transition / reinforcement spawn) and changes only when a
      // genuinely new combat starts. BattlefieldGrid keys its camera-pan
      // reset on it.
      combat_id: 'fight-0001',
      // `map_size` rides inside battle_state precisely because the top-level
      // whitelist would have dropped it (drift bug #6).
      map_size: 9,
      player_consumables: [],
      suggested_moves: [],
      suggestions_loading: false,
      last_move_outcome: '',
      last_move_name: null,
      last_move_target_id: null,
    },
    overrides
  )
}

/**
 * The exact set of TOP-LEVEL keys `transformCombatData` (useApi.js) copies
 * through. Anything emitted at the top level of the combat payload and absent
 * from this list never reaches the client — the trap that caused two of the
 * six drift bugs. Kept here so a test can assert it rather than prose alone.
 */
export const COMBAT_TOP_LEVEL_WHITELIST = Object.freeze([
  'log',
  'beat_states',
  'end_state',
  'combat_active',
  'suggested_moves',
  'suggestions_loading',
  'events_triggered',
  'last_move_outcome',
  'last_move_name',
  'last_move_target_id',
])

/** The full get_combat_status() response body, i.e. what axios resolves with. */
export function makeCombatResponse(overrides = {}) {
  const { battle_state, ...rest } = overrides
  return merge(
    {
      battle_state: makeBattleState(battle_state),
      combat_active: true,
      log: [],
      beat_states: [],
      suggested_moves: [],
      suggestions_loading: false,
      last_move_outcome: '',
      last_move_name: null,
      last_move_target_id: null,
      map_size: 9,
    },
    rest
  )
}

// ---------------------------------------------------------------------------
// Target-selection cards — ApiCombatAdapter._get_available_targets
// ---------------------------------------------------------------------------
// `hit_chance` is an INTEGER PERCENTAGE, not a 0-1 fraction. Rescaling it
// client-side collapsed every real value to 0%-1% (drift bug #5).
export function makeTargetOption(overrides = {}) {
  return merge(
    {
      id: 'enemy_1',
      name: 'Slime Ernerouchu',
      distance: 10,
      health: { current: 20, max: 20 },
      hit_chance: 87,
    },
    overrides
  )
}

// ---------------------------------------------------------------------------
// Player payload — usePlayer() spreads status, then inventory, then stats,
// then skills (later keys win). GameService.get_player_status/_stats.
// ---------------------------------------------------------------------------
export function makePlayerStatus(overrides = {}) {
  return merge(
    {
      name: 'Jean',
      level: 1,
      exp: 0,
      max_exp: 150,
      exp_to_next_level: 150,
      pending_attribute_points: 0,
      pending_level_ups: [],
      hp: 100,
      max_hp: 100,
      fatigue: 190,
      max_fatigue: 190,
      gold: 15,
      weight: 1.15,
      max_weight: 30.5,
      weight_pct: 3.77,
      state: 'Normal',
      states: [],
      party_members: [],
    },
    overrides
  )
}

export function makePlayerStats(overrides = {}) {
  return merge(
    {
      strength: 10, strength_base: 10,
      finesse: 11, finesse_base: 10,
      speed: 10, speed_base: 10,
      endurance: 11, endurance_base: 10,
      charisma: 9, charisma_base: 10,
      intelligence: 10, intelligence_base: 10,
      faith: 11, faith_base: 10,
      hp: 100, max_hp: 100,
      fatigue: 190, max_fatigue: 190,
      // Carry capacity is `weight_current`/`carrying_capacity`/`max_weight`.
      // There is NO `weight_tolerance` key — that is the engine-side attribute
      // name, and reading it is drift bug #3.
      weight_current: 1.15,
      carrying_capacity: 30.5,
      weight: 1.15,
      max_weight: 30.5,
      gold: 15,
      protection: 4,
      attack_damage_min: 17,
      attack_damage_max: 26,
      hit_accuracy: 108,
      evasion_chance: 11,
      resistance: { ...RESISTANCES },
      // Note: a DIFFERENT shape from combat status_effects. get_player_stats
      // emits {name, steps_left} pairs, not serialize_state() dicts.
      states: [],
      status_resistance: {},
    },
    overrides
  )
}

/** The merged client-side `player` object usePlayer() produces. */
export function makePlayer(overrides = {}) {
  return merge({ ...makePlayerStatus(), inventory: [], ...makePlayerStats() }, overrides)
}

// ---------------------------------------------------------------------------
// Shop — ShopSerializer.serialize_state / serialize_player_sellable
// ---------------------------------------------------------------------------
export function makeShopBuyItem(overrides = {}) {
  return merge(
    {
      id: 'c0ffee00112233445566778899aabbcc',
      name: 'Restorative',
      type: 'Restorative',
      subtype: 'Potion',
      description: 'A strange pink fluid of questionable chemistry.',
      value: 100,
      price: 100,
      weight: 0.25,
      count: 2,
      is_stackable: true,
      power: 60,
      is_buyback: false,
      merchandise: true,
    },
    overrides
  )
}

export function makeShopSellItem(overrides = {}) {
  return merge(
    {
      id: 'dec0de00112233445566778899aabbcc',
      name: 'Restorative',
      type: 'Restorative',
      subtype: 'Potion',
      description: 'A strange pink fluid of questionable chemistry.',
      value: 100,
      offer: 50,
      weight: 0.25,
      count: 1,
      is_stackable: false,
      power: 60,
    },
    overrides
  )
}

export function makeShopState(overrides = {}) {
  return merge(
    {
      npc_id: 'feed0000112233445566778899aabbcc',
      npc_name: 'Jambo',
      shop_name: "Jambo's Shop",
      buy_modifier: 1.0,
      sell_modifier: 0.5,
      stock: [makeShopBuyItem()],
      buyback_items: [],
      merchant_gold: 500,
      player_gold: 15,
      player_weight_current: 1.15,
      player_weight_max: 30.5,
    },
    overrides
  )
}

// ---------------------------------------------------------------------------
// Room / location — GameService.get_current_location()["room"]
// ---------------------------------------------------------------------------
// The SERVER sends `exits` as a dict of direction -> {x, y}. useApi.js's
// transformLocationData normalises it to an array of direction names, which is
// the shape every component downstream sees. Both shapes are exported so a
// test can state which side of that boundary it is on.
export function makeRoomResponse(overrides = {}) {
  return merge(
    {
      x: 0,
      y: 0,
      name: 'Empty Cave',
      map_name: 'Dark Grotto',
      description: 'A cave, empty but for the drip of water.',
      exits: { north: { x: 0, y: -1 }, east: { x: 1, y: 0 } },
      items: [],
      npcs: [],
      objects: [],
      is_passable: true,
      bgm: null,
    },
    overrides
  )
}

/** Post-transformLocationData shape (what components actually receive). */
export function makeLocation(overrides = {}) {
  return merge({ ...makeRoomResponse(), exits: ['north', 'east'] }, overrides)
}

// ---------------------------------------------------------------------------
// Saves — GameService.list_saves() rows
// ---------------------------------------------------------------------------
// `timestamp` is the DISPLAY string ("%Y-%m-%d %H:%M:%S %Z"); `timestamp_ms`
// is the epoch field ordering must key on, because Date.parse returns Invalid
// Date for most non-US timezone abbreviations.
export function makeSaveRow(overrides = {}) {
  return merge(
    {
      id: 'save-1',
      name: 'MySave',
      timestamp: '2026-01-01 12:00:00 CET',
      timestamp_ms: Date.UTC(2026, 0, 1, 11, 0, 0),
      is_autosave: false,
      level: 5,
      map_name: 'Dark Grotto',
      room_title: 'Entry Hall',
      playtime: 300,
    },
    overrides
  )
}

// ---------------------------------------------------------------------------
// Skills — GameService.get_player_skills()["known_moves"]
// ---------------------------------------------------------------------------
// `category` must be one the engine actually emits, because CATEGORY_GROUPS
// (utils/categories.js) routes moves to radial buttons by it, and a category
// no group claims leaves the move with no button at all.
export function makeMove(overrides = {}) {
  return merge(
    {
      name: 'Attack',
      display_name: 'Attack',
      category: 'Offensive',
      description: 'A basic attack.',
      fatigue_cost: 5,
      beats_left: 0,
      xp_gain: 1,
    },
    overrides
  )
}

// ---------------------------------------------------------------------------
// NPC chat — src/npc/_chat_llm.py chat_open/chat_respond, enriched by
// GameService._enrich_chat_result_with_relationship. The Flask route returns
// the result dict verbatim (jsonify(result)), so `response.data` IS this shape.
// ---------------------------------------------------------------------------

/**
 * A Jean dialogue option. `tone` is one of exactly three values the engine
 * emits — `_qc_jean_options` coerces anything else into direct/guarded/open,
 * so a fixture inventing e.g. 'curious' describes a payload that cannot occur.
 */
export function makeJeanOption(overrides = {}) {
  return merge({ text: 'What else can you tell me?', tone: 'direct' }, overrides)
}

/** NPCRelationshipSerializer.serialize_relationship — the badge payload. */
export function makeRelationship(overrides = {}) {
  return merge(
    {
      npc_id: 'Mynx',
      npc_name: 'Mynx',
      reputation: 0,
      attitude: 'neutral',
      emoji: '😐',
      trust_level: 'Neutral',
    },
    overrides
  )
}

/**
 * POST /api/npc/chat/open response body.
 *
 * `conversation_ended` defaults to false because a normal opening turn is not
 * over — but `/open` is a genuine sender of `true`: `chat_open`'s loquacity
 * cutoff returns the NPC's brush-off line with no options and the flag set.
 * Both builders go through `_base_payload`, so every field here that
 * `makeNpcChatRespond` also carries takes the same range of values on both.
 */
export function makeNpcChatOpen(overrides = {}) {
  return merge(
    {
      success: true,
      npc_key: 'Mynx',
      npc_name: 'Mynx',
      npc_opening: 'Well, well. What do we have here?',
      jean_options: [
        makeJeanOption({ text: 'What is this place?', tone: 'direct' }),
        makeJeanOption({ text: "I'll keep that in mind.", tone: 'guarded' }),
      ],
      loquacity_current: 2,
      loquacity_max: 5,
      turn: 0,
      llm_available: true,
      conversation_ended: false,
      reputation: 0,
      relationship: makeRelationship(),
    },
    overrides
  )
}

/** POST /api/npc/chat/respond response body. Note `npc_response`, not `npc_opening`. */
export function makeNpcChatRespond(overrides = {}) {
  return merge(
    {
      success: true,
      npc_key: 'Mynx',
      npc_response: 'That depends on who is asking.',
      jean_options: [makeJeanOption({ text: 'Go on.', tone: 'direct' })],
      loquacity_current: 1,
      loquacity_max: 5,
      turn: 1,
      llm_available: true,
      conversation_ended: false,
      reputation: 0,
      reputation_delta: 0,
      relationship: makeRelationship(),
    },
    overrides
  )
}

// ---------------------------------------------------------------------------
// Inventory — InventoryItemSerializer.serialize (src/api/serializers/inventory.py)
// ---------------------------------------------------------------------------
// Two field names here are routinely mis-guessed:
//   * `id` is a STRING — an opaque 32-hex wire handle minted by
//     `src.combatant.wire_handle`, never an int and never the CPython heap
//     address it used to be (issues #511/#518). It is what
//     `get_item_and_index` resolves back, so a fixture that invents a
//     decimal id encodes a contract the serializer no longer has.
//   * the stack size is `quantity`; `count` is the engine-side attribute the
//     serializer reads FROM, and no inventory payload carries it.
// The weapon/armor blocks (`damage`/`str_mod`/`fin_mod`/`damage_type`,
// `protection`) are conditional on the item's type, and `bonuses`/
// `resistances`/`status_resistances`/`comparison`/`effects` appear only when
// non-empty — so a fixture that always includes them describes a payload the
// serializer cannot produce. Compose them explicitly per test instead.
export function makeInventoryItem(overrides = {}) {
  return merge(
    {
      id: '3f9c1d2a4b5e46f78a0c1d2e3f405162',
      index: 0,
      name: 'Rusty Dagger',
      type: 'Weapon',
      maintype: 'Weapon',
      subtype: 'Dagger',
      quantity: 1,
      rarity: 'common',
      weight: 1.0,
      value: 10,
      can_equip: true,
      can_use: false,
      can_read: false,
      can_drop: true,
      is_equipped: false,
      is_merchandise: false,
      description: 'A pitted, rust-flecked blade. It has seen better centuries.',
      damage: 5,
      str_mod: 0.1,
      fin_mod: 1.0,
      damage_type: 'piercing',
    },
    overrides
  )
}

/** A consumable inventory row: no weapon block, `effects`, can_use. */
export function makeConsumableItem(overrides = {}) {
  const { damage, str_mod, fin_mod, damage_type, ...base } = makeInventoryItem()
  return merge(
    {
      ...base,
      id: '7a1b2c3d4e5f4071829304a5b6c7d8e9',
      name: 'Restorative',
      type: 'Restorative',
      maintype: 'Consumable',
      subtype: 'Potion',
      description: 'A strange pink fluid of questionable chemistry.',
      value: 100,
      weight: 0.25,
      quantity: 2,
      can_equip: false,
      can_use: true,
      // Mirrors src/api/serializers/inventory.py::_CONSUMABLE_EFFECTS exactly.
      // There is no `amount` key -- the serializer emits {type, stat, power,
      // range}. This factory previously invented `amount`, which is the very
      // wire-field drift this module exists to prevent: ItemDetailDialog read
      // `stat`/`power` and rendered "Restores undefined Fatigue".
      effects: [{ type: 'heal', stat: 'hp', power: 60, range: [48, 72] }],
    },
    overrides
  )
}
