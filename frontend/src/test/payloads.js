import { transformCombatData } from '../utils/combatTransform'

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
 *   p.combat_list=[e]; p.combat_proximity={e:5}  # == DEFAULT_ENEMY_DISTANCE
 *   print(json.dumps(a.get_combat_state(), indent=1, default=str))"
 *
 * The Python-side guard that these names still exist is
 * tests/test_wire_field_contract.py — it builds the same real objects and
 * asserts the frontend's declared field list is a subset of what actually
 * comes back. This module is its client-side counterpart: the contract test
 * proves the *server* emits the names, this module makes the *tests* use them.
 *
 * That guard PARSES this file (`_js_builder_keys`, and `js_literal` in
 * tests/_js_scan.py), which puts two constraints on what may be written here:
 * a builder's object literal must stay brace-balanced with its braces inside
 * the builder; no string value may contain `//` (comment stripping is a blunt
 * line-wise strip); and no comment between a builder's signature and its
 * `merge(` call may itself contain `merge(`, because the literal is located
 * on the raw source before comments are stripped. Breaking any of them fails
 * the contract test rather than passing quietly, but the failure will blame
 * the fixture, not the prose.
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

/**
 * The value of `key` a builder should emit: what the caller passed, or
 * `fallback` when the caller named no such key at all. `in` rather than `??`
 * or a default parameter, so a test that passes `key: undefined` gets exactly
 * that, an explicitly absent field, instead of silently getting the default
 * back. Every default another field is derived from goes through this, so the
 * rule is mechanical rather than retyped at each site.
 */
const provided = (overrides, key, fallback) => (key in overrides ? overrides[key] : fallback)

/**
 * The `name` a builder emits, which its `display_name` then follows: the
 * server derives both from one move, so a fixture whose display name belongs
 * to a different move describes no payload it can send.
 *
 * Following is the common case, not a rule of the wire: `display_name_of`
 * (src/moves/_base.py) prefers the class's own `display_name` and falls back
 * to `name`. No move Jean can cast diverges -- every one of them passes its
 * player-facing string as `name` ("Use Item", "Crusader's Oath"), and the
 * class-level `display_name` is what the NPC family uses instead: `NpcAttack`
 * declares `display_name = 'Attack'` (src/moves/_npc.py:126) over
 * `name="NPC_Attack"` (:164). That pair does reach the client, through
 * `_serialize_active_move` (src/api/serializers/combat.py:453), which emits
 * both keys for whatever an enemy is mid-swing on -- so a fixture for an
 * enemy's active move is the one that sets the two by hand.
 */
