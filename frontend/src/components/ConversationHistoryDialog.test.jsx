import { render, screen, fireEvent, within } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ConversationHistoryDialog from './ConversationHistoryDialog'

const CAST = [
    { id: 'Jean', name: 'Jean', side: 'left' },
    { id: 'Mynx', name: 'Mynx the Swift', side: 'right' },
]

const SEGMENTS = [
    { text: 'Well, well.', speaker: 'Mynx', emotion: 'curious' },
    { text: 'I need directions.', speaker: 'Jean', emotion: 'neutral' },
]

describe('ConversationHistoryDialog', () => {
    it('titles the dialog with the speaker it is a record of', () => {
        render(
            <ConversationHistoryDialog
                title="Mynx the Swift — Conversation"
                segments={SEGMENTS}
                cast={CAST}
                onClose={vi.fn()}
            />
        )

        expect(screen.getByText('Mynx the Swift — Conversation')).toBeInTheDocument()
    })

    it('lists every turn with its portrait thumbnail', () => {
        render(<ConversationHistoryDialog segments={SEGMENTS} cast={CAST} onClose={vi.fn()} />)

        const entries = within(screen.getByTestId('conversation-history')).getAllByTestId('transcript-entry')
        expect(entries).toHaveLength(2)
        expect(within(entries[0]).getByRole('img')).toHaveAttribute('alt', 'Mynx the Swift (curious)')
    })

    it('counts the turns on record', () => {
        const { rerender } = render(
            <ConversationHistoryDialog segments={SEGMENTS} cast={CAST} onClose={vi.fn()} />
        )
        expect(screen.getByTestId('conversation-history-count')).toHaveTextContent('2 turns')

        rerender(
            <ConversationHistoryDialog segments={[SEGMENTS[0]]} cast={CAST} onClose={vi.fn()} />
        )
        expect(screen.getByTestId('conversation-history-count')).toHaveTextContent('1 turn')
    })

    it('closes when the dialog close button is used', () => {
        const onClose = vi.fn()
        render(<ConversationHistoryDialog segments={SEGMENTS} cast={CAST} onClose={onClose} />)

        fireEvent.click(screen.getByText('✕'))
        expect(onClose).toHaveBeenCalled()
    })

    it('shows the empty state before anything has been said', () => {
        render(<ConversationHistoryDialog segments={[]} cast={CAST} onClose={vi.fn()} />)

        expect(screen.getByTestId('transcript-empty')).toBeInTheDocument()
        expect(screen.getByTestId('conversation-history-count')).toHaveTextContent('0 turns')
    })
})
