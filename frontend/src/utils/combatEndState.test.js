import { describe, it, expect, vi, beforeEach } from 'vitest'
import logger from './logger'
import { isResolvableEndState, resolvableEndState } from './combatEndState'

describe('isResolvableEndState (#704)', () => {
    it.each(['victory', 'defeat'])('accepts a %s that carries an id', (status) => {
        expect(isResolvableEndState({ id: 'e-1', status })).toBe(true)
    })

    it.each([
        ['no id', { status: 'victory' }],
        ['an empty id', { id: '', status: 'defeat' }],
        ['an unknown status', { id: 'e-1', status: 'fled' }],
        ['no status', { id: 'e-1' }],
        ['null', null],
        ['undefined', undefined],
    ])('rejects %s', (_label, endState) => {
        expect(isResolvableEndState(endState)).toBe(false)
    })
})

describe('resolvableEndState', () => {
    beforeEach(() => {
        vi.restoreAllMocks()
    })

    it('returns a resolvable end state unchanged, without logging', () => {
        const spy = vi.spyOn(logger, 'eventOnChange')
        const end = { id: 'e-1', status: 'victory' }
        expect(resolvableEndState(end)).toBe(end)
        expect(spy).not.toHaveBeenCalled()
    })

    it('drops an id-less end state and logs what was dropped', () => {
        const spy = vi.spyOn(logger, 'eventOnChange')
        expect(resolvableEndState({ status: 'defeat', message: 'x' })).toBeNull()
        expect(spy).toHaveBeenCalledWith('combat.end_state.dropped', { has_id: false, status: 'defeat' })
    })

    it('logs a null status for a payload with no status at all', () => {
        const spy = vi.spyOn(logger, 'eventOnChange')
        expect(resolvableEndState({ id: 'e-1' })).toBeNull()
        expect(spy).toHaveBeenCalledWith('combat.end_state.dropped', { has_id: true, status: null })
    })

    it('stays silent when there is no end state at all (every ordinary poll)', () => {
        const spy = vi.spyOn(logger, 'eventOnChange')
        expect(resolvableEndState(undefined)).toBeNull()
        expect(resolvableEndState(null)).toBeNull()
        expect(spy).not.toHaveBeenCalled()
    })
})
