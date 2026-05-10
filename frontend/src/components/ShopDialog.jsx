import { useState, useMemo } from 'react'
import BaseDialog from './BaseDialog'
import { useShop } from '../hooks/useShop'
import { colors, spacing, accessibility } from '../styles/theme'
import { getItemIcon } from '../utils/itemUtils'

// ── Sub-components ────────────────────────────────────────────────────────────

function WeightBar({ current, max, pendingDelta, isMobile }) {
  const currentPct = max > 0 ? Math.min(100, (current / max) * 100) : 0
  const isSellDelta = pendingDelta < 0
  const pendingPct = max > 0
    ? isSellDelta
      ? Math.min(currentPct, (Math.abs(pendingDelta) / max) * 100)
      : Math.min(100 - currentPct, (Math.abs(pendingDelta) / max) * 100)
    : 0
  const projectedTotal = current + pendingDelta
  const isOverweight = projectedTotal > max

  const fillColor =
    currentPct >= 90 ? colors.danger
    : currentPct >= 75 ? colors.secondary
    : colors.primary

  const pendingColor = isOverweight ? colors.danger : 'rgba(255,170,0,0.7)'

  const isBuy = pendingDelta > 0

  return (
    <div style={{
      padding: `6px ${spacing.md}`,
      background: 'rgba(0,0,0,0.3)',
      border: `1px solid ${colors.border.main}`,
      borderRadius: '6px',
      display: 'flex',
      flexDirection: 'column',
      gap: '4px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px', color: colors.text.muted }}>
          <span>⚖️</span>
          <span style={{ color: colors.text.main, fontWeight: 'bold' }}>{current.toFixed(1)}</span>
          {pendingDelta !== 0 && (
            <>
              <span style={{
                color: isSellDelta ? colors.primary : isOverweight ? colors.danger : colors.secondary,
                fontWeight: 'bold',
              }}>
                {isSellDelta ? '(−' : '(+'}{Math.abs(pendingDelta).toFixed(2)})
              </span>
              {!isMobile && (
                <span style={{ color: colors.text.dim, fontSize: '0.58rem' }}>
                  → {projectedTotal.toFixed(1)} kg after
                </span>
              )}
            </>
          )}
          {!isMobile && pendingDelta === 0 && <span style={{ color: colors.text.dim }}>&nbsp;kg</span>}
        </div>
        <span style={{ color: colors.text.dim, fontSize: '0.62rem' }}>max {max.toFixed(1)} kg</span>
      </div>
      <div style={{
        width: '100%',
        height: '8px',
        background: 'rgba(255,255,255,0.06)',
        borderRadius: '4px',
        overflow: 'hidden',
        display: 'flex',
      }}>
        <div style={{
          width: `${currentPct - (isSellDelta ? pendingPct : 0)}%`,
          height: '100%',
          background: fillColor,
          boxShadow: `0 0 4px ${fillColor}66`,
          flexShrink: 0,
          transition: 'width 0.2s ease',
        }} />
        {pendingDelta !== 0 && (
          <div style={{
            width: `${pendingPct}%`,
            height: '100%',
            background: isSellDelta ? 'rgba(0,255,136,0.25)' : pendingColor,
            flexShrink: 0,
            transition: 'width 0.2s ease',
          }} />
        )}
      </div>
      {isOverweight && (
        <div style={{ fontSize: '0.62rem', color: colors.danger }}>
          ⚠ Exceeds carry limit
        </div>
      )}
    </div>
  )
}

