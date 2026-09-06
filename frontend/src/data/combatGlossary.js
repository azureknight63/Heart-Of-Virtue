/**
 * combatGlossary.js — the single source of truth for combat-terminology copy.
 *
 * Issue #507 ("What the Heck are Beats?"): a player could not tell what a beat
 * was, and nothing on screen ever said. Both surfaces that answer that now —
 * the inline tooltip on a term and the full glossary panel — read from this
 * module, so the one-sentence version and the long version can never drift
 * apart into two copies of the same wording.
 *
 * Why data and not JSX: the copy states facts about the engine (cooldown
 * length, the heat clamp, the glance margin). Kept as data it stays greppable
 * and, more importantly, testable — `tests/test_combat_glossary_contract.py`
 * parses ENGINE_CONSTANTS below and asserts each value still matches the real
 * engine, so a balance change that moves a number breaks a test instead of
 * quietly making the glossary lie.
 *
 * Every definition here was derived from the engine, never invented. The
 * per-term source citations live in `docs/development/combat-glossary-mockup.html`
 * section 6.
 */

import { colors } from '../styles/theme'
import {
  HEAT_BANDS,
  HEAT_CEILING,
  HEAT_DECAY_PER_BEAT,
  HEAT_FLOOR,
} from '../utils/heat'

/**
 * Engine numbers quoted in the copy below.
 *
 * Each key names exactly one engine constant so the Python contract test can
 * check it. Do not add a key here that the copy does not use, and do not put a
 * number in the copy that is not sourced from here.
 */
export const ENGINE_CONSTANTS = {
  // src/moves/_utility.py — Rest.execute: ceil(maxfatigue * 0.4 * uniform(0.8, 1.2))
  restRecoveryFraction: 0.4,
  // src/player/_combat.py — change_heat clamps to [0.5, 10], and
  // src/api/combat_adapter.py — _update_heat closes 1/20th of the gap to 1.0
  // per beat. Both are owned by utils/heat.js, which the meter reads too;
  // re-exported here rather than re-typed so a balance change lands in one file.
  heatMin: HEAT_FLOOR,
  heatMax: HEAT_CEILING,
  heatDriftPercentPerBeat: HEAT_DECAY_PER_BEAT * 100,
  // src/moves/_base.py — cooldown = int(3 + weapon weight) - int(endurance / 10)
  cooldownWeightBase: 3,
  cooldownEnduranceDivisor: 10,
  // src/moves/_base.py — GLANCE_MARGIN
  glanceMargin: 10,
  // src/api/combat_adapter.py — MELEE_REACH_FT
  meleeReachFt: 6,
  // src/api/combat_adapter.py — ABORTABLE_MIN_PREP_BEATS
  abortableMinPrepBeats: 8,
  // src/moves/_movement.py — every mover clamps its own per-beat travel and
  // the caps are NOT uniform, so there is no single "movement cap" to quote:
  // Advance caps at 3 ft (:263-264), Withdraw at 2 ft (:428-429), and
  // BullCharge/TacticalRetreat/FlankingManeuver roll ranges of their own. Only
  // the two moves the copy actually names are declared here.
  stepMinFt: 1,
  advanceStepMaxFt: 3,
  withdrawStepMaxFt: 2,
}

/**
 * The "no category filter" sentinel, shared with the panel that renders the
 * chip for it. Exported rather than spelled 'all' at each site: it is compared
 * against `entry.category`, so a third spelling of it is a filter that silently
 * matches nothing. It is deliberately absent from GLOSSARY_CATEGORIES below —
 * that list stays the list of values an entry may actually carry, and
 * combatGlossary.test.js asserts no entry claims this one.
 */
export const ALL_CATEGORIES = 'all'

/**
 * Category chips, in the order the filter row shows them. `All` is not listed
 * here — the panel renders it itself so the list of real categories stays the
 * list of values an entry may carry.
 */
