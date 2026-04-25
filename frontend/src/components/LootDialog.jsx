import { useState, useMemo, useRef, useEffect, useCallback } from 'react'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import GameText from './GameText'
import { colors, spacing, fonts } from '../styles/theme'

const ENCH_COLORS = ['#888888', '#44FF88', '#FFD700']

function enchStars(count) {
  if (!count || count <= 0) return null
  const n = Math.min(count, 2)
  return { stars: '✦'.repeat(n), color: ENCH_COLORS[n] }
}

function ItemTooltip({ item, anchorRef }) {
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const ench = enchStars(item.enchantment_count)

  useEffect(() => {
    if (!anchorRef.current) return
    const rect = anchorRef.current.getBoundingClientRect()
    const tooltipW = 240
    const left = rect.right + 8 + tooltipW > window.innerWidth
      ? rect.left - tooltipW - 8
      : rect.right + 8
    setPos({ top: rect.top, left })
  }, [anchorRef])

  return (
    <div style={{
      position: 'fixed',
      top: pos.top,
      left: pos.left,
      width: 240,
      background: '#0d1a0d',
      border: `2px solid ${colors.secondary}`,
      padding: '10px',
      zIndex: 3000,
      pointerEvents: 'none',
      fontFamily: fonts.main,
      fontSize: '12px',
    }}>
      <div style={{ color: '#FFD700', fontSize: '14px', fontWeight: 'bold', borderBottom: `1px solid #664400`, paddingBottom: 6, marginBottom: 8 }}>
        {item.name}
      </div>
      {ench && (
        <div style={{ color: ench.color, fontSize: '11px', marginBottom: 6 }}>
          {ench.stars} Enchanted
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, background: '#664400', marginBottom: 8 }}>
        {[
          ['Type', item.type || '—'],
          ['Subtype', item.subtype || '—'],
          ['Weight', item.weight != null ? `${item.weight}w` : '—'],
          ['Value', item.value != null ? `${item.value}g` : '—'],
        ].map(([lbl, val]) => (
          <div key={lbl} style={{ background: '#0d0800', padding: '4px 6px', textAlign: 'center' }}>
            <div style={{ color: colors.secondary, fontSize: '10px', textTransform: 'uppercase', marginBottom: 2 }}>{lbl}</div>
            <div style={{ color: '#FFD700', fontSize: '12px' }}>{val}</div>
          </div>
        ))}
      </div>
      {item.description && (
        <div style={{ color: '#ffee99', fontStyle: 'italic', fontSize: '11px', lineHeight: 1.5, borderTop: `1px solid #664400`, paddingTop: 6 }}>
          {item.description}
        </div>
      )}
    </div>
  )
}

function LootRow({ item, selected, onToggle }) {
  const [hovered, setHovered] = useState(false)
  const rowRef = useRef(null)
  const ench = enchStars(item.enchantment_count)

  return (
    <div
      ref={rowRef}
      onClick={onToggle}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'grid',
        gridTemplateColumns: '18px 1fr 44px 36px 52px',
        alignItems: 'center',
        gap: 8,
        padding: '5px 7px',
        border: `1px solid ${selected ? colors.primary : '#111'}`,
        background: selected ? '#001500' : 'transparent',
        opacity: selected ? 1 : 0.45,
        cursor: 'pointer',
        fontFamily: fonts.main,
        fontSize: '12px',
        transition: 'opacity 0.1s',
        position: 'relative',
      }}
    >
      {/* Checkbox */}
      <div style={{
        width: 13, height: 13,
        border: `1px solid ${colors.primary}`,
        background: selected ? colors.primary : 'transparent',
        color: '#0a0a0a',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 9, flexShrink: 0,
      }}>
        {selected ? '✓' : ''}
      </div>
      {/* Name + type tag */}
      <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: colors.primary }}>
        {item.name}
        <span style={{ color: '#333', fontSize: 10, marginLeft: 4 }}>[{item.type || 'Item'}]</span>
      </div>
      {/* Qty */}
      <div style={{ color: colors.secondary, textAlign: 'right' }}>×{item.quantity}</div>
      {/* Enchantment stars */}
      <div style={{ textAlign: 'center', color: ench ? ench.color : 'transparent', fontSize: 11, letterSpacing: -1 }}>
        {ench ? ench.stars : ''}
      </div>
      {/* Weight */}
      <div style={{ color: '#555', textAlign: 'right', fontSize: 11 }}>
        {item.weight != null ? `${(item.weight * item.quantity).toFixed(1)}lb` : '—'}
      </div>

      {hovered && <ItemTooltip item={item} anchorRef={rowRef} />}
    </div>
  )
}

