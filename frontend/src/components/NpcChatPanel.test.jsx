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

// TIMERS / the typewriter. ConversationStage runs in `mode="live"` here, which
// is deliberately NON-interactive: there is no click-to-finish gesture, so
// "wait for the line to land on the stage" could only ever mean "wait out
// length x 20 ms of wall clock". That is not a wait for a state change, it is
// a wait for one React re-render per character, and its cost scales with CPU
// load while waitFor's budget does not — which is exactly how the sibling
// panels' 1000 ms waits lost the race under a loaded parallel run. The 5000 ms
// budgets that used to sit here were the same bet at longer odds.
//
// So the hook hands back the finished line instead. The panel's behaviour has
// nothing to do with the animation: the reveal itself is covered character by
// character, on fake timers, in hooks/useTypewriter.test.js and
// components/ConversationStage.test.jsx. `typewriter.mode = 'partial'` freezes
// the stage mid-line for the one test that needs to tell the typed text apart
// from the announced text.
const typewriter = vi.hoisted(() => ({ mode: 'complete', PREFIX_CHARS: 8 }))
vi.mock('../hooks/useTypewriter', () => ({
  default: (text = '') => {
    const full = String(text ?? '')
    const partial = typewriter.mode === 'partial'
    return {
      displayedText: partial ? full.slice(0, typewriter.PREFIX_CHARS) : full,
      isComplete: !partial,
      finishImmediately: () => {},
      reset: () => {},
    }
  },
}))