export const GLOSSARY_CATEGORIES = [
  { id: 'time', label: 'Time', color: colors.accent },
  { id: 'moves', label: 'Moves', color: colors.primary },
  { id: 'resources', label: 'Resources', color: colors.secondary },
  { id: 'position', label: 'Position', color: colors.gold },
  { id: 'damage', label: 'Damage', color: colors.danger },
  { id: 'effects', label: 'Effects', color: colors.special },
]

const CATEGORY_BY_ID = new Map(GLOSSARY_CATEGORIES.map(c => [c.id, c]))

export function glossaryCategory(id) {
  return CATEGORY_BY_ID.get(id) || null
}

/**
 * The entries.
 *
 * - `short` is the tooltip body: one or two sentences, no markup.
 * - `body` is the panel body: the full answer. Always an array joined at the
 *   end — `join('\n')` where the entry really is several paragraphs (the panel
 *   renders one <p> per line), `join(' ')` where it is one paragraph merely
 *   wrapped so a one-word copy edit reviews as a one-line diff.
 * - `tell` answers "how do I see this happening?" — the part that actually
 *   closes the player's question, and the reason the entries are grouped
 *   rather than alphabetised (a player who does not know what a beat is cannot
 *   look it up under B).
 * - `patterns` are the words that get a dotted underline when they appear in
 *   engine-authored text such as a move's unavailability reason. Source
 *   strings, not RegExp objects, so the module stays serialisable and the
 *   combined matcher can be built once.
 *
 *   **A pattern must not contain a capturing group.** MATCHER below wraps each
 *   ENTRY in exactly one group and attributes a match by which group matched,
 *   so one stray `(` shifts every later entry's group number: the wrong
 *   tooltip opens, or attribution runs off the end of this array entirely.
 *   Use `(?:…)` — as `break(?:ing)? off` does. Guarded from both sides, by
 *   combatGlossary.test.js and tests/test_combat_glossary_contract.py.
 *
 * Deliberate omissions, both confirmed open by the maintainer: a beat has no
 * in-fiction duration (the wording stays mechanical — no "about one heartbeat"
 * gloss), and Advance/Withdraw distance is a roll, stated as a range on purpose.
 */