export default function LootDialog({ endState, playerWeight, weightLimit, onCollect, onSkip }) {
  const drops = useMemo(() => endState?.items_dropped || [], [endState])
  const [selected, setSelected] = useState(() => new Set(drops.map((_, i) => i)))
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [toastMsg, setToastMsg] = useState('')

  const baseWeight = playerWeight ?? 0
  const maxWeight = weightLimit ?? 100

  const selectedWeight = useMemo(() => {
    let w = 0
    selected.forEach(i => {
      const item = drops[i]
      if (item?.weight != null) w += item.weight * (item.quantity || 1)
    })
    return Math.round(w * 100) / 100
  }, [selected, drops])

  const totalAfter = baseWeight + selectedWeight
  const basePct = Math.min((baseWeight / maxWeight) * 100, 100)
  const addPct = Math.min((selectedWeight / maxWeight) * 100, 100 - basePct)
  const totalPct = (totalAfter / maxWeight) * 100
  const barAddColor = totalPct >= 100 ? colors.danger : totalPct >= 80 ? colors.secondary : '#FFD700'

  const showToast = useCallback((msg) => {
    setToastMsg(msg)
    setTimeout(() => setToastMsg(''), 3000)
  }, [])

  function toggleItem(i) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  function selectAll(v) {
    setSelected(v ? new Set(drops.map((_, i) => i)) : new Set())
  }

  async function handleCollect() {
    if (totalAfter > maxWeight) {
      showToast('Cannot collect — carry weight would exceed capacity.')
      return
    }
    const names = [...selected].map(i => drops[i].name)
    setIsSubmitting(true)
    try {
      await onCollect(names)
    } finally {
      setIsSubmitting(false)
    }
  }

  const weightColor = totalPct >= 100 ? colors.danger : totalPct >= 80 ? colors.secondary : colors.primary

  return (
    <BaseDialog title="⚔ VICTORY — PHASE 2 OF 2: LOOT" maxWidth="640px" padding="16px" zIndex={2500}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md, fontFamily: fonts.main }}>

        {/* Section header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: `1px solid #003333`, paddingBottom: 4 }}>
          <GameText variant="accent" size="xs" weight="bold" style={{ textTransform: 'uppercase', letterSpacing: '0.2em' }}>
            Spoils of Battle
          </GameText>
          <GameText variant="secondary" size="xs">{drops.length} item{drops.length !== 1 ? 's' : ''} found</GameText>
        </div>

        {/* Column headers */}
        <div style={{
          display: 'grid', gridTemplateColumns: '18px 1fr 44px 36px 52px',
          gap: 8, padding: '0 7px',
          fontSize: 10, color: '#444', fontFamily: fonts.main, textTransform: 'uppercase', letterSpacing: '0.1em',
        }}>
          <span />
          <span>Item</span>
          <span style={{ textAlign: 'right' }}>Qty</span>
          <span style={{ textAlign: 'center' }}>Ench</span>
          <span style={{ textAlign: 'right' }}>Weight</span>
        </div>

        {/* Item rows */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {drops.length > 0
            ? drops.map((item, i) => (
              <LootRow key={`${item.name}-${i}`} item={item} selected={selected.has(i)} onToggle={() => toggleItem(i)} />
            ))
            : <GameText variant="muted" size="xs" style={{ fontStyle: 'italic' }}>No items dropped.</GameText>
          }
        </div>

        {/* Bulk actions */}
        {drops.length > 0 && (
          <div style={{ display: 'flex', gap: spacing.sm }}>
            <GameButton onClick={() => selectAll(true)} variant="secondary" style={{ fontSize: '11px', padding: '4px 10px' }}>Take All</GameButton>
            <GameButton onClick={() => selectAll(false)} variant="secondary" style={{ fontSize: '11px', padding: '4px 10px', color: '#555', borderColor: '#333' }}>Leave All</GameButton>
          </div>
        )}

        {/* Toast */}
        {toastMsg && (
          <div style={{
            background: '#330000', border: `1px solid ${colors.danger}`,
            color: colors.danger, padding: '8px 12px', fontSize: '11px', textAlign: 'center',
            fontFamily: fonts.main,
          }}>
            ⚠ {toastMsg}
          </div>
        )}

        {/* Weight tracker */}
        <div style={{ background: '#0d1a0d', border: `1px solid #003300`, padding: '8px 12px', fontSize: '11px', fontFamily: fonts.main }}>
          {[
            ['Current carry weight:', `${baseWeight.toFixed(1)} / ${maxWeight.toFixed(1)} lb`, colors.primary],
            ['Selected loot adds:', `${selectedWeight.toFixed(1)} lb`, '#FFD700'],
            ['Total after pickup:', `${totalAfter.toFixed(1)} lb`, weightColor],
          ].map(([lbl, val, col]) => (
            <div key={lbl} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
              <span style={{ color: '#555' }}>{lbl}</span>
              <span style={{ color: col }}>{val}</span>
            </div>
          ))}
          {/* Stacked weight bar */}
          <div style={{ height: 4, background: '#002200', marginTop: 4, position: 'relative', overflow: 'hidden' }}>
            <div style={{ position: 'absolute', top: 0, left: 0, height: '100%', width: `${basePct}%`, background: colors.primary, transition: 'width 0.2s' }} />
            <div style={{ position: 'absolute', top: 0, left: `${basePct}%`, height: '100%', width: `${addPct}%`, background: barAddColor, transition: 'width 0.2s, left 0.2s' }} />
          </div>
        </div>

        {/* Collect CTA */}
        <button
          onClick={handleCollect}
          disabled={isSubmitting || selected.size === 0}
          style={{
            width: '100%', border: `2px solid ${colors.secondary}`, background: 'transparent',
            color: selected.size === 0 ? '#333' : colors.secondary,
            borderColor: selected.size === 0 ? '#333' : colors.secondary,
            fontFamily: fonts.main, fontSize: '12px', padding: '10px',
            textTransform: 'uppercase', letterSpacing: '0.12em', cursor: selected.size === 0 ? 'not-allowed' : 'pointer',
          }}
          onMouseEnter={e => { if (selected.size > 0 && !isSubmitting) { e.currentTarget.style.background = colors.secondary; e.currentTarget.style.color = '#0a0a0a' } }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = selected.size === 0 ? '#333' : colors.secondary }}
        >
          {isSubmitting ? 'COLLECTING...' : selected.size === 0 ? 'NOTHING SELECTED' : `COLLECT SELECTED ITEMS (${selected.size} of ${drops.length})  →`}
        </button>

        {/* Skip */}
        <div style={{ textAlign: 'center', fontSize: '11px' }}>
          <span
            onClick={() => !isSubmitting && onSkip()}
            style={{ color: '#444', cursor: 'pointer', textDecoration: 'underline' }}
            onMouseEnter={e => e.currentTarget.style.color = '#777'}
            onMouseLeave={e => e.currentTarget.style.color = '#444'}
          >
            skip — drop all items on tile →
          </span>
        </div>

      </div>
    </BaseDialog>
  )
}
