/**
 * Player-facing copy for the post-combat loot flow.
 *
 * Its own module, not an export of GamePage or useCombatCoordinator: a page
 * that exports a constant loses Vite fast refresh, and the page tests mock
 * useCombatCoordinator wholesale, so a constant living there would read as
 * `undefined` in the component and the assertion alike — a test agreeing
 * with itself.
 */

/** Shown when the backend refuses a collect without saying why. */
export const LOOT_COLLECT_REFUSED = 'The spoils could not be collected.'
