import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useShop } from './useShop'
import { shop as shopApi } from '../api/endpoints'

vi.mock('../api/endpoints', () => ({
  shop: {
    getState: vi.fn(),
    buy: vi.fn(),
    sell: vi.fn(),
    buyback: vi.fn(),
  },
}))

describe('useShop', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does nothing when npcId is falsy', async () => {
    const { result } = renderHook(() => useShop(null))
    await waitFor(() => expect(result.current.isLoading).toBe(true))
    expect(shopApi.getState).not.toHaveBeenCalled()
  })

  it('loads shop state on mount', async () => {
    shopApi.getState.mockResolvedValue({
      data: {
        success: true,
        shop_state: { name: 'Jambo' },
        sell_inventory: [{ id: 1 }],
        message: 'Welcome!',
      },
    })

    const { result } = renderHook(() => useShop('npc-1'))

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.shopState).toEqual({ name: 'Jambo' })
    expect(result.current.sellInventory).toEqual([{ id: 1 }])
    expect(result.current.welcomeMessage).toBe('Welcome!')
    expect(result.current.error).toBeNull()
  })

  it('defaults sellInventory to an empty array when absent', async () => {
    shopApi.getState.mockResolvedValue({
      data: { success: true, shop_state: {}, message: null },
    })
    const { result } = renderHook(() => useShop('npc-1'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.sellInventory).toEqual([])
  })

  it('sets an error when the API reports failure', async () => {
    shopApi.getState.mockResolvedValue({
      data: { success: false, error: 'Shop closed' },
    })
    const { result } = renderHook(() => useShop('npc-1'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBe('Shop closed')
  })

  it('falls back to a default error message when the API omits one', async () => {
    shopApi.getState.mockResolvedValue({ data: { success: false } })
    const { result } = renderHook(() => useShop('npc-1'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBe('Failed to load shop')
  })

  it('captures a network error from a thrown exception', async () => {
    shopApi.getState.mockRejectedValue(new Error('timeout'))
    const { result } = renderHook(() => useShop('npc-1'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBe('timeout')
  })

  it('prefers err.response.data.error over err.message', async () => {
    shopApi.getState.mockRejectedValue({
      response: { data: { error: 'server says no' } },
    })
    const { result } = renderHook(() => useShop('npc-1'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBe('server says no')
  })

  it('falls back to a generic network error message', async () => {
    shopApi.getState.mockRejectedValue({})
    const { result } = renderHook(() => useShop('npc-1'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBe('Network error')
  })

  describe('transactions', () => {
    async function setup() {
      shopApi.getState.mockResolvedValue({
        data: { success: true, shop_state: { gold: 100 }, sell_inventory: [] },
      })
      const { result } = renderHook(() => useShop('npc-1'))
      await waitFor(() => expect(result.current.isLoading).toBe(false))
      return result
    }

    it('buy() updates shop state and sets a success message', async () => {
      const result = await setup()
      shopApi.buy.mockResolvedValue({
        data: {
          success: true,
          shop_state: { gold: 90 },
          sell_inventory: [{ id: 2 }],
          message: 'Bought!',
          gold_spent: 10,
        },
      })

      let txnResult
      await act(async () => {
        txnResult = await result.current.buy('item-1', 1)
      })

      expect(shopApi.buy).toHaveBeenCalledWith('npc-1', 'item-1', 1)
      expect(result.current.shopState).toEqual({ gold: 90 })
      expect(result.current.sellInventory).toEqual([{ id: 2 }])
      expect(result.current.txnMessage).toEqual({ type: 'success', text: 'Bought!' })
      expect(txnResult).toEqual({ success: true, message: 'Bought!', gold_spent: 10 })
    })

    it('buy() defaults the success message when none is provided', async () => {
      const result = await setup()
      shopApi.buy.mockResolvedValue({
        data: { success: true, shop_state: {}, sell_inventory: [] },
      })
      await act(async () => {
        await result.current.buy('item-1', 1)
      })
      expect(result.current.txnMessage).toEqual({ type: 'success', text: 'Done.' })
    })

    it('buy() sets an error message on failure', async () => {
      const result = await setup()
      shopApi.buy.mockResolvedValue({
        data: { success: false, error: 'Not enough gold' },
      })
      await act(async () => {
        await result.current.buy('item-1', 1)
      })
      expect(result.current.txnMessage).toEqual({ type: 'error', text: 'Not enough gold' })
    })

    it('buy() defaults the failure message when none is provided', async () => {
      const result = await setup()
      shopApi.buy.mockResolvedValue({ data: { success: false } })
      await act(async () => {
        await result.current.buy('item-1', 1)
      })
      expect(result.current.txnMessage).toEqual({ type: 'error', text: 'Transaction failed' })
    })

    it('buy() captures a thrown network error', async () => {
      const result = await setup()
      shopApi.buy.mockRejectedValue(new Error('down'))
      let txnResult
      await act(async () => {
        txnResult = await result.current.buy('item-1', 1)
      })
      expect(result.current.txnMessage).toEqual({ type: 'error', text: 'down' })
      expect(txnResult).toEqual({ success: false, message: 'down' })
    })

    it('sell() updates state via the sell endpoint', async () => {
      const result = await setup()
      shopApi.sell.mockResolvedValue({
        data: { success: true, shop_state: { gold: 110 }, sell_inventory: [], message: 'Sold!', gold_gained: 10 },
      })
      await act(async () => {
        await result.current.sell('item-1', 2)
      })
      expect(shopApi.sell).toHaveBeenCalledWith('npc-1', 'item-1', 2)
      expect(result.current.shopState).toEqual({ gold: 110 })
      expect(result.current.txnMessage).toEqual({ type: 'success', text: 'Sold!' })
    })

    it('buyback() updates state via the buyback endpoint', async () => {
      const result = await setup()
      shopApi.buyback.mockResolvedValue({
        data: { success: true, shop_state: { gold: 95 }, sell_inventory: [], message: 'Bought back!' },
      })
      await act(async () => {
        await result.current.buyback('item-1')
      })
      expect(shopApi.buyback).toHaveBeenCalledWith('npc-1', 'item-1')
      expect(result.current.txnMessage).toEqual({ type: 'success', text: 'Bought back!' })
    })

    it('refresh() can be called manually to re-fetch shop state', async () => {
      const result = await setup()
      shopApi.getState.mockResolvedValue({
        data: { success: true, shop_state: { gold: 200 }, sell_inventory: [] },
      })
      await act(async () => {
        await result.current.refresh()
      })
      expect(result.current.shopState).toEqual({ gold: 200 })
    })
  })
})