export const GLOSSARY_ENTRIES = [
  {
    id: 'beat',
    term: 'Beat',
    category: 'time',
    patterns: ['beats?'],
    short: 'The unit of combat time. On every beat each move in play advances one step, the enemies act, status effects tick down, and heat drifts back toward neutral.',
    body: [
      'The unit of combat time. Fights are measured in beats, not turns.',
      'On every beat, each move in play advances one step, the enemies act, status effects tick down,',
      'and heat drifts back toward neutral — then the beat counter goes up.',
    ].join(' '),
    tell: 'You will know a beat has passed when the BEAT counter above the battlefield ticks up. Outside combat, effects count down in steps — one per room you walk into — instead.',
  },
  {
    id: 'stages',
    term: 'The four stages',
    category: 'moves',
    patterns: ['prep', 'execute', 'recoil'],
    short: 'Every move runs Prep, Execute, Recoil, Cooldown — each lasting a set number of beats.',
    // The four labels are the ones CombatMovePanel's STAGE_LABELS puts on the
    // commitment bar; tests/test_combat_glossary_contract.py reads that map out
    // of the component and fails if this list stops naming what is on screen.
    body: [
      'Every move runs through four stages, each lasting a set number of beats.',
      'Prep — winding up; nothing has happened yet and a long wind-up can still be broken off.',
      'Execute — the move lands.',
      'Recoil — the backswing: the hit has landed, but you are still committed and cannot act until it finishes.',
      'Cooldown — you are free to act again, but this move is locked out.',
    ].join('\n'),
    tell: 'The four-segment bar on a move card is those stages, in that order. Its length compares that move’s total commitment against the heaviest move in the list.',
  },
  {
    id: 'cooldown',
    term: 'Cooldown',
    category: 'moves',
    patterns: ['cool ?downs?'],
    short: 'The last of a move’s four stages. Only that one move is locked out — everything else stays usable.',
    body: [
      'The last of a move’s four stages. Only that move is unavailable — everything else stays usable,',
      'which is why the card says "Available in 5 beats" rather than stopping you from acting.',
      `For a standard weapon attack the length is roughly ${ENGINE_CONSTANTS.cooldownWeightBase} + weapon weight − (endurance ÷ ${ENGINE_CONSTANTS.cooldownEnduranceDivisor}) beats,`,
      'plus the move’s own modifier and never below zero: heavier weapons cool slower, and endurance shortens every cooldown you have.',
    ].join(' '),
    tell: 'Moves cooling down are stacked in the COOLDOWN tray on the left panel, each showing the beats it still needs before you can use it again. Hover the tray to expand it.',
  },
  {
    id: 'fatigue',
    term: 'Fatigue (FP)',
    category: 'resources',
    patterns: ['fatigue'],
    short: 'The orange bar — what moves are paid for. It does not regenerate on its own during a fight.',
    body: [
      'The orange bar: what moves are paid for. It does not regenerate on its own during a fight.',
      `Rest recovers roughly ${Math.round(ENGINE_CONSTANTS.restRecoveryFraction * 100)}% of your maximum, some items restore it,`,
      'and winning a fight refills it completely — nothing else gives it back.',
    ].join(' '),
    tell: 'Endurance raises your maximum fatigue; carrying too much weight lowers it. "Jean recovered 60 FP!" in the log is fatigue points.',
  },
  {
    id: 'heat',
    term: 'Heat',
    category: 'resources',
    patterns: ['heat'],
    short: 'A multiplier on most of the damage Jean deals. Landing hits pushes it up, getting hit pulls it down, and it drifts back toward neutral every beat.',
    body: [
      'A multiplier on most of the damage Jean deals — shown as 1.62×.',
      'A few moves land flat and ignore it.',
      'Landing hits, parrying, and making enemies miss push it up; missing, being parried, and taking hits pull it down.',
      `It closes ${ENGINE_CONSTANTS.heatDriftPercentPerBeat}% of the gap back to 1.00× every beat, so it is a lease, not a bank.`,
      `It never leaves the range ${ENGINE_CONSTANTS.heatMin.toFixed(2)}×–${ENGINE_CONSTANTS.heatMax.toFixed(2)}×, and only Jean has one.`,
    ].join(' '),
    // Quotes the meter's on-screen heading, which reads HEAT since the
    // Momentum -> Heat rename: the engine stat, the wire field, this entry and
    // the caption are now one word. If the caption in HeatMeter.jsx ever moves
    // again, this line moves with it.
    //
    // The band names are BUILT from HEAT_BANDS, never retyped: an em-dash list
    // reads as exhaustive, and naming three of the five bands told a player
    // sitting in BROKEN or PRESSING something the meter beside them denied.
    tell: `The HEAT meter under the hero on the left panel shows the live multiplier and names the band you are in — ${HEAT_BANDS.map(band => band.label).join(', ')} — and, expanded, lists exactly what raises and lowers it.`,
  },
  {
    id: 'distance',
    term: 'Distance & reach',
    category: 'position',
    patterns: ['ranges?', 'reach', 'distance'],
    short: 'One grid square is about one foot. Every move has a minimum and maximum reach; a target outside it greys the move out.',
    // Two facts the earlier wording got wrong, both verified in the engine:
    // the adapter greys a move out whenever NOTHING sits inside [range_min,
    // range_max] — too close counts as much as too far — and the quoted string
    // is only one of two it can emit ("No valid target in range" is the other,
    // for any move reaching past 5 ft), hence "a range reason such as".
    body: [
      'The battlefield is a grid where one square is about one foot, and the "18 ft" under an enemy is the straight-line distance to them.',
      'Every move has a minimum and a maximum reach in feet; when nothing is inside that band — too far off, or drawn in too close for a long weapon —',
      'the move greys out with a range reason such as "Enemy out of range (too far)".',
      `Advancing covers roughly ${ENGINE_CONSTANTS.stepMinFt} to ${ENGINE_CONSTANTS.advanceStepMaxFt} feet per beat and withdrawing ${ENGINE_CONSTANTS.stepMinFt} to ${ENGINE_CONSTANTS.withdrawStepMaxFt},`,
      'depending on how much faster you are than what you are chasing.',
    ].join(' '),
    tell: `Moves that reach further than a sword — past ${ENGINE_CONSTANTS.meleeReachFt} ft — draw their range as a ring around Jean.`,
  },
  {
    id: 'protection',
    term: 'Protection & resistance',
    category: 'damage',
    patterns: ['protections?', 'resistances?'],
    short: 'Resistance scales an incoming blow, then protection is subtracted from it as a flat amount, and heat is applied to what is left.',
    // The mockup said this reads "Defense" on the stat panel; it does not —
    // StatsPanel labels the row "Protection", which is also the engine's own
    // name for it. Guarded by StatsPanel.test.jsx.
    body: [
      'A blow’s power is first scaled by the target’s resistance to that kind of damage (1.0 is neutral; lower resists more),',
      'then their protection is subtracted as a flat amount, and heat is applied to what is left.',
      'It is the "Protection" row on the stat panel.',
    ].join(' '),
    tell: 'A blow that never gets past protection reads as "struck … but did no damage".',
  },
  {
    id: 'hitChance',
    term: 'Hit chance',
    category: 'damage',
    patterns: ['hit chance', 'accuracy', 'evasion'],
    short: 'A percentage: your accuracy — a base value plus your finesse and intelligence — minus the target’s finesse, adjusted for the situation.',
    body: [
      'A percentage — your accuracy (a base value plus your finesse and intelligence) minus the target’s finesse, adjusted for the situation.',
      // The engine glances on `hit_chance - roll < GLANCE_MARGIN`, strictly, so
      // a roll exactly GLANCE_MARGIN under still lands as a full hit: "within
      // N points under" was one point too generous.
      `If the roll comes in under your hit chance by fewer than ${ENGINE_CONSTANTS.glanceMargin} points the blow only grazes and deals half damage;`,
      'the log calls that "just barely hit".',
    ].join(' '),
    tell: 'Target cards preview the hit chance before you commit the beats.',
  },
  {
    id: 'statusEffect',
    term: 'Status effect vs. passive',
    category: 'effects',
    patterns: ['status effects?', 'passives?'],
    short: 'A status effect is temporary and carries a duration in beats. A passive is a permanent trait from a skill you have learned.',
    body: [
      'A status effect is temporary and carries a duration in beats;',
      'it ticks down one per beat while you fight (one per step while you explore) and then falls off.',
      'A passive is a permanent trait from a skill you have learned — always on, never expires.',
    ].join(' '),
    tell: 'Status effects sit in the STATUS column beside the hero; passives in the PASSIVES column.',
  },
  {
    id: 'abort',
    term: 'Breaking off (abort)',
    category: 'moves',
    patterns: ['break(?:ing)? off', 'aborts?'],
    short: 'A move with a long wind-up can be abandoned mid-prep. The beats already spent are gone and you still pay the full cooldown.',
    body: [
      `While a move is still winding up you can hold the amber control to abandon it — but only a move whose prep runs ${ENGINE_CONSTANTS.abortableMinPrepBeats} beats or longer offers the control at all;`,
      'anything shorter is over before you could react to it.',
      'This is not an undo: the beats already spent are gone, and you still pay the move’s full cooldown before you can use it again.',
    ].join(' '),
    tell: 'The control only exists while a long move is in prep — that is the only window in which the move has not yet happened.',
  },
]

