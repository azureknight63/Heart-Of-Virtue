import { useState, useEffect } from 'react'
import { colors } from '../styles/theme'

export default function SuggestedMovesPanel({ suggestions = [], suggestionsLoading = false, lastOutcome = "", lastMoveViable = false, onSuggestClick, isPlayerTurn = false, onTargetHover }) {
    const [isVisible, setIsVisible] = useState(false)

    useEffect(() => {
        if (isPlayerTurn) {
            const timer = setTimeout(() => setIsVisible(true), 500)
            return () => clearTimeout(timer)
        } else {
            setIsVisible(false)
        }
    }, [isPlayerTurn])

    if (!isPlayerTurn) return null

    return (
        <div style={{
            width: '100%',
            backgroundColor: 'rgba(10, 15, 10, 0.9)',
            border: `2px solid ${colors.primary}`,
            borderRadius: '8px',
            boxShadow: `0 0 15px ${colors.primary}33, inset 0 0 10px rgba(0, 0, 0, 0.5)`,
            display: 'flex',
            flexDirection: 'column',
            fontFamily: 'monospace',
            opacity: isVisible ? 1 : 0,
            transform: isVisible ? 'translateY(0)' : 'translateY(10px)',
            transition: 'all 0.4s ease-out',
            overflow: 'hidden',
            marginBottom: '14px',
            flexShrink: 0
        }}>
            {/* Header */}
            <div style={{
                padding: '12px',
                backgroundColor: `${colors.primary}22`,
                borderBottom: `1px solid ${colors.primary}44`,
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
            }}>
                <div style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: colors.primary,
                    boxShadow: `0 0 8px ${colors.primary}`,
                    animation: 'blink 1.5s infinite ease-in-out'
                }} />
                <span style={{ color: colors.primary, fontWeight: 'bold', fontSize: '14px', letterSpacing: '1px' }}>
                    TACTICAL ADVISOR
                </span>
            </div>

            <style>
                {`
          @keyframes blink {
            0% { opacity: 0.3; transform: scale(0.8); }
            50% { opacity: 1; transform: scale(1.2); }
            100% { opacity: 0.3; transform: scale(0.8); }
          }
        `}
            </style>

            {/* Outcome Section & Repeat Action */}
            {lastOutcome && (
                <div style={{
                    padding: '10px 12px',
                    fontSize: '11px',
                    color: colors.text.muted,
                    borderBottom: '1px solid rgba(0, 255, 136, 0.1)',
                    backgroundColor: 'rgba(0, 255, 136, 0.03)',
                    fontStyle: 'italic',
                    position: 'relative'
                }}>
                    <div style={{ color: colors.text.highlight, fontSize: '9px', marginBottom: '2px', opacity: 0.7 }}>ANALYSIS OF PREVIOUS CYCLE:</div>
                    <div style={{ marginBottom: '8px' }}>"{lastOutcome}"</div>

                    {lastMoveViable && <button
                        onClick={() => {
                            // Extract move name from outcome if possible, or just look at last move
                            // For now, we rely on the parent to know what the last move was if it wants to repeat
                            if (onTargetHover) onTargetHover(null);
                            onSuggestClick?.({ move_name: 'repeat_last' })
                        }}
                        style={{
                            width: '100%',
                            padding: '6px',
                            backgroundColor: 'rgba(0, 255, 136, 0.1)',
                            border: `1px solid ${colors.primary}`,
                            borderRadius: '4px',
                            color: colors.primary,
                            fontSize: '10px',
                            fontWeight: 'bold',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '6px'
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(0, 255, 136, 0.2)'}
                        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'rgba(0, 255, 136, 0.1)'}
                    >
                        <span>🔄</span> DO IT AGAIN
                    </button>}
                </div>
            )}

            {/* Suggestions List */}
            <div style={{
                padding: '12px',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px'
            }}>
                {suggestionsLoading || suggestions.length === 0 ? (
                    <div style={{
                        padding: '20px 10px',
                        textAlign: 'center',
                        color: colors.text.muted,
                        fontSize: '11px',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: '12px'
                    }}>
                        <div className="animate-spin" style={{
                            width: '20px',
                            height: '20px',
                            border: `2px solid ${colors.primary}22`,
                            borderTop: `2px solid ${colors.primary}`,
                            borderRadius: '50%',
                            animation: 'spin 1s linear infinite'
                        }} />
                        <span>{suggestionsLoading ? 'ANALYZING COMBAT SITUATION...' : 'ANALYZING BATTLEFIELD COORDINATES...'}</span>
                        <style>{`
                            @keyframes spin {
                                from { transform: rotate(0deg); }
                                to { transform: rotate(360deg); }
                            }
                        `}</style>
                    </div>
                ) : (
                    suggestions.map((s, idx) => (
                        <div
                            key={idx}
                            onClick={() => {
                                if (onTargetHover) onTargetHover(null);
                                onSuggestClick?.(s);
                            }}
                            style={{
                                padding: '10px',
                                backgroundColor: 'rgba(255, 255, 255, 0.05)',
                                border: `1px solid rgba(0, 255, 136, 0.15)`,
                                borderRadius: '4px',
                                cursor: 'pointer',
                                transition: 'all 0.2s ease',
                                position: 'relative',
                                overflow: 'hidden'
                            }}
                            onMouseEnter={(e) => {
                                e.currentTarget.style.backgroundColor = 'rgba(0, 255, 136, 0.1)'
                                e.currentTarget.style.borderColor = colors.primary
                                e.currentTarget.style.boxShadow = `0 0 10px ${colors.primary}33`
                                if (s.target_id && onTargetHover) {
                                    onTargetHover(s.target_id);
                                }
                            }}
                            onMouseLeave={(e) => {
                                e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)'
                                e.currentTarget.style.borderColor = 'rgba(0, 255, 136, 0.15)'
                                e.currentTarget.style.boxShadow = 'none'
                                if (onTargetHover) {
                                    onTargetHover(null);
                                }
                            }}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                                <span style={{ color: colors.text.highlight, fontWeight: 'bold', fontSize: '13px' }}>
                                    {s.move_name}
                                </span>
                                <span style={{
                                    color: colors.primary,
                                    fontSize: '10px',
                                    fontWeight: 'bold',
                                    backgroundColor: `${colors.primary}22`,
                                    padding: '2px 6px',
                                    borderRadius: '10px'
                                }}>
                                    {s.score}%
                                </span>
                            </div>

                            <div style={{ fontSize: '11px', color: colors.text.muted, lineHeight: '1.4' }}>
                                {s.reasoning}
                            </div>

                            {/* Selection highlight bar */}
                            <div style={{
                                position: 'absolute',
                                left: 0,
                                top: 0,
                                bottom: 0,
                                width: '3px',
                                backgroundColor: colors.primary,
                                opacity: 0.6
                            }} />
                        </div>
                    ))
                )}
            </div>

            <div style={{
                padding: '10px',
                textAlign: 'center',
                fontSize: '9px',
                color: 'rgba(0, 255, 136, 0.4)',
                borderTop: '1px solid rgba(0, 255, 136, 0.1)'
            }}>
                NEURAL TACTICAL ENGINE ACTIVE
            </div>
        </div>
    )
}
