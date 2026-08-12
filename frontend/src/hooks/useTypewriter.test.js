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
})
