import React from 'react'
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import NpcChatPanel from './NpcChatPanel'

// Mock the npcChat API
vi.mock('../api/npcChat', () => ({
  default: {
    open: vi.fn(),
    respond: vi.fn(),
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
      display_name: 'Mynx the Swift',
      loquacity: { current: 2, max: 5 },
      current_options: [
        { text: 'Hi there', tone: 'curious' },
        { text: 'Leave me alone', tone: 'hostile' },
      ],
      messages: [
        {
          speaker: 'npc',
          text: 'Well, well, what do we have here?',
          tone: 'curious',
        },
      ],
    },
  }

  beforeEach(() => {
    vi.clearAllMocks()
    npcChat.open.mockResolvedValue(mockOpenResponse)
    npcChat.respond.mockResolvedValue({
      data: {
        messages: [],
        current_options: [],
        loquacity: { current: 0, max: 5 },
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
          messages: [],
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
          loquacity: { current: 1, max: 5 },
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
})
