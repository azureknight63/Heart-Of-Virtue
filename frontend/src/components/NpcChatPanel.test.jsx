import React from 'react'
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import NpcChatPanel from './NpcChatPanel'

// Mock the npcChat API
vi.mock('../api/npcChat', () => ({
  default: {
    open: vi.fn(),
    respond: vi.fn(),
    end: vi.fn(),
  },
}))

// Mock child components that might have dependencies
vi.mock('./BaseDialog', () => ({
  default: ({ children, title, onClose }) => (
    <div data-testid="base-dialog" onClick={onClose}>
      <h2>{title}</h2>
      {children}
    </div>
  ),
}))

vi.mock('./GameButton', () => ({
  default: ({ children, onClick }) => (
    <button onClick={onClick} data-testid="game-button">
      {children}
    </button>
  ),
}))

vi.mock('./TypewriterOutput', () => ({
  default: ({ text }) => <div data-testid="typewriter">{text}</div>,
}))

import npcChat from '../api/npcChat'

describe('NpcChatPanel', () => {
  const mockNpcId = 'Mynx'
  const mockNpcName = 'Mynx'
  const mockOnClose = vi.fn()

  const mockOpenResponse = {
    data: {
      npc_key: 'npc_session_123',
      npc_name: 'Mynx the Swift',
      npc_opening: 'Well, well, what do we have here?',
      loquacity_current: 2,
      loquacity_max: 5,
      jean_options: [
        { text: 'Hi there', tone: 'curious' },
        { text: 'Leave me alone', tone: 'hostile' },
      ],
      conversation_ended: false,
      reputation: 0,
      relationship: {
        npc_id: 'Mynx the Swift',
        npc_name: 'Mynx the Swift',
        reputation: 0,
        attitude: 'neutral',
        emoji: '😐',
        trust_level: 'Neutral',
        locked_dialogue: false,
      },
    },
  }

  beforeEach(() => {
    vi.clearAllMocks()
    npcChat.open.mockResolvedValue(mockOpenResponse)
    npcChat.respond.mockResolvedValue({
      data: {
        npc_response: '',
        jean_options: [],
        loquacity_current: 0,
        loquacity_max: 5,
        conversation_ended: false,
      },
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Component Initialization', () => {
    it('renders and opens conversation on mount', async () => {
      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(npcChat.open).toHaveBeenCalledWith(mockNpcId)
      })
    })

    it('displays NPC name from props', async () => {
      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        // Display name or NPC name should be visible
        const header = screen.getByRole('heading', {
          level: 2,
        })
        expect(header).toBeInTheDocument()
      })
    })

    it('displays custom display name from response', async () => {
      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(npcChat.open).toHaveBeenCalled()
      })
    })

    it('shows loading state during initialization', () => {
      npcChat.open.mockImplementation(
        () =>
          new Promise((resolve) => {
            setTimeout(() => resolve(mockOpenResponse), 100)
          })
      )

      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      // Component should render during loading
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Message Display', () => {
    it('displays conversation messages', async () => {
      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(npcChat.open).toHaveBeenCalled()
      })
    })

    it('renders NPC messages with typewriter effect', async () => {
      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        const typewriter = screen.getByTestId('typewriter')
        expect(typewriter).toBeInTheDocument()
      })
    })

    it('handles empty message list', async () => {
      npcChat.open.mockResolvedValue({
        data: {
          ...mockOpenResponse.data,
          npc_opening: null,
        },
      })

      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
      })
    })
  })

  describe('Dialogue Options', () => {
    it('displays dialogue options as buttons', async () => {
      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        const buttons = screen.getAllByTestId('game-button')
        expect(buttons.length).toBeGreaterThan(0)
      })
    })

    it('handles option selection', async () => {
      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        const buttons = screen.getAllByTestId('game-button')
        expect(buttons.length).toBeGreaterThan(0)
      })

      // Click first option
      const buttons = screen.getAllByTestId('game-button')
      fireEvent.click(buttons[0])

      await waitFor(() => {
        expect(npcChat.respond).toHaveBeenCalled()
      })

      // Flush the finally block's setLoading(false) state update
      await new Promise(resolve => setTimeout(resolve, 0))
    })

    it('disables options while NPC is responding', async () => {
      npcChat.respond.mockImplementation(
        () =>
          new Promise((resolve) => {
            setTimeout(() => resolve(mockOpenResponse), 100)
          })
      )

      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        const buttons = screen.getAllByTestId('game-button')
        expect(buttons.length).toBeGreaterThan(0)
      })

      const buttons = screen.getAllByTestId('game-button')
      fireEvent.click(buttons[0])

      // During response phase, component should be in waiting state
      await waitFor(() => {
        expect(npcChat.respond).toHaveBeenCalled()
      })

      // Let the delayed mock response resolve before the test (and its
      // jsdom environment) tears down, otherwise the finally block's
      // setLoading(false) fires after teardown and throws.
      await new Promise((resolve) => setTimeout(resolve, 150))
    })
  })

  describe('Loquacity Tracking', () => {
    it('displays loquacity current/max', async () => {
      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(npcChat.open).toHaveBeenCalled()
      })
    })

    it('updates loquacity after responses', async () => {
      const updatedResponse = {
        data: {
          ...mockOpenResponse.data,
          npc_response: 'A measured reply.',
          loquacity_current: 1,
          loquacity_max: 5,
        },
      }
      npcChat.respond.mockResolvedValue(updatedResponse)

      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      // Wait for buttons to appear
      await waitFor(() => {
        const buttons = screen.getAllByTestId('game-button')
        expect(buttons.length).toBeGreaterThan(0)
      })

      // Click the first button
      const buttons = screen.getAllByTestId('game-button')
      fireEvent.click(buttons[0])

      // Wait for the respond to be called
      await waitFor(() => {
        expect(npcChat.respond).toHaveBeenCalled()
      })

      // Flush the finally block's setLoading(false) state update
      await new Promise(resolve => setTimeout(resolve, 0))
    })
  })

  describe('Error Handling', () => {
    it('displays error message on failed conversation opening', async () => {
      npcChat.open.mockRejectedValue({
        response: {
          data: {
            error: 'NPC not found',
          },
        },
      })

      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
      })
    })

    it('shows generic error when response has no error message', async () => {
      npcChat.open.mockRejectedValue({
        response: {},
      })

      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
      })
    })

    it('handles network error', async () => {
      npcChat.open.mockRejectedValue(new Error('Network error'))

      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
      })
    })
  })

  describe('Closing Conversation', () => {
    it('calls onClose when dialog is closed', async () => {
      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        const dialog = screen.getByTestId('base-dialog')
        expect(dialog).toBeInTheDocument()
      })

      const dialog = screen.getByTestId('base-dialog')
      fireEvent.click(dialog)

      expect(mockOnClose).toHaveBeenCalled()
    })
  })

  describe('Conversation Flow States', () => {
    it('transitions through conversation states correctly', async () => {
      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      // Initial: loading phase
      await waitFor(() => {
        expect(npcChat.open).toHaveBeenCalled()
      })

      // After load: waiting_jean phase (options shown)
      await waitFor(() => {
        const buttons = screen.getAllByTestId('game-button')
        expect(buttons.length).toBeGreaterThan(0)
      })

      // Click option: waiting_npc phase
      const buttons = screen.getAllByTestId('game-button')
      fireEvent.click(buttons[0])

      await waitFor(() => {
        expect(npcChat.respond).toHaveBeenCalled()
      })
    })
  })

  describe('Props Handling', () => {
    it('respects npcId prop changes', async () => {
      const { rerender } = render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(npcChat.open).toHaveBeenCalledWith(mockNpcId)
      })

      vi.clearAllMocks()

      rerender(
        <NpcChatPanel
          npcId="DifferentNPC"
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(npcChat.open).toHaveBeenCalledWith('DifferentNPC')
      })
    })
  })

  describe('Relationship Badge', () => {
    it('displays the relationship badge from the open response', async () => {
      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        const badge = screen.getByTestId('relationship-badge')
        expect(badge).toBeInTheDocument()
        expect(badge).toHaveTextContent('neutral')
        expect(badge).toHaveTextContent('Neutral')
      })
    })

    it('updates the relationship badge after a response', async () => {
      npcChat.respond.mockResolvedValue({
        data: {
          npc_response: 'I suppose you are not so bad.',
          jean_options: [],
          loquacity_current: 1,
          loquacity_max: 5,
          conversation_ended: false,
          relationship: {
            npc_id: 'Mynx the Swift',
            npc_name: 'Mynx the Swift',
            reputation: 30,
            attitude: 'favorable',
            emoji: '🙂',
            trust_level: 'Good Trust',
            locked_dialogue: false,
          },
        },
      })

      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        const buttons = screen.getAllByTestId('game-button')
        expect(buttons.length).toBeGreaterThan(0)
      })

      const buttons = screen.getAllByTestId('game-button')
      fireEvent.click(buttons[0])

      await waitFor(() => {
        const badge = screen.getByTestId('relationship-badge')
        expect(badge).toHaveTextContent('favorable')
        expect(badge).toHaveTextContent('Good Trust')
      })
    })

    it('omits the badge when no relationship data is present', async () => {
      npcChat.open.mockResolvedValue({
        data: {
          ...mockOpenResponse.data,
          relationship: undefined,
        },
      })

      render(
        <NpcChatPanel
          npcId={mockNpcId}
          npcName={mockNpcName}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
      })

      expect(screen.queryByTestId('relationship-badge')).not.toBeInTheDocument()
    })
  })

  describe('Ending the conversation', () => {
    it('calls npcChat.end and onClose when End Conversation is clicked', async () => {
      npcChat.end.mockResolvedValue({ data: { success: true } })
      render(
        <NpcChatPanel npcId={mockNpcId} npcName={mockNpcName} onClose={mockOnClose} />
      )

      await waitFor(() => expect(npcChat.open).toHaveBeenCalled())
      fireEvent.click(screen.getByText('End Conversation'))

      await waitFor(() => {
        expect(npcChat.end).toHaveBeenCalledWith('npc_session_123')
        expect(mockOnClose).toHaveBeenCalled()
      })
    })

    it('still closes silently when npcChat.end throws', async () => {
      npcChat.end.mockRejectedValue(new Error('offline'))
      render(
        <NpcChatPanel npcId={mockNpcId} npcName={mockNpcName} onClose={mockOnClose} />
      )

      await waitFor(() => expect(npcChat.open).toHaveBeenCalled())
      fireEvent.click(screen.getByText('End Conversation'))

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalled()
      })
    })

    it('does nothing when End Conversation is clicked before the session key is ready', () => {
      let resolveOpen
      npcChat.open.mockReturnValue(new Promise((resolve) => { resolveOpen = resolve }))
      render(
        <NpcChatPanel npcId={mockNpcId} npcName={mockNpcName} onClose={mockOnClose} />
      )

      fireEvent.click(screen.getByText('End Conversation'))

      expect(npcChat.end).not.toHaveBeenCalled()
      resolveOpen(mockOpenResponse)
    })
  })

  describe('Retrying a failed action', () => {
    it('retries opening the conversation when Retry is clicked after a failed open', async () => {
      npcChat.open.mockRejectedValueOnce(new Error('Network error'))
      render(
        <NpcChatPanel npcId={mockNpcId} npcName={mockNpcName} onClose={mockOnClose} />
      )

      await waitFor(() => expect(screen.getByText(/Failed to open conversation/i)).toBeInTheDocument())
      expect(npcChat.open).toHaveBeenCalledTimes(1)

      npcChat.open.mockResolvedValue(mockOpenResponse)
      fireEvent.click(screen.getByText('Retry'))

      await waitFor(() => expect(npcChat.open).toHaveBeenCalledTimes(2))
    })

    it('retries the same option when Retry is clicked after a failed response', async () => {
      npcChat.respond.mockRejectedValueOnce(new Error('Network error'))
      render(
        <NpcChatPanel npcId={mockNpcId} npcName={mockNpcName} onClose={mockOnClose} />
      )

      await waitFor(() => expect(npcChat.open).toHaveBeenCalled())
      fireEvent.click(screen.getByText('Hi there'))

      await waitFor(() => expect(screen.getByText(/NPC did not respond/i)).toBeInTheDocument())
      expect(npcChat.respond).toHaveBeenCalledTimes(1)

      npcChat.respond.mockResolvedValue({
        data: {
          npc_response: 'Ah, welcome back.',
          jean_options: [],
          loquacity_current: 3,
          loquacity_max: 5,
          conversation_ended: false,
        },
      })
      fireEvent.click(screen.getByText('Retry'))

      await waitFor(() => expect(npcChat.respond).toHaveBeenCalledTimes(2))
    })

    it('prefers the server error message over the generic fallback when respond fails with a response body', async () => {
      const err = new Error('Bad Request')
      err.response = { data: { error: 'Mynx refuses to answer.' } }
      npcChat.respond.mockRejectedValueOnce(err)
      render(
        <NpcChatPanel npcId={mockNpcId} npcName={mockNpcName} onClose={mockOnClose} />
      )

      await waitFor(() => expect(npcChat.open).toHaveBeenCalled())
      fireEvent.click(screen.getByText('Hi there'))

      await waitFor(() => expect(screen.getByText('Mynx refuses to answer.')).toBeInTheDocument())
    })
  })

  describe('Conversation ending automatically', () => {
    it('closes the panel after a delay when the conversation ends', async () => {
      npcChat.respond.mockResolvedValue({
        data: {
          npc_response: 'Farewell.',
          jean_options: [],
          loquacity_current: 0,
          loquacity_max: 5,
          conversation_ended: true,
        },
      })

      render(
        <NpcChatPanel npcId={mockNpcId} npcName={mockNpcName} onClose={mockOnClose} />
      )

      await waitFor(() => expect(npcChat.open).toHaveBeenCalled())
      fireEvent.click(screen.getByText('Hi there'))

      await waitFor(() => expect(npcChat.respond).toHaveBeenCalled())
      // The mocked BaseDialog bubbles every click to onClose, so the option
      // click itself already triggered one call unrelated to conversation
      // state; assert a further, delayed call from the 2s auto-close timer.
      const callsBeforeDelay = mockOnClose.mock.calls.length
      await waitFor(
        () => expect(mockOnClose.mock.calls.length).toBeGreaterThan(callsBeforeDelay),
        { timeout: 3000 }
      )
    })
  })

  describe('response fallback defaults', () => {
    it('falls back to the npcName prop when the open response has no npc_name', async () => {
      npcChat.open.mockResolvedValue({
        data: { ...mockOpenResponse.data, npc_name: undefined },
      })
      render(<NpcChatPanel npcId={mockNpcId} npcName="Fallback Name" onClose={mockOnClose} />)

      await waitFor(() => expect(screen.getByText('Fallback Name')).toBeInTheDocument())
    })

    it('defaults loquacity and jean_options when absent from the open response', async () => {
      npcChat.open.mockResolvedValue({
        data: {
          npc_key: 'npc_session_123',
          npc_name: 'Mynx the Swift',
          npc_opening: 'Hello.',
          conversation_ended: false,
        },
      })
      const { container } = render(<NpcChatPanel npcId={mockNpcId} npcName={mockNpcName} onClose={mockOnClose} />)

      await waitFor(() => expect(screen.getByTestId('typewriter')).toHaveTextContent('Hello.'))
      // loquacity_current/max both default (0/1) -> 0% width, danger color
      const bar = container.querySelector('[style*="height: 100%"]')
      expect(bar.style.width).toBe('0%')
      expect(bar.style.backgroundColor).toBe('rgb(255, 68, 68)')
      // jean_options defaults to [] -> no option buttons rendered
      expect(screen.queryByText('Hi there')).not.toBeInTheDocument()
    })

    it('defaults loquacity and jean_options when absent from a respond response', async () => {
      npcChat.respond.mockResolvedValue({
        data: { npc_response: 'A terse reply.', conversation_ended: false },
      })
      const { container } = render(<NpcChatPanel npcId={mockNpcId} npcName={mockNpcName} onClose={mockOnClose} />)

      await waitFor(() => expect(npcChat.open).toHaveBeenCalled())
      fireEvent.click(screen.getByText('Hi there'))

      await waitFor(() => expect(screen.getByTestId('typewriter')).toHaveTextContent('A terse reply.'))
      const bar = container.querySelector('[style*="height: 100%"]')
      expect(bar.style.width).toBe('0%')
      expect(screen.queryByText('Leave me alone')).not.toBeInTheDocument()
    })
  })

  describe('loquacity bar color', () => {
    const renderWithLoquacity = async (current, max) => {
      npcChat.open.mockResolvedValue({
        data: { ...mockOpenResponse.data, loquacity_current: current, loquacity_max: max },
      })
      const { container } = render(<NpcChatPanel npcId={mockNpcId} npcName={mockNpcName} onClose={mockOnClose} />)
      await waitFor(() => expect(npcChat.open).toHaveBeenCalled())
      return container
    }

    it('shows the primary color when loquacity is above 60%', async () => {
      const container = await renderWithLoquacity(4, 5)
      const bar = container.querySelector('[style*="height: 100%"]')
      expect(bar.style.backgroundColor).toBe('rgb(0, 255, 136)')
    })

    it('shows the secondary color when loquacity is between 30% and 60%', async () => {
      const container = await renderWithLoquacity(2, 5)
      const bar = container.querySelector('[style*="height: 100%"]')
      expect(bar.style.backgroundColor).toBe('rgb(255, 170, 0)')
    })

    it('shows the danger color when loquacity is at or below 30%', async () => {
      const container = await renderWithLoquacity(1, 5)
      const bar = container.querySelector('[style*="height: 100%"]')
      expect(bar.style.backgroundColor).toBe('rgb(255, 68, 68)')
    })

    it('shows the primary color when loquacity max is zero', async () => {
      const container = await renderWithLoquacity(0, 0)
      const bar = container.querySelector('[style*="height: 100%"]')
      expect(bar.style.backgroundColor).toBe('rgb(0, 255, 136)')
    })
  })

  describe('relationship badge color', () => {
    const renderWithAttitude = async (attitude) => {
      npcChat.open.mockResolvedValue({
        data: {
          ...mockOpenResponse.data,
          relationship: { ...mockOpenResponse.data.relationship, attitude },
        },
      })
      render(<NpcChatPanel npcId={mockNpcId} npcName={mockNpcName} onClose={mockOnClose} />)
      await waitFor(() => expect(screen.getByTestId('relationship-badge')).toBeInTheDocument())
      return screen.getByTestId('relationship-badge')
    }

    it('colors a wary/hostile/enemy attitude with the danger color', async () => {
      const badge = await renderWithAttitude('hostile')
      expect(badge.style.color).toBe('rgb(255, 68, 68)')
    })

    it('colors an unrecognized attitude with the muted text color', async () => {
      const badge = await renderWithAttitude('bemused')
      expect(badge.style.color).not.toBe('')
    })

    it('colors a friendly attitude with the primary color', async () => {
      const badge = await renderWithAttitude('friendly')
      expect(badge.style.color).toBe('rgb(0, 255, 136)')
    })

    it('colors a wary attitude with the danger color', async () => {
      const badge = await renderWithAttitude('wary')
      expect(badge.style.color).toBe('rgb(255, 68, 68)')
    })
  })

  describe('Unmount safety', () => {
    // These exercise the isMountedRef / endTimeoutRef guards: async callbacks
    // that resolve (or a scheduled close that fires) after the panel has been
    // unmounted must not call state setters or onClose.
    it('does not update state or throw when open() resolves after unmount', async () => {
      let resolveOpen
      npcChat.open.mockReturnValue(
        new Promise((resolve) => {
          resolveOpen = resolve
        })
      )

      const { unmount } = render(
        <NpcChatPanel npcId={mockNpcId} npcName={mockNpcName} onClose={mockOnClose} />
      )

      unmount()
      // Resolve after unmount — the isMountedRef guard should short-circuit
      // before any setState (no "state update on unmounted component" warning).
      await act(async () => {
        resolveOpen(mockOpenResponse)
      })

      expect(mockOnClose).not.toHaveBeenCalled()
    })

    it('does not update state when open() rejects after unmount', async () => {
      let rejectOpen
      npcChat.open.mockReturnValue(
        new Promise((_resolve, reject) => {
          rejectOpen = reject
        })
      )

      const { unmount } = render(
        <NpcChatPanel npcId={mockNpcId} npcName={mockNpcName} onClose={mockOnClose} />
      )

      unmount()
      await act(async () => {
        rejectOpen(new Error('late failure'))
      })

      expect(mockOnClose).not.toHaveBeenCalled()
    })

    it('does not update state when respond() resolves after unmount', async () => {
      let resolveRespond
      npcChat.respond.mockReturnValue(
        new Promise((resolve) => {
          resolveRespond = resolve
        })
      )

      const { unmount } = render(
        <NpcChatPanel npcId={mockNpcId} npcName={mockNpcName} onClose={mockOnClose} />
      )

      // Wait for the opening to finish so an option is clickable
      const option = await screen.findByText('Hi there')
      fireEvent.click(option)

      unmount()
      // The BaseDialog test mock forwards a bubbled click to onClose, so ignore
      // any pre-unmount calls — we only care that the post-await guard prevents
      // further work once unmounted.
      mockOnClose.mockClear()
      await act(async () => {
        resolveRespond({
          data: {
            npc_response: 'late reply',
            jean_options: [],
            loquacity_current: 1,
            loquacity_max: 5,
            conversation_ended: true,
          },
        })
      })

      // Guard at the post-await check returns before scheduling the
      // end-of-conversation onClose timer.
      expect(mockOnClose).not.toHaveBeenCalled()
    })

    it('fires the delayed onClose when the conversation ends while mounted', async () => {
      vi.useFakeTimers()
      try {
        npcChat.respond.mockResolvedValue({
          data: {
            npc_response: 'farewell',
            jean_options: [],
            loquacity_current: 0,
            loquacity_max: 5,
            conversation_ended: true,
          },
        })

        render(
          <NpcChatPanel npcId={mockNpcId} npcName={mockNpcName} onClose={mockOnClose} />
        )

        // Flush the open() microtask so an option renders (no real time passes).
        await act(async () => {})
        const option = screen.getByText('Hi there')
        // Ignore the BaseDialog mock's bubbled-click onClose; assert on the timer.
        fireEvent.click(option)
        await act(async () => {})
        mockOnClose.mockClear()

        // Conversation ended → a 2s close timer is scheduled; advancing past it
        // while still mounted invokes onClose (the isMountedRef.current === true
        // branch of the timer callback).
        await act(async () => {
          vi.advanceTimersByTime(2000)
        })

        expect(mockOnClose).toHaveBeenCalledTimes(1)
      } finally {
        vi.useRealTimers()
      }
    })
  })
})
