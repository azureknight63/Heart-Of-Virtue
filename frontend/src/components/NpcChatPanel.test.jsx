import React from 'react'
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import NpcChatPanel from './NpcChatPanel'
import { makeNpcChatOpen, makeNpcChatRespond, makeJeanOption, makeRelationship } from '../test/payloads'

// Mock the npcChat API
vi.mock('../api/npcChat', () => ({
  default: {
    open: vi.fn(),
    respond: vi.fn(),
    end: vi.fn(),
  },
}))

// Stand-ins for the presentational children. They must stay FAITHFUL to the
// real components' contract, or the panel's own logic stops being observable:
//   - BaseDialog exposes close as a dedicated control. The previous mock fired
//     `onClose` from a click anywhere in the dialog, which meant every option
//     click also "closed" the panel and four downstream tests had to clear the
//     spy to work around their own mock.
//   - GameButton must honour `disabled`, otherwise the panel's loading gate is
//     invisible to the test and a regression that lets the player double-submit
//     an option would pass.
vi.mock('./BaseDialog', () => ({
  default: ({ children, title, onClose }) => (
    <div data-testid="base-dialog">
      <h2>{title}</h2>
      <button data-testid="dialog-close" onClick={onClose}>
        ×
      </button>
      {children}
    </div>
  ),
}))

