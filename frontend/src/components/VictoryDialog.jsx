import { useMemo, useState } from 'react'

export default function VictoryDialog({ endState, onClose, onAllocatePoints }) {
  const [selectedAttr, setSelectedAttr] = useState('strength_base')
  const [amount, setAmount] = useState('1')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const remainingPoints = Number(endState?.attribute_points_available || 0)

  const attrOptions = useMemo(() => {
    return [
      { key: 'strength_base', label: 'Strength', value: endState?.attributes?.strength_base },
      { key: 'finesse_base', label: 'Finesse', value: endState?.attributes?.finesse_base },
      { key: 'speed_base', label: 'Speed', value: endState?.attributes?.speed_base },
      { key: 'endurance_base', label: 'Endurance', value: endState?.attributes?.endurance_base },
      { key: 'charisma_base', label: 'Charisma', value: endState?.attributes?.charisma_base },
      { key: 'intelligence_base', label: 'Intelligence', value: endState?.attributes?.intelligence_base },
    ]
  }, [endState])

  const expEntries = useMemo(() => {
    const exp = endState?.exp_gained || {}
    return Object.keys(exp)
      .sort((a, b) => a.localeCompare(b))
      .map((k) => ({ category: k, amount: exp[k] }))
  }, [endState])

  const drops = useMemo(() => endState?.items_dropped || [], [endState])
  const levelUps = useMemo(() => endState?.level_ups || [], [endState])

  const canClose = remainingPoints <= 0

  const handleAllocate = async () => {
    setError('')

    const amt = parseInt(amount, 10)
    if (Number.isNaN(amt) || amt <= 0) {
      setError('Enter a valid point amount.')
      return
    }
    if (amt > remainingPoints) {
      setError('Not enough points available.')
      return
    }

    try {
      setIsSubmitting(true)
      const result = await onAllocatePoints(selectedAttr, amt)
      // Update local endState-like values via parent refresh; parent should pass a new endState next render.
      if (!result?.success) {
        setError(result?.error || 'Failed to allocate points.')
      }
    } catch (e) {
      setError(e?.message || 'Failed to allocate points.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.85)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 2500,
      }}
    >
      <div
        style={{
          backgroundColor: 'rgba(10, 20, 10, 0.98)',
          border: '3px solid #00cc66',
          borderRadius: '12px',
          padding: '24px',
          width: '90%',
          maxWidth: '720px',
          maxHeight: '80vh',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
          boxShadow: '0 0 30px rgba(0, 204, 102, 0.6), inset 0 0 20px rgba(0, 0, 0, 0.8)',
          overflowY: 'auto',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '2px solid #00cc66',
            paddingBottom: '12px',
          }}
        >
          <div
            style={{
              color: '#00ff88',
              fontWeight: 'bold',
              fontSize: '18px',
              fontFamily: 'monospace',
              textShadow: '0 0 8px rgba(0, 255, 136, 0.8)',
            }}
          >
            {endState?.message || 'Victory!'}
          </div>
          <button
            onClick={onClose}
            disabled={!canClose}
            style={{
              padding: '6px 12px',
              backgroundColor: canClose ? '#004422' : '#222222',
              color: canClose ? '#00ff88' : '#888888',
              border: '1px solid #00cc66',
              borderRadius: '6px',
              cursor: canClose ? 'pointer' : 'not-allowed',
              fontFamily: 'monospace',
              fontWeight: 'bold',
            }}
            title={canClose ? 'Close' : 'Spend all points before closing'}
          >
            CLOSE
          </button>
        </div>

        {/* EXP gained */}
        <div style={{ border: '1px solid #00cc66', borderRadius: '10px', padding: '12px' }}>
          <div style={{ color: '#00ff88', fontFamily: 'monospace', fontWeight: 'bold', marginBottom: '8px' }}>
            EXP gained
          </div>
          {expEntries.length === 0 ? (
            <div style={{ color: '#cccccc', fontFamily: 'monospace' }}>None</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {expEntries.map((e) => (
                <div key={e.category} style={{ color: '#e6ffe6', fontFamily: 'monospace' }}>
                  {e.category}: <span style={{ color: '#00ff88' }}>{e.amount}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Drops */}
        <div style={{ border: '1px solid #00cc66', borderRadius: '10px', padding: '12px' }}>
          <div style={{ color: '#00ff88', fontFamily: 'monospace', fontWeight: 'bold', marginBottom: '8px' }}>
            Items dropped
          </div>
          {drops.length === 0 ? (
            <div style={{ color: '#cccccc', fontFamily: 'monospace' }}>None</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {drops.map((d, idx) => (
                <div key={`${d.name}-${idx}`} style={{ color: '#e6ffe6', fontFamily: 'monospace' }}>
                  {d.name} x <span style={{ color: '#00ff88' }}>{d.quantity}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Level up + point spending */}
        {levelUps.length > 0 && (
          <div style={{ border: '1px solid #00cc66', borderRadius: '10px', padding: '12px' }}>
            <div style={{ color: '#00ff88', fontFamily: 'monospace', fontWeight: 'bold', marginBottom: '8px' }}>
              Level up
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {levelUps.map((lu, idx) => (
                <div key={idx} style={{ color: '#e6ffe6', fontFamily: 'monospace' }}>
                  Level {lu.old_level} → <span style={{ color: '#00ff88' }}>{lu.new_level}</span> (points awarded: {lu.points_awarded})
                </div>
              ))}
            </div>

            <div style={{ marginTop: '12px', color: '#e6ffe6', fontFamily: 'monospace' }}>
              Points to distribute: <span style={{ color: '#00ff88' }}>{remainingPoints}</span>
            </div>

            <div style={{ marginTop: '10px', display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <select
                value={selectedAttr}
                onChange={(e) => setSelectedAttr(e.target.value)}
                style={{
                  padding: '8px',
                  backgroundColor: '#002211',
                  color: '#00ff88',
                  border: '1px solid #00cc66',
                  borderRadius: '6px',
                  fontFamily: 'monospace',
                }}
              >
                {attrOptions.map((o) => (
                  <option key={o.key} value={o.key}>
                    {o.label}{typeof o.value === 'number' ? ` (${o.value})` : ''}
                  </option>
                ))}
              </select>

              <input
                type="number"
                min="1"
                max={Math.max(1, remainingPoints)}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                style={{
                  width: '120px',
                  padding: '8px',
                  backgroundColor: '#002211',
                  color: '#00ff88',
                  border: '1px solid #00cc66',
                  borderRadius: '6px',
                  fontFamily: 'monospace',
                }}
              />

              <button
                onClick={handleAllocate}
                disabled={isSubmitting || remainingPoints <= 0}
                style={{
                  padding: '8px 12px',
                  backgroundColor: remainingPoints > 0 ? '#00cc66' : '#222222',
                  color: '#000000',
                  border: '1px solid #000000',
                  borderRadius: '6px',
                  cursor: remainingPoints > 0 ? 'pointer' : 'not-allowed',
                  fontFamily: 'monospace',
                  fontWeight: 'bold',
                }}
              >
                {isSubmitting ? 'ALLOCATING...' : 'ALLOCATE'}
              </button>
            </div>

            {error && (
              <div style={{ marginTop: '10px', color: '#ff6666', fontFamily: 'monospace' }}>{error}</div>
            )}

            {!canClose && (
              <div style={{ marginTop: '8px', color: '#cccccc', fontFamily: 'monospace' }}>
                Spend all points to continue.
              </div>
            )}
          </div>
        )}

        {/* No level-up but still has points */}
        {levelUps.length === 0 && remainingPoints > 0 && (
          <div style={{ border: '1px solid #00cc66', borderRadius: '10px', padding: '12px' }}>
            <div style={{ color: '#00ff88', fontFamily: 'monospace', fontWeight: 'bold', marginBottom: '8px' }}>
              Attribute points
            </div>
            <div style={{ color: '#e6ffe6', fontFamily: 'monospace' }}>
              Points to distribute: <span style={{ color: '#00ff88' }}>{remainingPoints}</span>
            </div>
            <div style={{ marginTop: '8px', color: '#cccccc', fontFamily: 'monospace' }}>
              Spend all points to continue.
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
