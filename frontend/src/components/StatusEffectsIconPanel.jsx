import { useState } from 'react'
import { colors, spacing, shadows, fonts } from '../styles/theme'
import { displayNameOf } from '../utils/combatMoveStatus'

export default function StatusEffectsIconPanel({ effects = [], vertical = false }) {
    const [hoveredEffectName, setHoveredEffectName] = useState(null)

    if (!effects || effects.length === 0) return null

    // Helper to determine icon based on effect name/type. Coerces because a
    // serializer regression that drops `name` from one effect would otherwise
    // throw mid-render, and with no ErrorBoundary in the app that unmounts the
    // whole SPA — losing the fight over a missing icon.
    const getEffectIcon = (name) => {
        const n = String(name ?? '').toLowerCase()
        if (n.includes('burn') || n.includes('fire')) return '🔥'
        if (n.includes('poison') || n.includes('toxic')) return '🧪'
        if (n.includes('bleed')) return '🩸'
        if (n.includes('stun') || n.includes('daze')) return '💫'
        if (n.includes('blind')) return '🕶️'
        if (n.includes('slow')) return '🐢'
        if (n.includes('haste') || n.includes('quick')) return '👟'
        if (n.includes('regen')) return '💖'
        if (n.includes('shield') || n.includes('protect')) return '🛡️'
        if (n === 'str' || n.includes('strength') || n.includes('might')) return '💪'
        if (n.includes('weak')) return '🥀'
        return '✨' // Default
    }

    const getEffectColor = (type) => {
        switch (type?.toLowerCase()) {
            case 'buff': return colors.success
            case 'debuff': return colors.danger
            case 'ailment': return colors.gold
            case 'passive': return colors.info
            default: return colors.primary
        }
    }

    return (
        <div style={{
            display: 'flex',
            flexDirection: vertical ? 'column' : 'row',
            gap: spacing.xs,
            justifyContent: 'center',
            marginBottom: vertical ? '0' : spacing.sm,
            position: 'relative',
            zIndex: 100
        }}>
            {effects.filter(Boolean).map((effect, idx) => (
                <div
                    key={`${effect.name}-${idx}`}
                    onMouseEnter={() => setHoveredEffectName(effect.name)}
                    onMouseLeave={() => setHoveredEffectName(null)}
                    style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '4px',
                        border: `1px solid ${getEffectColor(effect.type)}`,
                        backgroundColor: 'rgba(0, 0, 0, 0.6)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '14px',
                        cursor: 'help',
                        position: 'relative',
                        boxShadow: `0 0 4px ${getEffectColor(effect.type)}44`,
                        transition: 'all 0.2s ease',
                        transform: hoveredEffectName === effect.name ? 'scale(1.1)' : 'scale(1)',
                    }}
                >
                    {getEffectIcon(effect.name)}

                    {/* Tooltip */}
                    {hoveredEffectName === effect.name && (
                        <div style={{
                            position: 'absolute',
                            bottom: '100%',
                            left: '50%',
                            transform: 'translateX(-50%)',
                            marginBottom: spacing.sm,
                            backgroundColor: colors.bg.panelDeep,
                            border: `1.5px solid ${getEffectColor(effect.type)}`,
                            borderRadius: '6px',
                            padding: spacing.sm,
                            width: '180px',
                            boxShadow: `0 4px 15px rgba(0, 0, 0, 0.8), 0 0 10px ${getEffectColor(effect.type)}44`,
                            color: colors.text.main,
                            zIndex: 110,
                            pointerEvents: 'none',
                            textAlign: 'left',
                            fontFamily: fonts.main,
                        }}>
                            <div style={{
                                fontWeight: 'bold',
                                color: getEffectColor(effect.type),
                                fontSize: '12px',
                                marginBottom: '4px',
                                borderBottom: `1px solid ${getEffectColor(effect.type)}44`,
                                paddingBottom: '2px'
                            }}>
                                {(displayNameOf(effect) ?? 'Unknown').toUpperCase()}
                            </div>
                            <div style={{ fontSize: '10px', color: '#ccc', lineHeight: '1.4' }}>
                                {effect.description || 'No description available.'}
                            </div>
                            {/* StateEffectSerializer.serialize_state emits `beats_left`.
                                `duration_remaining` comes from serialize_state_with_duration,
                                which currently has no callers — accept both so the line
                                renders against the contract the API actually sends.

                                The `> 0` is load-bearing too, not just a tidier
                                truthiness check: permanent/persistent states carry
                                beats_left AND beats_max fixed at 0 (states.py only
                                counts down under `if self.beats_max > 0`), so the
                                previous `!== undefined` rendered a permanent buff as
                                "0 beats remaining". Do not relax this back. */}
                            {(effect.beats_left ?? effect.duration_remaining) > 0 && (
                                <div style={{
                                    fontSize: '9px',
                                    marginTop: '4px',
                                    color: getEffectColor(effect.type),
                                    fontStyle: 'italic',
                                    fontWeight: 'bold'
                                }}>
                                    {effect.beats_left ?? effect.duration_remaining} beats remaining
                                </div>
                            )}
                            {/* Tooltip arrow */}
                            <div style={{
                                position: 'absolute',
                                top: '100%',
                                left: '50%',
                                transform: 'translateX(-50%)',
                                width: '0',
                                height: '0',
                                borderLeft: '6px solid transparent',
                                borderRight: '6px solid transparent',
                                borderTop: `6px solid ${getEffectColor(effect.type)}`,
                            }} />
                        </div>
                    )}
                </div>
            ))}
        </div>
    )
}
