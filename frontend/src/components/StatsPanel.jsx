export default function StatsPanel({ player, onClose }) {
  if (!player) return null

  const attributes = [
    {
      name: 'Strength',
      key: 'strength',
      tooltip: 'Increases melee damage and carrying capacity. Affects ability to use heavy weapons and armor.'
    },
    {
      name: 'Finesse',
      key: 'finesse',
      tooltip: 'Improves accuracy with ranged weapons and critical hit chance. Affects dexterity-based skills.'
    },
    {
      name: 'Speed',
      key: 'speed',
      tooltip: 'Determines turn order in combat and evasion chance. Affects movement and reaction time.'
    },
    {
      name: 'Endurance',
      key: 'endurance',
      tooltip: 'Increases maximum HP and fatigue. Improves stamina regeneration and resistance to exhaustion.'
    },
    {
      name: 'Charisma',
      key: 'charisma',
      tooltip: 'Affects dialogue options, merchant prices, and companion loyalty. Improves persuasion attempts.'
    },
    {
      name: 'Intelligence',
      key: 'intelligence',
      tooltip: 'Enhances magic effectiveness and skill learning speed. Unlocks advanced dialogue options.'
    },
    {
      name: 'Faith',
      key: 'faith',
      tooltip: 'Strengthens divine magic and holy abilities. Affects interactions with religious entities.'
    },
  ]

  const getAttributeColor = (current, base) => {
    if (current < base) return '#ff6666'
    if (current > base) return '#00ff88'
    return '#ffff00'
  }

  const resistance = player.resistance || {}
  const statusResistance = player.status_resistance || {}
  const states = player.states || []

  // Tooltips for core stats
  const coreStatTooltips = {
    hp: 'Health Points - When this reaches 0, you die. Restore with rest or healing items.',
    fatigue: 'Energy for special abilities and actions. Regenerates over time or with rest.',
    protection: 'Reduces incoming physical damage. Provided by armor and defensive buffs.',
    level: 'Your current character level. Gain experience to level up and become stronger.',
    weight: 'Current carried weight vs. maximum capacity. Exceeding capacity slows movement.',
    attack: 'Estimated damage range for a basic attack against a neutral target.',
    accuracy: 'Base chance to hit an enemy before their evasion is considered.',
    evasion: 'Chance to avoid incoming attacks. Subtracts from the attacker\'s accuracy.'
  }

  return (
    <div style={{
      backgroundColor: 'rgba(50, 20, 0, 0.4)',
      border: '2px solid #ffaa00',
      borderRadius: '6px',
      padding: '12px',
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      maxHeight: '70vh',
      overflowY: 'auto',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '2px solid #ffaa00',
        paddingBottom: '6px',
        marginBottom: '4px',
      }}>
        <div style={{
          color: '#ffff00',
          fontWeight: 'bold',
          fontSize: '16px',
          fontFamily: 'monospace',
        }}>
          ⚔️ STATS
        </div>
        <button
          onClick={onClose}
          style={{
            padding: '4px 10px',
            backgroundColor: '#cc4400',
            color: '#ffff00',
            border: '1px solid #ff6600',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '12px',
            fontFamily: 'monospace',
            fontWeight: 'bold',
          }}
          onMouseEnter={(e) => {
            e.target.style.backgroundColor = '#ff6600'
          }}
          onMouseLeave={(e) => {
            e.target.style.backgroundColor = '#cc4400'
          }}
        >
          ✕
        </button>
      </div>

      {/* Core Stats - Button-like Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '12px',
        fontFamily: 'monospace',
      }}>
        {/* HP */}
        <div
          title={coreStatTooltips.hp}
          style={{
            backgroundColor: 'rgba(80, 20, 20, 0.4)',
            border: '1px solid #884444',
            borderRadius: '4px',
            padding: '8px 10px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'help',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(100, 30, 30, 0.6)'
            e.currentTarget.style.borderColor = '#aa6666'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(80, 20, 20, 0.4)'
            e.currentTarget.style.borderColor = '#884444'
          }}
        >
          <span style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '12px' }}>HP:</span>
          <span style={{ color: '#ff6666', fontSize: '14px', fontWeight: 'bold' }}>
            {player.hp || 0}/{player.max_hp || 100}
          </span>
        </div>

        {/* Fatigue */}
        <div
          title={coreStatTooltips.fatigue}
          style={{
            backgroundColor: 'rgba(80, 80, 20, 0.4)',
            border: '1px solid #888844',
            borderRadius: '4px',
            padding: '8px 10px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'help',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(100, 100, 30, 0.6)'
            e.currentTarget.style.borderColor = '#aaaa66'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(80, 80, 20, 0.4)'
            e.currentTarget.style.borderColor = '#888844'
          }}
        >
          <span style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '12px' }}>Fatigue:</span>
          <span style={{ color: '#ffff00', fontSize: '14px', fontWeight: 'bold' }}>
            {player.fatigue || 0}/{player.max_fatigue || 100}
          </span>
        </div>

        {/* Protection */}
        <div
          title={coreStatTooltips.protection}
          style={{
            backgroundColor: 'rgba(20, 60, 80, 0.4)',
            border: '1px solid #446688',
            borderRadius: '4px',
            padding: '8px 10px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'help',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(30, 80, 100, 0.6)'
            e.currentTarget.style.borderColor = '#6688aa'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(20, 60, 80, 0.4)'
            e.currentTarget.style.borderColor = '#446688'
          }}
        >
          <span style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '12px' }}>Protection:</span>
          <span style={{
            color: (player.protection || 0) > 0 ? '#00ff88' : (player.protection || 0) < 0 ? '#ff6666' : '#ffff00',
            fontSize: '14px',
            fontWeight: 'bold'
          }}>
            {player.protection || 0}
          </span>
        </div>

        {/* Level */}
        <div
          title={coreStatTooltips.level}
          style={{
            backgroundColor: 'rgba(60, 20, 80, 0.4)',
            border: '1px solid #664488',
            borderRadius: '4px',
            padding: '8px 10px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'help',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(80, 30, 100, 0.6)'
            e.currentTarget.style.borderColor = '#8866aa'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(60, 20, 80, 0.4)'
            e.currentTarget.style.borderColor = '#664488'
          }}
        >
          <span style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '12px' }}>Level:</span>
          <span style={{ color: '#ffff00', fontSize: '14px', fontWeight: 'bold' }}>
            {player.level || 1}
          </span>
        </div>

        {/* Attack Damage */}
        <div
          title={coreStatTooltips.attack}
          style={{
            backgroundColor: 'rgba(80, 40, 20, 0.4)',
            border: '1px solid #886644',
            borderRadius: '4px',
            padding: '8px 10px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'help',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(100, 60, 30, 0.6)'
            e.currentTarget.style.borderColor = '#aa8866'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(80, 40, 20, 0.4)'
            e.currentTarget.style.borderColor = '#886644'
          }}
        >
          <span style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '12px' }}>Attack:</span>
          <span style={{ color: '#ffcc66', fontSize: '14px', fontWeight: 'bold' }}>
            {player.attack_damage_min || 0}-{player.attack_damage_max || 0}
          </span>
        </div>

        {/* Accuracy */}
        <div
          title={coreStatTooltips.accuracy}
          style={{
            backgroundColor: 'rgba(20, 80, 60, 0.4)',
            border: '1px solid #448866',
            borderRadius: '4px',
            padding: '8px 10px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'help',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(30, 100, 80, 0.6)'
            e.currentTarget.style.borderColor = '#66aa88'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(20, 80, 60, 0.4)'
            e.currentTarget.style.borderColor = '#448866'
          }}
        >
          <span style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '12px' }}>Accuracy:</span>
          <span style={{ color: '#66ffcc', fontSize: '14px', fontWeight: 'bold' }}>
            {player.hit_accuracy || 0}%
          </span>
        </div>

        {/* Evasion */}
        <div
          title={coreStatTooltips.evasion}
          style={{
            backgroundColor: 'rgba(60, 60, 60, 0.4)',
            border: '1px solid #888888',
            borderRadius: '4px',
            padding: '8px 10px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'help',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(80, 80, 80, 0.6)'
            e.currentTarget.style.borderColor = '#aaaaaa'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(60, 60, 60, 0.4)'
            e.currentTarget.style.borderColor = '#888888'
          }}
        >
          <span style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '12px' }}>Evasion:</span>
          <span style={{ color: '#cccccc', fontSize: '14px', fontWeight: 'bold' }}>
            {player.evasion_chance || 0}%
          </span>
        </div>

        {/* Weight - centered, same width as others */}
        <div
          title={coreStatTooltips.weight}
          style={{
            gridColumn: '1 / -1',
            backgroundColor: 'rgba(40, 60, 40, 0.4)',
            border: '1px solid #668866',
            borderRadius: '4px',
            padding: '8px 10px',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: '12px',
            cursor: 'help',
            transition: 'all 0.2s',
            width: '50%',
            margin: '0 auto',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(60, 80, 60, 0.6)'
            e.currentTarget.style.borderColor = '#88aa88'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(40, 60, 40, 0.4)'
            e.currentTarget.style.borderColor = '#668866'
          }}
        >
          <span style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '12px' }}>Weight:</span>
          <span style={{ color: '#ffff00', fontSize: '14px', fontWeight: 'bold' }}>
            {player.weight_current || 0}/{player.carrying_capacity || 100}
          </span>
        </div>
      </div>

      {/* Attributes */}
      <div style={{
        backgroundColor: 'rgba(30, 15, 0, 0.3)',
        border: '1px solid #664400',
        borderRadius: '4px',
        padding: '10px',
      }}>
        <div style={{
          color: '#ffcc00',
          fontWeight: 'bold',
          fontSize: '12px',
          marginBottom: '8px',
          borderBottom: '1px solid #664400',
          paddingBottom: '4px',
        }}>
          Attributes
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
          {attributes.map((attr) => {
            const current = player[attr.key] || 10
            const base = player[attr.key + '_base'] || 10
            const color = getAttributeColor(current, base)
            return (
              <div
                key={attr.key}
                title={attr.tooltip}
                style={{
                  backgroundColor: 'rgba(0, 30, 50, 0.3)',
                  border: '1px solid #334466',
                  borderRadius: '3px',
                  padding: '6px 8px',
                  fontFamily: 'monospace',
                  cursor: 'help',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(0, 40, 70, 0.5)'
                  e.currentTarget.style.borderColor = '#4466aa'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(0, 30, 50, 0.3)'
                  e.currentTarget.style.borderColor = '#334466'
                }}
              >
                <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '11px', marginBottom: '2px' }}>
                  {attr.name}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ color, fontSize: '14px', fontWeight: 'bold' }}>{current}</span>
                  <span style={{ color: '#999999', fontSize: '10px' }}>(base: {base})</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Damage Resistances */}
      {Object.keys(resistance).length > 0 && (
        <div style={{
          backgroundColor: 'rgba(30, 15, 0, 0.3)',
          border: '1px solid #664400',
          borderRadius: '4px',
          padding: '10px',
        }}>
          <div style={{
            color: '#ffcc00',
            fontWeight: 'bold',
            fontSize: '12px',
            marginBottom: '8px',
            borderBottom: '1px solid #664400',
            paddingBottom: '4px',
          }}>
            Damage Resistance
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(90px, 1fr))', gap: '6px' }}>
            {Object.entries(resistance).map(([type, value]) => {
              const percentage = Math.round(value * 100)
              let color = '#ffff00'
              if (percentage === 100) color = '#ffff00'
              else if (percentage < 100) color = '#0088ff'
              else color = '#ff6666'

              const resistTooltips = {
                physical: 'Reduces damage from physical attacks like swords, arrows, and blunt weapons.',
                fire: 'Reduces damage from fire-based attacks and environmental fire hazards.',
                ice: 'Reduces damage from ice and cold-based attacks. May prevent freezing.',
                lightning: 'Reduces damage from electrical attacks and lightning strikes.',
                poison: 'Reduces damage from poison effects and toxic environments.',
                holy: 'Reduces damage from holy and divine magic attacks.',
                dark: 'Reduces damage from dark magic and shadow-based attacks.'
              }

              return (
                <div
                  key={type}
                  title={resistTooltips[type] || `Reduces ${type} damage taken.`}
                  style={{
                    fontFamily: 'monospace',
                    textAlign: 'center',
                    backgroundColor: 'rgba(0, 0, 0, 0.2)',
                    padding: '6px',
                    borderRadius: '3px',
                    border: '1px solid #334466',
                    cursor: 'help',
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(20, 20, 40, 0.4)'
                    e.currentTarget.style.borderColor = '#4466aa'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(0, 0, 0, 0.2)'
                    e.currentTarget.style.borderColor = '#334466'
                  }}
                >
                  <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '10px', marginBottom: '2px' }}>
                    {type.charAt(0).toUpperCase() + type.slice(1)}
                  </div>
                  <div style={{ color, fontSize: '13px', fontWeight: 'bold' }}>{percentage}%</div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Status Resistances */}
      {Object.keys(statusResistance).length > 0 && (
        <div style={{
          backgroundColor: 'rgba(30, 15, 0, 0.3)',
          border: '1px solid #664400',
          borderRadius: '4px',
          padding: '10px',
        }}>
          <div style={{
            color: '#ffcc00',
            fontWeight: 'bold',
            fontSize: '12px',
            marginBottom: '8px',
            borderBottom: '1px solid #664400',
            paddingBottom: '4px',
          }}>
            Status Resistance
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(90px, 1fr))', gap: '6px' }}>
            {Object.entries(statusResistance).map(([type, value]) => {
              const percentage = Math.round(value * 100)
              let color = '#ffff00'
              if (percentage === 100) color = '#ffff00'
              else if (percentage < 100) color = '#0088ff'
              else color = '#ff6666'

              const statusTooltips = {
                poison: 'Chance to resist being poisoned. Poison deals damage over time.',
                paralysis: 'Chance to resist paralysis. Paralyzed characters cannot act.',
                sleep: 'Chance to resist sleep effects. Sleeping characters are vulnerable.',
                confusion: 'Chance to resist confusion. Confused characters act randomly.',
                blind: 'Chance to resist blindness. Blind characters have reduced accuracy.',
                silence: 'Chance to resist silence. Silenced characters cannot cast spells.',
                stun: 'Chance to resist being stunned. Stunned characters skip their turn.'
              }

              return (
                <div
                  key={type}
                  title={statusTooltips[type] || `Chance to resist ${type} status effects.`}
                  style={{
                    fontFamily: 'monospace',
                    textAlign: 'center',
                    backgroundColor: 'rgba(0, 0, 0, 0.2)',
                    padding: '6px',
                    borderRadius: '3px',
                    border: '1px solid #334466',
                    cursor: 'help',
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(20, 20, 40, 0.4)'
                    e.currentTarget.style.borderColor = '#4466aa'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(0, 0, 0, 0.2)'
                    e.currentTarget.style.borderColor = '#334466'
                  }}
                >
                  <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '10px', marginBottom: '2px' }}>
                    {type.charAt(0).toUpperCase() + type.slice(1)}
                  </div>
                  <div style={{ color, fontSize: '13px', fontWeight: 'bold' }}>{percentage}%</div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Status Effects */}
      {states.length > 0 && (
        <div style={{
          backgroundColor: 'rgba(30, 15, 0, 0.3)',
          border: '1px solid #664400',
          borderRadius: '4px',
          padding: '10px',
        }}>
          <div style={{
            color: '#ffcc00',
            fontWeight: 'bold',
            fontSize: '12px',
            marginBottom: '8px',
            borderBottom: '1px solid #664400',
            paddingBottom: '4px',
          }}>
            Active Effects
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {states.map((state, idx) => (
              <div
                key={idx}
                title={state.description || `Active status effect: ${state.name}`}
                style={{
                  fontSize: '12px',
                  fontFamily: 'monospace',
                  color: '#ff9999',
                  backgroundColor: 'rgba(100, 0, 0, 0.2)',
                  padding: '4px 6px',
                  borderRadius: '3px',
                  border: '1px solid #663333',
                  cursor: 'help',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(120, 20, 20, 0.4)'
                  e.currentTarget.style.borderColor = '#884444'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(100, 0, 0, 0.2)'
                  e.currentTarget.style.borderColor = '#663333'
                }}
              >
                {state.name}
                {state.steps_left && (
                  <span style={{ color: '#999999', marginLeft: '4px', fontSize: '11px' }}>
                    ({state.steps_left} turns)
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
