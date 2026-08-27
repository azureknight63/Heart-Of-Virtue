import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useNpcChat, toneEmotion, qualityEmotion, npcCast, JEAN_ID } from './useNpcChat'
import { portraitUrl } from '../utils/portraits'
import { makeNpcChatOpen, makeNpcChatRespond, makeJeanOption, makeRelationship } from '../test/payloads'

vi.mock('../api/npcChat', () => ({
  default: {
    open: vi.fn(),
    respond: vi.fn(),
    end: vi.fn(),
  },
}))

import npcChat from '../api/npcChat'

/** A promise plus its settle handles, so a request can be held mid-flight. */
function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('useNpcChat', () => {
  const onClose = vi.fn()
  let consoleError

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

  /** Mount the hook against `npcId`, defaulting to the fixture NPC. */
  const mount = (npcId = 'Mynx', npcName = 'Mynx') =>
    renderHook(({ id, name }) => useNpcChat(id, name, onClose), {
      initialProps: { id: npcId, name: npcName },
    })

  /** Mount and wait until the opening turn has landed. */
  const mountOpened = async (npcId = 'Mynx') => {
    const rendered = mount(npcId)
    await waitFor(() => expect(rendered.result.current.phase).toBe('waiting_jean'))
    return rendered
  }

  beforeEach(() => {
    vi.clearAllMocks()
    // The hook logs the raw server detail on every failure path (it is never
    // rendered — that text is provider-SDK exception detail). Silenced so the
    // expected-failure tests do not spew, and spied so "logged, not shown" is
    // actually assertable.
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    npcChat.open.mockResolvedValue({ data: openData })
    npcChat.respond.mockResolvedValue({
      data: makeNpcChatRespond({ npc_response: 'A measured reply.', jean_options: [] }),
    })
    npcChat.end.mockResolvedValue({ data: { success: true } })
  })

  afterEach(() => {
    consoleError.mockRestore()
  })

  // -------------------------------------------------------------------------
  // Portrait preloading
  //
  // Declared FIRST on purpose: `preloadedPortraits` is a module-level Set that
  // deliberately outlives any one conversation, so these tests only see a clean
  // registry while nothing else in the file has mounted the hook yet.
  // -------------------------------------------------------------------------
  describe('portrait preloading', () => {
    let realImage
    let built

    beforeEach(() => {
      built = []
      realImage = globalThis.Image
      globalThis.Image = class FakeImage {
        constructor() {
          built.push(this)
        }
      }
    })

    afterEach(() => {
      globalThis.Image = realImage
    })

    it('warms every portrait the next turn can need, and each URL only once', async () => {
      // A unique npcId per test: the preload registry is process-wide on
      // purpose (a 404 is not cached by the browser, so without it a speaker
      // with a partial emotion set is re-requested every single turn).
      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({
          npc_key: 'k',
          npc_name: 'Preloadable',
          jean_options: [
            makeJeanOption({ text: 'a', tone: 'open' }),
            makeJeanOption({ text: 'b', tone: 'open' }), // same tone -> same URL
            makeJeanOption({ text: 'c', tone: 'guarded' }),
          ],
        }),
      })
      const { result } = await mountOpened('PreloadableAlpha')

      const urls = built.map((img) => img.src)
      expect(new Set(urls).size).toBe(urls.length)
      // Jean wears the tone of whichever option is clicked (2 distinct here);
      // the NPC's reaction is one of the four conversation-quality emotions.
      expect(urls).toContain(portraitUrl(JEAN_ID, 'curious'))
      expect(urls).toContain(portraitUrl(JEAN_ID, 'skeptical'))
      for (const emotion of ['happy', 'neutral', 'concerned', 'angry']) {
        expect(urls).toContain(portraitUrl('PreloadableAlpha', emotion))
      }
      expect(urls).toHaveLength(6)

      // A second turn serving the same option tones must not re-request them.
      built.length = 0
      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({
          npc_response: 'Again.',
          jean_options: [makeJeanOption({ text: 'a', tone: 'open' })],
        }),
      })
      await act(async () => {
        await result.current.handleOptionClick({ text: 'a', tone: 'open' })
      })
      expect(built).toHaveLength(0)
    })

    it('marks preloads for asynchronous decode', async () => {
      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({ jean_options: [makeJeanOption({ tone: 'direct' })] }),
      })
      await mountOpened('PreloadableBeta')

      expect(built.length).toBeGreaterThan(0)
      expect(built.every((img) => img.decoding === 'async')).toBe(true)
    })
  })

  // -------------------------------------------------------------------------
  // Emotion tables
  // -------------------------------------------------------------------------
  describe('toneEmotion', () => {
    // `direct` / `guarded` / `open` are the ONLY tones the engine emits
    // (src/npc/_chat_llm.py, src/api/routes/npc_chat.py). Fixtures elsewhere
    // used to invent 'curious'/'hostile', which fell through the `|| 'neutral'`
    // fallback — so every portrait assertion in the suite read 'neutral' and
    // rewriting this function as `() => 'neutral'` broke nothing.
    it.each([
      ['direct', 'neutral'],
      ['guarded', 'skeptical'],
      ['open', 'curious'],
    ])('maps the %s tone to the %s portrait', (tone, emotion) => {
      expect(toneEmotion(tone)).toBe(emotion)
    })

    it('is case-insensitive', () => {
      expect(toneEmotion('GUARDED')).toBe('skeptical')
      expect(toneEmotion('Open')).toBe('curious')
    })

    it.each([undefined, null, '', 'hostile', 'curious', 42])(
      'falls back to neutral for %s',
      (tone) => {
        expect(toneEmotion(tone)).toBe('neutral')
      }
    )

    it('resolves to art that exists in the portrait vocabulary', () => {
      // A mapped emotion outside utils/portraits' EMOTIONS list would be
      // normalised away to neutral in the URL while still reading as mapped
      // here — a mapping that silently does nothing.
      for (const tone of ['direct', 'guarded', 'open']) {
        const emotion = toneEmotion(tone)
        expect(portraitUrl(JEAN_ID, emotion)).toContain(`/${emotion}.png`)
      }
    })
  })

  describe('qualityEmotion', () => {
    it.each([
      ['positive', 'happy'],
      ['neutral', 'neutral'],
      ['negative', 'concerned'],
      ['offensive', 'angry'],
    ])('maps %s conversation quality to the %s portrait', (quality, emotion) => {
      expect(qualityEmotion(quality)).toBe(emotion)
    })

    it.each([undefined, null, '', 'delighted'])(
      'falls back to neutral for %s',
      (quality) => {
        expect(qualityEmotion(quality)).toBe('neutral')
      }
    )
  })

  describe('npcCast', () => {
    it('stages Jean left and the NPC right, under the display name', () => {
      expect(npcCast('Mynx', 'Mynx the Swift')).toEqual([
        { id: 'Jean', name: 'Jean', side: 'left', emotion: 'neutral' },
        { id: 'Mynx', name: 'Mynx the Swift', side: 'right', emotion: 'neutral' },
      ])
    })

    it('falls back to the npc id when no display name is known yet', () => {
      expect(npcCast('Gorran', undefined)[1].name).toBe('Gorran')
    })
  })

  // -------------------------------------------------------------------------
  // Opening
  // -------------------------------------------------------------------------
  describe('opening the conversation', () => {
    it('opens once for the npcId and publishes the served turn', async () => {
      const { result } = await mountOpened()

      expect(npcChat.open).toHaveBeenCalledTimes(1)
      expect(npcChat.open).toHaveBeenCalledWith('Mynx')
      expect(result.current.displayName).toBe('Mynx the Swift')
      expect(result.current.loquacity).toEqual({ current: 2, max: 5 })
      expect(result.current.currentOptions).toHaveLength(2)
      expect(result.current.relationship.attitude).toBe('neutral')
      expect(result.current.conversationCast).toEqual(npcCast('Mynx', 'Mynx the Swift'))
      expect(result.current.conversationSegments).toEqual([
        {
          text: 'Well, well, what do we have here?',
          speaker: 'Mynx',
          emotion: 'neutral',
          flavor: '',
          reactions: {},
          in_conversation: true,
        },
      ])
      expect(result.current.loading).toBe(false)
    })

    it('applies the malformed-payload defaults for a bare response', async () => {
      npcChat.open.mockResolvedValue({ data: { npc_key: 'k', npc_opening: 'Hm.' } })
      const { result } = await mountOpened()

      // Missing loquacity reads as 0/1, missing options as none, missing
      // standing as unknown — the defaults ARE the contract.
      expect(result.current.loquacity).toEqual({ current: 0, max: 1 })
      expect(result.current.currentOptions).toEqual([])
      expect(result.current.relationship).toBeNull()
      expect(result.current.displayName).toBe('Mynx')
    })

    it('stages nothing when the server sends no opening line', async () => {
      npcChat.open.mockResolvedValue({ data: makeNpcChatOpen({ npc_opening: null }) })
      const { result } = await mountOpened()

      expect(result.current.conversationSegments).toEqual([])
    })

    it('carries npc_flavor onto the opening segment', async () => {
      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({ npc_opening: 'Aye.', npc_flavor: 'She does not look up.' }),
      })
      const { result } = await mountOpened()

      expect(result.current.conversationSegments[0].flavor).toBe('She does not look up.')
    })
  })

  // -------------------------------------------------------------------------
  // The reset + supersession guard on the open effect
  // -------------------------------------------------------------------------
  describe('switching NPC', () => {
    it('clears the previous conversation synchronously, before the new request resolves', async () => {
      const pending = deferred()
      const { result, rerender } = await mountOpened()
      expect(result.current.conversationSegments).toHaveLength(1)

      npcChat.open.mockReturnValue(pending.promise)
      act(() => rerender({ id: 'Gorran', name: 'Gorran' }))

      // Every write used to happen only AFTER the await, so for the whole round
      // trip the stage kept drawing the previous NPC's portraits and options
      // and `npcKey` still addressed the old conversation.
      expect(result.current.phase).toBe('opening')
      expect(result.current.displayName).toBe('Gorran')
      expect(result.current.conversationSegments).toEqual([])
      expect(result.current.conversationCast).toBeNull()
      expect(result.current.currentOptions).toEqual([])
      expect(result.current.loquacity).toEqual({ current: 0, max: 1 })
      expect(result.current.relationship).toBeNull()
      expect(result.current.error).toBeNull()
      expect(result.current.retry).toBeNull()

      await act(async () => {
        pending.resolve({ data: makeNpcChatOpen({ npc_name: 'Gorran', npc_opening: 'You again.' }) })
      })
      expect(result.current.conversationSegments[0].text).toBe('You again.')
    })

    it('ignores a superseded /open response for the NPC that was switched away from', async () => {
      const first = deferred()
      npcChat.open.mockImplementation((id) =>
        id === 'Mynx'
          ? first.promise
          : Promise.resolve({
              data: makeNpcChatOpen({
                npc_key: 'gorran_key',
                npc_name: 'Gorran',
                npc_opening: 'You again.',
                jean_options: [makeJeanOption({ text: 'Peace, Gorran.', tone: 'open' })],
              }),
            })
      )

      const { result, rerender } = mount('Mynx')
      // Switch before the first request comes back.
      await act(async () => {
        rerender({ id: 'Gorran', name: 'Gorran' })
      })
      await waitFor(() => expect(result.current.phase).toBe('waiting_jean'))
      expect(result.current.displayName).toBe('Gorran')

      // The stale response lands last and must be dropped on the floor.
      await act(async () => {
        first.resolve({ data: openData })
      })

      expect(result.current.displayName).toBe('Gorran')
      expect(result.current.conversationSegments[0].text).toBe('You again.')
      expect(result.current.currentOptions).toEqual([
        makeJeanOption({ text: 'Peace, Gorran.', tone: 'open' }),
      ])
      expect(result.current.conversationCast).toEqual(npcCast('Gorran', 'Gorran'))
    })

    it('ignores a superseded /open REJECTION rather than showing an error for the old NPC', async () => {
      const first = deferred()
      npcChat.open.mockImplementationOnce(() => first.promise)

      const { result, rerender } = mount('Mynx')
      await act(async () => {
        rerender({ id: 'Gorran', name: 'Gorran' })
      })
      await waitFor(() => expect(result.current.phase).toBe('waiting_jean'))

      await act(async () => {
        first.reject(new Error('too late'))
      })

      expect(result.current.phase).toBe('waiting_jean')
      expect(result.current.error).toBeNull()
    })

    it('does not re-open when only the display name changes', async () => {
      const { rerender } = await mountOpened()
      expect(npcChat.open).toHaveBeenCalledTimes(1)

      await act(async () => {
        rerender({ id: 'Mynx', name: 'Mynx the Swift' })
      })

      // A display-name change must not re-open (and re-bill) the conversation.
      expect(npcChat.open).toHaveBeenCalledTimes(1)
    })
  })

  // -------------------------------------------------------------------------
  // The 'failed' phase
  // -------------------------------------------------------------------------
  describe('a failed open', () => {
    it("lands on 'failed', not 'ended', and logs the server detail instead of showing it", async () => {
      npcChat.open.mockRejectedValue({ response: { data: { error: 'openai 404 model_not_found' } } })
      const { result } = mount()

      await waitFor(() => expect(result.current.phase).toBe('failed'))
      // 'ended' rendered a transport error as a finished conversation: the panel
      // showed "Conversation ended.", withdrew End Conversation, and Retry could
      // never move the phase off it.
      expect(result.current.phase).not.toBe('ended')
      expect(result.current.error).toBe('Failed to open conversation')
      expect(result.current.error).not.toContain('404')
      expect(consoleError).toHaveBeenCalledWith(
        '[npcChat] open failed:',
        'openai 404 model_not_found'
      )
      expect(result.current.loading).toBe(false)
    })

    it('logs the JS error message when there is no response body', async () => {
      npcChat.open.mockRejectedValue(new Error('Network Error'))
      const { result } = mount()

      await waitFor(() => expect(result.current.phase).toBe('failed'))
      expect(consoleError).toHaveBeenCalledWith('[npcChat] open failed:', 'Network Error')
    })

    it('exposes a retry that clears the failed phase on success', async () => {
      npcChat.open.mockRejectedValueOnce(new Error('boom'))
      const { result } = mount()

      await waitFor(() => expect(result.current.phase).toBe('failed'))
      expect(typeof result.current.retry).toBe('function')

      npcChat.open.mockResolvedValue({ data: openData })
      await act(async () => {
        await result.current.retry()
      })

      expect(npcChat.open).toHaveBeenCalledTimes(2)
      expect(result.current.phase).toBe('waiting_jean')
      expect(result.current.error).toBeNull()
      expect(result.current.currentOptions).toHaveLength(2)
    })

    it('offers no retry while nothing has failed', async () => {
      const { result } = await mountOpened()
      expect(result.current.retry).toBeNull()
    })
  })

  // -------------------------------------------------------------------------
  // Responding
  // -------------------------------------------------------------------------
  describe('sending Jean\'s reply', () => {
    it('sends the option verbatim against the session key and stages both turns', async () => {
      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({
          npc_response: 'Coin first.',
          jean_options: [makeJeanOption({ text: 'Go on', tone: 'direct' })],
          loquacity_current: 1,
          conversation_quality: 'positive',
        }),
      })
      const { result } = await mountOpened()

      await act(async () => {
        await result.current.handleOptionClick({ text: 'Hi there', tone: 'open' })
      })

      expect(npcChat.respond).toHaveBeenCalledWith('npc_session_123', 'Hi there', 'open')
      const segments = result.current.conversationSegments
      expect(segments).toHaveLength(3)
      // Jean wears the tone she answered with; the NPC wears the turn quality.
      expect(segments[1]).toMatchObject({ speaker: 'Jean', emotion: 'curious', text: 'Hi there' })
      expect(segments[1].reactions).toEqual({ Mynx: 'curious' })
      expect(segments[2]).toMatchObject({ speaker: 'Mynx', emotion: 'happy', text: 'Coin first.' })
      expect(segments[2].reactions).toEqual({ Jean: 'curious' })
      expect(result.current.loquacity).toEqual({ current: 1, max: 5 })
      expect(result.current.phase).toBe('waiting_jean')
    })

    it('ignores a click while the NPC is still composing', async () => {
      const pending = deferred()
      npcChat.respond.mockReturnValue(pending.promise)
      const { result } = await mountOpened()

      act(() => {
        result.current.handleOptionClick({ text: 'Hi there', tone: 'open' })
      })
      await waitFor(() => expect(result.current.phase).toBe('waiting_npc'))

      await act(async () => {
        await result.current.handleOptionClick({ text: 'Leave me alone', tone: 'guarded' })
      })
      expect(npcChat.respond).toHaveBeenCalledTimes(1)

      await act(async () => {
        pending.resolve({ data: makeNpcChatRespond({ npc_response: 'Done.', jean_options: [] }) })
      })
    })

    it('ignores a click before the session key exists', async () => {
      const pending = deferred()
      npcChat.open.mockReturnValue(pending.promise)
      const { result } = mount()

      await act(async () => {
        await result.current.handleOptionClick({ text: 'Hi there', tone: 'open' })
      })
      expect(npcChat.respond).not.toHaveBeenCalled()

      await act(async () => { pending.resolve({ data: openData }) })
    })
  })

  describe('a failed respond', () => {
    it('stages Jean optimistically, then rolls that segment back', async () => {
      const pending = deferred()
      npcChat.respond.mockReturnValue(pending.promise)
      const { result } = await mountOpened()

      act(() => {
        result.current.handleOptionClick({ text: 'Hi there', tone: 'open' })
      })

      // The optimistic write must actually happen, or "rollback" proves nothing.
      await waitFor(() => expect(result.current.conversationSegments).toHaveLength(2))
      expect(result.current.conversationSegments[1].text).toBe('Hi there')

      await act(async () => {
        pending.reject(new Error('Network Error'))
      })

      expect(result.current.conversationSegments).toHaveLength(1)
      expect(result.current.conversationSegments[0].speaker).toBe('Mynx')
      expect(result.current.error).toBe('NPC did not respond')
      // Back to waiting_jean, not 'failed': the conversation itself is intact.
      expect(result.current.phase).toBe('waiting_jean')
      expect(consoleError).toHaveBeenCalledWith('[npcChat] respond failed:', 'Network Error')
    })

    it('replays exactly the same option through retry, re-adding the line once', async () => {
      npcChat.respond.mockRejectedValueOnce(new Error('Network Error'))
      const { result } = await mountOpened()

      await act(async () => {
        await result.current.handleOptionClick({ text: 'Leave me alone', tone: 'guarded' })
      })
      expect(result.current.conversationSegments).toHaveLength(1)

      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({ npc_response: 'Suit yourself.', jean_options: [] }),
      })
      await act(async () => {
        await result.current.retry()
      })

      expect(npcChat.respond).toHaveBeenLastCalledWith(
        'npc_session_123',
        'Leave me alone',
        'guarded'
      )
      const segments = result.current.conversationSegments
      expect(segments.filter((s) => s.text === 'Leave me alone')).toHaveLength(1)
      expect(segments).toHaveLength(3)
      expect(result.current.error).toBeNull()
      expect(result.current.retry).toBeNull()
    })

    it('clears a stale error when the next option is clicked directly', async () => {
      npcChat.respond.mockRejectedValueOnce(new Error('Network Error'))
      const { result } = await mountOpened()

      await act(async () => {
        await result.current.handleOptionClick({ text: 'Hi there', tone: 'open' })
      })
      expect(result.current.error).toBe('NPC did not respond')

      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({ npc_response: 'Fine.', jean_options: [] }),
      })
      await act(async () => {
        await result.current.handleOptionClick({ text: 'Leave me alone', tone: 'guarded' })
      })

      // The panel gates the option list on `!error`, so a stale error hid every
      // remaining choice for the rest of the conversation.
      expect(result.current.error).toBeNull()
    })
  })

  // -------------------------------------------------------------------------
  // Ending
  // -------------------------------------------------------------------------
  describe('ending the conversation', () => {
    it('ends server-side then closes', async () => {
      const { result } = await mountOpened()

      await act(async () => {
        await result.current.handleEndConversation()
      })

      expect(npcChat.end).toHaveBeenCalledWith('npc_session_123')
      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('still closes when /end fails — and logs it instead of swallowing it', async () => {
      npcChat.end.mockRejectedValue(new Error('expired key'))
      const { result } = await mountOpened()

      await act(async () => {
        await result.current.handleEndConversation()
      })

      // Closing is still right for the player, but a failed /end can mean an
      // expired key or leaked server-side conversation state; swallowing it
      // whole made that invisible to player, dev and log pipeline at once.
      expect(onClose).toHaveBeenCalledTimes(1)
      expect(consoleError).toHaveBeenCalledWith(
        '[npcChat] end failed; closing anyway:',
        'expired key'
      )
    })

    it('closes without calling the server when there is no session key', async () => {
      npcChat.open.mockRejectedValue(new Error('boom'))
      const { result } = mount()
      await waitFor(() => expect(result.current.phase).toBe('failed'))

      await act(async () => {
        await result.current.handleEndConversation()
      })

      expect(npcChat.end).not.toHaveBeenCalled()
      expect(onClose).toHaveBeenCalledTimes(1)
    })
  })

  describe('the end-of-conversation auto-close', () => {
    beforeEach(() => vi.useFakeTimers())
    afterEach(() => vi.useRealTimers())

    const openEndedTurn = async () => {
      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({
          npc_response: 'Farewell.',
          jean_options: [],
          conversation_ended: true,
        }),
      })
      const rendered = mount()
      await act(async () => {})
      await act(async () => {
        await rendered.result.current.handleOptionClick({ text: 'Hi there', tone: 'open' })
      })
      expect(rendered.result.current.phase).toBe('ended')
      return rendered
    }

    it('closes exactly 2s after the server reports the conversation ended', async () => {
      const { result } = await openEndedTurn()
      expect(result.current.phase).toBe('ended')

      await act(async () => { vi.advanceTimersByTime(1999) })
      expect(onClose).not.toHaveBeenCalled()

      await act(async () => { vi.advanceTimersByTime(1) })
      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('cancelAutoClose suspends that close indefinitely', async () => {
      const { result } = await openEndedTurn()

      act(() => result.current.cancelAutoClose())
      await act(async () => { vi.advanceTimersByTime(60000) })

      expect(onClose).not.toHaveBeenCalled()
    })

    it('does not close after unmount', async () => {
      const { unmount } = await openEndedTurn()

      unmount()
      await act(async () => { vi.advanceTimersByTime(5000) })

      expect(onClose).not.toHaveBeenCalled()
    })
  })

  describe('unmount safety', () => {
    it('drops a /respond response that lands after unmount', async () => {
      const pending = deferred()
      npcChat.respond.mockReturnValue(pending.promise)
      const { result, unmount } = await mountOpened()

      act(() => {
        result.current.handleOptionClick({ text: 'Hi there', tone: 'open' })
      })
      await waitFor(() => expect(result.current.phase).toBe('waiting_npc'))
      unmount()

      await act(async () => {
        pending.resolve({
          data: makeNpcChatRespond({ npc_response: 'late', conversation_ended: true }),
        })
      })

      // The post-await guard returns before scheduling the auto-close timer.
      expect(onClose).not.toHaveBeenCalled()
    })

    it('drops a /respond rejection that lands after unmount', async () => {
      const pending = deferred()
      npcChat.respond.mockReturnValue(pending.promise)
      const { result, unmount } = await mountOpened()

      act(() => {
        result.current.handleOptionClick({ text: 'Hi there', tone: 'open' })
      })
      await waitFor(() => expect(result.current.phase).toBe('waiting_npc'))
      unmount()

      await act(async () => {
        pending.reject(new Error('late failure'))
      })

      expect(consoleError).not.toHaveBeenCalled()
    })
  })

})
