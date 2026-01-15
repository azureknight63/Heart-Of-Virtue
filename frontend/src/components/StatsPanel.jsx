import BaseDialog from './BaseDialog'
import GameButton from './GameButton'

/**
 * StatsPanel - Detailed view of character attributes, resistances, and status effects
 */
export default function StatsPanel({ player, onClose }) {
  if (!player) return null

  const attributes = [
    { name: 'Strength', key: 'strength', icon: '💪', tooltip: 'Increases melee damage and carrying capacity.' },
    { name: 'Finesse', key: 'finesse', icon: '🎯', tooltip: 'Improves accuracy and critical hit chance.' },
    { name: 'Speed', key: 'speed', icon: '⚡', tooltip: 'Determines turn order and evasion chance.' },
    { name: 'Endurance', key: 'endurance', icon: '🛡️', tooltip: 'Increases maximum HP and fatigue.' },
    { name: 'Charisma', key: 'charisma', icon: '🗣️', tooltip: 'Affects dialogue and merchant prices.' },
    { name: 'Intelligence', key: 'intelligence', icon: '🧠', tooltip: 'Enhances magic and skill learning.' },
    { name: 'Faith', key: 'faith', icon: '📿', tooltip: 'Strengthens divine abilities.' },
  ]

  const getAttributeColor = (current, base) => {
    if (current < base) return '#ff6666'
    if (current > base) return '#00ff88'
    return '#ffff00'
  }

  const resistance = player.resistance || {}
  const statusResistance = player.status_resistance || {}
  const states = player.states || []

  const coreStats = [
    { label: 'HP', val: `${player.hp}/${player.max_hp}`, color: '#ff6666', icon: '❤️' },
    { label: 'Fatigue', val: `${player.fatigue}/${player.max_fatigue}`, color: '#ffff00', icon: '🔋' },
    { label: 'Protection', val: player.protection || 0, color: '#00ccff', icon: '🛡️' },
    { label: 'Level', val: player.level || 1, color: '#cc88ff', icon: '⭐' },
    { label: 'Attack', val: `${player.attack_damage_min}-${player.attack_damage_max}`, color: '#ffaa00', icon: '⚔️' },
    { label: 'Accuracy', val: `${player.hit_accuracy}%`, color: '#00ffcc', icon: '🎯' },
    { label: 'Evasion', val: `${player.evasion_chance}%`, color: '#cccccc', icon: '💨' },
  ]

  return (
    <BaseDialog
      title="📊 CHARACTER STATS"
      onClose={onClose}
      maxWidth="600px"
      zIndex={2000}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Core Stats Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: '10px',
        }}>
          {coreStats.map((stat, idx) => (
            <div key={idx} style={{
              backgroundColor: 'rgba(0,0,0,0.3)',
              border: `1px solid ${stat.color}44`,
              borderRadius: '8px',
              padding: '10px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '4px',
              fontFamily: 'monospace',
            }}>
              <div style={{ fontSize: '18px' }}>{stat.icon}</div>
              <div style={{ fontSize: '10px', color: '#888', textTransform: 'uppercase' }}>{stat.label}</div>
              <div style={{ fontSize: '14px', fontWeight: 'bold', color: stat.color }}>{stat.val}</div>
            </div>
          ))}
        </div>

        {/* Attributes Section */}
        <div style={{
          backgroundColor: 'rgba(255, 170, 0, 0.05)',
          border: '1px solid rgba(255, 170, 0, 0.2)',
          borderRadius: '12px',
          padding: '16px',
        }}>
          <div style={{ color: '#ffaa00', fontSize: '12px', fontWeight: 'bold', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>
            Core Attributes
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '10px' }}>
            {attributes.map((attr) => {
              const current = player[attr.key] || 10
              const base = player[attr.key + '_base'] || 10
              const color = getAttributeColor(current, base)
              return (
                <div key={attr.key} title={attr.tooltip} style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '8px 12px',
                  backgroundColor: 'rgba(0,0,0,0.2)',
                  borderRadius: '8px',
                  fontFamily: 'monospace',
                  cursor: 'help',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '16px' }}>{attr.icon}</span>
                    <span style={{ color: '#ccc', fontSize: '13px' }}>{attr.name}</span>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ color, fontWeight: 'bold', fontSize: '15px' }}>{current}</div>
                    <div style={{ color: '#666', fontSize: '9px' }}>BASE: {base}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Resistances & Status Section */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
          {/* Damage Resistances */}
          {Object.keys(resistance).length > 0 && (
            <div style={{ padding: '12px', backgroundColor: 'rgba(0, 204, 255, 0.05)', border: '1px solid rgba(0, 204, 255, 0.2)', borderRadius: '12px' }}>
              <div style={{ color: '#00ccff', fontSize: '11px', fontWeight: 'bold', marginBottom: '10px', textTransform: 'uppercase' }}>
                Resistances
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {Object.entries(resistance).map(([type, value]) => (
                  <div key={type} style={{
                    padding: '4px 8px',
                    backgroundColor: 'rgba(0,0,0,0.2)',
                    borderRadius: '6px',
                    fontSize: '11px',
                    fontFamily: 'monospace',
                    color: value >= 1 ? '#ffff00' : value < 1 ? '#00ccff' : '#ff6666',
                  }}>
                    {type.toUpperCase()}: {Math.round(value * 100)}%
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Active Effects */}
          <div style={{ padding: '12px', backgroundColor: 'rgba(255, 68, 68, 0.05)', border: '1px solid rgba(255, 68, 68, 0.2)', borderRadius: '12px' }}>
            <div style={{ color: '#ff4444', fontSize: '11px', fontWeight: 'bold', marginBottom: '10px', textTransform: 'uppercase' }}>
              Active Effects
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {states.length > 0 ? states.map((state, idx) => (
                <div key={idx} style={{
                  padding: '6px 10px',
                  backgroundColor: 'rgba(255, 0, 0, 0.1)',
                  borderRadius: '6px',
                  fontSize: '12px',
                  color: '#ff9999',
                  display: 'flex',
                  justifyContent: 'space-between',
                }}>
                  <span>{state.name}</span>
                  {state.steps_left && <span style={{ opacity: 0.6, fontSize: '10px' }}>{state.steps_left}T</span>}
                </div>
              )) : <div style={{ color: '#666', fontStyle: 'italic', fontSize: '12px' }}>No active status effects</div>}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', marginTop: '10px' }}>
          <GameButton onClick={onClose} variant="secondary">
            CLOSE SHEET
          </GameButton>
        </div>
      </div>
    </BaseDialog>
  )
}
