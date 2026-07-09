import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import useAsyncAction from './useAsyncAction'

describe('useAsyncAction', () => {
  it('starts in an idle, non-loading state', () => {
    const { result } = renderHook(() => useAsyncAction(vi.fn()))
    expect(result.current.isLoading).toBe(false)
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
    expect(result.current.data).toBeNull()
  })

  it('sets isLoading true during execution and stores the result on success', async () => {
    const actionFn = vi.fn().mockResolvedValue({ ok: true })
    const onSuccess = vi.fn()
    const { result } = renderHook(() => useAsyncAction(actionFn, { onSuccess }))

    let promise
    act(() => {
      promise = result.current.execute('arg1')
    })
    expect(result.current.isLoading).toBe(true)

    await act(async () => {
      await promise
    })

    expect(actionFn).toHaveBeenCalledWith('arg1')
    expect(result.current.isLoading).toBe(false)
    expect(result.current.data).toEqual({ ok: true })
    expect(result.current.error).toBeNull()
    expect(onSuccess).toHaveBeenCalledWith({ ok: true })
  })

  it('captures a plain Error message on failure', async () => {
    const actionFn = vi.fn().mockRejectedValue(new Error('boom'))
    const onError = vi.fn()
    const { result } = renderHook(() => useAsyncAction(actionFn, { onError }))

    await act(async () => {
      await result.current.execute()
    })

    expect(result.current.isLoading).toBe(false)
    expect(result.current.error).toBe('boom')
    expect(onError).toHaveBeenCalledWith('boom')
  })

  it('prefers err.response.data.error when present', async () => {
    const actionFn = vi.fn().mockRejectedValue({
      response: { data: { error: 'server rejected request' } }
    })
    const { result } = renderHook(() => useAsyncAction(actionFn))

    await act(async () => {
      await result.current.execute()
    })

    expect(result.current.error).toBe('server rejected request')
  })

  it('falls back to a generic message when the error has no message', async () => {
    const actionFn = vi.fn().mockRejectedValue({})
    const { result } = renderHook(() => useAsyncAction(actionFn))

    await act(async () => {
      await result.current.execute()
    })

    expect(result.current.error).toBe('An unexpected error occurred')
  })

  it('works without onSuccess/onError callbacks provided', async () => {
    const actionFn = vi.fn().mockRejectedValue(new Error('no callbacks'))
    const { result } = renderHook(() => useAsyncAction(actionFn))

    await act(async () => {
      await result.current.execute()
    })

    expect(result.current.error).toBe('no callbacks')
  })

  it('reset clears loading, error, and data state', async () => {
    const actionFn = vi.fn().mockRejectedValue(new Error('fail'))
    const { result } = renderHook(() => useAsyncAction(actionFn))

    await act(async () => {
      await result.current.execute()
    })
    expect(result.current.error).toBe('fail')

    act(() => {
      result.current.reset()
    })

    expect(result.current.isLoading).toBe(false)
    expect(result.current.error).toBeNull()
    expect(result.current.data).toBeNull()
  })

  it('setError can be used to set an error directly', () => {
    const { result } = renderHook(() => useAsyncAction(vi.fn()))

    act(() => {
      result.current.setError('manual error')
    })

    expect(result.current.error).toBe('manual error')
  })
})
