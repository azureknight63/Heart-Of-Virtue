import { expect } from 'vitest'

import { accessibility } from '../styles/theme'

const FLOOR_PX = parseFloat(accessibility.touchTarget)

const px = (value) => {
    const match = /^(\d+(?:\.\d+)?)px$/.exec(value || '')
    return match ? parseFloat(match[1]) : null
}

/**
 * Every `<button>` under `container` whose declared height floor is below the
 * 44px token — the second direction of the touch-target audit (issue #649).
 *
 * WHY A RENDER-LEVEL CHECK AND NOT ANOTHER AST WALK
 * -------------------------------------------------
 * `findWidthGatedTouchTargets` (sourceAudit.js) starts from each read of
 * `accessibility.touchTarget` and asks what guards it. A control that never
 * reads the token at all is invisible to it, which is how the glossary close
 * button and FleeButton went without a floor on every device. Enumerating
 * interactive elements statically means resolving spreads, props and style
 * helpers per element, and every shape it cannot resolve would have to pass —
 * fail-open. Rendering the component on the device in question and reading
 * each button's own inline style is tight to the element by construction.
 *
 * WHAT IT MEASURES, SAID PLAINLY
 * ------------------------------
 *   - DECLARED inline style only: `minHeight` or `height`, in px. jsdom does
 *     no layout, so padding + font size are not summed and an ancestor
 *     transform (HeroPanel's auto-scale) is not seen. A button sized only by
 *     padding is reported, which is the conservative direction.
 *   - HEIGHT only. A text-labelled button at 44px tall is wider than that; an
 *     icon-only button must additionally assert `minWidth` in its own test.
 *   - only the components a test actually renders — it is opt-in per
 *     component, not a sweep of the tree.
 *
 * @param {HTMLElement} container
 * @returns {Array<{label: string, minHeight: string}>}
 */
export function findUndersizedButtons(container) {
    return [...container.querySelectorAll('button')]
        .filter((el) => {
            const declared = Math.max(px(el.style.minHeight) ?? 0, px(el.style.height) ?? 0)
            return declared < FLOOR_PX
        })
        .map((el) => ({
            label: el.getAttribute('aria-label') || el.textContent.trim(),
            minHeight: el.style.minHeight || el.style.height || '(none)',
        }))
}

/**
 * Assert every button under `container` carries the 44px floor, refusing to
 * pass a render that contained no buttons at all.
 */
export function expectTouchFloorOnEveryButton(container) {
    expect(
        container.querySelectorAll('button').length,
        'no <button> rendered — the check was vacuous',
    ).toBeGreaterThan(0)
    expect(findUndersizedButtons(container)).toEqual([])
}