// SCOPE. Everything the API state machine owns — phase transitions, payload
// defaults, supersession, unmount guards, the emotion tables, retry replay,
// the auto-close timer — is tested one level down, against the hook itself, in
// hooks/useNpcChat.test.js. This file covers what the PANEL owns: which props
// it hands BaseDialog, the recap strip, the loquacity bar and its colours, the
// relationship badge, the history dialog and what it gates, which controls go
// inert, the live region, and that dismissal ends the session server-side.
// Anything asserted in both places was removed from here, not from there.
//
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
// NOT mocked: the panel composes them, and mocking them out would leave the
// recap strip and the staged conversation unobservable. (Only the leaf
// `useTypewriter` inside the stage is stubbed — see the timers note above.
// The stage itself, portraits and all, is the real component.) The tone -> emotion
// and quality -> emotion mappings themselves are asserted directly against the
// tables in the hook suite, not inferred from an alt attribute here.
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
   * Wait for a line to land on the stage.
   *
   * The only wait left is for the mocked API promise to put the stage in the
   * DOM — one state transition, not `text.length` of them. With the typewriter
   * stubbed (see the top of the file) the prose is there the moment the stage
   * is, so the text assertion is synchronous and cannot lose a race.
   */
  const findStageText = async (text) => {
    const stage = await screen.findByTestId('conversation-stage')
    expect(stage).toHaveTextContent(text)
    return stage
  }

  beforeEach(() => {
    typewriter.mode = 'complete'
    vi.clearAllMocks()
    // The hook logs the server's detail on every failure path and never renders
    // it. Silenced here so an expected-failure test does not spew, and spied so
    // "logged instead of shown" can actually be asserted.
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    npcChat.open.mockResolvedValue(mockOpenResponse)
    // Every path out of the panel now ends the session, including the ones
    // that unmount it, so `end` must resolve for every test — not only the
    // handful that assert on it.
    npcChat.end.mockResolvedValue({ data: { success: true } })
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

  })

  describe('Loquacity Tracking', () => {
    it('fills the bar to the served current/max ratio', async () => {
      const { container } = renderPanel()

      await screen.findByText('Hi there')
      // 2 of 5 -> 40%.
      expect(loquacityBar(container).style.width).toBe('40%')
    })

  })

  describe('Error Handling', () => {
    it('shows fixed local copy and logs the server detail when open fails', async () => {
      npcChat.open.mockRejectedValue({ response: { data: { error: 'NPC not found' } } })

      renderPanel()

      // The server's `error` field is diagnostic detail — endpoint, model id,
      // status body, request id — and the panel holds whether or not the
      // server sanitised it. It is logged, never rendered.
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

  })

  describe('Closing Conversation', () => {
    // Every door out of the panel is the same door. BaseDialog's `onClose` is
    // ✕, the overlay click AND Escape — by far the most common way out — and
    // wired straight to the panel's own `onClose` it dismissed without ever
    // calling `POST /npc/chat/end`, leaving `player._active_chat_npc_id` and
    // the conversation record set server-side. The button was the only one
    // that closed properly, so both are asserted against the same claim.
    const dismissals = [
      ['the dialog chrome (✕ / overlay / Escape)', () => screen.getByTestId('dialog-close')],
      ['the End Conversation button', () => screen.getByText('End Conversation')],
    ]

    it.each(dismissals)('ends the session server-side when closed through %s', async (_door, control) => {
      renderPanel()

      // Wait on the RENDER, not on the call: open() having fired says nothing
      // about the panel having consumed the response.
      await screen.findByText('Hi there')
      fireEvent.click(control())

      await waitFor(() => expect(npcChat.end).toHaveBeenCalledWith('npc_session_123'))
      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })

    it('still closes on dismissal when there is no session to end', async () => {
      // `/open` never resolved, so there is nothing server-side to end and
      // routing the ✕ through the end handler must not trap the player.
      let resolveOpen
      npcChat.open.mockReturnValue(new Promise((resolve) => { resolveOpen = resolve }))
      renderPanel()

      fireEvent.click(screen.getByTestId('dialog-close'))

      expect(npcChat.end).not.toHaveBeenCalled()
      expect(mockOnClose).toHaveBeenCalledTimes(1)

      await act(async () => { resolveOpen(mockOpenResponse) })
    })

    it('ends the conversation the server opened after the panel was already gone', async () => {
      // The owner unmounts the panel on close — `InteractPanel` renders it as
      // `{showChatPanel && <NpcChatPanel/>}` — so a dismissal mid-`/open` left
      // the response landing on a hook with nowhere to put the `npc_key`. It
      // was dropped, `/end` was never sent, and `_active_chat_npc_id` stayed
      // set server-side.
      let resolveOpen
      npcChat.open.mockReturnValue(new Promise((resolve) => { resolveOpen = resolve }))

      function ChatHost() {
        const [open, setOpen] = React.useState(true)
        return open ? (
          <NpcChatPanel npcId={mockNpcId} npcName={mockNpcName} onClose={() => setOpen(false)} />
        ) : null
      }
      render(<ChatHost />)

      fireEvent.click(screen.getByTestId('dialog-close'))
      expect(screen.queryByTestId('base-dialog')).not.toBeInTheDocument()

      await act(async () => { resolveOpen(mockOpenResponse) })

      expect(npcChat.end).toHaveBeenCalledWith('npc_session_123')
    })
  })

  describe('Props Handling', () => {
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
      // The 2s delay itself is pinned with fake timers against the hook, in
      // useNpcChat.test.js's "closes exactly 2s after the server reports the
      // conversation ended"; burning 2s of real wall time here would only
      // duplicate it. What the panel owns is the state on screen meanwhile.
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

  describe('Announcing the reply to assistive tech', () => {
    // The dialog SHELL is accessible (focus trap, Escape, aria-modal,
    // per-instance labelling, role="status" on the loader). The feature's
    // PAYLOAD — the NPC's reply — landed in a plain <div>, so a screen-reader
    // user was told a reply was being fetched and never told it had arrived.
    const announcer = () => screen.getByTestId('npc-chat-announcer')

    it('announces the NPC line politely, without stealing focus', async () => {
      renderPanel()

      await waitFor(() =>
        expect(announcer()).toHaveTextContent('Well, well, what do we have here?')
      )
      expect(announcer()).toHaveAttribute('aria-live', 'polite')
      // atomic: the region is re-read whole, so a reply is never announced as
      // a diff against the previous one.
      expect(announcer()).toHaveAttribute('aria-atomic', 'true')
    })

    it('announces the COMPLETED line, not the typewriter text', async () => {
      // ConversationStage types the line out at 20ms/char. Feeding a polite
      // live region that per-character stream would re-announce on every
      // keystroke, which is worse than saying nothing at all.
      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({
          npc_key: 'npc_session_123',
          npc_name: 'Mynx the Swift',
          npc_opening: 'A rather long opening line, delivered slowly.',
          jean_options: [makeJeanOption({ text: 'Hi there', tone: 'open' })],
        }),
      })
      // Freeze the stage mid-line. The old version of this test only waited
      // for the animation to catch up, so nothing in it ever asserted that the
      // stage and the announcement disagreed — the claim in its name.
      typewriter.mode = 'partial'
      renderPanel()

      const stage = await screen.findByTestId('conversation-stage')
      // Mid-type: the stage is still partway through the line...
      expect(stage).toHaveTextContent('A rather')
      expect(stage).not.toHaveTextContent('delivered slowly.')
      // ...but the announcement is already the whole of it.
      expect(announcer().textContent).toBe('A rather long opening line, delivered slowly.')
    })

    it('names the aside as an aside instead of speaking it as part of the line', async () => {
      // The branch's standing decision is that an aside is FLAVOR, NOT SPEECH:
      // the stage gives it its own italic slot above the line. A live region
      // has no typography, so it says so in words — otherwise a screen-reader
      // user hears the stage direction as something the NPC said out loud.
      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({
          ...openData,
          npc_opening: 'Coin first.',
          npc_flavor: 'She does not look up.',
        }),
      })
      renderPanel()

      await waitFor(() =>
        // And exactly one terminator at the seam: joining the two with a bare
        // '. ' produced "…look up.. Coin first." for every flavor the server
        // had already terminated, which is most of them.
        expect(announcer().textContent).toBe('Aside: She does not look up. Coin first.')
      )
    })

    it('spares a deliberate ellipsis and an aside that ends on its own mark', async () => {
      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({
          ...openData,
          npc_opening: 'Coin first.',
          npc_flavor: 'She weighs the purse...',
        }),
      })
      const { rerender } = renderPanel()

      await waitFor(() =>
        expect(announcer().textContent).toBe('Aside: She weighs the purse... Coin first.')
      )

      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({
          ...openData,
          npc_key: 'npc_session_456',
          npc_opening: 'Coin first.',
          npc_flavor: 'She laughs!',
        }),
      })
      rerender(<NpcChatPanel npcId="Gorran" npcName="Gorran" onClose={mockOnClose} />)

      await waitFor(() =>
        expect(announcer().textContent).toBe('Aside: She laughs! Coin first.')
      )
    })

    it('adds a terminator to an aside the server left unpunctuated', async () => {
      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({
          ...openData,
          npc_opening: 'Coin first.',
          npc_flavor: 'She does not look up',
        }),
      })
      renderPanel()

      await waitFor(() =>
        expect(announcer().textContent).toBe('Aside: She does not look up. Coin first.')
      )
    })

    it('announces the reply, not Jean\'s own words', async () => {
      // Jean's line is the option the player just clicked; re-reading it back
      // interrupts the reply they are actually waiting on.
      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({ npc_response: 'You have my attention.', jean_options: [] }),
      })
      renderPanel()
      await screen.findByText('Hi there')

      fireEvent.click(screen.getByText('Hi there'))

      await waitFor(() => expect(announcer()).toHaveTextContent('You have my attention.'))
      expect(announcer()).not.toHaveTextContent('Hi there')
    })

    it('says nothing while the opening line is still being fetched', async () => {
      let resolveOpen
      npcChat.open.mockReturnValue(new Promise((resolve) => { resolveOpen = resolve }))
      renderPanel()

      // Empty, not absent: a live region has to be in the DOM before the text
      // lands, or the change that arrives with it is never announced.
      expect(announcer()).toBeInTheDocument()
      expect(announcer().textContent).toBe('')

      await act(async () => { resolveOpen(mockOpenResponse) })
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

    it('locks Retry while the transcript is open', async () => {
      // Retry re-issues a PAID `/open` or `/respond`. It was the one live
      // control left behind the stacked transcript — the options and End
      // Conversation were both already gated — so a click landing on the panel
      // underneath spent a provider turn the player never saw.
      npcChat.respond.mockRejectedValueOnce(new Error('Network error'))
      renderPanel()
      await screen.findByText('Hi there')
      fireEvent.click(screen.getByText('Hi there'))
      await waitFor(() => expect(screen.getByText('Retry')).toBeInTheDocument())
      expect(screen.getByText('Retry').closest('button')).toBeEnabled()

      fireEvent.click(screen.getByText('View History'))

      expect(screen.getByText('Retry').closest('button')).toBeDisabled()
      npcChat.respond.mockClear()
      fireEvent.click(screen.getByText('Retry'))
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