function ItemRow({ item, isSelected, tab, onClick, isMobile }) {
  const count = item.count || 1
  const isBuyback = item.is_buyback

  const borderColor = isSelected
    ? isBuyback ? colors.accent
      : tab === 'sell' ? colors.secondary
      : colors.primary
    : 'transparent'

  const bgColor = isSelected
    ? isBuyback ? 'rgba(0,204,255,0.10)'
      : tab === 'sell' ? 'rgba(255,170,0,0.10)'
      : 'rgba(0,255,136,0.10)'
    : isBuyback ? 'rgba(0,204,255,0.04)'
    : 'transparent'

  const priceColor = isBuyback ? colors.accent
    : tab === 'sell' ? colors.secondary
    : colors.gold

  const displayPrice = tab === 'sell' ? item.offer : item.price

  return (
    <div
      onClick={onClick}
      style={{
        display: 'grid',
        gridTemplateColumns: '2fr 58px 68px 86px',
        alignItems: 'center',
        padding: `0 14px`,
        minHeight: isMobile ? accessibility.touchTarget : '44px',
        borderLeft: `3px solid ${borderColor}`,
        paddingLeft: isSelected ? '11px' : '14px',
        background: bgColor,
        borderBottom: '1px solid rgba(255,170,0,0.07)',
        cursor: 'pointer',
        transition: 'background 0.12s',
      }}
    >
      <div style={{
        display: 'flex', alignItems: 'center', gap: '7px',
        fontSize: '0.82rem', color: colors.text.main, fontWeight: 500,
        minWidth: 0,
      }}>
        <span style={{ fontSize: '0.95rem', flexShrink: 0 }}>
          {getItemIcon(item)}
        </span>
        <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {item.name}
        </span>
        {count > 1 && (
          <span style={{
            fontSize: '0.58rem',
            background: 'rgba(255,204,0,0.15)',
            color: colors.gold,
            border: `1px solid rgba(255,204,0,0.3)`,
            padding: '1px 5px', borderRadius: '8px', fontWeight: 'bold', flexShrink: 0,
          }}>
            ×{count}
          </span>
        )}
        {isBuyback && (
          <span style={{
            fontSize: '0.55rem',
            background: 'rgba(0,204,255,0.15)',
            color: colors.accent,
            border: `1px solid rgba(0,204,255,0.35)`,
            padding: '1px 5px', borderRadius: '8px', fontWeight: 'bold',
            flexShrink: 0, letterSpacing: '0.5px',
            display: 'flex', alignItems: 'center', gap: '2px',
          }}>
            ↩ BUYBACK
          </span>
        )}
      </div>
      <div style={{ textAlign: 'right', fontSize: '0.62rem', color: colors.text.dim, textTransform: 'uppercase' }}>
        {item.subtype || item.type || ''}
      </div>
      <div style={{ textAlign: 'right', fontSize: '0.7rem', color: colors.text.muted }}>
        {(item.weight || 0).toFixed(2)} kg
      </div>
      <div style={{ textAlign: 'right', fontSize: '0.78rem', fontWeight: 'bold', color: priceColor }}>
        {tab === 'sell' && (
          <div style={{ fontSize: '0.58rem', color: colors.text.muted, fontWeight: 'normal', marginBottom: '1px' }}>
            Offer:
          </div>
        )}
        {displayPrice} 💰
      </div>
    </div>
  )
}

