import React from 'react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor, act, within } from '@testing-library/react'
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
//   - BaseDialog exposes close as a dedicated control. An earlier mock fired
//     `onClose` from a click anywhere in the dialog, which meant every option
//     click also "closed" the panel and four downstream tests had to clear the
//     spy to work around their own mock.
//   - `width` is forwarded RAW, not re-derived: BaseDialog computes its own
//     `min(94vw, maxWidth)` default, and a mock that copied that formula would
//     only be asserting against its own copy of it. What the panel owns is
//     which props it sends, so that is what is asserted below.
//   - GameButton must honour `disabled`, otherwise the panel's loading gate is
//     invisible to the test and a regression that lets the player double-submit
//     an option would pass.
// ConversationStage / ConversationTranscript / PortraitImage are deliberately
// NOT mocked: the portrait emotions they render are the only place the
// tone -> emotion and quality -> emotion mappings are observable.
vi.mock('./BaseDialog', () => ({
  default: ({ children, title, onClose, maxWidth = '400px', width, className }) => (
    <div
      data-testid="base-dialog"
      data-max-width={maxWidth}
      data-width={width}
      className={className}
    >
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

import npcChat from '../api/npcChat'

describe('NpcChatPanel', () => {
  const mockNpcId = 'Mynx'
  const mockNpcName = 'Mynx'
  const mockOnClose = vi.fn()
  let consoleError

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

  /** Option buttons only — the action row's own buttons share the testid. */
  const optionButtons = () =>
    screen
      .getAllByTestId('game-button')
      .filter((b) => !['View History', 'End Conversation', 'Retry'].includes(b.textContent))

  /**
   * Wait for a line to finish typing onto the stage.
   *
   * ConversationStage runs a real-timer typewriter at 20ms/char, so a 30-odd
   * character line needs ~600ms of wall clock — close enough to waitFor's 1000ms
   * default that these assertions flake under a loaded parallel run. The wait is
   * still bounded; it is the budget that is generous, not the assertion.
   */
  const findStageText = async (text) => {
    const stage = await screen.findByTestId('conversation-stage')
    await waitFor(() => expect(stage).toHaveTextContent(text), { timeout: 5000 })
    return stage
  }

  /** Open the transcript and read back its ordered entries. */
  const transcriptEntries = () => {
    fireEvent.click(screen.getByText('View History'))
    return within(screen.getByTestId('conversation-history')).getAllByTestId('transcript-entry')
  }

  beforeEach(() => {
    vi.clearAllMocks()
    // The hook logs the raw server detail on every failure path (it is never
    // rendered — see S5). Silenced here so an expected-failure test does not
    // spew, and spied so "logged instead of shown" can actually be asserted.
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
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
    consoleError.mockRestore()
    vi.clearAllMocks()
  })

  describe('Component Initialization', () => {
    it('opens the conversation for exactly the npcId it was given', async () => {
      renderPanel()

      await waitFor(() => expect(npcChat.open).toHaveBeenCalledWith(mockNpcId))
      expect(npcChat.open).toHaveBeenCalledTimes(1)
    })

    it('uses a wide dialog for the desktop portrait-backed conversation stage', async () => {
      renderPanel()

      await waitFor(() => expect(screen.getByTestId('conversation-stage')).toBeInTheDocument())
      const dialog = screen.getByTestId('base-dialog')
      expect(dialog).toHaveAttribute('data-max-width', '1100px')
      // No explicit `width`: BaseDialog derives `min(94vw, maxWidth)` itself, so
      // restating a pixel value here would just be a second copy of that
      // default, free to drift. (Nor is the derived value observable in jsdom —
      // cssstyle drops `min()` outright, leaving `style.width` empty.)
      expect(dialog).not.toHaveAttribute('data-width')
      expect(screen.getByTestId('conversation-stage')).toHaveClass('conversation-stage--wide')
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

    it('renders the server npc_opening as the NPC first line, attributed to the server name', async () => {
      renderPanel()

      const stage = await findStageText('Well, well, what do we have here?')
      // Attributed to the server's display name, not the prop.
      expect(stage).toHaveTextContent('Mynx the Swift')
    })

    it('shows the loading affordance, and no options, while open() is in flight', async () => {
      let resolveOpen
      npcChat.open.mockReturnValue(new Promise((resolve) => { resolveOpen = resolve }))

      renderPanel()

      // loading && segments.length === 0 -> the block loading indicator.
      expect(screen.getByTestId('npc-chat-loading')).toBeInTheDocument()
      expect(screen.queryByText('Hi there')).not.toBeInTheDocument()
      // End Conversation exists but is inert during the 'opening' phase.
      expect(screen.getByText('End Conversation')).toBeDisabled()

      await act(async () => { resolveOpen(mockOpenResponse) })
      expect(screen.queryByTestId('npc-chat-loading')).not.toBeInTheDocument()
      expect(screen.getByText('End Conversation')).toBeEnabled()
    })

    it('shows an inline loader over the existing stage while a reply is pending', async () => {
      let resolveRespond
      npcChat.respond.mockReturnValue(new Promise((resolve) => { resolveRespond = resolve }))
      renderPanel()

      fireEvent.click(await screen.findByText('Hi there'))

      // The stage keeps the conversation so far; the loader stacks under it.
      expect(screen.getByTestId('npc-chat-loading')).toBeInTheDocument()
      expect(screen.getByTestId('conversation-stage')).toBeInTheDocument()

      await act(async () => {
        resolveRespond({
          data: makeNpcChatRespond({ npc_response: 'Done.', jean_options: [] }),
        })
      })
      expect(screen.queryByTestId('npc-chat-loading')).not.toBeInTheDocument()
    })
  })

  describe('Message Display', () => {
    it('appends Jean line then NPC reply, in speaker order', async () => {
      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({ npc_response: 'You have my attention.', jean_options: [] }),
      })
      renderPanel()

      fireEvent.click(await screen.findByText('Hi there'))
      await findStageText('You have my attention.')

      const entries = transcriptEntries()
      expect(entries).toHaveLength(3)
      expect(entries.map((e) => e.dataset.speaker)).toEqual(['Mynx', 'Jean', 'Mynx'])
      expect(entries[0]).toHaveTextContent('Well, well, what do we have here?')
      expect(entries[1]).toHaveTextContent('Hi there')
      expect(entries[2]).toHaveTextContent('You have my attention.')
    })

    it('stages the newest beat only, with the speaker in the dialogue card', async () => {
      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({ npc_response: 'The newest line.', jean_options: [] }),
      })
      renderPanel()

      fireEvent.click(await screen.findByText('Hi there'))
      const stage = await findStageText('The newest line.')

      // The opening has scrolled off the stage into the recap/history.
      expect(stage).not.toHaveTextContent('Well, well, what do we have here?')
    })

    it('renders NPC portraits in the portrait-backed conversation stage', async () => {
      renderPanel()

      const stage = await screen.findByTestId('conversation-stage')
      await waitFor(() =>
        expect(within(stage).getByAltText('Mynx the Swift (neutral)')).toBeInTheDocument()
      )
      expect(within(stage).getByAltText('Jean (neutral)')).toBeInTheDocument()
    })

    it('shows the waiting placeholder when the server sends no opening line', async () => {
      npcChat.open.mockResolvedValue({ data: makeNpcChatOpen({ npc_opening: null }) })

      renderPanel()

      expect(await screen.findByText('Waiting for NPC to speak…')).toBeInTheDocument()
      expect(screen.queryByTestId('conversation-stage')).not.toBeInTheDocument()
    })
  })

  describe('Dialogue Options', () => {
    it('renders one button per jean_option, labelled with its text and tone', async () => {
      renderPanel()

      await screen.findByText('Hi there')
      const buttons = optionButtons()

      expect(buttons).toHaveLength(2)
      expect(buttons[0]).toHaveTextContent('Hi there[open]')
      expect(buttons[1]).toHaveTextContent('Leave me alone[guarded]')
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

    it('withdraws the options and disables End Conversation while the NPC composes a reply', async () => {
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
      await waitFor(() => expect(loquacityBar(container).style.width).toBe('20%'))
    })
  })

  describe('Error Handling', () => {
    it('shows fixed local copy and logs the server detail when open fails', async () => {
      npcChat.open.mockRejectedValue({ response: { data: { error: 'NPC not found' } } })

      renderPanel()

      // The server's `error` field is raw provider-SDK exception text (endpoint
      // URL, model id, status body, request id). It must never be rendered.
      expect(await screen.findByText('Failed to open conversation')).toBeInTheDocument()
      expect(screen.queryByText('NPC not found')).not.toBeInTheDocument()
      expect(consoleError).toHaveBeenCalledWith('[npcChat] open failed:', 'NPC not found')
      expect(screen.queryByText('Hi there')).not.toBeInTheDocument()
    })

    it('reads a failed open as failed, not as a finished conversation', async () => {
      npcChat.open.mockRejectedValue({ response: { data: { error: 'NPC not found' } } })

      renderPanel()

      await screen.findByText('Failed to open conversation')
      // phase 'failed' is deliberately distinct from 'ended': "Conversation
      // ended." with End Conversation withdrawn described a finished chat that
      // Retry could never clear.
      expect(screen.queryByText('Conversation ended.')).not.toBeInTheDocument()
      expect(screen.getByText('End Conversation')).toBeInTheDocument()
      expect(screen.getByText('Retry')).toBeInTheDocument()
    })

    it('shows the same fixed copy when the error body carries no detail', async () => {
      npcChat.open.mockRejectedValue({ response: {} })

      renderPanel()

      expect(await screen.findByText('Failed to open conversation')).toBeInTheDocument()
    })

    it('shows the same fixed copy for a transport error with no response', async () => {
      npcChat.open.mockRejectedValue(new Error('Network error'))

      renderPanel()

      expect(await screen.findByText('Failed to open conversation')).toBeInTheDocument()
      // The raw JS error text must never leak into the UI.
      expect(screen.queryByText(/Network error/)).not.toBeInTheDocument()
      expect(consoleError).toHaveBeenCalledWith('[npcChat] open failed:', 'Network error')
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

      // opening: loader, no options.
      expect(screen.getByTestId('npc-chat-loading')).toBeInTheDocument()

      // waiting_jean: options are live.
      expect(await screen.findByText('Hi there')).toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: /Hi there/ }))
      // waiting_npc: Jean's line is on stage, options withdrawn.
      await waitFor(() =>
        expect(screen.queryByRole('button', { name: /Hi there/ })).not.toBeInTheDocument()
      )
      await findStageText('Hi there')

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
      await screen.findByText('Hi there')

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

    it('clears the previous NPC off the stage before the new open() resolves', async () => {
      const { rerender } = renderPanel()

      await screen.findByText('Hi there')

      let resolveOpen
      npcChat.open.mockReturnValue(new Promise((resolve) => { resolveOpen = resolve }))
      rerender(
        <NpcChatPanel npcId="Gorran" npcName="Gorran" onClose={mockOnClose} />
      )

      // The synchronous reset at the top of the open effect: for the whole
      // round trip the stage used to keep drawing the PREVIOUS NPC's portraits,
      // options and npc_key.
      expect(screen.queryByTestId('conversation-stage')).not.toBeInTheDocument()
      expect(screen.queryByText('Hi there')).not.toBeInTheDocument()
      expect(screen.queryByTestId('relationship-badge')).not.toBeInTheDocument()
      expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Gorran')

      await act(async () => { resolveOpen(mockOpenResponse) })
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
        data: makeNpcChatOpen({ ...openData, relationship: undefined }),
      })

      renderPanel()

      // Wait for the OPENING LINE, not for base-dialog: base-dialog renders
      // before open() resolves, so waiting on it let the negative assertion run
      // against a panel that had not received the payload yet — it would have
      // passed even if the badge appeared a tick later.
      await findStageText('Well, well, what do we have here?')
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

    it('closes and logs when npcChat.end throws', async () => {
      npcChat.end.mockRejectedValue(new Error('offline'))
      renderPanel()

      await screen.findByText('Hi there')
      fireEvent.click(screen.getByText('End Conversation'))

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalledTimes(1)
      })
      // The server call still went out, and its rejection is logged rather than
      // swallowed whole — a failed /end can mean leaked server-side state.
      expect(npcChat.end).toHaveBeenCalledWith('npc_session_123')
      expect(consoleError).toHaveBeenCalledWith(
        '[npcChat] end failed; closing anyway:',
        'offline'
      )
    })

    it('closes without calling the server when the session key is not ready', async () => {
      let resolveOpen
      npcChat.open.mockReturnValue(new Promise((resolve) => { resolveOpen = resolve }))
      renderPanel()

      // Disabled during 'opening', so drive the handler the way the enabled
      // button would once loading clears but npcKey is still null.
      expect(screen.getByText('End Conversation')).toBeDisabled()
      expect(npcChat.end).not.toHaveBeenCalled()

      await act(async () => { resolveOpen({ data: makeNpcChatOpen({ npc_key: undefined }) }) })

      fireEvent.click(screen.getByText('End Conversation'))
      expect(npcChat.end).not.toHaveBeenCalled()
      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })
  })

  describe('Retrying a failed action', () => {
    it('retries opening the conversation when Retry is clicked after a failed open', async () => {
      npcChat.open.mockRejectedValueOnce(new Error('Network error'))
      renderPanel()

      await waitFor(() => expect(screen.getByText(/Failed to open conversation/i)).toBeInTheDocument())
      expect(npcChat.open).toHaveBeenCalledTimes(1)

      npcChat.open.mockResolvedValue(mockOpenResponse)
      fireEvent.click(screen.getByText('Retry'))

      await waitFor(() => expect(npcChat.open).toHaveBeenCalledTimes(2))
      // Retry must actually leave the 'failed' phase, not just re-fire the call.
      expect(await screen.findByText('Hi there')).toBeInTheDocument()
      expect(screen.queryByText(/Failed to open conversation/i)).toBeNull()
    })

    it('retries the same option when Retry is clicked after a failed response', async () => {
      npcChat.respond.mockRejectedValueOnce(new Error('Network error'))
      renderPanel()

      await screen.findByText('Hi there')
      fireEvent.click(screen.getByText('Hi there'))

      await waitFor(() => expect(screen.getByText(/NPC did not respond/i)).toBeInTheDocument())
      expect(npcChat.respond).toHaveBeenCalledTimes(1)

      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({ npc_response: 'Ah, welcome back.', jean_options: [] }),
      })
      fireEvent.click(screen.getByText('Retry'))

      await waitFor(() => expect(npcChat.respond).toHaveBeenCalledTimes(2))
      // The same option is replayed verbatim, key/text/tone included.
      expect(npcChat.respond).toHaveBeenLastCalledWith('npc_session_123', 'Hi there', 'open')
    })

    it('shows fixed local copy, not the server error body, when respond fails', async () => {
      const err = new Error('Bad Request')
      err.response = { data: { error: 'openai.APIStatusError: 404 model not found (req_abc)' } }
      npcChat.respond.mockRejectedValueOnce(err)
      renderPanel()

      await screen.findByText('Hi there')
      fireEvent.click(screen.getByText('Hi there'))

      // The provider-SDK exception text is disclosure, not a message: it is
      // logged for the dev and never rendered for the player.
      await waitFor(() => expect(screen.getByText('NPC did not respond')).toBeInTheDocument())
      expect(screen.queryByText(/APIStatusError/)).not.toBeInTheDocument()
      expect(screen.queryByText(/req_abc/)).not.toBeInTheDocument()
      expect(consoleError).toHaveBeenCalledWith(
        '[npcChat] respond failed:',
        'openai.APIStatusError: 404 model not found (req_abc)'
      )
    })

    it('does not duplicate Jean\'s line when a failed option is retried', async () => {
      npcChat.respond.mockRejectedValueOnce(new Error('Network error'))
      renderPanel()

      await screen.findByText('Hi there')
      fireEvent.click(screen.getByText('Hi there'))
      await waitFor(() => expect(screen.getByText(/NPC did not respond/i)).toBeInTheDocument())

      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({
          npc_response: 'Ah, welcome back.',
          jean_options: [makeJeanOption({ text: 'Hi there', tone: 'open' })],
        }),
      })
      fireEvent.click(screen.getByText('Retry'))
      await waitFor(() => expect(npcChat.respond).toHaveBeenCalledTimes(2))

      // The optimistic line is rolled back on failure, so the retry re-adds it
      // exactly once instead of stacking a second copy in the transcript.
      const entries = transcriptEntries()
      expect(entries.map((e) => e.dataset.speaker)).toEqual(['Mynx', 'Jean', 'Mynx'])
      expect(entries[1]).toHaveTextContent('Hi there')
    })

    it('clears the error and restores the dialogue options after a successful retry', async () => {
      npcChat.respond.mockRejectedValueOnce(new Error('Network error'))
      renderPanel()

      await screen.findByText('Hi there')
      fireEvent.click(screen.getByText('Hi there'))
      await waitFor(() => expect(screen.getByText(/NPC did not respond/i)).toBeInTheDocument())

      // While the error is up the option list is hidden.
      expect(screen.queryByText('Leave me alone')).toBeNull()

      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({
          npc_response: 'Ah, welcome back.',
          jean_options: [
            makeJeanOption({ text: 'Tell me more', tone: 'direct' }),
            makeJeanOption({ text: 'Leave me alone', tone: 'guarded' }),
          ],
        }),
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
      await findStageText('Farewell.')
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
        data: makeNpcChatOpen({ ...openData, npc_name: undefined }),
      })
      renderPanel({ npcName: 'Fallback Name' })

      // The prop must survive the response landing, and must be used to
      // attribute the NPC's line too — not just appear somewhere on screen.
      const stage = await findStageText('Well, well, what do we have here?')
      expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Fallback Name')
      expect(within(stage).getByAltText('Fallback Name (neutral)')).toBeInTheDocument()
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
      const { container } = renderPanel()

      await findStageText('Hello.')
      // loquacity_current/max both default (0/1) -> 0% width, danger color
      const bar = loquacityBar(container)
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

      await findStageText('A terse reply.')
      expect(loquacityBar(container).style.width).toBe('0%')
      expect(screen.queryByText('Leave me alone')).not.toBeInTheDocument()
    })
  })

  describe('loquacity bar color', () => {
    const renderWithLoquacity = async (current, max) => {
      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({ ...openData, loquacity_current: current, loquacity_max: max }),
      })
      const { container } = renderPanel()
      await screen.findByText('Hi there')
      return loquacityBar(container)
    }

    it('shows the primary color when loquacity is above 60%', async () => {
      const bar = await renderWithLoquacity(4, 5)
      expect(bar.style.width).toBe('80%')
      expect(bar.style.backgroundColor).toBe('rgb(0, 255, 136)')
    })

    it('shows the secondary color when loquacity is between 30% and 60%', async () => {
      const bar = await renderWithLoquacity(2, 5)
      expect(bar.style.width).toBe('40%')
      expect(bar.style.backgroundColor).toBe('rgb(255, 170, 0)')
    })

    it('shows the danger color when loquacity is at or below 30%', async () => {
      const bar = await renderWithLoquacity(1, 5)
      expect(bar.style.width).toBe('20%')
      expect(bar.style.backgroundColor).toBe('rgb(255, 68, 68)')
    })

    it('reads a zero loquacity max as spent, not as full', async () => {
      // `barColorFor` is a pure function of the percentage now, so the
      // malformed `max: 0` payload lands on 0% -> danger like any other empty
      // meter. (The old special case claimed "primary" for a bar that is
      // zero-width and therefore invisible either way.)
      const bar = await renderWithLoquacity(0, 0)
      expect(bar.style.width).toBe('0%')
      expect(bar.style.backgroundColor).toBe('rgb(255, 68, 68)')
    })
  })

  describe('relationship badge color', () => {
    const renderWithAttitude = async (attitude) => {
      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({
          ...openData,
          relationship: makeRelationship({ ...openData.relationship, attitude }),
        }),
      })
      renderPanel()
      return await screen.findByTestId('relationship-badge')
    }

    it('colors a hostile attitude with the danger color', async () => {
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

      const { unmount } = renderPanel()

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

      const { unmount } = renderPanel()

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

      const { unmount } = renderPanel()

      // Wait for the opening to finish so an option is clickable
      fireEvent.click(await screen.findByText('Hi there'))

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

        // Conversation ended -> a 2s close timer is scheduled. One millisecond
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

  describe('Conversation history', () => {
    const respondWith = (text) =>
      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({
          npc_response: text,
          jean_options: [makeJeanOption({ text: 'Go on', tone: 'open' })],
          loquacity_current: 1,
          conversation_quality: 'positive',
        }),
      })

    const openAndAnswer = async () => {
      renderPanel()
      await screen.findByText('Hi there')
      fireEvent.click(screen.getByText('Hi there'))
      await waitFor(() => expect(npcChat.respond).toHaveBeenCalled())
    }

    it('shows no preceding line on the opening beat', async () => {
      renderPanel()

      await waitFor(() => expect(screen.getByTestId('conversation-stage')).toBeInTheDocument())
      expect(screen.queryByTestId('npc-chat-previous-line')).not.toBeInTheDocument()
    })

    it("keeps Jean's line on screen above the NPC's reply", async () => {
      respondWith('Coin first.')
      await openAndAnswer()

      const previous = await screen.findByTestId('npc-chat-previous-line')
      await waitFor(() => expect(previous).toHaveTextContent('Hi there'))
      expect(within(previous).getByText('Jean')).toBeInTheDocument()
      // The `open` tone maps to the `curious` portrait — the only place the
      // TONE_EMOTIONS table is observable from the panel.
      expect(within(previous).getByRole('img')).toHaveAttribute('alt', 'Jean (curious)')

      // The newest line still belongs to the stage, not the recap strip.
      expect(previous).not.toHaveTextContent('Coin first.')
      await findStageText('Coin first.')
    })

    it('reacts to a positive turn with the matching NPC portrait', async () => {
      respondWith('Coin first.')
      await openAndAnswer()

      const stage = await screen.findByTestId('conversation-stage')
      // conversation_quality 'positive' -> QUALITY_EMOTIONS.positive === 'happy'.
      await waitFor(() =>
        expect(within(stage).getByAltText('Mynx the Swift (happy)')).toBeInTheDocument()
      )
      // ...and Jean keeps the tone she answered with, via the reaction map.
      expect(within(stage).getByAltText('Jean (curious)')).toBeInTheDocument()
    })

    it('opens the full transcript, with a portrait thumbnail per turn', async () => {
      respondWith('Coin first.')
      await openAndAnswer()
      await screen.findByTestId('npc-chat-previous-line')

      expect(screen.queryByTestId('conversation-history')).not.toBeInTheDocument()
      fireEvent.click(screen.getByText('View History'))

      const history = screen.getByTestId('conversation-history')
      const entries = within(history).getAllByTestId('transcript-entry')
      expect(entries).toHaveLength(3)
      expect(entries[0]).toHaveTextContent('Well, well, what do we have here?')
      expect(entries[1]).toHaveTextContent('Hi there')
      expect(entries[2]).toHaveTextContent('Coin first.')
      expect(within(entries[0]).getByRole('img')).toHaveAttribute('alt', 'Mynx the Swift (neutral)')
      expect(within(entries[1]).getByRole('img')).toHaveAttribute('alt', 'Jean (curious)')
      expect(within(entries[2]).getByRole('img')).toHaveAttribute('alt', 'Mynx the Swift (happy)')
      expect(screen.getByTestId('conversation-history-count')).toHaveTextContent('3 turns')
    })

    it('locks the dialogue options while the transcript is open', async () => {
      renderPanel()
      await screen.findByText('Hi there')

      fireEvent.click(screen.getByText('View History'))

      // The transcript covers the panel, but nothing makes the options behind it
      // inert — a stray Enter would otherwise spend a turn the player never saw.
      expect(screen.getByText('Hi there').closest('button')).toBeDisabled()
      fireEvent.click(screen.getByText('Hi there'))
      expect(npcChat.respond).not.toHaveBeenCalled()
    })

    it('suspends the end-of-conversation auto-close while the transcript is open', async () => {
      vi.useFakeTimers()
      try {
        npcChat.respond.mockResolvedValue({
          data: makeNpcChatRespond({
            npc_response: 'Farewell.',
            jean_options: [],
            loquacity_current: 0,
            conversation_ended: true,
          }),
        })

        renderPanel()
        await act(async () => {})
        fireEvent.click(screen.getByText('Hi there'))
        await act(async () => {})
        expect(screen.getByText('Conversation ended.')).toBeInTheDocument()

        fireEvent.click(screen.getByText('View History'))
        await act(async () => {
          vi.advanceTimersByTime(5000)
        })

        // Still reading: the panel must not close underneath the transcript.
        expect(mockOnClose).not.toHaveBeenCalled()
        expect(screen.getByTestId('conversation-history')).toBeInTheDocument()

        // Dismissing the transcript resumes the close it suspended.
        const closers = screen.getAllByTestId('dialog-close')
        fireEvent.click(closers[closers.length - 1])
        expect(mockOnClose).toHaveBeenCalledTimes(1)
      } finally {
        vi.useRealTimers()
      }
    })

    it('titles the history with the NPC display name', async () => {
      renderPanel()
      await waitFor(() => expect(screen.getByTestId('conversation-stage')).toBeInTheDocument())

      fireEvent.click(screen.getByText('View History'))

      expect(screen.getByText('Mynx the Swift — Conversation')).toBeInTheDocument()
    })
  })
})
