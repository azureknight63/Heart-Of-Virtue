/**
 * The NPC chat auto-close, driven with the REAL typewriter (#618 scrub).
 *
 * NpcChatPanel.test.jsx mocks `useTypewriter` statelessly, so it could never
 * see the one render where the hook still reported the PREVIOUS text complete
 * -- which is exactly when the panel armed its 2s close, before a character of
 * the closing line had typed. `vi.mock` is file-scoped, hence this file: only
 * the API is mocked here.
 */
import React from 'react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, act } from '@testing-library/react'
import NpcChatPanel from './NpcChatPanel'
import { makeNpcChatOpen, makeNpcChatRespond } from '../test/payloads'

vi.mock('../api/npcChat', () => ({
  default: { open: vi.fn(), respond: vi.fn(), end: vi.fn() },
}))

import npcChat from '../api/npcChat'

/** The panel types at this speed (NpcChatPanel's CONVERSATION_STAGE_SPEED). */
const SPEED_MS = 20
/** useNpcChat's AUTO_CLOSE_DELAY_MS. */
const CLOSE_DELAY_MS = 2000
const CLOSING_LINE =
  'The merchant turns back to his ledger and does not look up again, ' +
  'not even when the tent flap stirs behind you on your way out.'

/** Advance in small steps, flushing effects between them, the way real time
 * interleaves the typewriter's ticks with the effects that react to them. */
async function elapse(ms, step = 100) {
  for (let spent = 0; spent < ms; spent += step) {
    await act(async () => {
      vi.advanceTimersByTime(step)
    })
  }
}

/** The one moment the old code closed: the close delay after the line lands. */
async function expectStillOpenAfterTheCloseDelay(onClose) {
  await elapse(CLOSE_DELAY_MS + 200)
  expect(onClose).not.toHaveBeenCalled()
}

async function expectClosedOnceReadAndWaited(onClose) {
  await elapse(CLOSING_LINE.length * SPEED_MS + CLOSE_DELAY_MS + 500)
  expect(onClose).toHaveBeenCalledTimes(1)
}

describe('NpcChatPanel auto-close with the real typewriter (#618)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    npcChat.end.mockResolvedValue({ data: { success: true } })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('lets an /open brush-off line finish typing before it closes', async () => {
    npcChat.open.mockResolvedValue({
      data: makeNpcChatOpen({
        conversation_ended: true,
        npc_opening: '',
        npc_flavor: CLOSING_LINE,
        jean_options: [],
      }),
    })
    const onClose = vi.fn()
    render(<NpcChatPanel npcId="Mynx" npcName="Mynx" onClose={onClose} />)

    await expectStillOpenAfterTheCloseDelay(onClose)
    await expectClosedOnceReadAndWaited(onClose)
  })

  it('lets a spoken closing reply finish typing before it closes', async () => {
    npcChat.open.mockResolvedValue({ data: makeNpcChatOpen({ npc_opening: 'Well?' }) })
    const onClose = vi.fn()
    const view = render(<NpcChatPanel npcId="Mynx" npcName="Mynx" onClose={onClose} />)
    await elapse(1000) // the opening types out and the options appear

    let resolveRespond
    npcChat.respond.mockReturnValue(
      new Promise((resolve) => {
        resolveRespond = resolve
      })
    )
    await act(async () => {
      view.getByText('What is this place?').click()
    })
    await elapse(5000) // Jean's line types out while the reply is pending

    await act(async () => {
      resolveRespond({
        data: makeNpcChatRespond({ conversation_ended: true, npc_response: CLOSING_LINE }),
      })
    })

    await expectStillOpenAfterTheCloseDelay(onClose)
    await expectClosedOnceReadAndWaited(onClose)
  })
})
