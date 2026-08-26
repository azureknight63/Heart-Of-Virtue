import React from 'react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, fireEvent } from '@testing-library/react'
import TypewriterOutput from './TypewriterOutput'

describe('TypewriterOutput', () => {
    beforeEach(() => {
        vi.useFakeTimers()
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it('reveals the text and fires onComplete when finished', () => {
        const onComplete = vi.fn()
        render(<TypewriterOutput text="Hello" speed={10} onComplete={onComplete} />)

        act(() => { vi.advanceTimersByTime(200) })

        expect(screen.getByTestId('event-text-container').textContent).toContain('Hello')
        // Exactly once. onComplete gates the caller's "continue" affordance, and
        // a second call re-arms a beat the player has already passed — the same
        // class of bug as ConversationStage's completedRef soft-lock.
        expect(onComplete).toHaveBeenCalledTimes(1)
        act(() => { vi.advanceTimersByTime(1000) })
        expect(onComplete).toHaveBeenCalledTimes(1)
    })

    it('fires onComplete for an empty beat', () => {
        // The engine emits genuinely empty beats (stage ops with no prose).
        // Without completion the caller never gets its continue affordance.
        const onComplete = vi.fn()
        render(<TypewriterOutput text="" speed={10} onComplete={onComplete} />)

        act(() => { vi.advanceTimersByTime(50) })

        expect(onComplete).toHaveBeenCalledTimes(1)
        // No prose and no blinking caret: `isComplete` must be true on the very
        // first render for an empty beat, otherwise the player sees a cursor
        // pulsing over nothing while the continue affordance is withheld.
        const container = screen.getByTestId('event-text-container')
        expect(container.querySelector('span')).toBeNull()
        expect(container.style.cursor).toBe('default')
    })

    it('finishes immediately when the output is clicked', () => {
        render(<TypewriterOutput text="A longer line of prose" speed={100} />)

        fireEvent.click(screen.getByTestId('event-text-container'))

        expect(screen.getByTestId('event-text-container').textContent).toContain('A longer line of prose')
    })

    it('applies a formatter to the displayed text when provided', () => {
        render(
            <TypewriterOutput
                text="shout"
                speed={10}
                formatter={(t) => <strong>{t.toUpperCase()}</strong>}
            />
        )

        act(() => { vi.advanceTimersByTime(200) })

        expect(screen.getByText('SHOUT')).toBeInTheDocument()
    })
})
