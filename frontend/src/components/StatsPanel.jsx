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
      maxWidth="620px"
      padding="16px"
      zIndex={2000}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {/* Core Stats Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
          gap: '8px',
        }}>
          {coreStats.map((stat, idx) => (
            <div key={idx} style={{
              backgroundColor: 'rgba(0,0,0,0.3)',
              border: `1px solid ${stat.color}44`,
              borderRadius: '8px',
              padding: '8px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '2px',
              fontFamily: 'monospace',
            }}>
              <div style={{ fontSize: '16px' }}>{stat.icon}</div>
              <div style={{ fontSize: '9px', color: '#888', textTransform: 'uppercase' }}>{stat.label}</div>
              <div style={{ fontSize: '13px', fontWeight: 'bold', color: stat.color }}>{stat.val}</div>
            </div>
          ))}
        </div>

        {/* Attributes Section */}
        <div style={{
          backgroundColor: 'rgba(255, 170, 0, 0.05)',
          border: '1px solid rgba(255, 170, 0, 0.2)',
          borderRadius: '12px',
          padding: '12px',
        }}>
          <div style={{ color: '#ffaa00', fontSize: '11px', fontWeight: 'bold', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '1px' }}>
            Core Attributes
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '8px' }}>
            {attributes.map((attr) => {
              const current = player[attr.key] || 10
              const base = player[attr.key + '_base'] || 10
              const color = getAttributeColor(current, base)
              return (
                <div key={attr.key} title={attr.tooltip} style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '6px 10px',
                  backgroundColor: 'rgba(0,0,0,0.2)',
                  borderRadius: '8px',
                  fontFamily: 'monospace',
                  cursor: 'help',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '14px' }}>{attr.icon}</span>
                    <span style={{ color: '#ccc', fontSize: '12px' }}>{attr.name}</span>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ color, fontWeight: 'bold', fontSize: '14px' }}>{current}</div>
                    <div style={{ color: '#666', fontSize: '9px' }}>BASE: {base}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Resistances & Status Section */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
          {/* Damage Resistances */}
          {Object.entries(resistance).filter(([_, v]) => v !== 1).length > 0 && (
            <div style={{ padding: '10px', backgroundColor: 'rgba(0, 204, 255, 0.05)', border: '1px solid rgba(0, 204, 255, 0.2)', borderRadius: '12px' }}>
              <div style={{ color: '#00ccff', fontSize: '11px', fontWeight: 'bold', marginBottom: '8px', textTransform: 'uppercase' }}>
                Resistances & Weaknesses
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {Object.entries(resistance)
                  .filter(([_, value]) => value !== 1)
                  .map(([type, value]) => (
                    <div key={type} style={{
                      padding: '3px 6px',
                      backgroundColor: 'rgba(0,0,0,0.2)',
                      borderRadius: '6px',
                      fontSize: '10px',
                      fontFamily: 'monospace',
                      color: value > 1 ? '#ff6666' : '#00ccff',
                    }}>
                      {type.toUpperCase()}: {Math.round(value * 100)}%
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Active Effects */}
          <div style={{ padding: '10px', backgroundColor: 'rgba(255, 68, 68, 0.05)', border: '1px solid rgba(255, 68, 68, 0.2)', borderRadius: '12px' }}>
            <div style={{ color: '#ff4444', fontSize: '11px', fontWeight: 'bold', marginBottom: '8px', textTransform: 'uppercase' }}>
              Active Effects
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {states.length > 0 ? states.map((state, idx) => (
                <div key={idx} style={{
                  padding: '4px 8px',
                  backgroundColor: 'rgba(255, 0, 0, 0.1)',
                  borderRadius: '6px',
                  fontSize: '11px',
                  color: '#ff9999',
                  display: 'flex',
                  justifyContent: 'space-between',
                }}>
                  <span>{state.name}</span>
                  {state.steps_left && <span style={{ opacity: 0.6, fontSize: '10px' }}>{state.steps_left}T</span>}
                </div>
              )) : <div style={{ color: '#666', fontStyle: 'italic', fontSize: '11px' }}>No active status effects</div>}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', marginTop: '4px' }}>
          <GameButton onClick={onClose} variant="secondary" style={{ padding: '8px 20px', fontSize: '12px' }}>
            CLOSE SHEET
          </GameButton>
        </div>
      </div>
    </BaseDialog>
  )
}
