import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import GameText from './GameText'
import GamePanel from './GamePanel'
import { colors, spacing, fonts, shadows } from '../styles/theme'

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
    if (current < base) return colors.danger
    if (current > base) return colors.success
    return colors.gold
  }

  const resistance = player.resistance || {}
  const statusResistance = player.status_resistance || {}
  const states = player.states || []

  const coreStats = [
    { label: 'HP', val: `${player.hp}/${player.max_hp}`, color: colors.danger, icon: '❤️' },
    { label: 'Fatigue', val: `${player.fatigue}/${player.max_fatigue}`, color: colors.gold, icon: '🔋' },
    { label: 'Protection', val: player.protection || 0, color: colors.info, icon: '🛡️' },
    { label: 'Level', val: player.level || 1, color: '#cc88ff', icon: '⭐' },
    { label: 'Attack', val: `${player.attack_damage_min}-${player.attack_damage_max}`, color: colors.secondary, icon: '⚔️' },
    { label: 'Accuracy', val: `${player.hit_accuracy}%`, color: colors.primary, icon: '🎯' },
    { label: 'Evasion', val: `${player.evasion_chance}%`, color: colors.text.muted, icon: '💨' },
  ]

  return (
    <BaseDialog
      title="📊 CHARACTER STATS"
      onClose={onClose}
      maxWidth="620px"
      padding="16px"
      zIndex={2000}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        {/* Core Stats Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
          gap: spacing.xs,
        }}>
          {coreStats.map((stat, idx) => (
            <GamePanel key={idx} padding="sm" style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '2px',
              borderColor: colors.alpha.secondary[30],
            }}>
              <div style={{ fontSize: '16px' }}>{stat.icon}</div>
              <GameText variant="muted" size="xs" style={{ textTransform: 'uppercase' }}>{stat.label}</GameText>
              <GameText weight="bold" style={{ color: stat.color }}>{stat.val}</GameText>
            </GamePanel>
          ))}
        </div>

        {/* Attributes Section */}
        <GamePanel
          style={{
            backgroundColor: colors.alpha.secondary[10],
            borderColor: colors.alpha.secondary[30],
          }}
        >
          <GameText variant="secondary" size="xs" weight="bold" style={{ marginBottom: spacing.sm, textTransform: 'uppercase', letterSpacing: '1px' }}>
            Core Attributes
          </GameText>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: spacing.xs }}>
            {attributes.map((attr) => {
              const current = player[attr.key] || 10
              const base = player[attr.key + '_base'] || 10
              const color = getAttributeColor(current, base)
              return (
                <div key={attr.key} title={attr.tooltip} style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: `${spacing.xs} ${spacing.sm}`,
                  backgroundColor: 'rgba(0,0,0,0.2)',
                  borderRadius: '8px',
                  fontFamily: fonts.main,
                  cursor: 'help',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: spacing.xs }}>
                    <span style={{ fontSize: '14px' }}>{attr.icon}</span>
                    <GameText size="sm">{attr.name}</GameText>
                  </div>
                  <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column' }}>
                    <GameText weight="bold" style={{ color }}>{current}</GameText>
                    <GameText variant="dim" size="xs">BASE: {base}</GameText>
                  </div>
                </div>
              )
            })}
          </div>
        </GamePanel>

        {/* Resistances & Status Section */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: spacing.md }}>
          {/* Damage Resistances */}
          {Object.entries(resistance).filter(([_, v]) => v !== 1).length > 0 && (
            <GamePanel padding="md" style={{ backgroundColor: colors.alpha.info[10], borderColor: colors.alpha.info[30] }}>
              <GameText variant="info" size="xs" weight="bold" style={{ marginBottom: spacing.sm, textTransform: 'uppercase' }}>
                Resistances & Weaknesses
              </GameText>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: spacing.xs }}>
                {Object.entries(resistance)
                  .filter(([_, value]) => value !== 1)
                  .map(([type, value]) => (
                    <div key={type} style={{
                      padding: '3px 6px',
                      backgroundColor: 'rgba(0,0,0,0.2)',
                      borderRadius: '6px',
                      fontSize: '10px',
                      fontFamily: fonts.main,
                      color: value > 1 ? colors.danger : colors.info,
                    }}>
                      {type.toUpperCase()}: {Math.round(value * 100)}%
                    </div>
                  ))}
              </div>
            </GamePanel>
          )}

          {/* Active Effects */}
          <GamePanel padding="md" style={{ backgroundColor: colors.alpha.danger[10], borderColor: colors.alpha.danger[30] }}>
            <GameText variant="danger" size="xs" weight="bold" style={{ marginBottom: spacing.sm, textTransform: 'uppercase' }}>
              Active Effects
            </GameText>
            <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.xs }}>
              {states.length > 0 ? states.map((state, idx) => (
                <div key={idx} style={{
                  padding: '4px 8px',
                  backgroundColor: 'rgba(255, 0, 0, 0.1)',
                  borderRadius: '6px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}>
                  <GameText size="sm" style={{ color: '#ff9999' }}>{state.name}</GameText>
                  {state.steps_left && <GameText variant="dim" size="xs">{state.steps_left}T</GameText>}
                </div>
              )) : <GameText variant="muted" size="sm" style={{ fontStyle: 'italic' }}>No active status effects</GameText>}
            </div>
          </GamePanel>
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', marginTop: spacing.sm }}>
          <GameButton onClick={onClose} variant="secondary" size="small">
            CLOSE SHEET
          </GameButton>
        </div>
      </div>
    </BaseDialog>
  )
}
