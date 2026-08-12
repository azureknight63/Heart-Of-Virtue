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
        expect(onComplete).toHaveBeenCalled()
    })

    it('fires onComplete for an empty beat', () => {
        // The engine emits genuinely empty beats (stage ops with no prose).
        // Without completion the caller never gets its continue affordance.
        const onComplete = vi.fn()
        render(<TypewriterOutput text="" speed={10} onComplete={onComplete} />)

        act(() => { vi.advanceTimersByTime(50) })

        expect(onComplete).toHaveBeenCalled()
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
