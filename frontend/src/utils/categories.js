import { colors } from '../styles/theme'

/**
 * Canonical move category → solid color. Used for borders, text, and progress bars.
 * Keys match the category strings returned by the backend API (_get_available_moves).
 * Fallback: colors.text.muted
 */
// NOTE for reviewers: `Special` and `Supernatural` appear in the three style
// maps below but no engine move currently emits either category, so those
// entries are unreachable today. They are kept deliberately — moves of those
// categories are planned once the current beta work lands, and the styling is
// already agreed. tests/test_move_categories_ui_contract.py guards
// CATEGORY_GROUPS (the button routing) and does NOT reach these maps, so it
// will not flag them; that is intended, not an oversight. Drop them only if
// the plan changes.
export const MOVE_CATEGORY_COLOR = {
  Offensive:    colors.danger,
  Defensive:    colors.primary,
  Maneuver:     colors.primary,
  Mastery:      colors.special,
  Special:      colors.special,
  Supernatural: colors.info,
  Tactical:     colors.special,
  Miscellaneous: colors.gold,
  Utility:      colors.gold,
}

/**
 * Move category → alpha glow color. Used for CSS-var-driven pulsing halos on
 * the battlefield grid. Slightly higher opacity than the border color.
 */
export const MOVE_CATEGORY_GLOW = {
  Offensive:    colors.alpha.danger[80],
  Defensive:    colors.alpha.primary[80],
  Maneuver:     colors.alpha.primary[80],
  Mastery:      colors.alpha.special[80],
  Special:      colors.alpha.special[80],
  Supernatural: colors.alpha.info[80],
  Tactical:     colors.alpha.special[80],
  Miscellaneous: `${colors.text.bright}CC`,
  Utility:      `${colors.text.bright}CC`,
}

/**
 * Move category → Unicode icon for compact display (cooldown chips, etc.).
 * Fallback: '◈'
 */
export const MOVE_CATEGORY_ICON = {
  Offensive:    '⚔',
  Defensive:    '◈',
  Maneuver:     '↯',
  Mastery:      '✦',
  Special:      '✦',
  Supernatural: '⬡',
  Tactical:     '✦',
  Miscellaneous: '◈',
  Utility:      '◈',
}

/**
 * Look a category up in one of the maps above, ignoring inherited members.
 *
 * A bare `map[category]` resolves Object.prototype keys, so a category of
 * `"constructor"` or `"toString"` yields a *function* — which is truthy, so it
 * does not fall through to the fallback, it defeats it. The value then reaches
 * a style property that silently discards it, and the caller loses the default
 * it thought it had. `getAnimationConfig` guards the same way.
 */
const lookup = (map, category, fallback) =>
  (typeof category === 'string' && Object.hasOwn(map, category)) ? map[category] : fallback

/** Solid color for a category, falling back to muted text color. */
export function categoryColor(category) {
  return lookup(MOVE_CATEGORY_COLOR, category, colors.text.muted)
}

/** Icon character for a category, falling back to '◈'. */
export function categoryIcon(category) {
  return lookup(MOVE_CATEGORY_ICON, category, '◈')
}

/**
 * Color / glow for a category, or `null` when it has none.
 *
 * These are the shape a caller needs when the *absence* of a category color
 * selects a different rendering — an alignment border, an alignment halo —
 * rather than a default color. The `||`-fallback variants above return a
 * truthy value in that case (`colors.text.muted`, `'transparent'`) and would
 * silently pick the wrong branch.
 */
export function categoryColorOrNull(category) {
  return lookup(MOVE_CATEGORY_COLOR, category, null)
}

export function categoryGlowOrNull(category) {
  return lookup(MOVE_CATEGORY_GLOW, category, null)
}

/**
 * The accessible name of the combat category nav.
 *
 * Exported because it is a CONTRACT, not decoration: `categoryNavContract.test.jsx`
 * and `LeftPanel.categoryNavStacking.test.jsx` both build a
 * `document.querySelectorAll` from `CATEGORY_NAV_SELECTOR` below to find the
 * REAL nav buttons HeroPanel renders, rather than a stand-in with the same
 * hard-coded string — a rename here cannot silently pass while the tests find
 * nothing, the way a mock built from the same literal would let it.
 *
 * Until issue #575 this selector also backed `useOccludedNavHandoff`, which
 * hit-tested it to hand back clicks CombatMovePanel's flyout occluded (#557).
 * That hook is retired: #575 raises the nav's real stacking context above the
 * flyout (LeftPanel.jsx's `HERO_PANEL_STACKING_Z_INDEX`) instead of hit-testing
 * around the occlusion, so the nav can no longer be covered in the first
 * place.
 */
export const CATEGORY_NAV_LABEL = 'Game actions'

/** The selector the nav-identity tests above hit-test against. Derived, never retyped. */
export const CATEGORY_NAV_SELECTOR = `nav[aria-label="${CATEGORY_NAV_LABEL}"] button`

/**
 * Combat radial button group → the engine move categories it collects.
 *
 * SINGLE SOURCE OF TRUTH for which radial button a move appears under. Both
 * LeftPanel (which buttons to show) and CombatMovePanel (which moves the opened
 * panel lists) read this map — do not re-implement the grouping anywhere else.
 * The keys are the existing HeroPanel button keys/labels; the values are the
 * `category` strings the engine actually emits (grep `category=` in src/moves/).
 *
 * MISC is the catch-all for the low-volume categories (Miscellaneous, Utility,
 * Tactical), which do not each warrant their own radial button.
 *
 * `Passive` is absent by design: PassiveMove subclasses are never castable, so
 * they need no button. Every other category the engine emits must appear here —
 * tests/test_move_categories_ui_contract.py fails if one does not.
 */
export const CATEGORY_GROUPS = {
  Offensive: ['Offensive'],
  Maneuver: ['Maneuver'],
  Defensive: ['Defensive'],
  Special: ['Mastery'],
  Miscellaneous: ['Miscellaneous', 'Utility', 'Tactical'],
}

/**
 * The moves belonging to a radial button group. Returns [] for an unknown group
 * or a non-array `moves`, so a mis-keyed group renders the empty state rather
 * than leaking every move.
 */
export function movesInGroup(moves, group) {
  const categories = CATEGORY_GROUPS[group]
  if (!categories || !Array.isArray(moves)) return []
  return moves.filter((move) => categories.includes(move?.category))
}

/** Whether any move belongs to a radial button group (gates the button). */
export function groupHasMoves(moves, group) {
  return movesInGroup(moves, group).length > 0
}
