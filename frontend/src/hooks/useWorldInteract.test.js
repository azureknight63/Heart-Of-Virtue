import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useWorldInteract } from './useWorldInteract'
import apiEndpoints from '../api/endpoints'

vi.mock('../api/endpoints', () => ({
  default: {
    world: {
      interact: vi.fn(),
      search: vi.fn(),
      getEvents: vi.fn(),
    },
  },
}))

describe('useWorldInteract', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('starts with empty/idle default state', () => {
    const { result } = renderHook(() => useWorldInteract())
    expect(result.current.loading).toBe(false)
    expect(result.current.isLocked).toBe(false)
    expect(result.current.error).toBeNull()
    expect(result.current.interactionOutput).toBeNull()
    expect(result.current.interactionHistory).toEqual([])
    expect(result.current.searchLoading).toBe(false)
    expect(result.current.searchOutput).toBeNull()
    expect(result.current.takingAllItems).toBe(false)
  })

  describe('search', () => {
    it('joins returned messages into searchOutput and calls onRefetch', async () => {
      apiEndpoints.world.search.mockResolvedValue({
        data: { messages: ['You found a key!', 'And a coin.'] },
      })
      const onRefetch = vi.fn()
      const { result } = renderHook(() => useWorldInteract({ onRefetch }))

      await act(async () => {
        await result.current.search()
      })

      expect(result.current.searchOutput).toBe('You found a key! And a coin.')
      expect(onRefetch).toHaveBeenCalled()
      expect(result.current.searchLoading).toBe(false)
    })

    it('shows a nothing-found message when messages is empty', async () => {
      apiEndpoints.world.search.mockResolvedValue({ data: { messages: [] } })
      const { result } = renderHook(() => useWorldInteract())

      await act(async () => {
        await result.current.search()
      })

      expect(result.current.searchOutput).toBe('Nothing new found.')
    })

    it('shows a failure message when the response has no data', async () => {
      apiEndpoints.world.search.mockResolvedValue({ data: null })
      const { result } = renderHook(() => useWorldInteract())

      await act(async () => {
        await result.current.search()
      })

      expect(result.current.searchOutput).toBe('Search failed.')
    })

    it('shows a failure message and logs when the request throws', async () => {
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      apiEndpoints.world.search.mockRejectedValue(new Error('offline'))
      const { result } = renderHook(() => useWorldInteract())

      await act(async () => {
        await result.current.search()
      })

      expect(result.current.searchOutput).toBe('Search failed.')
      expect(errorSpy).toHaveBeenCalledWith('Search error:', expect.any(Error))
      errorSpy.mockRestore()
    })

    it('ignores a concurrent call while one is already in flight', async () => {
      let resolveFirst
      apiEndpoints.world.search.mockReturnValue(new Promise((r) => { resolveFirst = r }))
      const { result } = renderHook(() => useWorldInteract())

      let firstCall
      act(() => {
        firstCall = result.current.search()
      })
      expect(result.current.searchLoading).toBe(true)

      await act(async () => {
        await result.current.search()
      })
      expect(apiEndpoints.world.search).toHaveBeenCalledTimes(1)

      await act(async () => {
        resolveFirst({ data: { messages: [] } })
        await firstCall
      })
    })
  })

  describe('takeAll', () => {
    it('does nothing when given an empty list', async () => {
      const { result } = renderHook(() => useWorldInteract())
      await act(async () => {
        await result.current.takeAll([])
      })
      expect(apiEndpoints.world.interact).not.toHaveBeenCalled()
      expect(result.current.takingAllItems).toBe(false)
    })

    it('takes every item, summarizes, and notifies callbacks', async () => {
      apiEndpoints.world.interact
        .mockResolvedValueOnce({ data: { success: true } })
        .mockResolvedValueOnce({ data: { success: true } })
      const onRefetch = vi.fn().mockResolvedValue(undefined)
      const onInteractionComplete = vi.fn()
      const onTypingChange = vi.fn()
      const { result } = renderHook(() => useWorldInteract({ onRefetch, onInteractionComplete, onTypingChange }))

      const items = [
        { id: 'item1', name: 'Gold Coin', count: 10 },
        { id: 'item2', name: 'Silver Ring', count: 1 },
      ]

      await act(async () => {
        await result.current.takeAll(items)
      })

      expect(apiEndpoints.world.interact).toHaveBeenNthCalledWith(1, 'item1', 'take', 10)
      expect(apiEndpoints.world.interact).toHaveBeenNthCalledWith(2, 'item2', 'take', 1)
      expect(result.current.interactionOutput).toBe('Jean takes: 10× Gold Coin, Silver Ring.')
      expect(result.current.interactionHistory).toEqual(['Jean takes: 10× Gold Coin, Silver Ring.'])
      expect(onTypingChange).toHaveBeenCalledWith(true)
      expect(onRefetch).toHaveBeenCalled()
      expect(onInteractionComplete).toHaveBeenCalled()
      expect(result.current.takingAllItems).toBe(false)
    })

    it('stops on the first failure and surfaces the error', async () => {
      apiEndpoints.world.interact
        .mockResolvedValueOnce({ data: { success: true } })
        .mockResolvedValueOnce({ data: { success: false, error: 'Too heavy to carry.' } })
      const { result } = renderHook(() => useWorldInteract())

      const items = [
        { id: 'item1', name: 'Gold Coin', count: 10 },
        { id: 'item2', name: 'Silver Ring', count: 1 },
      ]

      await act(async () => {
        await result.current.takeAll(items)
      })

      expect(apiEndpoints.world.interact).toHaveBeenCalledTimes(2)
      expect(result.current.error).toBe('Too heavy to carry.')
      // Only the first item succeeded before the break, so a summary is still shown
      expect(result.current.interactionOutput).toBe('Jean takes: 10× Gold Coin.')
    })

    it('sets a network error and stops when a request throws', async () => {
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      apiEndpoints.world.interact.mockRejectedValue(new Error('offline'))
      const { result } = renderHook(() => useWorldInteract())

      await act(async () => {
        await result.current.takeAll([{ id: 'item1', name: 'Gold Coin', count: 10 }])
      })

      expect(result.current.error).toBe('Network error')
      expect(errorSpy).toHaveBeenCalledWith('Take all error:', expect.any(Error))
      errorSpy.mockRestore()
    })

    it('does nothing when isLocked is already true', async () => {
      apiEndpoints.world.interact.mockResolvedValue({
        data: { success: true, message: 'Locked now', object_state: {} },
      })
      const { result } = renderHook(() => useWorldInteract())

      // Lock via a normal 'take' interact where requested qty === count
      await act(async () => {
        await result.current.interact({ id: 'x', count: 1 }, 'take', 1)
      })
      expect(result.current.isLocked).toBe(true)

      apiEndpoints.world.interact.mockClear()
      await act(async () => {
        await result.current.takeAll([{ id: 'item1', name: 'Gold Coin', count: 10 }])
      })
      expect(apiEndpoints.world.interact).not.toHaveBeenCalled()
    })
  })

  describe('takeOne', () => {
    it('sets interactionOutput and refetches on success', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'Took Gold.' } })
      const onRefetch = vi.fn().mockResolvedValue(undefined)
      const { result } = renderHook(() => useWorldInteract({ onRefetch }))

      await act(async () => {
        await result.current.takeOne('gold1', 'Gold')
      })

      expect(apiEndpoints.world.interact).toHaveBeenCalledWith('gold1', 'take')
      expect(result.current.interactionOutput).toBe('Took Gold.')
      expect(onRefetch).toHaveBeenCalled()
    })

    it('defaults to "Took <name>" when the response omits a message', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: true } })
      const { result } = renderHook(() => useWorldInteract())

      await act(async () => {
        await result.current.takeOne('gold1', 'Gold')
      })

      expect(result.current.interactionOutput).toBe('Took Gold')
    })

    it('sets an error on failure', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: false, error: 'Cannot take that.' } })
      const { result } = renderHook(() => useWorldInteract())

      await act(async () => {
        await result.current.takeOne('gold1', 'Gold')
      })

      expect(result.current.error).toBe('Cannot take that.')
    })

    it('defaults to "Failed to take item" when no error field is present', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: false } })
      const { result } = renderHook(() => useWorldInteract())

      await act(async () => {
        await result.current.takeOne('gold1', 'Gold')
      })

      expect(result.current.error).toBe('Failed to take item')
    })

    it('sets a network error when the request throws', async () => {
      apiEndpoints.world.interact.mockRejectedValue(new Error('offline'))
      const { result } = renderHook(() => useWorldInteract())

      await act(async () => {
        await result.current.takeOne('gold1', 'Gold')
      })

      expect(result.current.error).toBe('Network error')
    })
  })

  describe('interact', () => {
    it('sets output/history and calls onTypingChange on success', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'The guard nods.' } })
      apiEndpoints.world.getEvents.mockResolvedValue({ data: { success: true, events: [] } })
      const onTypingChange = vi.fn()
      const onInteractionComplete = vi.fn()
      const { result } = renderHook(() => useWorldInteract({ onTypingChange, onInteractionComplete }))

      await act(async () => {
        await result.current.interact({ id: 'npc1', count: 1 }, 'talk', null)
      })

      expect(apiEndpoints.world.interact).toHaveBeenCalledWith('npc1', 'talk', null)
      expect(result.current.interactionOutput).toBe('The guard nods.')
      expect(result.current.interactionHistory).toEqual(['The guard nods.'])
      expect(onTypingChange).toHaveBeenCalledWith(true)
      expect(onInteractionComplete).toHaveBeenCalled()
    })

    it('defaults to "Action completed." when the response omits a message', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: true } })
      apiEndpoints.world.getEvents.mockResolvedValue({ data: { success: true, events: [] } })
      const { result } = renderHook(() => useWorldInteract())

      await act(async () => {
        await result.current.interact({ id: 'npc1', count: 1 }, 'talk', null)
      })

      expect(result.current.interactionOutput).toBe('Action completed.')
    })

    it('sets an error on failure, preferring data.error then data.message then a default', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: false, error: 'You cannot do that.' } })
      const { result } = renderHook(() => useWorldInteract())

      await act(async () => {
        await result.current.interact({ id: 'npc1', count: 1 }, 'attack', null)
      })

      expect(result.current.error).toBe('You cannot do that.')
    })

    it('falls back to "Interaction failed" when both error and message are absent', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: false } })
      const { result } = renderHook(() => useWorldInteract())

      await act(async () => {
        await result.current.interact({ id: 'npc1', count: 1 }, 'attack', null)
      })

      expect(result.current.error).toBe('Interaction failed')
    })

    it('sets a network error and logs when the request throws', async () => {
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      apiEndpoints.world.interact.mockRejectedValue(new Error('offline'))
      const { result } = renderHook(() => useWorldInteract())

      await act(async () => {
        await result.current.interact({ id: 'npc1', count: 1 }, 'attack', null)
      })

      expect(result.current.error).toBe('Network error')
      expect(errorSpy).toHaveBeenCalledWith('Interaction error:', expect.any(Error))
      errorSpy.mockRestore()
    })

    it('applies object_state via onObjectStateUpdate without calling onClose', async () => {
      apiEndpoints.world.interact.mockResolvedValue({
        data: { success: true, message: 'Click.', object_state: { keywords: ['Open'], locked: false, state: 'unlocked' } },
      })
      apiEndpoints.world.getEvents.mockResolvedValue({ data: { success: true, events: [] } })
      const onObjectStateUpdate = vi.fn()
      const onClose = vi.fn()
      const { result } = renderHook(() => useWorldInteract({ onObjectStateUpdate, onClose }))

      await act(async () => {
        await result.current.interact({ id: 'door1', count: 1 }, 'unlock', null)
      })

      expect(onObjectStateUpdate).toHaveBeenCalledWith({ keywords: ['Open'], locked: false, state: 'unlocked' })
      expect(onClose).not.toHaveBeenCalled()
    })

    it('locks when a full-stack locking action succeeds', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'Taken.' } })
      apiEndpoints.world.getEvents.mockResolvedValue({ data: { success: true, events: [] } })
      const { result } = renderHook(() => useWorldInteract())

      await act(async () => {
        await result.current.interact({ id: 'item1', count: 5 }, 'take', 5)
      })

      expect(result.current.isLocked).toBe(true)
    })

    it('does not lock when only a partial quantity of a stackable was taken', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'Taken some.' } })
      apiEndpoints.world.getEvents.mockResolvedValue({ data: { success: true, events: [] } })
      const { result } = renderHook(() => useWorldInteract())

      await act(async () => {
        await result.current.interact({ id: 'item1', count: 5 }, 'take', 2)
      })

      expect(result.current.isLocked).toBe(false)
    })

    it('does not touch isLocked for non-locking actions', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'Hello.' } })
      apiEndpoints.world.getEvents.mockResolvedValue({ data: { success: true, events: [] } })
      const { result } = renderHook(() => useWorldInteract())

      await act(async () => {
        await result.current.interact({ id: 'npc1', count: 1 }, 'talk', null)
      })

      expect(result.current.isLocked).toBe(false)
    })

    it('forwards events_triggered directly from the interact response', async () => {
      apiEndpoints.world.interact.mockResolvedValue({
        data: { success: true, message: 'Something stirs.', events_triggered: [{ output_text: 'A trap springs!' }] },
      })
      apiEndpoints.world.getEvents.mockResolvedValue({ data: { success: true, events: [] } })
      const onEventsTriggered = vi.fn()
      const { result } = renderHook(() => useWorldInteract({ onEventsTriggered }))

      await act(async () => {
        await result.current.interact({ id: 'npc1', count: 1 }, 'talk', null)
      })

      expect(onEventsTriggered).toHaveBeenCalledWith([{ output_text: 'A trap springs!' }])
    })

    it('chains a getEvents check after interact and forwards displayable events', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'Ok.' } })
      apiEndpoints.world.getEvents.mockResolvedValue({
        data: { success: true, events: [{ output_text: 'Something happened!' }] },
      })
      const onEventsTriggered = vi.fn()
      const onRefetch = vi.fn().mockResolvedValue(undefined)
      const { result } = renderHook(() => useWorldInteract({ onEventsTriggered, onRefetch }))

      await act(async () => {
        await result.current.interact({ id: 'npc1', count: 1 }, 'talk', null)
      })

      expect(apiEndpoints.world.getEvents).toHaveBeenCalled()
      expect(onEventsTriggered).toHaveBeenCalledWith([{ output_text: 'Something happened!' }])
      // Called once after the main interact, once after the events check
      expect(onRefetch).toHaveBeenCalledTimes(2)
    })

    it('filters out events with neither output_text nor needs_input', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'Ok.' } })
      apiEndpoints.world.getEvents.mockResolvedValue({
        data: { success: true, events: [{ output_text: '   ' }, { needs_input: true }] },
      })
      const onEventsTriggered = vi.fn()
      const { result } = renderHook(() => useWorldInteract({ onEventsTriggered }))

      await act(async () => {
        await result.current.interact({ id: 'npc1', count: 1 }, 'talk', null)
      })

      expect(onEventsTriggered).toHaveBeenCalledWith([{ needs_input: true }])
    })

    it('silently logs when the background events check fails, but still completes', async () => {
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'Ok.' } })
      apiEndpoints.world.getEvents.mockRejectedValue(new Error('events offline'))
      const onInteractionComplete = vi.fn()
      const { result } = renderHook(() => useWorldInteract({ onInteractionComplete }))

      await act(async () => {
        await result.current.interact({ id: 'npc1', count: 1 }, 'talk', null)
      })

      expect(errorSpy).toHaveBeenCalledWith('Failed to trigger events:', expect.any(Error))
      expect(onInteractionComplete).toHaveBeenCalled()
      errorSpy.mockRestore()
    })

    describe('teleport', () => {
      beforeEach(() => {
        vi.useFakeTimers()
      })
      afterEach(() => {
        vi.useRealTimers()
      })

      it('refetches, completes, and closes after a delay without chaining getEvents', async () => {
        apiEndpoints.world.interact.mockResolvedValue({
          data: { success: true, message: 'The floor gives way!', teleported: true },
        })
        const onRefetch = vi.fn().mockResolvedValue(undefined)
        const onInteractionComplete = vi.fn()
        const onClose = vi.fn()
        const { result } = renderHook(() => useWorldInteract({ onRefetch, onInteractionComplete, onClose }))

        await act(async () => {
          await result.current.interact({ id: 'trap1', count: 1 }, 'step', null)
        })

        expect(onRefetch).toHaveBeenCalledTimes(1)
        expect(onInteractionComplete).toHaveBeenCalled()
        expect(onClose).not.toHaveBeenCalled()
        expect(apiEndpoints.world.getEvents).not.toHaveBeenCalled()
        expect(result.current.loading).toBe(false)

        act(() => {
          vi.advanceTimersByTime(800)
        })
        expect(onClose).toHaveBeenCalled()
      })
    })
  })

  describe('reset', () => {
    it('clears interactionOutput, interactionHistory, error, and isLocked', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: false, error: 'Nope.' } })
      const { result } = renderHook(() => useWorldInteract())

      await act(async () => {
        await result.current.interact({ id: 'x', count: 1 }, 'attack', null)
      })
      expect(result.current.error).toBe('Nope.')

      act(() => {
        result.current.reset()
      })

      expect(result.current.interactionOutput).toBeNull()
      expect(result.current.interactionHistory).toEqual([])
      expect(result.current.error).toBeNull()
      expect(result.current.isLocked).toBe(false)
    })
  })
})