function QtyPicker({ value, max, onChange, isMobile }) {
  const btnSize = isMobile ? accessibility.touchTarget : '26px'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '6px',
        background: 'rgba(0,0,0,0.4)',
        border: '1px solid rgba(0,255,136,0.3)',
        borderRadius: '6px', padding: '4px 8px',
      }}>
        <button
          onClick={() => onChange(Math.max(1, value - 1))}
          disabled={value <= 1}
          style={{
            width: btnSize, height: btnSize, minWidth: btnSize,
            borderRadius: '4px',
            border: '1px solid rgba(0,255,136,0.4)',
            background: 'rgba(0,255,136,0.1)', color: colors.primary,
            fontSize: '1rem', fontWeight: 'bold', cursor: value <= 1 ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            opacity: value <= 1 ? 0.4 : 1,
            fontFamily: 'monospace', lineHeight: 1,
          }}
        >−</button>
        <input
          type="number"
          value={value}
          min={1}
          max={max}
          onChange={(e) => {
            const v = Math.max(1, Math.min(max, parseInt(e.target.value, 10) || 1))
            onChange(v)
          }}
          style={{
            width: '36px', textAlign: 'center',
            background: 'rgba(0,0,0,0.5)',
            border: '1px solid rgba(0,255,136,0.3)',
            borderRadius: '3px', color: colors.text.bright,
            fontFamily: 'monospace', fontSize: '0.85rem',
            fontWeight: 'bold', padding: '3px 4px',
            // Remove native browser spinners
            WebkitAppearance: 'none',
            MozAppearance: 'textfield',
            appearance: 'textfield',
          }}
        />
        <button
          onClick={() => onChange(Math.min(max, value + 1))}
          disabled={value >= max}
          style={{
            width: btnSize, height: btnSize, minWidth: btnSize,
            borderRadius: '4px',
            border: '1px solid rgba(0,255,136,0.4)',
            background: 'rgba(0,255,136,0.1)', color: colors.primary,
            fontSize: '1rem', fontWeight: 'bold', cursor: value >= max ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            opacity: value >= max ? 0.4 : 1,
            fontFamily: 'monospace', lineHeight: 1,
          }}
        >+</button>
        <span style={{ fontSize: '0.6rem', color: colors.text.muted, whiteSpace: 'nowrap' }}>/ {max}</span>
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

/**
 * ShopDialog — full shop modal overlay.
 *
 * Props:
 *   npcId      {string}   str(id(npc)) of the merchant
 *   npcName    {string}   Display name of the merchant
 *   initialTab {string}   'buy' | 'sell'
 *   player     {object}   Current player state (gold, weight)
 *   onClose    {function}
 *   onRefetch  {function} Called after each successful transaction to sync parent
 *   isMobile   {boolean}
 */
