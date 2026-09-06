import { describe, expect, it } from 'vitest'

import { lookupOr } from './lookup'

describe('lookupOr', () => {
    const TABLE = { damage: 'red', zero: 0, blank: '', missing: undefined }

    it('returns the value for an own key', () => {
        expect(lookupOr(TABLE, 'damage', 'white')).toBe('red')
    })

    it('returns the fallback for a key the table simply does not have', () => {
        expect(lookupOr(TABLE, 'nonsense', 'white')).toBe('white')
    })

    it('returns an own falsy value rather than the fallback', () => {
        // The second, quieter half of the `TABLE[key] || fallback` bug: an own
        // `0` or `''` is a real answer and `||` threw it away.
        expect(lookupOr(TABLE, 'zero', 99)).toBe(0)
        expect(lookupOr(TABLE, 'blank', 'white')).toBe('')
        expect(lookupOr(TABLE, 'missing', 'white')).toBeUndefined()
    })

    it('returns the fallback for every property inherited from Object.prototype', () => {
        // Derived from the language, not from a list somebody typed. If a
        // future runtime adds a member to Object.prototype, this covers it the
        // day it lands — and it is the only way to know the set is complete,
        // since the whole defect was somebody assuming they knew what was on
        // there.
        const inherited = Object.getOwnPropertyNames(Object.prototype)
        expect(inherited.length).toBeGreaterThan(5)
        for (const key of inherited) {
            expect(lookupOr(TABLE, key, 'FALLBACK'), key).toBe('FALLBACK')
            // Guard the guard: prove each of these really would have been a
            // truthy hit under the old expression, so the assertion above is
            // testing something rather than agreeing with a table that never
            // had the key in any sense.
            expect(TABLE[key] || 'FALLBACK', key).not.toBe('FALLBACK')
        }
    })

    it('returns the fallback for __proto__ specifically', () => {
        // Covered by the derived case above (it is an accessor on
        // Object.prototype, so `getOwnPropertyNames` lists it), and pinned
        // again by name because it is the spelling a hostile key uses first —
        // a reader looking for it should find it, not have to reason about
        // what a reflection loop happens to enumerate.
        expect(lookupOr(TABLE, '__proto__', 'FALLBACK')).toBe('FALLBACK')
    })

    it('handles a numeric key the way a bracket read would', () => {
        expect(lookupOr({ 0: 'first' }, 0, 'none')).toBe('first')
        expect(lookupOr({ 0: 'first' }, 1, 'none')).toBe('none')
    })

    it('returns the fallback instead of throwing on an absent table', () => {
        expect(lookupOr(null, 'damage', 'white')).toBe('white')
        expect(lookupOr(undefined, 'damage', 'white')).toBe('white')
    })

    it('reads a null-prototype table without inheriting anything', () => {
        const bare = Object.assign(Object.create(null), { a: 1 })
        expect(lookupOr(bare, 'a', 0)).toBe(1)
        expect(lookupOr(bare, 'constructor', 0)).toBe(0)
    })
})
