import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import useTypewriter from './useTypewriter'

describe('useTypewriter', () => {
    beforeEach(() => {
        vi.useFakeTimers()
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it('types the text out one character at a time and then completes', () => {
        const { result } = renderHook(() => useTypewriter('hi', 10))

        expect(result.current.isComplete).toBe(false)

        act(() => { vi.advanceTimersByTime(10) })
        expect(result.current.displayedText).toBe('h')

        act(() => { vi.advanceTimersByTime(30) })
        expect(result.current.displayedText).toBe('hi')
        expect(result.current.isComplete).toBe(true)
    })

    it('completes immediately for empty text instead of stalling forever', () => {
        const { result } = renderHook(() => useTypewriter('', 10))

        // No characters to type — the beat must still report completion, or
        // consumers gated on isComplete (auto-advance, "continue" hint) hang.
        expect(result.current.isComplete).toBe(true)

        act(() => { vi.advanceTimersByTime(1000) })
        expect(result.current.isComplete).toBe(true)
        expect(result.current.displayedText).toBe('')
    })

    it('completes immediately when text is undefined', () => {
        const { result } = renderHook(() => useTypewriter(undefined, 10))
        expect(result.current.isComplete).toBe(true)
    })

    it('restarts when the text changes from empty to real prose', () => {
        const { result, rerender } = renderHook(({ text }) => useTypewriter(text, 10), {
            initialProps: { text: '' },
        })
        expect(result.current.isComplete).toBe(true)

        rerender({ text: 'ok' })
        expect(result.current.isComplete).toBe(false)

        act(() => { vi.advanceTimersByTime(40) })
        expect(result.current.displayedText).toBe('ok')
        expect(result.current.isComplete).toBe(true)
    })

    it('finishImmediately reveals the whole text at once', () => {
        const { result } = renderHook(() => useTypewriter('abcdef', 50))

        act(() => { result.current.finishImmediately() })

        expect(result.current.displayedText).toBe('abcdef')
        expect(result.current.isComplete).toBe(true)
    })

    it('never reports a new text complete on the render that brings it (#618)', () => {
        // The reset runs in an effect, AFTER the render that carries the new
        // text -- so that one render used to return the PREVIOUS text's
        // isComplete=true. A consumer arming a timer on completion (the NPC
        // chat panel's auto-close) fired before a single new character typed.
        const seen = []
        const { rerender } = renderHook(
            ({ text }) => {
                const state = useTypewriter(text, 20)
                seen.push({ text, ...state })
                return state
            },
            { initialProps: { text: 'ab' } },
        )
        act(() => { vi.advanceTimersByTime(200) })
        expect(seen.at(-1).isComplete).toBe(true)

        seen.length = 0
        rerender({ text: 'a closing line nobody has read yet' })

        const falselyComplete = seen.filter(
            (s) => s.isComplete && s.displayedText !== s.text,
        )
        expect(falselyComplete).toEqual([])
    })

    it('reports an empty new text complete at once', () => {
        const seen = []
        const { rerender } = renderHook(
            ({ text }) => {
                const state = useTypewriter(text, 20)
                seen.push(state.isComplete)
                return state
            },
            { initialProps: { text: 'ab' } },
        )
        act(() => { vi.advanceTimersByTime(200) })

        rerender({ text: '' })

        expect(seen.at(-1)).toBe(true)
    })
})
