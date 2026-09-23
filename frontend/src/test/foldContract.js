import { expect } from 'vitest'

import { DISCLOSURE_GLYPHS, accessibility } from '../styles/theme'

/**
 * Assert a fold toggle honours the CollapsibleSectionHeader contract
 * (issues #625, #640) in its CURRENT state, and return the region it folds.
 *
 * Pinned from the outside, on the rendered DOM, so a component that went back
 * to a hand-rolled `<div onClick>` fails here whatever it imports:
 *   - a real `<button type="button">` — keyboard-reachable and unable to
 *     submit an enclosing form (a `<div onClick>` fails the focus check);
 *   - `aria-expanded` matching the state;
 *   - `aria-controls` naming a region that is IN THE DOCUMENT in both states
 *     (a dangling id is worse than none);
 *   - the state glyph, so fold state is never colour-only;
 *   - the 44px floor and `touch-action: manipulation`.
 *
 * @param {HTMLElement} header
 * @param {{expanded: boolean}} state
 * @returns {HTMLElement} the controlled region
 */
export function expectFoldContract(header, { expanded }) {
    expect(header.tagName).toBe('BUTTON')
    expect(header.getAttribute('type')).toBe('button')
    header.focus()
    expect(document.activeElement).toBe(header)
    expect(header.getAttribute('aria-expanded')).toBe(String(expanded))
    expect(header.textContent).toContain(
        expanded ? DISCLOSURE_GLYPHS.expanded : DISCLOSURE_GLYPHS.collapsed,
    )
    expect(header.style.minHeight).toBe(accessibility.touchTarget)
    expect(header.style.touchAction).toBe('manipulation')

    const controls = header.getAttribute('aria-controls')
    expect(controls, 'aria-controls is missing').toBeTruthy()
    const region = document.getElementById(controls)
    expect(region, `aria-controls="${controls}" names nothing in the document`).not.toBeNull()
    expect(header.contains(region), 'the header cannot control itself').toBe(false)
    return region
}
