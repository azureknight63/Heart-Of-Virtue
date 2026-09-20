import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { StrictMode } from 'react'
import { renderHook, act, waitFor } from '@testing-library/react'
import {
  useNpcChat,
  toneEmotion,
  qualityEmotion,
  npcCast,
  JEAN_ID,
  KIND_LABELS,
  kindLabel,
  QUALITY_EMOTIONS,
  NPC_LISTENING_EMOTION,
  __resetPreloadedPortraits,
} from './useNpcChat'
import { portraitUrl, EMOTIONS } from '../utils/portraits'
import { makeNpcChatOpen, makeNpcChatRespond, makeJeanOption, makeRelationship } from '../test/payloads'

// The real module's constants survive; only the calls are stubbed.
vi.mock('../api/npcChat', async (importOriginal) => ({
  ...(await importOriginal()),
  default: {
    open: vi.fn(),
    respond: vi.fn(),
    end: vi.fn(),
  },
}))

import npcChat, { NPC_CHAT_TIMEOUT_MS } from '../api/npcChat'

/** What axios rejects with when the client deadline on a chat call fires. */
const axiosTimeoutError = () =>
  Object.assign(new Error(`timeout of ${NPC_CHAT_TIMEOUT_MS}ms exceeded`), { code: 'ECONNABORTED' })

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
      makeJeanOption({ text: 'Hi there', tone: 'curious' }),
      makeJeanOption({ text: 'Leave me alone', tone: 'skeptical' }),
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
    // The portrait preload registry is module-level and survives between
    // tests, so without this the "each URL only once" counts below would
    // depend on which describe block ran first.
    __resetPreloadedPortraits()
    // The hook logs the server's detail on every failure path and never
    // renders it: the field is diagnostic (endpoint, model id, status body,
    // request id) and the hook holds whether or not the server sanitised it.
    // Silenced so the expected-failure tests do not spew, and spied so
    // "logged, not shown" is actually assertable.
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
  // `preloadedPortraits` is a module-level Set that deliberately outlives any
  // one conversation. The file-wide `beforeEach` clears it via
  // `__resetPreloadedPortraits`, so the exact-count assertions below hold no
  // matter where this block sits or what runs before it -- they used to pass
  // only because this block was declared first.
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
            makeJeanOption({ text: 'a', tone: 'curious' }),
            makeJeanOption({ text: 'b', tone: 'curious' }), // same tone -> same URL
            makeJeanOption({ text: 'c', tone: 'skeptical' }),
          ],
        }),
      })
      const { result } = await mountOpened('PreloadableAlpha')

      const urls = built.map((img) => img.src)
      expect(new Set(urls).size).toBe(urls.length)
      // Jean wears the tone of whichever option is clicked (2 distinct here);
      // the NPC wears the listening emotion while she speaks and then one of
      // the four conversation-quality emotions.
      expect(urls).toContain(portraitUrl(JEAN_ID, 'curious'))
      expect(urls).toContain(portraitUrl(JEAN_ID, 'skeptical'))
      // Iterated from the tables themselves — a hand-copied list cannot fail
      // when an emotion is added to one of them without being preloaded, which
      // is the only regression this assertion exists to catch.
      for (const emotion of [NPC_LISTENING_EMOTION, ...Object.values(QUALITY_EMOTIONS)]) {
        expect(urls).toContain(portraitUrl('PreloadableAlpha', emotion))
      }
      // 2 Jean tones + every distinct NPC emotion above.
      const npcEmotions = new Set([NPC_LISTENING_EMOTION, ...Object.values(QUALITY_EMOTIONS)])
      expect(urls).toHaveLength(2 + npcEmotions.size)

      // A second turn serving the same option tones must not re-request them.
      built.length = 0
      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({
          npc_response: 'Again.',
          jean_options: [makeJeanOption({ text: 'a', tone: 'curious' })],
        }),
      })
      await act(async () => {
        await result.current.handleOptionClick({ text: 'a', tone: 'curious' })
      })
      expect(built).toHaveLength(0)
    })

    it('warms the emotion the NPC is guaranteed to wear on every Jean beat', async () => {
      // `handleOptionClick` stages the NPC with NPC_LISTENING_EMOTION on EVERY
      // turn. While that was a bare literal it was also the one emotion the
      // preload set never covered, so a speaker shipping partial art (gorran/
      // has two portraits) 404'd it once per beat — uncached, undeduped, and
      // invisible to `preloadedPortraits`, which only remembers what it asked for.
      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({ jean_options: [makeJeanOption({ tone: 'neutral' })] }),
      })
      const { result } = await mountOpened('PreloadableGamma')

      expect(built.map((img) => img.src)).toContain(
        portraitUrl('PreloadableGamma', NPC_LISTENING_EMOTION)
      )
      // ...and it is the same constant the optimistic Jean segment reacts with.
      await act(async () => {
        await result.current.handleOptionClick({ text: 'Hi', tone: 'neutral' })
      })
      expect(result.current.conversationSegments[1].reactions).toEqual({
        PreloadableGamma: NPC_LISTENING_EMOTION,
      })
    })

    it('marks preloads for asynchronous decode', async () => {
      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({ jean_options: [makeJeanOption({ tone: 'neutral' })] }),
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
    // Tone IS the portrait emotion (issue #591) — there is no table between
    // them, so this is `normalizeEmotion` and the test is that every emotion
    // the art registers survives the trip unchanged.
    it.each(EMOTIONS)('passes the %s tone through as its own portrait', (tone) => {
      expect(toneEmotion(tone)).toBe(tone)
    })

    it('is case-insensitive', () => {
      expect(toneEmotion('SKEPTICAL')).toBe('skeptical')
      expect(toneEmotion('Curious')).toBe('curious')
    })

    it.each([undefined, null, '', 'hostile', 'direct', 'guarded', 42])(
      'falls back to neutral for %s',
      (tone) => {
        expect(toneEmotion(tone)).toBe('neutral')
      }
    )
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

  describe('the vocabularies as a whole', () => {
    // Tone no longer has a table — it IS the emotion list — so what is left to
    // check is the quality table, the guaranteed listening emotion, and that
    // both engine-owned vocabularies still line up with their client halves.
    const everyMappedEmotion = () => [
      ...EMOTIONS,
      ...Object.values(QUALITY_EMOTIONS),
      NPC_LISTENING_EMOTION,
    ]

    it('maps only to emotions utils/portraits actually registers', () => {
      expect(everyMappedEmotion().length).toBeGreaterThan(0)
      for (const emotion of everyMappedEmotion()) {
        expect(EMOTIONS, `"${emotion}" is not a registered portrait emotion`)
          .toContain(emotion)
      }
    })

    it('resolves every mapping to art at its own emotion path', () => {
      for (const emotion of everyMappedEmotion()) {
        expect(portraitUrl(JEAN_ID, emotion)).toContain(`/${emotion}.png`)
      }
    })

    it('routes every quality through its own lookup', () => {
      for (const quality of Object.keys(QUALITY_EMOTIONS)) {
        expect(qualityEmotion(quality)).toBe(QUALITY_EMOTIONS[quality])
      }
    })

    /** A module-level tuple or dict literal, read out of the Python source. */
    const engineVocabulary = (name, open, close) => {
      const source = readFileSync(
        join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', 'ai', 'llm_client.py'),
        'utf8'
      )
      // Module level (column 0), so the indented fallback copies in
      // src/npc/_chat_llm.py's ImportError branch can never be what matches —
      // and those are pinned to these by
      // tests/test_npc_chat_turn_pipeline.py.
      const match = source.match(
        new RegExp(`^${name}\\s*=\\s*\\${open}([^\\${close}]*)\\${close}`, 'm')
      )
      expect(match, `could not find ${name} in ai/llm_client.py`).toBeTruthy()
      return match[1]
    }

    it('has exactly the tones the engine emits, read from the engine', () => {
      // `tone` selects Jean's portrait directly now, so the vocabulary the
      // engine emits and the vocabulary the art registers have to be the SAME
      // list — a tone with no portrait renders a neutral face and says nothing
      // about it, and a portrait no tone names is art the chat can never show.
      const engineTones = engineVocabulary('JEAN_TONES', '(', ')')
        .split(',')
        .map((token) => token.trim().replace(/^['"]|['"]$/g, ''))
        .filter(Boolean)
      // Guard-the-guard: a regex that quietly matched nothing useful would
      // make the comparison below vacuous in the permissive direction.
      expect(engineTones.length).toBeGreaterThan(1)

      expect([...engineTones].sort()).toEqual([...EMOTIONS].sort())
    })

    it('labels exactly the kinds the engine emits, read from the engine', () => {
      // A kind the engine can emit with no entry in KIND_LABELS renders a
      // button with a blank label slot; one here that the engine never emits
      // is a dead row. Same pinning as the tones above, against JEAN_KINDS.
      const engineKinds = [
        ...engineVocabulary('JEAN_KINDS', '{', '}').matchAll(/^\s*"([^"]+)":/gm),
      ].map((m) => m[1])
      expect(engineKinds.length).toBeGreaterThan(1)

      expect([...engineKinds].sort()).toEqual(Object.keys(KIND_LABELS).sort())
    })
  })

  describe('kindLabel', () => {
    it('renders the player-facing words, never the schema name', () => {
      expect(kindLabel('ask-lore', 'Mara')).toBe('Ask about the world')
      expect(kindLabel('reply', 'Mara')).toBe('Answer')
    })

    it("fills {npc} with the NPC's display name", () => {
      expect(kindLabel('ask-npc', 'Mara')).toBe('Ask about Mara')
      expect(kindLabel('ask-guidance', 'Mara')).toBe("Ask Mara's advice")
    })

    it('falls back to a pronoun when the name is missing', () => {
      expect(kindLabel('ask-npc', '')).toBe('Ask about them')
    })

    it('is case-insensitive', () => {
      expect(kindLabel('ASK-LORE', 'Mara')).toBe('Ask about the world')
    })

    it.each([undefined, null, '', 'haggle', 'constructor', 'toString', 42])(
      'renders nothing for %s rather than leaking it to the button',
      (kind) => {
        expect(kindLabel(kind, 'Mara')).toBe('')
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

    // Issue #532: a total-fallback opening (llm_available: false) carries its
    // authored line in npc_flavor with npc_opening left empty — the engine's
    // own narration, not spoken dialogue. Rendering it under the NPC's
    // speaker label was the bug; ConversationStage centres a speaker-less
    // segment as italic narration, so the fix is to leave `speaker` unset
    // rather than defaulting it to npcId.
    it('renders a narration-only fallback opening with no speaker label', async () => {
      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({
          npc_opening: '',
          npc_flavor: "She glances up briefly, reading Jean's gear before his face.",
          llm_available: false,
        }),
      })
      const { result } = await mountOpened()

      expect(result.current.conversationSegments).toEqual([
        {
          text: '',
          speaker: null,
          emotion: 'neutral',
          flavor: "She glances up briefly, reading Jean's gear before his face.",
          reactions: {},
          in_conversation: true,
        },
      ])
    })
  })

  // -------------------------------------------------------------------------
  // Issue #661: the open effect's `cancelled` flag only gates which closure
  // APPLIES a response -- it never stopped a second closure from firing a
  // second real `POST /npc/chat/open`. React 18 StrictMode intentionally
  // double-invokes an effect (mount -> cleanup -> mount) on dev, so mounting
  // this hook fired two real requests for the same npcId every time. The
  // server's one-turn-per-player lock (`_chat_turn_lock`, game_service.py) is
  // non-blocking, so the second request could land on the first one still
  // being processed and come back 409 -- which the NOT-cancelled (second)
  // closure then rendered as STILL_TALKING_MESSAGE, even though Jean never
  // actually had a prior conversation open.
  // -------------------------------------------------------------------------
  describe('React 18 StrictMode double-invoke (#661)', () => {
    /** Mount wrapped in StrictMode, which double-invokes mount effects in dev. */
    const mountStrict = (npcId = 'Mynx', npcName = 'Mynx') =>
      renderHook(({ id, name }) => useNpcChat(id, name, onClose), {
        initialProps: { id: npcId, name: npcName },
        wrapper: StrictMode,
      })

    it('fires exactly one /open request for the npcId, not one per StrictMode invocation', async () => {
      const { result } = mountStrict()

      await waitFor(() => expect(result.current.phase).toBe('waiting_jean'))

      expect(npcChat.open).toHaveBeenCalledTimes(1)
    })

    it('never shows "still finishing another conversation" from its own duplicate open call', async () => {
      // The first (real) call is held open, standing in for the per-player
      // lock still being processed server-side. If a second real request
      // fires, it is refused exactly the way the server refuses a genuine
      // collision: 409, "in flight".
      let calls = 0
      npcChat.open.mockImplementation(() => {
        calls += 1
        if (calls === 1) return new Promise(() => {})
        return Promise.reject({
          response: { status: 409, data: { success: false, error: 'server copy' } },
        })
      })

      const { result } = mountStrict()

      // Let both StrictMode-invoked effects (and any microtasks their promises
      // settle) run.
      await act(async () => {})

      expect(npcChat.open).toHaveBeenCalledTimes(1)
      expect(result.current.phase).not.toBe('failed')
      expect(result.current.error).not.toBe(
        'Jean is still finishing another conversation — give it a moment.'
      )
    })

    it('still lands the served turn normally once the shared request resolves', async () => {
      let calls = 0
      npcChat.open.mockImplementation(() => {
        calls += 1
        // Whichever closure asks first gets the real network promise; a
        // second real call here would mean the dedupe failed.
        if (calls === 1) return Promise.resolve({ data: openData })
        return Promise.reject(new Error('a second /open call went out for the same npcId'))
      })

      const { result } = mountStrict()

      // Both StrictMode-invoked closures await the same settled promise
      // (post-fix) or their own separate ones (pre-fix); either way, one
      // microtask flush is enough for both to land.
      await act(async () => {})

      expect(npcChat.open).toHaveBeenCalledTimes(1)
      expect(result.current.phase).toBe('waiting_jean')
      expect(result.current.displayName).toBe('Mynx the Swift')
      expect(result.current.error).toBeNull()
    })
  })

  // -------------------------------------------------------------------------
  // Issue #533: the backend always carried `llm_available` in the /open and
  // /respond payloads (_base_payload, src/npc/_chat_llm.py) so a degraded
  // turn could be told apart from a live one -- but nothing on this side
  // ever read the field. It reached this hook and was silently dropped.
  // -------------------------------------------------------------------------
  describe('llm_available', () => {
    it('exposes llm_available: false from the opening response', async () => {
      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({ llm_available: false }),
      })
      const { result } = await mountOpened()

      expect(result.current.llmAvailable).toBe(false)
    })

    it('exposes llm_available: true from the opening response', async () => {
      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({ llm_available: true }),
      })
      const { result } = await mountOpened()

      expect(result.current.llmAvailable).toBe(true)
    })

    it('updates llm_available from a respond response', async () => {
      const { result } = await mountOpened()
      expect(result.current.llmAvailable).toBe(true)

      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({ npc_response: '', npc_flavor: 'Silence.', llm_available: false }),
      })
      await act(async () => {
        await result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
      })

      expect(result.current.llmAvailable).toBe(false)
    })

    it('treats a missing llm_available as available, like every other malformed-payload default', async () => {
      npcChat.open.mockResolvedValue({ data: { npc_key: 'k', npc_opening: 'Hm.' } })
      const { result } = await mountOpened()

      expect(result.current.llmAvailable).toBe(true)
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
                jean_options: [makeJeanOption({ text: 'Peace, Gorran.', tone: 'curious' })],
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
        makeJeanOption({ text: 'Peace, Gorran.', tone: 'curious' }),
      ])
      expect(result.current.conversationCast).toEqual(npcCast('Gorran', 'Gorran'))
      // Dropped, NOT ended. `npc_chat_end` pops `_active_chat_npc_id`
      // unconditionally, and Gorran's `/open` has already claimed it — so
      // ending Mynx's superseded conversation would clear GORRAN's marker.
      // This is the one case that must not be treated like an unmount.
      expect(npcChat.end).not.toHaveBeenCalled()
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

    it('logs a string, never the error object, when nothing else is available', async () => {
      // utils/logger mirrors console arguments to /api/logs/browser and
      // JSON-stringifies any object it is handed — and `AxiosError.toJSON()`
      // carries `config.headers.Authorization`, the Bearer session id, with it.
      npcChat.open.mockRejectedValue({ config: { headers: { Authorization: 'Bearer sekrit' } } })
      const { result } = mount()

      await waitFor(() => expect(result.current.phase).toBe('failed'))
      const [, detail] = consoleError.mock.calls.find(([label]) => label === '[npcChat] open failed:')
      expect(typeof detail).toBe('string')
      expect(detail).not.toContain('sekrit')
    })

    it('logs the prose in `message` ahead of the machine token in `error`', async () => {
      // A 429 from `rate_limited_response()` puts the token "rate_limited" in
      // `error` and the prose in `message`. Reading `error` first would log the
      // token and drop the only useful half — and nothing pinned that order.
      npcChat.open.mockRejectedValue({
        response: {
          status: 429,
          data: { error: 'rate_limited', message: 'Slow down — too many messages.' },
        },
      })
      const { result } = mount()

      await waitFor(() => expect(result.current.phase).toBe('failed'))
      expect(consoleError).toHaveBeenCalledWith(
        '[npcChat] open failed:',
        'Slow down — too many messages.'
      )
    })

    it('tells a throttled player to wait instead of blaming the NPC', async () => {
      npcChat.open.mockRejectedValue({
        response: { status: 429, data: { error: 'rate_limited', message: 'Slow down.' } },
      })
      const { result } = mount()

      await waitFor(() => expect(result.current.phase).toBe('failed'))
      // Our copy, not the server's — the fixed-string policy holds for a 429
      // exactly as it does for every other failure.
      expect(result.current.error).toBe('Too many messages — give it a moment.')
      expect(result.current.error).not.toBe('Failed to open conversation')
      expect(result.current.error).not.toContain('Slow down')
    })

    it('names the deadline when the request timed out, instead of blaming the open (#618)', async () => {
      // ECONNABORTED is the code axios raises when its own `timeout` fires —
      // the client deadline npcChat.js puts on every chat call. "Failed to open
      // conversation" reads as "the server said no"; a player who waited out
      // the whole spinner needs to be told the wait itself is what ended, or Retry
      // looks like the same dead end rather than a fresh try.
      npcChat.open.mockRejectedValue(axiosTimeoutError())
      const { result } = mount()

      await waitFor(() => expect(result.current.phase).toBe('failed'))
      expect(result.current.error).toBe('The conversation timed out — try again.')
      expect(result.current.error).not.toBe('Failed to open conversation')
      // Still OUR fixed copy: the axios message carries the raw millisecond
      // budget, which is diagnostics, not a sentence for a player.
      expect(NPC_CHAT_TIMEOUT_MS).toBeGreaterThan(0) // the real constant, not mocked away
      expect(result.current.error).not.toContain(String(NPC_CHAT_TIMEOUT_MS))
      expect(result.current.loading).toBe(false)
      expect(typeof result.current.retry).toBe('function')
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
          jean_options: [makeJeanOption({ text: 'Go on', tone: 'neutral' })],
          loquacity_current: 1,
          conversation_quality: 'positive',
        }),
      })
      const { result } = await mountOpened()

      await act(async () => {
        await result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
      })

      expect(npcChat.respond).toHaveBeenCalledWith('npc_session_123', 'Hi there', 'curious')
      const segments = result.current.conversationSegments
      expect(segments).toHaveLength(3)
      // Jean wears the tone he answered with; the NPC wears the turn quality.
      expect(segments[1]).toMatchObject({ speaker: 'Jean', emotion: 'curious', text: 'Hi there' })
      expect(segments[1].reactions).toEqual({ Mynx: 'curious' })
      expect(segments[2]).toMatchObject({ speaker: 'Mynx', emotion: 'happy', text: 'Coin first.' })
      expect(segments[2].reactions).toEqual({ Jean: 'curious' })
      expect(result.current.loquacity).toEqual({ current: 1, max: 5 })
      expect(result.current.phase).toBe('waiting_jean')
    })

    // Issue #532: same routing rule as the opening turn, for a mid-conversation
    // fallback.
    it('renders a narration-only fallback reply with no speaker label', async () => {
      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({
          npc_response: '',
          npc_flavor: 'She says nothing, just watches the road.',
          llm_available: false,
        }),
      })
      const { result } = await mountOpened()

      await act(async () => {
        await result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
      })

      const segments = result.current.conversationSegments
      expect(segments[segments.length - 1]).toMatchObject({
        text: '',
        speaker: null,
        flavor: 'She says nothing, just watches the road.',
      })
    })

    it('ignores a click while the NPC is still composing', async () => {
      const pending = deferred()
      npcChat.respond.mockReturnValue(pending.promise)
      const { result } = await mountOpened()

      act(() => {
        result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
      })
      await waitFor(() => expect(result.current.phase).toBe('waiting_npc'))

      await act(async () => {
        await result.current.handleOptionClick({ text: 'Leave me alone', tone: 'skeptical' })
      })
      expect(npcChat.respond).toHaveBeenCalledTimes(1)

      await act(async () => {
        pending.resolve({ data: makeNpcChatRespond({ npc_response: 'Done.', jean_options: [] }) })
      })
    })

    it('drops a /respond that resolves after the hook is pointed at another NPC', async () => {
      // The `[npcId]` open effect has a supersession guard; `handleOptionClick`
      // had none, so a reply still in flight for NPC A landed in NPC B's
      // segments, options, loquacity and relationship. Latent today only
      // because InteractPanel keys the panel — but switching NPC is advertised
      // in this hook's own contract.
      const pending = deferred()
      npcChat.respond.mockReturnValue(pending.promise)
      const { result, rerender } = await mountOpened('Mynx')

      act(() => {
        result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
      })
      await waitFor(() => expect(result.current.phase).toBe('waiting_npc'))

      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({
          npc_key: 'npc_session_999',
          npc_name: 'Gorran',
          npc_opening: 'You again.',
          loquacity_current: 4,
          loquacity_max: 4,
          jean_options: [makeJeanOption({ text: 'Peace, Gorran.', tone: 'curious' })],
        }),
      })
      await act(async () => rerender({ id: 'Gorran', name: 'Gorran' }))
      await waitFor(() => expect(result.current.phase).toBe('waiting_jean'))

      await act(async () => {
        pending.resolve({
          data: makeNpcChatRespond({
            npc_response: 'Mynx answers, far too late.',
            jean_options: [makeJeanOption({ text: 'Stale option', tone: 'neutral' })],
            loquacity_current: 1,
            loquacity_max: 5,
          }),
        })
      })

      // Gorran's conversation is untouched: one opening line, his options, his
      // loquacity, and still his turn.
      expect(result.current.conversationSegments).toHaveLength(1)
      expect(result.current.conversationSegments[0].text).toBe('You again.')
      expect(result.current.currentOptions.map((o) => o.text)).toEqual(['Peace, Gorran.'])
      expect(result.current.loquacity).toEqual({ current: 4, max: 4 })
      expect(result.current.phase).toBe('waiting_jean')
    })

    it('drops a /respond REJECTION that lands after a switch, rather than erroring on the new NPC', async () => {
      const pending = deferred()
      npcChat.respond.mockReturnValue(pending.promise)
      const { result, rerender } = await mountOpened('Mynx')

      act(() => {
        result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
      })
      await waitFor(() => expect(result.current.phase).toBe('waiting_npc'))

      npcChat.open.mockResolvedValue({ data: makeNpcChatOpen({ npc_key: 'k2', npc_name: 'Gorran' }) })
      await act(async () => rerender({ id: 'Gorran', name: 'Gorran' }))
      await waitFor(() => expect(result.current.phase).toBe('waiting_jean'))

      await act(async () => { pending.reject(new Error('Mynx timed out')) })

      // No error copy, no Retry replaying Mynx's option against Gorran's key.
      expect(result.current.error).toBeNull()
      expect(result.current.retry).toBeNull()
      expect(consoleError).not.toHaveBeenCalled()
    })

    it('ignores a click before the session key exists', async () => {
      const pending = deferred()
      npcChat.open.mockReturnValue(pending.promise)
      const { result } = mount()

      await act(async () => {
        await result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
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
        result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
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
        await result.current.handleOptionClick({ text: 'Leave me alone', tone: 'skeptical' })
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
        'skeptical'
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
        await result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
      })
      expect(result.current.error).toBe('NPC did not respond')

      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({ npc_response: 'Fine.', jean_options: [] }),
      })
      await act(async () => {
        await result.current.handleOptionClick({ text: 'Leave me alone', tone: 'skeptical' })
      })

      // The panel gates the option list on `!error`, so a stale error hid every
      // remaining choice for the rest of the conversation.
      expect(result.current.error).toBeNull()
    })

    it('tells a throttled player to wait rather than that the NPC went quiet', async () => {
      // The turn was never delivered: `npc_chat.py` rejected it before the NPC
      // saw it. "NPC did not respond" beside a live Retry invited the player to
      // keep clicking straight back into the throttle.
      npcChat.respond.mockRejectedValue({
        response: { status: 429, data: { error: 'rate_limited', message: 'Slow down.' } },
      })
      const { result } = await mountOpened()

      await act(async () => {
        await result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
      })

      expect(result.current.error).toBe('Too many messages — give it a moment.')
      expect(result.current.phase).toBe('waiting_jean')
    })

    it('says the NPC is still composing when a turn is already in flight (#618)', async () => {
      // The server runs one chat turn per player at a time and answers 409 to
      // a second -- typically a Retry after a timeout, while the abandoned
      // turn is still finishing. Neither "did not respond" nor "timed out" is
      // what happened.
      npcChat.respond.mockRejectedValue({
        response: { status: 409, data: { success: false, error: 'server copy' } },
      })
      const { result } = await mountOpened()

      await act(async () => {
        await result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
      })

      expect(result.current.error).toBe('Still composing a reply — give it a moment.')
      expect(result.current.phase).toBe('waiting_jean')
    })

    it('says Jean is still in another conversation when /open is refused (#618)', async () => {
      // The one-turn-per-player gate is per PLAYER, not per NPC: close NPC A
      // mid-turn, open NPC B, and B's /open meets A's turn. "Still composing a
      // reply" on a panel that has asked nothing yet would be false.
      npcChat.open.mockRejectedValue({
        response: { status: 409, data: { success: false, error: 'server copy' } },
      })
      const { result } = mount()

      await waitFor(() => expect(result.current.phase).toBe('failed'))
      expect(result.current.error).toBe('Jean is still finishing another conversation — give it a moment.')
    })

    it('names the deadline when the turn timed out, and hands the options back (#618)', async () => {
      // Issue #618's actual failure: one `/respond` walked the provider chain
      // for over 90 seconds while the panel sat at WAITING_NPC with no options,
      // no error and an inert End Conversation button. The client deadline is
      // what turns that into a normal failed turn.
      npcChat.respond.mockRejectedValue(axiosTimeoutError())
      const { result } = await mountOpened()

      await act(async () => {
        await result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
      })

      expect(result.current.error).toBe('The conversation timed out — try again.')
      expect(result.current.error).not.toBe('NPC did not respond')
      // The conversation itself survives a timed-out turn, same as any other
      // failed respond: Jean gets her options back rather than a dead panel.
      expect(result.current.phase).toBe('waiting_jean')
      expect(result.current.loading).toBe(false)
      expect(result.current.currentOptions.length).toBeGreaterThan(0)
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
      await waitFor(() =>
        expect(consoleError).toHaveBeenCalledWith(
          '[npcChat] end after dismissal failed:',
          'expired key'
        )
      )
    })

    it('closes at once, even while /end is still waiting on the server (#618)', async () => {
      // Production runs one sync worker, so an /end sent while a turn is still
      // running waits behind that turn. The panel used to stay up, its button
      // latched, for the whole wait -- "walk out of a hang" only worked on the
      // threaded dev server.
      const pending = deferred()
      npcChat.end.mockReturnValue(pending.promise)
      const { result } = await mountOpened()

      act(() => { result.current.handleEndConversation() })

      expect(npcChat.end).toHaveBeenCalledWith('npc_session_123')
      expect(onClose).toHaveBeenCalledTimes(1)
      await act(async () => { pending.resolve({ data: { success: true } }) })
      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('spends one /end and one close no matter how often it is invoked', async () => {
      // The panel now stays on screen for the whole `/end` round trip, because
      // the ✕, the overlay click and Escape all route through here rather than
      // dismissing instantly. That opens a window a second click lands in.
      const pending = deferred()
      npcChat.end.mockReturnValue(pending.promise)
      const { result } = await mountOpened()

      act(() => {
        result.current.handleEndConversation()
        result.current.handleEndConversation()
      })
      await act(async () => { pending.resolve({ data: { success: true } }) })

      expect(npcChat.end).toHaveBeenCalledTimes(1)
      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('can end again after the hook is pointed at a different NPC', async () => {
      // The one-dismissal latch is per CONVERSATION, not per hook. Left set
      // across a re-target it made `handleEndConversation` — the only
      // sanctioned way out of the panel — a permanent no-op for the new NPC:
      // no `/end`, no `onClose`, and `_active_chat_npc_id` left pointing at
      // Gorran server-side. Latent today only because InteractPanel keys the
      // panel per NPC, which is exactly the assumption the supersession guard
      // in the same file refuses to make.
      const { result, rerender } = await mountOpened('Mynx')

      await act(async () => {
        await result.current.handleEndConversation()
      })
      expect(npcChat.end).toHaveBeenCalledTimes(1)

      npcChat.open.mockResolvedValue({
        data: makeNpcChatOpen({ npc_key: 'gorran_session_1', npc_name: 'Gorran' }),
      })
      await act(async () => rerender({ id: 'Gorran', name: 'Gorran' }))
      await waitFor(() => expect(result.current.phase).toBe('waiting_jean'))

      await act(async () => {
        await result.current.handleEndConversation()
      })

      expect(npcChat.end).toHaveBeenCalledTimes(2)
      expect(npcChat.end).toHaveBeenLastCalledWith('gorran_session_1')
      expect(onClose).toHaveBeenCalledTimes(2)
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

    // Issue #531: the closing line is fetched, paid for, then auto-closed
    // before it can be read — the 2s countdown used to start the instant
    // `conversation_ended` landed, not once the closing line had actually
    // finished typing out on screen. The hook no longer arms the timer on
    // its own; NpcChatPanel calls `handleFinalBeatRendered` once its own
    // typewriter tracking says the final segment is fully rendered.
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
        await rendered.result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
      })
      expect(rendered.result.current.phase).toBe('ended')
      return rendered
    }

    it('sends no /end when dismissed after the server has ended the conversation', async () => {
      // The server pops its conversation marker itself when a turn ends one
      // (settleTurnPhase clears the open key for exactly this). An /end sent
      // from the auto-close window would pop it again -- by then possibly the
      // NEXT conversation's.
      const { result } = await openEndedTurn()

      act(() => { result.current.handleEndConversation() })

      expect(onClose).toHaveBeenCalledTimes(1)
      expect(npcChat.end).not.toHaveBeenCalled()
    })

    it('does NOT arm the close timer just because the conversation ended', async () => {
      const { result } = await openEndedTurn()
      expect(result.current.phase).toBe('ended')

      // The old bug: this alone used to start (and finish) a 2s countdown.
      // A long closing line can still be typing out well past that window,
      // and nothing has told the hook the player has actually seen it yet.
      await act(async () => { vi.advanceTimersByTime(60000) })
      expect(onClose).not.toHaveBeenCalled()
    })

    it('closes exactly 2s after the panel reports the final beat rendered', async () => {
      const { result } = await openEndedTurn()

      act(() => result.current.handleFinalBeatRendered())

      await act(async () => { vi.advanceTimersByTime(1999) })
      expect(onClose).not.toHaveBeenCalled()

      await act(async () => { vi.advanceTimersByTime(1) })
      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('ignores a stale render-complete signal from before the conversation ended', async () => {
      const rendered = mount()
      await act(async () => {})
      expect(rendered.result.current.phase).toBe('waiting_jean')

      // A late call (e.g. the previous turn's typewriter finally settling)
      // must not arm a close for a conversation that has not ended.
      act(() => rendered.result.current.handleFinalBeatRendered())
      await act(async () => { vi.advanceTimersByTime(60000) })

      expect(onClose).not.toHaveBeenCalled()
    })

    it('cancelAutoClose suspends that close indefinitely', async () => {
      const { result } = await openEndedTurn()
      act(() => result.current.handleFinalBeatRendered())

      act(() => result.current.cancelAutoClose())
      await act(async () => { vi.advanceTimersByTime(60000) })

      expect(onClose).not.toHaveBeenCalled()
    })

    it('does not close after unmount', async () => {
      const { result, unmount } = await openEndedTurn()
      act(() => result.current.handleFinalBeatRendered())

      unmount()
      await act(async () => { vi.advanceTimersByTime(5000) })

      expect(onClose).not.toHaveBeenCalled()
    })
  })

  // -------------------------------------------------------------------------
  // `conversation_ended`, on every endpoint that can send it
  //
  // The flag is not a `/respond` field. The engine builds both response bodies
  // through one `_base_payload` (src/npc/_chat_llm.py), and `chat_open`'s
  // loquacity cutoff is a real `/open` sender of it: the NPC brushes Jean off,
  // returns no options, and `npc_chat_open` pops `_active_chat_npc_id` on the
  // spot. The hook honoured it on `/respond` only, so that cutoff parked the
  // player on a dead line with an empty option list, no "Conversation ended."
  // and no auto-close.
  //
  // Every fixture in this file carrying the flag was a `/respond` mock, which
  // is why the suite agreed. The population is derived from the engine below
  // rather than listed here, so a THIRD sender added in Python fails this
  // suite as unhandled instead of quietly repeating the same half-coverage.
  // -------------------------------------------------------------------------
  describe('conversation_ended', () => {
    beforeEach(() => vi.useFakeTimers())
    afterEach(() => vi.useRealTimers())

    /**
     * Every endpoint whose response body can carry `conversation_ended`, read
     * out of the engine.
     *
     * `_base_payload` is the one builder that emits the field; the wrappers
     * that call it each name the endpoint they assemble in their first
     * docstring line. So the population is: every `_*_payload` helper that
     * delegates to `_base_payload`, keyed by the path it says it builds.
     */
    const enginePathsCarryingTheFlag = () => {
      const source = readFileSync(
        join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..',
          'src', 'npc', '_chat_llm.py'),
        'utf8'
      )
      // The field really is minted in the shared builder, not per wrapper --
      // if that stops being true this derivation is measuring the wrong thing.
      const base = source.match(/def _base_payload\([\s\S]*?\n\s+return \{([\s\S]*?)\n\s+\}/)
      expect(base, 'could not find _base_payload in src/npc/_chat_llm.py').toBeTruthy()
      expect(base[1]).toContain('"conversation_ended"')

      const paths = []
      for (const chunk of source.split('\n    def ').slice(1)) {
        const name = chunk.slice(0, chunk.indexOf('('))
        if (!/^_\w+_payload$/.test(name) || name === '_base_payload') continue
        if (!chunk.includes('self._base_payload(')) continue
        const endpoint = chunk.match(/Assemble the (\/\w+) response body/)
        expect(
          endpoint,
          `${name} in src/npc/_chat_llm.py builds on _base_payload but its docstring `
          + 'does not name the endpoint it assembles, so this suite cannot tell '
          + 'which client call sends it'
        ).toBeTruthy()
        paths.push(endpoint[1])
      }
      return paths
    }

    /**
     * How this hook is driven into each of those endpoints, with the server
     * reporting the conversation over. Keys are matched against the engine's.
     */
    const drivers = {
      '/open': async () => {
        npcChat.open.mockResolvedValue({
          data: makeNpcChatOpen({
            npc_opening: 'Not now. Ask me again later.',
            jean_options: [],
            conversation_ended: true,
          }),
        })
        const rendered = mount()
        await act(async () => {})
        return rendered
      },
      '/respond': async () => {
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
          await rendered.result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
        })
        return rendered
      },
    }

    it('is driven from every engine endpoint that can send it', () => {
      const paths = enginePathsCarryingTheFlag()
      // Guard-the-guard: an empty derivation would make the per-endpoint case
      // below iterate over nothing and pass for any hook at all.
      expect(paths.length).toBeGreaterThan(1)
      // Both directions: a new engine sender is unhandled here, and a driver
      // for an endpoint the engine no longer has is stale.
      expect([...paths].sort()).toEqual(Object.keys(drivers).sort())
    })

    for (const path of ['/open', '/respond']) {
      it(`ends the conversation when ${path} reports it over`, async () => {
        const { result } = await drivers[path]()

        // The phase IS the affordance: NpcChatPanel keys "Conversation ended."
        // and the suppression of the option list on it.
        expect(
          result.current.phase,
          `useNpcChat.js left the panel in "${result.current.phase}" after ${path} `
          + 'reported conversation_ended -- no end affordance, no auto-close'
        ).toBe('ended')
        expect(result.current.currentOptions).toEqual([])

        // ...and the auto-close arms once the panel reports the final beat
        // rendered (issue #531 — it is no longer armed by ended-phase alone).
        act(() => result.current.handleFinalBeatRendered())
        await act(async () => { vi.advanceTimersByTime(2000) })
        expect(onClose).toHaveBeenCalledTimes(1)

        // The server already popped `_active_chat_npc_id` for this case, so
        // the way out must not spend a request re-ending it.
        expect(npcChat.end).not.toHaveBeenCalled()
      })
    }
  })

  describe('unmount safety', () => {
    it('ends the conversation an /open opened for a panel that is already gone', async () => {
      // The last door left open to a leaked `_active_chat_npc_id`. The panel is
      // dismissed mid-`/open`; the server opens the conversation anyway and
      // sends back an `npc_key` that used to be dropped on the floor, so `/end`
      // was never sent and `_recover_npc_loquacity` (game_service.py) went on
      // reading "a conversation is in progress" until the next move self-healed
      // the marker.
      const pending = deferred()
      npcChat.open.mockReturnValue(pending.promise)
      const { unmount } = mount()

      unmount()
      await act(async () => { pending.resolve({ data: openData }) })

      expect(npcChat.end).toHaveBeenCalledWith('npc_session_123')
      // No setState on an unmounted hook, and nothing schedules a close.
      expect(onClose).not.toHaveBeenCalled()
    })

    it('ends a live conversation when the panel is taken off screen without a dismissal', async () => {
      // InteractPanel drops `selectedTarget` when the room resyncs, and the
      // chat panel is keyed per NPC — both unmount it without ever routing
      // through `handleEndConversation`.
      const { unmount } = await mountOpened()

      unmount()

      expect(npcChat.end).toHaveBeenCalledWith('npc_session_123')
    })

    it('does not re-end a conversation the server already closed', async () => {
      // `npc_chat_respond` pops the marker itself when it reports
      // `conversation_ended`, so the auto-close on the way out has nothing left
      // to end and must not spend a request saying so.
      npcChat.respond.mockResolvedValue({
        data: makeNpcChatRespond({
          npc_response: 'Farewell.',
          jean_options: [],
          conversation_ended: true,
        }),
      })
      const { result, unmount } = await mountOpened()
      await act(async () => {
        await result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
      })
      expect(result.current.phase).toBe('ended')

      unmount()

      expect(npcChat.end).not.toHaveBeenCalled()
    })

    it('sends exactly one /end when the player walks out mid-turn (#618)', async () => {
      // The window issue #618's fix OPENS: End Conversation is no longer gated
      // on `loading`, so a dismissal can now land while `/respond` is still in
      // flight. `openNpcKeyRef` is cleared before `/end` goes out, so the
      // unmount cleanup must not fire a second one — and the reply that lands
      // afterwards must not write into a hook that is gone.
      const pending = deferred()
      npcChat.respond.mockReturnValue(pending.promise)
      const { result, unmount } = await mountOpened()

      act(() => {
        result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
      })
      await waitFor(() => expect(result.current.phase).toBe('waiting_npc'))

      await act(async () => {
        await result.current.handleEndConversation()
      })
      unmount()

      await act(async () => {
        pending.resolve({ data: makeNpcChatRespond({ npc_response: 'Too late.' }) })
      })

      expect(npcChat.end).toHaveBeenCalledTimes(1)
      expect(npcChat.end).toHaveBeenCalledWith('npc_session_123')
      // No "Cannot update an unmounted component" from the late reply either.
      expect(consoleError).not.toHaveBeenCalledWith(
        expect.stringContaining('unmounted'),
        expect.anything()
      )
    })

    it('sends exactly one /end when a dismissal is what unmounted the panel', async () => {
      const { result, unmount } = await mountOpened()

      await act(async () => {
        await result.current.handleEndConversation()
      })
      unmount()

      expect(npcChat.end).toHaveBeenCalledTimes(1)
    })

    it('logs a failed post-dismissal /end rather than swallowing it', async () => {
      npcChat.end.mockRejectedValue(new Error('expired key'))
      const { unmount } = await mountOpened()

      unmount()
      // The rejection settles a microtask later, with nothing on screen to
      // await against.
      await act(async () => {})

      expect(consoleError).toHaveBeenCalledWith(
        '[npcChat] end after dismissal failed:',
        'expired key'
      )
    })

    it('drops an /open rejection that lands after unmount', async () => {
      const pending = deferred()
      npcChat.open.mockReturnValue(pending.promise)
      const { unmount } = mount()

      unmount()
      await act(async () => { pending.reject(new Error('late failure')) })

      expect(consoleError).not.toHaveBeenCalled()
      expect(onClose).not.toHaveBeenCalled()
    })

    it('closes once, at the click -- a slow /end settling after unmount adds nothing', async () => {
      // The close no longer waits for /end (#618: it queued behind a running
      // turn on the single production worker), so the old hazard -- a
      // `finally` asking the owner to close a panel already gone -- cannot
      // arise; what is left to pin is that settling adds no second close.
      const pending = deferred()
      npcChat.end.mockReturnValue(pending.promise)
      const { result, unmount } = await mountOpened()

      act(() => { result.current.handleEndConversation() })
      expect(onClose).toHaveBeenCalledTimes(1)
      unmount()

      await act(async () => { pending.resolve({ data: { success: true } }) })

      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('drops a /respond response that lands after unmount', async () => {
      const pending = deferred()
      npcChat.respond.mockReturnValue(pending.promise)
      const { result, unmount } = await mountOpened()

      act(() => {
        result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
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
        result.current.handleOptionClick({ text: 'Hi there', tone: 'curious' })
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
