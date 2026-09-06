import { expect } from 'vitest'

/**
 * Assert that no element under `container` carries `NaN` in its inline style.
 *
 * The failure this catches is specific and has shipped before: `theme.js`'s
 * `spacing` values are CSS length STRINGS, so any arithmetic on one — a unary
 * minus for a negative offset, a `* 2` for a double gap — evaluates to `NaN`
 * rather than a length. React drops a `NaN` style with a dev-only warning and
 * says nothing in production, so the first symptom is a layout that is subtly
 * wrong on someone else's machine. The same shape reaches inline styles from a
 * divide-by-zero in a percentage (`hp / max_hp` with `max_hp: 0`).
 *
 * Written as a helper rather than copied into each component test because the
 * copies drift: the first version of this lived alone in HeroPanel.test.jsx
 * and so guarded exactly one component, while every other component that
 * interpolates `spacing` had the same exposure and no check at all.
 *
 * Deliberately asserts on the serialized `style` ATTRIBUTE rather than on
 * `el.style.foo`: a property React refused to apply is absent from the CSSOM
 * object, so a per-property check would read `undefined` and pass. The
 * attribute is what actually reaches the DOM.
 *
 * @param {HTMLElement} container - a render() container, or any subtree root
 */
export function expectNoNaNStyles(container) {
    const styled = container.querySelectorAll('[style]')
    expect(styled.length, 'nothing carried an inline style — the scan was vacuous').toBeGreaterThan(0)
    styled.forEach((el) => {
        expect(
            el.getAttribute('style'),
            `NaN in the inline style of <${el.tagName.toLowerCase()}> — a CSS length string was probably used in arithmetic`
        ).not.toMatch(/NaN/)
    })
}
