import { useState, useCallback, useEffect } from 'react'
import { shop as shopApi } from '../api/endpoints'

/**
 * useShop — manages all shop API interactions for a given merchant NPC.
 *
 * Fetches shop state on mount, exposes buy / sell / buyback actions that
 * re-fetch state after every successful transaction. Callers should also
 * invoke onRefetch() (from the parent) after success to sync player gold
 * and inventory in the rest of the UI.
 *
 * @param {string} npcId - str(id(npc)) of the target merchant
 */
export function useShop(npcId) {
  const [shopState, setShopState] = useState(null)
  const [sellInventory, setSellInventory] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [txnMessage, setTxnMessage] = useState(null)

  const refresh = useCallback(async () => {
    if (!npcId) return
    setIsLoading(true)
    setError(null)
    try {
      const res = await shopApi.getState(npcId)
      const data = res.data
      if (data.success) {
        setShopState(data.shop_state)
        setSellInventory(data.sell_inventory || [])
      } else {
        setError(data.error || 'Failed to load shop')
      }
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'Network error')
    } finally {
      setIsLoading(false)
    }
  }, [npcId])

  useEffect(() => {
    refresh()
  }, [refresh])

  const _handleTxn = async (apiFn, successKey) => {
    setTxnMessage(null)
    try {
      const res = await apiFn()
      const data = res.data
      if (data.success) {
        setShopState(data.shop_state)
        setSellInventory(data.sell_inventory || [])
        setTxnMessage({ type: 'success', text: data.message || 'Done.' })
      } else {
        setTxnMessage({ type: 'error', text: data.error || 'Transaction failed' })
      }
      return { success: data.success, message: data.message, [successKey]: data[successKey] }
    } catch (err) {
      const msg = err.response?.data?.error || err.message || 'Network error'
      setTxnMessage({ type: 'error', text: msg })
      return { success: false, message: msg }
    }
  }

  const buy = (itemId, quantity) =>
    _handleTxn(() => shopApi.buy(npcId, itemId, quantity), 'gold_spent')

  const sell = (itemId, quantity) =>
    _handleTxn(() => shopApi.sell(npcId, itemId, quantity), 'gold_gained')

  const buyback = (itemId) =>
    _handleTxn(() => shopApi.buyback(npcId, itemId), 'gold_spent')

  return { shopState, sellInventory, isLoading, error, txnMessage, buy, sell, buyback, refresh }
}