const ENTRY_BY_ID = new Map(GLOSSARY_ENTRIES.map(e => [e.id, e]))

export function getGlossaryEntry(id) {
  return ENTRY_BY_ID.get(id) || null
}

/**
 * The haystack `filterGlossaryEntries` searches, lowercased once at module
 * load rather than per entry per keystroke: the entries are immutable, and the
 * panel re-filters on every character the player types.
 */
const SEARCH_HAYSTACK = new Map(
  GLOSSARY_ENTRIES.map(e => [e.id, `${e.term} ${e.body} ${e.tell}`.toLowerCase()])
)

/**
 * Filter for the panel. Search matches the term name, the body and the tell —
 * a player searching "backswing" should land on the stages entry even though
 * the word is not in its title.
 *
 * An absent category means "no filter": the default only covers `undefined`,
 * so null and '' are normalised here too rather than filtering everything out.
 */
export function filterGlossaryEntries({ category = ALL_CATEGORIES, query = '' } = {}) {
  const wanted = category || ALL_CATEGORIES
  const needle = query.trim().toLowerCase()
  return GLOSSARY_ENTRIES.filter(entry => {
    if (wanted !== ALL_CATEGORIES && entry.category !== wanted) return false
    if (!needle) return true
    return SEARCH_HAYSTACK.get(entry.id).includes(needle)
  })
}

