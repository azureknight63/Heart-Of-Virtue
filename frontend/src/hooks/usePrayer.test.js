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

describe('usePrayer (issue #646)', () => {
  it('posts the prayer and hands back the narration', async () => {
    playerApi.pray.mockResolvedValue({
      data: { success: true, message: 'Jean kneels.', cleared: ['Hollowed'] },
    })
    const { result } = renderHook(() => usePrayer())

    let outcome
    await act(async () => { outcome = await result.current.pray() })

    expect(playerApi.pray).toHaveBeenCalledTimes(1)
    expect(outcome).toEqual({ ok: true, message: 'Jean kneels.' })
    expect(result.current.isPraying).toBe(false)
  })

  it('surfaces the server refusal (mid-fight, too spent) as prose', async () => {
    playerApi.pray.mockRejectedValue({
      response: { status: 400, data: { success: false, error: 'Prayer needs 37 fatigue; he has 5.' } },
    })
    const { result } = renderHook(() => usePrayer())

    let outcome
    await act(async () => { outcome = await result.current.pray() })

    expect(outcome).toEqual({ ok: false, message: 'Prayer needs 37 fatigue; he has 5.' })
    expect(result.current.isPraying).toBe(false)
  })

  it('falls back to a generic line on a transport failure', async () => {
    playerApi.pray.mockRejectedValue(new Error('Network Error'))
    const { result } = renderHook(() => usePrayer())

    let outcome
    await act(async () => { outcome = await result.current.pray() })

    expect(outcome).toEqual({ ok: false, message: PRAYER_FAILED })
  })

  it('treats a 2xx without success as a failure', async () => {
    playerApi.pray.mockResolvedValue({ data: { success: false } })
    const { result } = renderHook(() => usePrayer())

    let outcome
    await act(async () => { outcome = await result.current.pray() })

    expect(outcome).toEqual({ ok: false, message: PRAYER_FAILED })
  })

  it('treats an empty response as a failure', async () => {
    playerApi.pray.mockResolvedValue(undefined)
    const { result } = renderHook(() => usePrayer())

    let outcome
    await act(async () => { outcome = await result.current.pray() })

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
})
