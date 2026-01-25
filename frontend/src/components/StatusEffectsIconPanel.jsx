import { useState } from 'react'
import { colors } from '../styles/theme'

export default function StatusEffectsIconPanel({ effects = [], vertical = false }) {
    const [hoveredEffect, setHoveredEffect] = useState(null)

    if (!effects || effects.length === 0) return null

    // Helper to determine icon based on effect name/type
    const getEffectIcon = (name) => {
        const n = name.toLowerCase()
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
            case 'buff': return colors.primary
            case 'debuff': return colors.danger
            case 'ailment': return '#ffaa00'
            case 'passive': return colors.text.highlight
            default: return colors.text.highlight
        }
    }

    return (
        <div style={{
            display: 'flex',
            flexDirection: vertical ? 'column' : 'row',
            gap: '4px',
            justifyContent: 'center',
            marginBottom: vertical ? '0' : '8px',
            position: 'relative',
            zIndex: 100
        }}>
            {effects.map((effect, idx) => (
                <div
                    key={`${effect.name}-${idx}`}
                    onMouseEnter={() => setHoveredEffect(effect)}
                    onMouseLeave={() => setHoveredEffect(null)}
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
                        transform: hoveredEffect === effect ? 'scale(1.1)' : 'scale(1)',
                    }}
                >
                    {getEffectIcon(effect.name)}

                    {/* Tooltip */}
                    {hoveredEffect === effect && (
                        <div style={{
                            position: 'absolute',
                            bottom: '100%',
                            left: '50%',
                            transform: 'translateX(-50%)',
                            marginBottom: '8px',
                            backgroundColor: '#1a1a1a',
                            border: `1.5px solid ${getEffectColor(effect.type)}`,
                            borderRadius: '6px',
                            padding: '8px',
                            width: '180px',
                            boxShadow: `0 4px 15px rgba(0, 0, 0, 0.8), 0 0 10px ${getEffectColor(effect.type)}44`,
                            color: '#fff',
                            zIndex: 110,
                            pointerEvents: 'none',
                            textAlign: 'left'
                        }}>
                            <div style={{
                                fontWeight: 'bold',
                                color: getEffectColor(effect.type),
                                fontSize: '12px',
                                marginBottom: '4px',
                                borderBottom: `1px solid ${getEffectColor(effect.type)}44`,
                                paddingBottom: '2px'
                            }}>
                                {effect.name.toUpperCase()}
                            </div>
                            <div style={{ fontSize: '10px', color: '#ccc', lineHeight: '1.4' }}>
                                {effect.description || 'No description available.'}
                            </div>
                            {effect.duration_remaining !== undefined && (
                                <div style={{
                                    fontSize: '9px',
                                    marginTop: '4px',
                                    color: getEffectColor(effect.type),
                                    fontStyle: 'italic',
                                    fontWeight: 'bold'
                                }}>
                                    {effect.duration_remaining} beats remaining
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
