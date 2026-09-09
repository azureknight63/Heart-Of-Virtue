import { useEffect } from 'react'
import { CATEGORY_NAV_SELECTOR } from '../utils/categories'

// A click that lands on any of these inside the panel is the panel's own
// business, whatever it happens to be covering.
//
// EDITING RULE, because `useOccludedNavHandoff` reads this as an inverse: any
// new clickable element in this panel MUST match this selector — a <button>,
// or `role="button"`/`tabindex` on whatever you used instead. A plain
// `<div onClick>` is treated as inert chrome, and its clicks are swallowed
// (stopPropagation, so React's delegated handler never runs) and forwarded to
// HeroPanel's category nav wherever the two overlap. Nothing throws.
const PANEL_CONTROL_SELECTOR = 'button, a, input, select, textarea, [role="button"], [tabindex]';

/**
 * The category nav button under a viewport point, or null.
 *
 * Read, never written: this panel needs to know where HeroPanel's radial
 * category buttons ARE, and must not reach into HeroPanel to restyle them.
 * The selector itself is owned by `utils/categories.js` so a rename of the
 * nav's accessible name cannot silently retire the handoff.
 */
function categoryNavButtonAt(clientX, clientY) {
    if (typeof clientX !== 'number' || typeof clientY !== 'number') return null;
    for (const button of document.querySelectorAll(CATEGORY_NAV_SELECTOR)) {
        const rect = button.getBoundingClientRect();
        // A zero-sized rect means the button is not laid out (or jsdom gave up
        // on it); treating a point as "inside" it would hand every click to a
        // button nobody can see.
        if (rect.width <= 0 || rect.height <= 0) continue;
        if (clientX >= rect.left && clientX <= rect.right && clientY >= rect.top && clientY <= rect.bottom) {
            return button;
        }
    }
    return null;
}

/**
 * Give back the category-tab clicks this flyout steals (issue #557).
 *
 * The panel is `zIndex: 100` and centered over the whole left column; the
 * category buttons it opens from are `zIndex: 5` inside HeroPanel's hero-head
 * box, which sits in that same region. So a player who clicks a *different*
 * category tab while a panel is open hits the panel instead, and nothing at
 * all happens — a hit-test at the tab's centre reports the panel on top. The
 * handler that would have done the right thing already exists
 * (`LeftPanel.handleCombatMoveClick` swaps the open category, or closes the
 * panel when the same tab is clicked twice); it simply never hears the click.
 *
 * Raising the nav bar's z-index would be the structural fix, but it lives in
 * HeroPanel — so the panel takes responsibility for what it occludes instead:
 * on a click that lands on the panel's own inert chrome, hit-test the category
 * buttons and, if one is underneath, activate it.
 *
 * Only inert chrome is forwarded. Where the panel has its own control at that
 * point the intent is genuinely ambiguous, and a click that both cast a move
 * and switched category would be far worse than one dead click — so the
 * panel's control wins, and a tab fully covered by a move card stays occluded
 * until the nav bar is raised above the panel.
 *
 * `click`, deliberately, and not `pointerdown`: pointerdown is the FIRST event
 * of the gesture, and stopping it does not stop the mousedown/mouseup/click
 * that follow. Forwarding there swapped the open category and then let the
 * trailing click land on whatever the *replacement* panel had put under the
 * pointer — a move card, at which point one tap both switched category and
 * cast a move. Click is the last event of the gesture, so there is nothing
 * left behind it to misfire.
 */
export function useOccludedNavHandoff(contentRef) {
    useEffect(() => {
        // GamePanel accepts no ref, so the ref sits on the header row and the
        // panel ROOT — whose padding ring is exactly the inert chrome the
        // reported hit-test landed on — is resolved from it.
        const content = contentRef.current;
        const panel = content?.closest('.game-panel') ?? content;
        if (!panel) return undefined;

        // Deliberately NOT gated on `event.isTrusted`, though a scrub pass
        // suggested it: this synthesises an activation from raw coordinates,
        // so in principle an untrusted event is a coordinate-addressed
        // activation primitive on the action nav. It buys nothing real --
        // anyone with script execution can call `button.click()` directly --
        // and `isTrusted` is non-configurable in jsdom, so the gate makes
        // every test of this behaviour impossible to write. Five regression
        // tests for a reproduced dead-click bug beat a guard with no
        // privilege boundary.
        const handOff = (event) => {
            if (!panel.contains(event.target)) return;
            if (event.target.closest?.(PANEL_CONTROL_SELECTOR)) return;
            const navButton = categoryNavButtonAt(event.clientX, event.clientY);
            if (!navButton) return;
            // Capture phase on `document` runs before React's delegated
            // handler at the app root, so stopping here means the panel never
            // sees the click at all — then activate what the player aimed at.
            // The synthetic click this dispatches re-enters this handler with
            // the nav button as its target, which the containment check above
            // rejects immediately.
            event.stopPropagation();
            navButton.click();
        };

        document.addEventListener('click', handOff, true);
        return () => document.removeEventListener('click', handOff, true);
    }, [contentRef]);
}