export default function ShopDialog({ npcId, npcName, initialTab = 'buy', player, onClose, onRefetch, isMobile }) {
  const { shopState, sellInventory, isLoading, error, txnMessage, buy, sell, buyback } = useShop(npcId)

  const [activeTab, setActiveTab] = useState(initialTab)
  const [selectedId, setSelectedId] = useState(null)
  const [quantity, setQuantity] = useState(1)

  // ── Derived values ─────────────────────────────────────────────────────────

  const allBuyItems = useMemo(() => {
    if (!shopState) return []
    return [...(shopState.buyback_items || []), ...(shopState.stock || [])]
  }, [shopState])

  const selectedItem = useMemo(() => {
    if (!selectedId) return null
    const list = activeTab === 'buy' ? allBuyItems : sellInventory
    return list.find(i => i.id === selectedId) || null
  }, [selectedId, activeTab, allBuyItems, sellInventory])

  // ── Weight delta for the weight bar ───────────────────────────────────────

  const pendingWeight = useMemo(() => {
    if (!selectedItem) return 0
    const w = (selectedItem.weight || 0) * quantity
    return activeTab === 'buy' ? w : -w
  }, [selectedItem, quantity, activeTab])

  // ── Buy validation ─────────────────────────────────────────────────────────

  const playerGold = shopState?.player_gold ?? (player?.gold ?? 0)
  const playerWeightCurrent = shopState?.player_weight_current ?? (player?.weight_current ?? 0)
  const playerWeightMax = shopState?.player_weight_max ?? (player?.weight_tolerance ?? 100)
  const merchantGold = shopState?.merchant_gold ?? 0

  const buyTotal = selectedItem && activeTab === 'buy'
    ? (selectedItem.price || 0) * quantity
    : 0
  const sellTotal = selectedItem && activeTab === 'sell'
    ? (selectedItem.offer || 0) * quantity
    : 0

  const cannotAffordBuy = activeTab === 'buy' && selectedItem && playerGold < buyTotal
  const wouldExceedWeight = activeTab === 'buy' && selectedItem
    && (playerWeightCurrent + pendingWeight) > playerWeightMax
  const merchantCantAfford = activeTab === 'sell' && selectedItem && merchantGold < sellTotal

  const buyDisabledReason =
    cannotAffordBuy ? `Not enough gold — need ${buyTotal - playerGold} more`
    : wouldExceedWeight ? 'Exceeds carry limit'
    : null

  // ── Max qty for picker ──────────────────────────────────────────────────────

  const maxQty = useMemo(() => {
    if (!selectedItem) return 1
    const available = selectedItem.count || 1
    if (activeTab === 'buy' && !selectedItem.is_buyback) {
      const unitPrice = selectedItem.price || 1
      const affordable = unitPrice > 0 ? Math.floor(playerGold / unitPrice) : available
      return Math.max(1, Math.min(available, affordable))
    }
    if (activeTab === 'sell') {
      const unitOffer = selectedItem.offer || 1
      const merchantCan = unitOffer > 0 ? Math.floor(merchantGold / unitOffer) : available
      return Math.max(1, Math.min(available, merchantCan))
    }
    return Math.max(1, available)
  }, [selectedItem, activeTab, playerGold, merchantGold])

  // ── Handlers ───────────────────────────────────────────────────────────────

  const handleSelectItem = (id) => {
    setSelectedId(prev => prev === id ? null : id)
    setQuantity(1)
  }

  const handleTabChange = (tab) => {
    setActiveTab(tab)
    setSelectedId(null)
    setQuantity(1)
  }

  const handleBuy = async () => {
    if (!selectedItem || buyDisabledReason) return
    const result = await buy(selectedItem.id, quantity)
    if (result.success) {
      setSelectedId(null)
      setQuantity(1)
      if (onRefetch) await onRefetch()
    }
  }

  const handleSell = async () => {
    if (!selectedItem || merchantCantAfford) return
    const result = await sell(selectedItem.id, quantity)
    if (result.success) {
      setSelectedId(null)
      setQuantity(1)
      if (onRefetch) await onRefetch()
    }
  }

  const handleBuyback = async () => {
    if (!selectedItem) return
    const result = await buyback(selectedItem.id)
    if (result.success) {
      setSelectedId(null)
      setQuantity(1)
      if (onRefetch) await onRefetch()
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  const shopName = shopState?.shop_name || `${npcName}'s Shop`
  const tagline = npcName === 'Jambo' ? '"When you blue, Jambo Heals U!"' : `${npcName} — open for business`

  const hasBuyback = (shopState?.buyback_items || []).length > 0
  const buyItems = shopState?.stock || []

  return (
    <BaseDialog
      title={`🏪 ${shopName.toUpperCase()}`}
      onClose={onClose}
      maxWidth="640px"
      width="95%"
      padding={isMobile ? '12px' : '16px'}
      zIndex={1500}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>

        {/* NPC Strip */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '12px',
          padding: '8px 12px',
          background: 'rgba(0,204,255,0.05)',
          border: '1px solid rgba(0,204,255,0.2)',
          borderRadius: '6px',
        }}>
          <div style={{
            width: '40px', height: '40px', borderRadius: '50%',
            background: 'linear-gradient(135deg, #2a1a00, #3d2800)',
            border: `2px solid ${colors.gold}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '1.3rem', flexShrink: 0,
            boxShadow: '0 0 8px rgba(255,204,0,0.3)',
          }}>🧕</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ color: colors.accent, fontSize: '0.8rem', fontWeight: 'bold' }}>{npcName}</div>
            <div style={{ color: colors.text.muted, fontSize: '0.62rem', fontStyle: 'italic', marginTop: '2px' }}>
              {tagline}
            </div>
          </div>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            color: cannotAffordBuy && selectedItem ? colors.danger : colors.gold,
            fontSize: '0.85rem', fontWeight: 'bold', whiteSpace: 'nowrap',
          }}>
            💰 {isLoading ? '…' : playerGold}
          </div>
        </div>

        {/* Weight Bar */}
        <WeightBar
          current={playerWeightCurrent}
          max={playerWeightMax}
          pendingDelta={pendingWeight}
          isMobile={isMobile}
        />

        {/* Tab Bar */}
        <div style={{
          display: 'flex', gap: '4px',
          background: 'rgba(0,0,0,0.3)', padding: '4px',
          borderRadius: '6px', border: `1px solid ${colors.border.main}`,
        }}>
          {['buy', 'sell'].map(tab => {
            const isActive = activeTab === tab
            const activeColor = tab === 'sell' ? colors.secondary : colors.primary
            return (
              <button
                key={tab}
                onClick={() => handleTabChange(tab)}
                style={{
                  flex: 1,
                  padding: isMobile ? '10px 12px' : '7px 12px',
                  background: isActive ? (tab === 'sell' ? 'rgba(255,170,0,0.12)' : 'rgba(0,255,136,0.12)') : 'transparent',
                  border: `1px solid ${isActive ? activeColor : 'transparent'}`,
                  borderRadius: '4px',
                  color: isActive ? activeColor : colors.text.muted,
                  fontFamily: 'monospace', fontSize: '0.75rem',
                  fontWeight: 'bold', textTransform: 'uppercase',
                  letterSpacing: '1px', cursor: 'pointer', textAlign: 'center',
                }}
              >
                {tab === 'buy' ? '⬇ Buy' : '⬆ Sell'}
              </button>
            )
          })}
        </div>

        {/* Loading / Error */}
        {isLoading && (
          <div style={{ color: colors.text.muted, fontSize: '0.8rem', textAlign: 'center', padding: spacing.md }}>
            Loading shop…
          </div>
        )}
        {error && (
          <div style={{
            color: colors.danger, fontSize: '0.75rem', padding: '8px 12px',
            background: 'rgba(255,68,68,0.1)', border: '1px solid rgba(255,68,68,0.3)',
            borderRadius: '6px',
          }}>
            ⚠ {error}
          </div>
        )}

        {/* Transaction feedback */}
        {txnMessage && (
          <div style={{
            fontSize: '0.72rem', padding: '6px 12px',
            background: txnMessage.type === 'success' ? 'rgba(0,255,136,0.08)' : 'rgba(255,68,68,0.08)',
            border: `1px solid ${txnMessage.type === 'success' ? 'rgba(0,255,136,0.25)' : 'rgba(255,68,68,0.25)'}`,
            color: txnMessage.type === 'success' ? colors.primary : colors.danger,
            borderRadius: '6px',
          }}>
            {txnMessage.type === 'success' ? '✓' : '✗'} {txnMessage.text}
          </div>
        )}

        {/* Item List */}
        {!isLoading && !error && (
          <div style={{
            background: 'rgba(0,0,0,0.4)',
            border: `1px solid ${colors.border.main}`,
            borderRadius: '8px', overflow: 'hidden',
          }}>
            {/* List header */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '2fr 58px 68px 86px',
              padding: '5px 14px',
              background: 'rgba(0,0,0,0.5)',
              borderBottom: `1px solid ${colors.border.main}`,
            }}>
              {[activeTab === 'buy' ? 'Item' : 'Your Item', 'Type', 'Weight', activeTab === 'buy' ? 'Price' : 'Offer'].map((h, i) => (
                <div key={h} style={{
                  color: colors.text.dim, fontSize: '0.58rem',
                  fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '1px',
                  textAlign: i > 0 ? 'right' : 'left',
                }}>{h}</div>
              ))}
            </div>

            {/* Buy tab content */}
            {activeTab === 'buy' && (
              <>
                {/* Buyback section */}
                {hasBuyback && (
                  <>
                    <div style={{
                      padding: '4px 14px',
                      background: 'rgba(0,204,255,0.07)',
                      borderBottom: '1px solid rgba(0,204,255,0.15)',
                      color: colors.accent, fontSize: '0.58rem',
                      fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '1.5px',
                      display: 'flex', alignItems: 'center', gap: '6px',
                    }}>
                      ↩ Buyback Available
                      <span style={{ color: colors.text.dim, fontWeight: 'normal', letterSpacing: 0 }}>
                        (until next beat)
                      </span>
                    </div>
                    {shopState.buyback_items.map(item => (
                      <ItemRow
                        key={item.id}
                        item={item}
                        isSelected={selectedId === item.id}
                        tab="buy"
                        onClick={() => handleSelectItem(item.id)}
                        isMobile={isMobile}
                      />
                    ))}
                  </>
                )}

                {/* Regular stock */}
                {hasBuyback && (
                  <div style={{
                    padding: '4px 14px',
                    background: 'rgba(0,0,0,0.2)',
                    borderBottom: '1px dashed rgba(255,255,255,0.05)',
                    color: colors.text.dim, fontSize: '0.58rem',
                    fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '1.5px',
                  }}>
                    {npcName}'s Stock
                  </div>
                )}
                {buyItems.length === 0 && (
                  <div style={{
                    color: colors.text.muted, fontSize: '0.8rem',
                    padding: spacing.lg, textAlign: 'center', fontStyle: 'italic',
                  }}>
                    Out of stock.
                  </div>
                )}
                {buyItems.map(item => (
                  <ItemRow
                    key={item.id}
                    item={item}
                    isSelected={selectedId === item.id}
                    tab="buy"
                    onClick={() => handleSelectItem(item.id)}
                    isMobile={isMobile}
                  />
                ))}
              </>
            )}

            {/* Sell tab content */}
            {activeTab === 'sell' && (
              <>
                {/* Merchant gold bar */}
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '6px 14px',
                  background: 'rgba(255,170,0,0.06)',
                  borderBottom: `1px solid rgba(255,170,0,0.2)`,
                  fontSize: '0.7rem',
                }}>
                  <span style={{ color: colors.text.muted }}>
                    {npcName}'s gold:
                  </span>
                  <span style={{
                    color: merchantGold < 50 ? colors.danger : colors.gold,
                    fontWeight: 'bold',
                  }}>
                    {merchantGold} 💰
                  </span>
                  <span style={{ color: colors.text.dim, fontSize: '0.6rem' }}>
                    Max per sale
                  </span>
                </div>

                {sellInventory.length === 0 && (
                  <div style={{
                    color: colors.text.muted, fontSize: '0.8rem',
                    padding: spacing.lg, textAlign: 'center', fontStyle: 'italic',
                  }}>
                    Nothing to sell.
                  </div>
                )}
                {sellInventory.map(item => (
                  <ItemRow
                    key={item.id}
                    item={item}
                    isSelected={selectedId === item.id}
                    tab="sell"
                    onClick={() => handleSelectItem(item.id)}
                    isMobile={isMobile}
                  />
                ))}
              </>
            )}

            {/* Action Row */}
            {selectedItem && (
              <div style={{
                display: 'flex',
                flexDirection: isMobile ? 'column' : 'row',
                alignItems: isMobile ? 'stretch' : 'center',
                justifyContent: 'space-between',
                padding: '10px 14px',
                gap: '10px',
                background: selectedItem.is_buyback
                  ? 'rgba(0,204,255,0.05)'
                  : activeTab === 'sell'
                  ? 'rgba(255,170,0,0.05)'
                  : 'rgba(0,255,136,0.05)',
                borderTop: `1px solid ${
                  selectedItem.is_buyback ? 'rgba(0,204,255,0.2)'
                  : activeTab === 'sell' ? 'rgba(255,170,0,0.2)'
                  : 'rgba(0,255,136,0.2)'
                }`,
              }}>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: '0.72rem', color: colors.text.muted }}>
                    {selectedItem.is_buyback ? 'Buying back:' : activeTab === 'buy' ? 'Selected:' : 'Selling:'}
                    <span style={{ color: colors.text.main, fontWeight: 'bold', marginLeft: '4px' }}>
                      {getItemIcon(selectedItem)} {selectedItem.name}
                    </span>
                  </div>

                  {/* Qty picker for stackable items (not buyback) */}
                  {selectedItem.is_stackable && !selectedItem.is_buyback && maxQty > 1 && (
                    <div style={{ marginTop: '5px', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                      <QtyPicker value={quantity} max={maxQty} onChange={setQuantity} isMobile={isMobile} />
                      <span style={{ fontSize: '0.65rem', color: colors.gold, whiteSpace: 'nowrap' }}>
                        = {activeTab === 'buy' ? buyTotal : sellTotal} 💰
                      </span>
                    </div>
                  )}

                  {/* Sell breakdown */}
                  {activeTab === 'sell' && !selectedItem.is_buyback && (
                    <div style={{ fontSize: '0.6rem', color: colors.text.dim, marginTop: '3px' }}>
                      Value {selectedItem.value} 💰 · Offer {Math.round((shopState?.sell_modifier || 0.5) * 100)}% = {selectedItem.offer} 💰
                    </div>
                  )}

                  {/* Buyback note */}
                  {selectedItem.is_buyback && (
                    <div style={{ fontSize: '0.6rem', color: 'rgba(0,204,255,0.7)', marginTop: '3px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      ⏱ Expires next game beat
                    </div>
                  )}

                  {/* Error reason */}
                  {buyDisabledReason && (
                    <div style={{ fontSize: '0.63rem', color: colors.danger, marginTop: '3px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      ⚠ {buyDisabledReason}
                    </div>
                  )}
                  {merchantCantAfford && (
                    <div style={{ fontSize: '0.63rem', color: colors.danger, marginTop: '3px' }}>
                      ⚠ Merchant has insufficient funds
                    </div>
                  )}
                </div>

                {/* Action button */}
                {selectedItem.is_buyback ? (
                  <ActionButton
                    onClick={handleBuyback}
                    color={colors.accent}
                    label={`Buyback · ${selectedItem.price} 💰`}
                    isMobile={isMobile}
                  />
                ) : activeTab === 'buy' ? (
                  <ActionButton
                    onClick={handleBuy}
                    color={colors.primary}
                    label={quantity > 1 ? `Buy ${quantity} · ${buyTotal} 💰` : `Buy · ${buyTotal} 💰`}
                    disabled={!!buyDisabledReason}
                    isMobile={isMobile}
                  />
                ) : (
                  <ActionButton
                    onClick={handleSell}
                    color={colors.secondary}
                    label={quantity > 1 ? `Sell ${quantity} · +${sellTotal} 💰` : `Sell · +${sellTotal} 💰`}
                    disabled={merchantCantAfford}
                    isMobile={isMobile}
                  />
                )}
              </div>
            )}
          </div>
        )}

      </div>
    </BaseDialog>
  )
}

function ActionButton({ onClick, color, label, disabled, isMobile }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: isMobile ? '12px 20px' : '7px 18px',
        borderRadius: '5px',
        fontFamily: 'monospace',
        fontSize: '0.72rem', fontWeight: 'bold',
        textTransform: 'uppercase', letterSpacing: '1px',
        cursor: disabled ? 'not-allowed' : 'pointer',
        whiteSpace: 'nowrap',
        flexShrink: 0,
        width: isMobile ? '100%' : 'auto',
        background: disabled ? 'rgba(255,68,68,0.08)' : `${color}33`,
        border: `2px solid ${disabled ? 'rgba(255,68,68,0.3)' : color}`,
        color: disabled ? 'rgba(255,68,68,0.45)' : color,
        transition: 'all 0.15s',
      }}
    >
      {label}
    </button>
  )
}
