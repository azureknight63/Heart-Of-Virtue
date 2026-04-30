import { colors } from '../styles/theme'

/**
 * Canonical move category → solid color. Used for borders, text, and progress bars.
 * Keys match the category strings returned by the backend API (_get_available_moves).
 * Fallback: colors.text.muted
 */
export const MOVE_CATEGORY_COLOR = {
  Offensive:    colors.danger,
  Defensive:    colors.primary,
  Maneuver:     colors.primary,
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
  Special:      '✦',
  Supernatural: '⬡',
  Tactical:     '✦',
  Miscellaneous: '◈',
  Utility:      '◈',
}

/** Solid color for a category, falling back to muted text color. */
export function categoryColor(category) {
  return MOVE_CATEGORY_COLOR[category] || colors.text.muted
}

/** Glow color for a category, falling back to transparent. */
export function categoryGlow(category) {
  return MOVE_CATEGORY_GLOW[category] || 'transparent'
}

/** Icon character for a category, falling back to '◈'. */
export function categoryIcon(category) {
  return MOVE_CATEGORY_ICON[category] || '◈'
}
