/**
 * The mobile tab contract, shared by `MobileTabBar` (which renders the tabs)
 * and `GamePage` (whose `panelWrap()` compares `activeTab` against these to
 * decide which panel is visible).
 *
 * The keys address GamePage's two panel slots and must NOT vary by mode:
 * emitting mode-specific keys ('combat'/'battlefield') once matched neither
 * slot, hid BOTH panels, and left the player staring at a blank screen
 * mid-combat. Only the tab *labels* change with mode.
 *
 * Defined here rather than in `MobileTabBar.jsx` because this is a contract
 * *between* the two modules, and the component is mocked wholesale in
 * `GamePage.handlers.test.jsx`. A constant exported from the component
 * resolves to `undefined` under that mock, so the consumer breaks in a suite
 * that isn't testing it. Nothing mocks this file.
 */
export const TAB_KEYS = { left: 'character', right: 'map' }