// One alternation over every entry's patterns, each entry in its own capture
// group so a match can be attributed back to an entry without a second pass.
// Built once: this runs over every unavailability reason on every combat poll.
//
// The group-per-entry numbering is the whole attribution scheme, so no pattern
// may open a capturing group of its own — see the `patterns` note above.
const MATCHER = new RegExp(
  GLOSSARY_ENTRIES.map(e => `(\\b(?:${e.patterns.join('|')})\\b)`).join('|'),
  'gi'
)

/**
 * The entry a match belongs to: the first group that participated names it,
 * because group i + 1 is GLOSSARY_ENTRIES[i] by MATCHER's construction.
 *
 * Returns null rather than throwing if that correspondence has been broken (a
 * pattern that opened its own capturing group renumbers everything after it,
 * and can index past the end of the array). This runs inside render, on every
 * unavailability reason of every combat poll, so the failure mode has to be a
 * term that renders as plain text — not a TypeError that blanks the combat
 * panel mid-fight.
 */
function entryIdForMatch(match) {
  for (let group = 1; group < match.length; group += 1) {
    if (match[group] !== undefined) return GLOSSARY_ENTRIES[group - 1]?.id ?? null
  }
  return null
}

/**
 * Split engine-authored text into plain runs and glossary-term runs.
 *
 * Returns `[{ text }, { text, entryId }, …]`. Callers render the second kind as
 * an interactive term. Text with no terms in it comes back as a single plain
 * run, so a caller can render it exactly as it rendered the raw string before.
 */
export function splitTextByGlossaryTerms(text) {
  if (typeof text !== 'string' || text === '') return []
  const segments = []
  let cursor = 0
  // Guards a future early `break`/`return` from this loop, which would leave
  // the shared matcher parked mid-string and make the NEXT call start from
  // there. The `while` runs to null today, which resets it — do not delete
  // this on the strength of that.
  MATCHER.lastIndex = 0
  let match
  while ((match = MATCHER.exec(text)) !== null) {
    // A zero-length match would spin the loop forever; no pattern can produce
    // one today, but the guard costs nothing next to a frozen combat screen.
    if (match[0] === '') {
      MATCHER.lastIndex += 1
      continue
    }
    if (match.index > cursor) segments.push({ text: text.slice(cursor, match.index) })
    const entryId = entryIdForMatch(match)
    segments.push(entryId ? { text: match[0], entryId } : { text: match[0] })
    cursor = match.index + match[0].length
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor) })
  return segments
}
