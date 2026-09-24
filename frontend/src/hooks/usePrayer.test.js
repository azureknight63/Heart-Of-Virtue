import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import usePrayer, { PRAYER_FAILED } from './usePrayer'
import { player as playerApi } from '../api/endpoints'

vi.mock('../api/endpoints', () => ({
  player: { pray: vi.fn() },
}))

beforeEach(() => {
  vi.clearAllMocks()
})

/** Mount the hook, pray once, and hand back the outcome and the hook. */
async function prayOnce() {
  const hook = renderHook(() => usePrayer())
  let outcome
  await act(async () => { outcome = await hook.result.current.pray() })
  return { outcome, result: hook.result }
}

describe('usePrayer (issue #646)', () => {
  it('posts the prayer and hands back the narration', async () => {
    playerApi.pray.mockResolvedValue({
      data: { success: true, message: 'Jean kneels.', cleared: ['Hollowed'] },
    })
    const { outcome, result } = await prayOnce()

    expect(playerApi.pray).toHaveBeenCalledTimes(1)
    expect(outcome).toEqual({ ok: true, message: 'Jean kneels.' })
    expect(result.current.isPraying).toBe(false)
  })

  it('surfaces the server refusal (mid-fight, too spent) as prose', async () => {
    playerApi.pray.mockRejectedValue({
      response: { status: 400, data: { success: false, error: 'Prayer needs 37 fatigue; he has 5.' } },
    })
    const { outcome, result } = await prayOnce()

    expect(outcome).toEqual({ ok: false, message: 'Prayer needs 37 fatigue; he has 5.' })
    expect(result.current.isPraying).toBe(false)
  })

  it('falls back to a generic line on a transport failure', async () => {
    playerApi.pray.mockRejectedValue(new Error('Network Error'))
    const { outcome } = await prayOnce()

    expect(outcome).toEqual({ ok: false, message: PRAYER_FAILED })
  })

  it('treats a 2xx without success as a failure', async () => {
    playerApi.pray.mockResolvedValue({ data: { success: false } })
    const { outcome } = await prayOnce()

    expect(outcome).toEqual({ ok: false, message: PRAYER_FAILED })
  })

  it('treats an empty response as a failure', async () => {
    playerApi.pray.mockResolvedValue(undefined)
    const { outcome } = await prayOnce()

    expect(outcome).toEqual({ ok: false, message: PRAYER_FAILED })
  })

  it('is busy while the request is in flight', async () => {
    let resolve
    playerApi.pray.mockReturnValue(new Promise((r) => { resolve = r }))
    const { result } = renderHook(() => usePrayer())

    let pending
    act(() => { pending = result.current.pray() })
    expect(result.current.isPraying).toBe(true)

    await act(async () => {
      resolve({ data: { success: true, message: 'Amen.' } })
      await pending
    })
    expect(result.current.isPraying).toBe(false)
  })

  it('sends one prayer for a double click that lands before the re-render', async () => {
    // Both clicks reach `pray` before `isPraying` has disabled the button, so
    // only a ref can see the first; state has not re-rendered yet.
    let resolve
    playerApi.pray.mockReturnValue(new Promise((r) => { resolve = r }))
    const { result } = renderHook(() => usePrayer())

    const { pray } = result.current
    let first
    let second
    act(() => {
      first = pray()
      second = pray()
    })
    await act(async () => {
      resolve({ data: { success: true, message: 'Amen.' } })
    })

    expect(playerApi.pray).toHaveBeenCalledTimes(1)
    expect(await second).toEqual(await first)

    // The latch belongs to one prayer: the next click sends again.
    playerApi.pray.mockResolvedValue({ data: { success: true, message: 'Again.' } })
    let third
    await act(async () => { third = await result.current.pray() })
    expect(playerApi.pray).toHaveBeenCalledTimes(2)
    expect(third).toEqual({ ok: true, message: 'Again.' })
  })
})