vi.mock('./GameButton', () => ({
  default: ({ children, onClick, disabled }) => (
    <button onClick={onClick} disabled={disabled} data-testid="game-button">
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

  // Realistic wire payloads. `npc_key` is the NPC key the engine mints, the
  // tones are the only three `_qc_jean_options` ever emits, and the shape
  // comes from src/test/payloads.js so a serializer rename breaks this file
  // rather than silently passing against an invented field name.
  const openData = makeNpcChatOpen({
    npc_key: 'npc_session_123',
    npc_name: 'Mynx the Swift',
    npc_opening: 'Well, well, what do we have here?',
    loquacity_current: 2,
    loquacity_max: 5,
    jean_options: [
      makeJeanOption({ text: 'Hi there', tone: 'open' }),
      makeJeanOption({ text: 'Leave me alone', tone: 'guarded' }),
    ],
    relationship: makeRelationship({ npc_id: 'Mynx the Swift', npc_name: 'Mynx the Swift' }),
  })
  const mockOpenResponse = { data: openData }

  const renderPanel = (props = {}) =>
    render(
      <NpcChatPanel
        npcId={mockNpcId}
        npcName={mockNpcName}
        onClose={mockOnClose}
        {...props}
      />
    )

  /** The loquacity fill element — the only place loquacity is rendered. */
  const loquacityBar = (container) => container.querySelector('[style*="height: 100%"]')

  beforeEach(() => {
    vi.clearAllMocks()
    npcChat.open.mockResolvedValue(mockOpenResponse)
    npcChat.respond.mockResolvedValue({
      data: makeNpcChatRespond({
        npc_response: 'A measured reply.',
        jean_options: [],
        loquacity_current: 1,
        loquacity_max: 5,
      }),
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Component Initialization', () => {
    it('opens the conversation for exactly the npcId it was given', async () => {
      renderPanel()

      await waitFor(() => expect(npcChat.open).toHaveBeenCalledWith(mockNpcId))
      expect(npcChat.open).toHaveBeenCalledTimes(1)
    })

    it('shows the npcName prop as the title until the server sends npc_name', async () => {
      let resolveOpen
      npcChat.open.mockReturnValue(new Promise((resolve) => { resolveOpen = resolve }))
      renderPanel({ npcName: 'Mynx' })

      // Pre-response: the prop is the only name the panel has.
      expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Mynx')

      await act(async () => { resolveOpen(mockOpenResponse) })
      // Post-response: the server's display name replaces it.
      expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Mynx the Swift')
    })

    it('renders the server npc_opening as the NPC first line', async () => {
      renderPanel()

      const line = await screen.findByTestId('typewriter')
      expect(line).toHaveTextContent('Well, well, what do we have here?')
      // Attributed to the server's display name, not the prop.
      expect(line.parentElement).toHaveTextContent('Mynx the Swift:')
    })

    it('shows the pulsing placeholder, and no options, while open() is in flight', async () => {
      let resolveOpen
      npcChat.open.mockReturnValue(new Promise((resolve) => { resolveOpen = resolve }))

      renderPanel()

      // loading && messages.length === 0 -> the ellipsis placeholder.
      expect(screen.getByText('…')).toBeInTheDocument()
      expect(screen.queryByText('Hi there')).not.toBeInTheDocument()
      // End Conversation exists but is inert during the 'opening' phase.
      expect(screen.getByText('End Conversation')).toBeDisabled()

      await act(async () => { resolveOpen(mockOpenResponse) })
      expect(screen.queryByText('…')).not.toBeInTheDocument()
      expect(screen.getByText('End Conversation')).toBeEnabled()
    })
  })

  describe('Message Display', () => {
    it('appends Jean line then NPC reply, in order, with the tone tag', async () => {
      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({ npc_response: 'You have my attention.', jean_options: [] }),
      })
      const { container } = renderPanel()

      fireEvent.click(await screen.findByText('Hi there'))
      await screen.findByText(/You have my attention/)

      const transcript = container.querySelectorAll('[style*="line-height: 1.5"]')
      expect(transcript).toHaveLength(3)
      expect(transcript[0]).toHaveTextContent('Mynx the Swift: Well, well, what do we have here?')
      // Jean's chosen line carries the option's tone, straight off the payload.
      expect(transcript[1]).toHaveTextContent('Jean: Hi there[open]')
      expect(transcript[2]).toHaveTextContent('Mynx the Swift: You have my attention.')
    })

    it('typewrites only the latest NPC line and leaves earlier ones static', async () => {
      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({ npc_response: 'The newest line.', jean_options: [] }),
      })
      renderPanel()

      fireEvent.click(await screen.findByText('Hi there'))
      await screen.findByText(/The newest line/)

      // Exactly one typewriter, and it is the newest NPC line — the opening
      // has settled into plain text.
      const typewriters = screen.getAllByTestId('typewriter')
      expect(typewriters).toHaveLength(1)
      expect(typewriters[0]).toHaveTextContent('The newest line.')
    })

    it('shows the waiting placeholder when the server sends no opening line', async () => {
      npcChat.open.mockResolvedValue({ data: makeNpcChatOpen({ npc_opening: null }) })

      renderPanel()

      expect(await screen.findByText('Waiting for NPC to speak...')).toBeInTheDocument()
      expect(screen.queryByTestId('typewriter')).not.toBeInTheDocument()
    })
  })

  describe('Dialogue Options', () => {
    it('renders one button per jean_option, labelled with its text and tone', async () => {
      renderPanel()

      await screen.findByText('Hi there')
      const optionButtons = screen
        .getAllByTestId('game-button')
        .filter((b) => b.textContent !== 'End Conversation')

      expect(optionButtons).toHaveLength(2)
      expect(optionButtons[0]).toHaveTextContent('Hi there[open]')
      expect(optionButtons[1]).toHaveTextContent('Leave me alone[guarded]')
    })

    it('sends the clicked option\'s text and tone with the session npc_key', async () => {
      renderPanel()

      fireEvent.click(await screen.findByText('Leave me alone'))

      await waitFor(() =>
        // npc_key comes from the open response, NOT the npcId prop; text and
        // tone come from the option that was clicked, not the first one.
        expect(npcChat.respond).toHaveBeenCalledWith('npc_session_123', 'Leave me alone', 'guarded')
      )
      expect(npcChat.respond).toHaveBeenCalledTimes(1)
    })

    it('withdraws the options while the NPC is composing a reply', async () => {
      let resolveRespond
      npcChat.respond.mockReturnValue(new Promise((resolve) => { resolveRespond = resolve }))
      renderPanel()

      fireEvent.click(await screen.findByText('Hi there'))

      // phase === 'waiting_npc': no option is clickable, and End Conversation
      // is disabled by the loading gate so the player cannot double-submit.
      await waitFor(() => expect(screen.queryByText('Leave me alone')).not.toBeInTheDocument())
      expect(screen.getByText('End Conversation')).toBeDisabled()

      await act(async () => {
        resolveRespond({
          data: makeNpcChatRespond({
            npc_response: 'Back to you.',
            jean_options: [makeJeanOption({ text: 'Go on.', tone: 'direct' })],
          }),
        })
      })
      expect(screen.getByText('Go on.')).toBeInTheDocument()
      expect(screen.getByText('End Conversation')).toBeEnabled()
    })

    it('ignores an option click that arrives before the session key exists', async () => {
      let resolveOpen
      npcChat.open.mockReturnValue(new Promise((resolve) => { resolveOpen = resolve }))
      renderPanel()

      // No options render during 'opening', so nothing can be dispatched.
      expect(screen.queryByText('Hi there')).not.toBeInTheDocument()
      expect(npcChat.respond).not.toHaveBeenCalled()
      await act(async () => { resolveOpen(mockOpenResponse) })
    })
  })

  describe('Loquacity Tracking', () => {
    it('fills the bar to the served current/max ratio', async () => {
      const { container } = renderPanel()

      await screen.findByText('Hi there')
      // 2 of 5 -> 40%.
      expect(loquacityBar(container).style.width).toBe('40%')
    })

    it('redraws the bar from the respond payload, not the open payload', async () => {
      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({
          npc_response: 'A measured reply.',
          jean_options: [],
          loquacity_current: 1,
          loquacity_max: 5,
        }),
      })
      const { container } = renderPanel()

      fireEvent.click(await screen.findByText('Hi there'))
      await screen.findByText(/A measured reply/)

      // 1 of 5 -> 20%, down from the opening's 40%.
      expect(loquacityBar(container).style.width).toBe('20%')
    })
  })

  describe('Error Handling', () => {
    it('surfaces the server error body verbatim when open fails', async () => {
      npcChat.open.mockRejectedValue({ response: { data: { error: 'NPC not found' } } })

      renderPanel()

      expect(await screen.findByText('NPC not found')).toBeInTheDocument()
      // The error ends the panel: no options, and the End Conversation button
      // is gone because phase === 'ended'.
      expect(screen.queryByText('Hi there')).not.toBeInTheDocument()
      expect(screen.queryByText('End Conversation')).not.toBeInTheDocument()
      expect(screen.getByText('Conversation ended.')).toBeInTheDocument()
    })

    it('falls back to the generic message when the error body carries none', async () => {
      npcChat.open.mockRejectedValue({ response: {} })

      renderPanel()

      expect(await screen.findByText('Failed to open conversation')).toBeInTheDocument()
    })

    it('falls back to the generic message for a transport error with no response', async () => {
      npcChat.open.mockRejectedValue(new Error('Network error'))

      renderPanel()

      expect(await screen.findByText('Failed to open conversation')).toBeInTheDocument()
      // The raw JS error text must never leak into the UI.
      expect(screen.queryByText(/Network error/)).not.toBeInTheDocument()
    })
  })

  describe('Closing Conversation', () => {
    it('calls onClose once when the dialog close control is used', async () => {
      renderPanel()

      await screen.findByText('Hi there')
      fireEvent.click(screen.getByTestId('dialog-close'))

      expect(mockOnClose).toHaveBeenCalledTimes(1)
      // Dismissing the dialog is not the same as ending the session server-side.
      expect(npcChat.end).not.toHaveBeenCalled()
    })
  })

  describe('Conversation Flow States', () => {
    it('walks opening -> waiting_jean -> waiting_npc -> waiting_jean', async () => {
      let resolveRespond
      npcChat.respond.mockReturnValue(new Promise((resolve) => { resolveRespond = resolve }))
      renderPanel()

      // opening: placeholder, no options.
      expect(screen.getByText('…')).toBeInTheDocument()

      // waiting_jean: options are live.
      expect(await screen.findByText('Hi there')).toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: /Hi there/ }))
      // waiting_npc: Jean's line is on stage as transcript, options withdrawn.
      await waitFor(() =>
        expect(screen.queryByRole('button', { name: /Hi there/ })).not.toBeInTheDocument()
      )
      expect(screen.getByText('Hi there', { selector: 'em' })).toBeInTheDocument()

      await act(async () => {
        resolveRespond({
          data: makeNpcChatRespond({
            npc_response: 'And so it goes.',
            jean_options: [makeJeanOption({ text: 'Go on.', tone: 'direct' })],
          }),
        })
      })
      // waiting_jean again, with the server's fresh option list.
      expect(screen.getByText('Go on.')).toBeInTheDocument()
    })
  })

  describe('Props Handling', () => {
    it('re-opens against the new npcId when the prop changes', async () => {
      const { rerender } = renderPanel()

      await waitFor(() => expect(npcChat.open).toHaveBeenCalledWith(mockNpcId))

      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({
          npc_key: 'npc_session_999',
          npc_name: 'Gorran',
          npc_opening: 'You again.',
          jean_options: [makeJeanOption({ text: 'Peace, Gorran.', tone: 'open' })],
        }),
      })
      rerender(
        <NpcChatPanel npcId="Gorran" npcName={mockNpcName} onClose={mockOnClose} />
      )

      await waitFor(() => expect(npcChat.open).toHaveBeenCalledWith('Gorran'))
      expect(npcChat.open).toHaveBeenCalledTimes(2)
      // The new conversation replaces the old one wholesale — options and title
      // both come from the second response.
      expect(await screen.findByText('Peace, Gorran.')).toBeInTheDocument()
      expect(screen.queryByText('Hi there')).not.toBeInTheDocument()
      expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Gorran')
    })
  })

  describe('Relationship Badge', () => {
    it('displays the relationship badge from the open response', async () => {
      renderPanel()

      const badge = await screen.findByTestId('relationship-badge')
      // attitude, trust_level and emoji are three separate serializer fields;
      // assert all three so a badge wired to the wrong one fails.
      expect(badge).toHaveTextContent('neutral')
      expect(badge).toHaveTextContent('Neutral')
      expect(badge).toHaveTextContent('😐')
    })

    it('updates the relationship badge after a response', async () => {
      // Built from the shared factory, not hand-written: NPCRelationshipSerializer
      // renaming a field must break this test rather than pass against an
      // invented shape the server never sends.
      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({
          npc_response: 'I suppose you are not so bad.',
          jean_options: [],
          loquacity_current: 1,
          reputation: 30,
          reputation_delta: 30,
          relationship: makeRelationship({
            npc_id: 'Mynx the Swift',
            npc_name: 'Mynx the Swift',
            reputation: 30,
            attitude: 'favorable',
            emoji: '🙂',
            trust_level: 'Good Trust',
          }),
        }),
      })

      renderPanel()

      // The badge opens on the *neutral* relationship from open()...
      const badge = await screen.findByTestId('relationship-badge')
      expect(badge).toHaveTextContent('neutral')

      fireEvent.click(await screen.findByText('Hi there'))

      // ...and is redrawn from the respond payload, emoji included.
      await waitFor(() => {
        expect(screen.getByTestId('relationship-badge')).toHaveTextContent('favorable')
      })
      expect(screen.getByTestId('relationship-badge')).toHaveTextContent('Good Trust')
      expect(screen.getByTestId('relationship-badge')).toHaveTextContent('🙂')
    })

    it('omits the badge when no relationship data is present', async () => {
      npcChat.open.mockResolvedValue({
        data: {
          ...mockOpenResponse.data,
          relationship: undefined,
        },
      })

      renderPanel()

      // Wait for the OPENING LINE, not for base-dialog: base-dialog renders
      // before open() resolves, so the old wait let the negative assertion run
      // against a panel that had not received the payload yet — it would have
      // passed even if the badge appeared a tick later.
      expect(await screen.findByTestId('typewriter')).toHaveTextContent(
        'Well, well, what do we have here?'
      )
      expect(screen.queryByTestId('relationship-badge')).not.toBeInTheDocument()
    })
  })

  describe('Ending the conversation', () => {
    it('calls npcChat.end and onClose when End Conversation is clicked', async () => {
      npcChat.end.mockResolvedValue({ data: { success: true } })
      renderPanel()

      // Wait on the RENDER, not on the call: open() having fired says nothing
      // about the panel having consumed the response.
      await screen.findByText('Hi there')
      fireEvent.click(screen.getByText('End Conversation'))

      await waitFor(() => {
        expect(npcChat.end).toHaveBeenCalledWith('npc_session_123')
        expect(mockOnClose).toHaveBeenCalledTimes(1)
      })
    })

    it('still closes silently when npcChat.end throws', async () => {
      npcChat.end.mockRejectedValue(new Error('offline'))
      renderPanel()

      // Wait on the RENDER, not on the call: open() having fired says nothing
      // about the panel having consumed the response.
      await screen.findByText('Hi there')
      fireEvent.click(screen.getByText('End Conversation'))

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalledTimes(1)
      })
      // The server call still went out; only its rejection was swallowed.
      expect(npcChat.end).toHaveBeenCalledWith('npc_session_123')
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
      renderPanel()

      // Wait on the RENDER, not on the call: open() having fired says nothing
      // about the panel having consumed the response.
      await screen.findByText('Hi there')
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
      renderPanel()

      // Wait on the RENDER, not on the call: open() having fired says nothing
      // about the panel having consumed the response.
      await screen.findByText('Hi there')
      fireEvent.click(screen.getByText('Hi there'))

      await waitFor(() => expect(screen.getByText('Mynx refuses to answer.')).toBeInTheDocument())
    })

    it('does not duplicate Jean\'s line when a failed option is retried', async () => {
      npcChat.respond.mockRejectedValueOnce(new Error('Network error'))
      renderPanel()

      // Wait on the RENDER, not on the call: open() having fired says nothing
      // about the panel having consumed the response.
      await screen.findByText('Hi there')
      fireEvent.click(screen.getByText('Hi there'))
      await waitFor(() => expect(screen.getByText(/NPC did not respond/i)).toBeInTheDocument())

      npcChat.respond.mockResolvedValue({
        data: {
          npc_response: 'Ah, welcome back.',
          jean_options: [{ text: 'Hi there', tone: 'curious' }],
          loquacity_current: 3,
          loquacity_max: 5,
          conversation_ended: false,
        },
      })
      fireEvent.click(screen.getByText('Retry'))
      await waitFor(() => expect(npcChat.respond).toHaveBeenCalledTimes(2))

      // The optimistic line is rolled back on failure, so the retry re-adds it
      // exactly once instead of stacking a second copy in the transcript.
      const jeanLines = screen
        .getAllByText(/Hi there/)
        .filter((node) => node.tagName === 'EM')
      expect(jeanLines).toHaveLength(1)
    })

    it('clears the error and restores the dialogue options after a successful retry', async () => {
      npcChat.respond.mockRejectedValueOnce(new Error('Network error'))
      renderPanel()

      // Wait on the RENDER, not on the call: open() having fired says nothing
      // about the panel having consumed the response.
      await screen.findByText('Hi there')
      fireEvent.click(screen.getByText('Hi there'))
      await waitFor(() => expect(screen.getByText(/NPC did not respond/i)).toBeInTheDocument())

      // While the error is up the option list is hidden.
      expect(screen.queryByText('Leave me alone')).toBeNull()

      npcChat.respond.mockResolvedValue({
        data: {
          npc_response: 'Ah, welcome back.',
          jean_options: [
            { text: 'Tell me more', tone: 'curious' },
            { text: 'Leave me alone', tone: 'hostile' },
          ],
          loquacity_current: 3,
          loquacity_max: 5,
          conversation_ended: false,
        },
      })
      fireEvent.click(screen.getByText('Retry'))

      await waitFor(() => expect(screen.queryByText(/NPC did not respond/i)).toBeNull())
      expect(screen.queryByText('Retry')).toBeNull()
      // Without clearing `error`, the option list stayed gated off forever and
      // "End Conversation" was the player's only remaining action.
      expect(screen.getByText('Tell me more')).toBeInTheDocument()
      expect(screen.getByText('Leave me alone')).toBeInTheDocument()
    })
  })

  describe('Conversation ending automatically', () => {
    it('shows the ended state and holds the panel open until the close timer fires', async () => {
      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({
          npc_response: 'Farewell.',
          jean_options: [],
          loquacity_current: 0,
          conversation_ended: true,
        }),
      })

      renderPanel()

      fireEvent.click(await screen.findByText('Hi there'))
      await screen.findByText('Conversation ended.')

      // The NPC's parting line stays on screen and the End Conversation button
      // is withdrawn, but the panel is NOT closed yet.
      expect(screen.getByTestId('typewriter')).toHaveTextContent('Farewell.')
      expect(screen.queryByText('End Conversation')).not.toBeInTheDocument()
      // The 2s auto-close timer itself is pinned with fake timers in
      // "fires the delayed onClose when the conversation ends while mounted";
      // burning 2s of real wall time here would only duplicate it.
      expect(mockOnClose).not.toHaveBeenCalled()
    })
  })

  describe('response fallback defaults', () => {
    it('falls back to the npcName prop when the open response has no npc_name', async () => {
      npcChat.open.mockResolvedValue({
        data: { ...mockOpenResponse.data, npc_name: undefined },
      })
      render(<NpcChatPanel npcId={mockNpcId} npcName="Fallback Name" onClose={mockOnClose} />)

      // The prop must survive the response landing, and must be used to
      // attribute the NPC's line too — not just appear somewhere on screen.
      expect(await screen.findByTestId('typewriter')).toHaveTextContent(
        'Well, well, what do we have here?'
      )
      expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Fallback Name')
      expect(screen.getByTestId('typewriter').parentElement).toHaveTextContent('Fallback Name:')
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
      const { container } = renderPanel()

      fireEvent.click(await screen.findByText('Hi there'))

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
      const { container } = renderPanel()
      await screen.findByText('Hi there')
      return container
    }

    it('shows the primary color when loquacity is above 60%', async () => {
      const container = await renderWithLoquacity(4, 5)
      const bar = container.querySelector('[style*="height: 100%"]')
      expect(bar.style.width).toBe('80%')
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
      renderPanel()
      return await screen.findByTestId('relationship-badge')
    }

    it('colors a wary/hostile/enemy attitude with the danger color', async () => {
      const badge = await renderWithAttitude('hostile')
      expect(badge.style.color).toBe('rgb(255, 68, 68)')
    })

    it('colors an unrecognized attitude with the muted text color', async () => {
      // `.not.toBe('')` passed for ANY colour, including the danger red the
      // default branch must not use. Pin the real fallback (colors.text.muted).
      const badge = await renderWithAttitude('bemused')
      expect(badge.style.color).toBe('rgb(136, 136, 136)')
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
      await act(async () => {
        resolveRespond({
          data: makeNpcChatRespond({
            npc_response: 'late reply',
            jean_options: [],
            loquacity_current: 1,
            conversation_ended: true,
          }),
        })
      })

      // Guard at the post-await check returns before scheduling the
      // end-of-conversation onClose timer. Nothing has ever closed the panel,
      // so this is an exact zero rather than "no further calls".
      expect(mockOnClose).not.toHaveBeenCalled()
    })

    it('fires the delayed onClose when the conversation ends while mounted', async () => {
      vi.useFakeTimers()
      try {
        npcChat.respond.mockResolvedValue({
          data: makeNpcChatRespond({
            npc_response: 'farewell',
            jean_options: [],
            loquacity_current: 0,
            conversation_ended: true,
          }),
        })

        renderPanel()

        // Flush the open() microtask so an option renders (no real time passes).
        await act(async () => {})
        fireEvent.click(screen.getByText('Hi there'))
        await act(async () => {})

        // Conversation ended → a 2s close timer is scheduled. One millisecond
        // short of it the panel must still be open; the exact delay is the
        // contract, not "eventually".
        await act(async () => { vi.advanceTimersByTime(1999) })
        expect(mockOnClose).not.toHaveBeenCalled()

        await act(async () => { vi.advanceTimersByTime(1) })
        expect(mockOnClose).toHaveBeenCalledTimes(1)
      } finally {
        vi.useRealTimers()
      }
    })
  })
})