const nameFrom = (overrides, fallback) => provided(overrides, 'name', fallback)

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
// Passives — CombatantSerializer._serialize_passives
// ---------------------------------------------------------------------------
// NOT a status effect: {name, display_name, type, description, category},
// with no severity and no beats_left. The default is a real PassiveMove,
// ShadowStep (src/moves/_dagger.py), which keeps PassiveMove's default
// category. tests/test_wire_field_contract.py holds these keys to the
// serializer's.
export function makePassive(overrides = {}) {
  const name = nameFrom(overrides, 'Shadow Step')
  return merge(
    {
      name,
      display_name: name,
      type: 'passive',
      description:
        'Deliberate, silent footwork lets you approach without alerting targets. ' +
        'Your steps give nothing away.',
      category: 'Passive',
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

/**
 * How far a combatant can be and still be targetable with an item, and the
 * threshold `serialize_combatant` derives `in_range` from
 * (src/api/constants.py -> src/api/serializers/combat.py). Exported so
 * tests/test_wire_field_contract.py can hold this copy to the engine's.
 */
export const ITEM_USE_RANGE = 5

export function makeCombatant(overrides = {}) {
  // Three pairs the serializer builds from ONE engine value each, so no real
  // payload can carry them disagreeing (src/api/serializers/combat.py):
  // `health` is `{hp, maxhp}` restated, and `in_range` is
  // `distance <= ITEM_USE_RANGE`. Derived here rather than defaulted, because
  // a default only fixes the un-overridden case -- `makeCombatant({ hp: 20 })`
  // used to leave `health.current` at 100, and `{ distance: 25 }` used to
  // leave `in_range` true.
  const hp = provided(overrides, 'hp', 100)
  const maxHp = provided(overrides, 'max_hp', 100)
  const distance = provided(overrides, 'distance', 0)
  // `max_fatigue` and `maxfatigue` are the same engine attribute emitted
  // twice (`combatant.maxfatigue`), so they cannot disagree on the wire
  // either; a caller who sets one gets both.
  const maxFatigue = provided(overrides, 'maxfatigue', provided(overrides, 'max_fatigue', 190))
  return merge(
    {
      id: 'player',
      in_range: distance === undefined ? undefined : distance <= ITEM_USE_RANGE,
      name: 'Jean',
      battle_symbol: null,
      type: 'player',
      level: 1,
      health: { current: hp, max: maxHp },
      hp,
      max_hp: maxHp,
      fatigue: 190,
      max_fatigue: maxFatigue,
      maxfatigue: maxFatigue,
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
      distance,
      position: { x: 0, y: 3, facing: 'N' },
      current_move: null,
      move_in_process: null,
    },
    overrides
  )
}

/**
 * A combatant id in the shape `CombatantSerializer.stream_id` emits. The
 * scheme is three-way -- `player`, `ally_<handle>`, `enemy_<handle>` -- and
 * the PREFIX is the load-bearing half: the client keys the two sides apart by
 * it, and a combatant that changes sides changes id. The handle itself is an
 * opaque wire token, so a readable stand-in serves. New fixtures take ids
 * from here rather than spelling `enemy_2` by hand; a handful of older files
 * (Battlefield, BattlefieldGrid, GamePage) still spell theirs and are
 * unmigrated.
 */
export const enemyId = (n) => `enemy_${n}`
export const allyId = (n) => `ally_${n}`

// The one enemy every combat fixture defaults to: a Slime, as the provenance
// capture above spawns. makeEnemy (the battle-state combatant) and
// makeTargetOption (a target card naming it) both read these, so a default
// card cannot name a different enemy from the default fight's.
const DEFAULT_ENEMY_ID = enemyId(1)
const DEFAULT_ENEMY_NAME = 'Slime Ernerouchu'
const DEFAULT_ENEMY_HP = 20

// Where it stands. One value for both builders because one payload cannot
// carry two: the combatant card and the target card read the two reciprocal
// `combat_proximity` entries for the same pair, which the engine keeps in
// step. It sits at the far edge of the (0, 5) reach a weapon has by default
// (src/items.py), which is what lets the target card below carry
// `in_range: true`, a hit chance and a damage preview. Exported because
// tests/test_wire_field_contract.py reads it and holds it to the engine's
// real reaches.
// How far the default move reaches: Attack's `range_max`, the top of the
// (0, 5) band a weapon has by default (src/items.py). This is the threshold
// `_build_target_entry` compares a target's distance against, and
// tests/test_wire_field_contract.py holds it to the engine's own
// `_move_range`. Kept apart from DEFAULT_ENEMY_DISTANCE below even though the
// two are equal today: one is a reach, the other a position, and deriving
// "in range" from the position would make the test a tautology.
export const DEFAULT_MOVE_REACH_FT = 5

// A literal, not `= DEFAULT_MOVE_REACH_FT`: tests/_js_scan.py reads these
// with ast.literal_eval and cannot resolve a name. Both are pinned to the
// engine's own `_move_range` separately, which is the point -- the two facts
// are equal today and a test would have to notice if they stopped being.
export const DEFAULT_ENEMY_DISTANCE = 5

// The arena's width in tiles. Two builders carry it (the battle state and the
// whole response), and makeCombat routes an override into exactly one of
// them, so the two copies must start equal or a fixture is incoherent before
// any test touches it.
const DEFAULT_MAP_SIZE = 9

// Attack's fatigue cost, at the two readings that genuinely differ. Both are
// `move.fatigue_cost` off a real move -- the difference is WHICH move.
//
//   * 49 is what `Attack.evaluate` computes for the Jean captured above:
//     `max(10, ceil(70 + weight*wt_mult - 2*endurance))` is 48 at endurance
//     11 with weightless fists, and `_apply_carry_fatigue` rounds it up for
//     the 1.15 lb he carries. A move card is built from a move Jean is
//     holding now, so `_get_available_moves` ships this.
//   * 50 is what the moves in `Player().known_moves` carry: they were built
//     DURING `Player.__init__`, before endurance and carry weight settled,
//     and nothing re-evaluates them until Jean swings. `get_player_skills`
//     reads them as they stand, so a freshly loaded player's skills list
//     shows this.
//
// Both are exported and held to the engine by
// tests/test_wire_field_contract.py, because a key-set guard cannot see a
// wrong number and two review rounds proposed a wrong one from arithmetic.
export const ATTACK_CARD_FATIGUE_COST = 49
export const ATTACK_DECLARED_FATIGUE_COST = 50

// Jean's damage against that Slime. `lethal` is derived from the enemy's HP
// rather than typed, so raising DEFAULT_ENEMY_HP cannot leave a preview
// claiming a kill it could not land.
const DEFAULT_DAMAGE_PREVIEW = { min: 17, max: 26 }

/** An enemy combatant (same serializer, `type: 'npc'` and an `enemy_<id>` id). */
export function makeEnemy(overrides = {}) {
  return makeCombatant(
    merge(
      {
        id: DEFAULT_ENEMY_ID,
        name: DEFAULT_ENEMY_NAME,
        type: 'npc',
        hp: DEFAULT_ENEMY_HP,
        max_hp: DEFAULT_ENEMY_HP,
        fatigue: 100,
        maxfatigue: 100,
        stats: { damage: 26, speed: 10, accuracy: 108, evasion: 10, defense: 0, attack_power: 26 },
        attributes: {
          strength: 10, finesse: 10, speed: 10,
          endurance: 10, intelligence: 10, charisma: 10,
        },
        equipment: { weapon: null, armor: null, resistances: { ...RESISTANCES } },
        distance: DEFAULT_ENEMY_DISTANCE,
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
  const player = provided(overrides, 'player', makeCombatant())
  const enemies = provided(overrides, 'enemies', [makeEnemy()])
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
      map_size: DEFAULT_MAP_SIZE,
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
 * The exact set of TOP-LEVEL keys `transformCombatData`
 * (utils/combatTransform.js) copies through. Anything emitted at the top level
 * of the combat payload and absent from this list never reaches the client —
 * the trap that caused two of the six drift bugs. Kept here so a test can
 * assert it rather than prose alone.
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

/**
 * The client-side `combat` object useCombat hands the panels. Built by running
 * the real `transformCombatData` over `makeCombatResponse`, so it is exactly
 * what the client makes of a response, `battle_state` spread flat plus the
 * whitelisted top-level keys, and cannot drift from it. Components read THIS
 * shape, never the response body.
 *
 * Each override goes where the server would put it: a whitelisted top-level
 * key into the response body, everything else into `battle_state`. They used
 * to go into both, which let a fixture set `log` inside `battle_state` (a
 * place the adapter never sends it) and, worse, kept the fixture's value even
 * when the transform dropped the key -- the exact blindness this module
 * exists to remove.
 */
export function makeCombat(overrides = {}) {
  if ('battle_state' in overrides) {
    throw new Error(
      'makeCombat takes battle_state fields directly; passing `battle_state` ' +
      'nests it as battle_state.battle_state, a shape no response carries.'
    )
  }
  const topLevel = {}
  const battleState = {}
  for (const [key, value] of Object.entries(overrides)) {
    const target = COMBAT_TOP_LEVEL_WHITELIST.includes(key) ? topLevel : battleState
    target[key] = value
  }
  return transformCombatData(makeCombatResponse({ battle_state: battleState, ...topLevel }))
}

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
      map_size: DEFAULT_MAP_SIZE,
    },
    rest
  )
}

// ---------------------------------------------------------------------------
// Backend-driven input prompts -- ApiCombatAdapter._handle_move_selection
// ---------------------------------------------------------------------------
// These two land VERBATIM in `combat.available_options` when a move asks the
// player something instead of executing: the compass a Turn offers, and the
// duration a Wait offers. They are the adapter's own module constants
// (TURN_DIRECTIONS / WAIT_DURATION_PROMPT in src/api/combat_adapter.py), and
// tests/test_wire_field_contract.py holds these to them, so a renamed key or
// a changed bound cannot leave a green fixture behind. That guard reads the
// literal with `ast.literal_eval`, which is why the prompt's keys are quoted
// and both stay flat.
export const TURN_DIRECTIONS = ['north', 'south', 'east', 'west']

export const WAIT_DURATION_PROMPT = {
  'prompt': 'How many beats do you want to wait?',
  'min': 3,
  'max': 10,
  'default': 5,
}

// ---------------------------------------------------------------------------
// Unavailability reasons -- ApiCombatAdapter._get_available_moves
// ---------------------------------------------------------------------------
// Two of the sentences a move card's `reason` carries, which the panel renders
// verbatim. The adapter owns them as TOO_FAR_REASON and
// NOT_ENOUGH_FATIGUE_REASON, and tests/test_wire_field_contract.py holds these
// to those.
export const TOO_FAR_REASON = 'Enemy out of range (too far)'

export const NOT_ENOUGH_FATIGUE_REASON = 'Not enough fatigue'

// ---------------------------------------------------------------------------
// Target-selection cards — ApiCombatAdapter._build_target_entry, the one
// builder behind both _get_available_targets and _get_target_previews
// ---------------------------------------------------------------------------
// `hit_chance` is an INTEGER PERCENTAGE, not a 0-1 fraction. Rescaling it
// client-side collapsed every real value to 0%-1% (drift bug #5). The default
// is makeEnemy's Slime, at the same DEFAULT_ENEMY_DISTANCE and so within the
// default move's (Attack's) reach, so it carries what an in-reach entry
// carries: a hit chance, a damage preview, no shortfall.
// tests/test_wire_field_contract.py holds these keys to the builder's.
export function makeTargetOption(overrides = {}) {
  // Pulled through `provided` before the merge, the way makeCombatant and
  // makeAvailableOption do it, so the emitted shape reads off one expression.
  const health = provided(overrides, 'health', { current: DEFAULT_ENEMY_HP, max: DEFAULT_ENEMY_HP })
  const distance = provided(overrides, 'distance', DEFAULT_ENEMY_DISTANCE)
  // Reach, not taste: `_build_target_entry` sets `in_range` by comparing the
  // distance against the MOVE's band, so a card put past DEFAULT_MOVE_REACH_FT
  // is out of reach. An explicit `distance: undefined` stays absent, the rule
  // `index` and `display_name` follow, and leaves everything derived from it
  // absent too rather than inventing a NaN shortfall.
  const inRange = provided(
    overrides, 'in_range',
    distance === undefined ? undefined : distance <= DEFAULT_MOVE_REACH_FT
  )
  // Everything the adapter gates on `in_range`, gated here too, so a test that
  // moves a target out of reach gets the payload the server would send rather
  // than four overrides and a discarded destructure:
  //   * `shortfall_ft` is `int(distance - range_max)`, and None in reach;
  //   * `damage_preview` is the key present as null (never omitted);
  //   * `hit_chance` is the one field omitted OUTRIGHT -- including when the
  //     caller asked for one, because no out-of-reach entry carries it.
  // `lethal` inside the preview is the engine's own test, `high >= target.hp`
  // (Move.preview_payload in src/moves/_base.py), so a caller who raises the
  // target's health gets a preview that no longer claims a kill instead of
  // one contradicting its own health field.
  //
  // `damage_preview` is taken out of `overrides` before the merge on purpose:
  // it is already folded in through `provided` above, and leaving it in let
  // `merge` put the caller's raw object back over the derived one -- so
  // `makeTargetOption({ damage_preview: { min: 1, max: 2 } })` came back with
  // no `lethal` key at all, and kept its preview even out of reach.
  const { damage_preview: _derivedAbove, ...rest } = overrides
  const preview = inRange
    ? provided(overrides, 'damage_preview', { ...DEFAULT_DAMAGE_PREVIEW })
    : null
  const card = merge(
    {
      id: DEFAULT_ENEMY_ID,
      name: DEFAULT_ENEMY_NAME,
      distance,
      is_ally: false,
      health,
      in_range: inRange,
      // Truncated, as the adapter's `int()` truncates it: a fractional
      // distance would otherwise carry a fractional shortfall to the client.
      shortfall_ft: inRange || distance === undefined
        ? null
        : Math.trunc(distance - DEFAULT_MOVE_REACH_FT),
      damage_preview: preview && { ...preview, lethal: preview.max >= health?.current },
      hit_chance: 87,
    },
    rest
  )
  if (inRange !== false) return card
  // Omitted, not nulled, and dropped AFTER the merge rather than spread in
  // conditionally: `hit_chance` has to stay a literal key of the object above
  // or tests/test_wire_field_contract.py's reader cannot see it, and that
  // guard is what holds this builder to `_build_target_entry` at all.
  const { hit_chance: _omittedOutOfReach, ...outOfReach } = card
  return outOfReach
}

// ---------------------------------------------------------------------------
// Check-move rows -- one entry of `combat.check_data`, as
// Check._generate_api_check_data builds it (src/moves/_utility.py); the
// adapter passes it through battle_state.
// ---------------------------------------------------------------------------
// `facing` and `direction_from_player` are null for a combatant with no
// coordinate position, and `current_move` is null when nothing is in progress
// -- all three keys are always present. A combatant mid-move also carries
// `current_move_display_name` and `current_move_stage`; a test that needs
// those adds them. tests/test_wire_field_contract.py holds these keys to the
// move's own output.
export function makeCheckEntry(overrides = {}) {
  return merge(
    {
      name: DEFAULT_ENEMY_NAME,
      is_ally: false,
      distance: DEFAULT_ENEMY_DISTANCE,
      facing: null,
      direction_from_player: null,
      current_move: null,
    },
    overrides
  )
}

// ---------------------------------------------------------------------------
// Suggested moves -- one entry of `combat.suggested_moves`, as
// CombatStrategist emits it (ai/combat_strategist.py)
// ---------------------------------------------------------------------------
// Every suggestion carries a `score` and a `reasoning` -- the LLM path forces
// the score in too -- so a fixture with only the name and target describes a
// suggestion no strategist can send.
export function makeSuggestedMove(overrides = {}) {
  return merge(
    {
      move_name: 'Attack',
      target_id: null,
      score: 10,
      reasoning: 'Closest target, clean line.',
    },
    overrides
  )
}

/**
 * Two target cards, the smallest list the adapter will ask the player to
 * choose from (`requires_target_selection` is `is_targeted and
 * len(viable_targets) > 1`). Exported because a fixture that needs a real
 * choice needs exactly this, and three copies of it had already appeared.
 */
export function twoTargets() {
  return [
    makeTargetOption({ id: enemyId(1) }),
    makeTargetOption({ id: enemyId(2) }),
  ]
}

// ---------------------------------------------------------------------------
// Move cards — one entry of `combat.available_options`, exactly as
// ApiCombatAdapter._get_available_moves emits it (src/api/combat_adapter.py).
// ---------------------------------------------------------------------------
/**
 * Two details hand-written literals used to get wrong, which is the
 * fixture-agreeing-with-itself failure CLAUDE.md warns about:
 *   * `id` is a STRING (`str(i)`), never an int, and `index` is the same `i`
 *     as a number — so `index` is derived from `id` here rather than given
 *     a default of its own.
 *   * every gating field is always present — `available`, `targeted`,
 *     `viable_targets`, `requires_target_selection`, `cooldown_remaining` —
 *     so a fixture that omits one describes a payload the adapter cannot send.
 *
 * The default is the engine's Attack with one enemy in reach. Attack is a
 * targeted move (src/moves/_utility.py), so the card carries that enemy as
 * its one viable target and, with only one, needs no target selection. The
 * target lists follow `targeted`: the adapter fills `viable_targets` only for
 * a targeted move, and _get_target_previews returns [] for any other.
 */
export function makeAvailableOption(overrides = {}) {
  // Through `provided`, not `??`, for every default a later field derives
  // from: `index`, the target lists and the selection flag follow what the
  // card actually carries, an explicit undefined included.
  const id = provided(overrides, 'id', '0')
  const name = nameFrom(overrides, 'Attack')
  const targeted = provided(overrides, 'targeted', true)
  // Read once, as a boolean: `targeted: undefined` is a card the fixture may
  // deliberately build, and every field derived from it must then say `false`
  // rather than passing the undefined along.
  const isTargeted = Boolean(targeted)
  const viableTargets = provided(overrides, 'viable_targets', isTargeted ? [makeTargetOption()] : [])
  return merge(
    {
      id,
      index: id === undefined ? undefined : Number(id),
      name,
      display_name: name,
      description: 'A basic attack.',
      category: 'Offensive',
      fatigue_cost: ATTACK_CARD_FATIGUE_COST,
      available: true,
      reason: null,
      targeted,
      viable_targets: viableTargets,
      // Derived, as the adapter derives it (`is_targeted and
      // len(viable_targets) > 1`): a card listing two targets and claiming
      // it needs no selection is a payload _get_available_moves cannot send.
      requires_target_selection: isTargeted && viableTargets?.length > 1,
      cooldown_remaining: 0,
      cooldown_max: 0,
      // Display-only. _get_target_previews lists every living candidate of a
      // targeted move, in reach or not; by default that is exactly the viable
      // targets, i.e. every candidate is in reach. A test that wants one out
      // of reach sets this. _get_affected_previews fills only for an area
      // swing, and _range_ring is null for a move that does not outreach a
      // sword.
      target_previews: isTargeted && viableTargets ? [...viableTargets] : [],
      affected_preview: [],
      range_ring: null,
      // Attack's real stage timing (Move.stage_beat), the same values
      // tests/test_wire_field_contract.py pins against the engine.
      stage_beats: { prep: 4, execute: 1, recoil: 1, cooldown: 4 },
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
  const name = nameFrom(overrides, 'Attack')
  return merge(
    {
      name,
      display_name: name,
      category: 'Offensive',
      description: 'A basic attack.',
      fatigue_cost: ATTACK_DECLARED_FATIGUE_COST,
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
