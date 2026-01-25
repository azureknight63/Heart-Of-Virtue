import { useState, useEffect } from 'react'
import { colors } from '../styles/theme'

export default function SuggestedMovesPanel({ suggestions = [], lastOutcome = "", onSuggestClick, isPlayerTurn = false }) {
    const [isVisible, setIsVisible] = useState(false)

    useEffect(() => {
        if (suggestions.length > 0 && isPlayerTurn) {
            const timer = setTimeout(() => setIsVisible(true), 500)
            return () => clearTimeout(timer)
        } else {
            setIsVisible(false)
        }
    }, [suggestions.length, isPlayerTurn])

    if (!isPlayerTurn || suggestions.length === 0) return null

    return (
        <div style={{
            position: 'absolute',
            right: '20px',
            top: '20px',
            width: '280px',
            maxHeight: 'calc(100vh - 40px)',
            backgroundColor: 'rgba(10, 15, 10, 0.9)',
            border: `2px solid ${colors.primary}`,
            borderRadius: '8px',
            boxShadow: `0 0 20px ${colors.primary}44, inset 0 0 10px rgba(0, 0, 0, 0.5)`,
            display: 'flex',
            flexDirection: 'column',
            zIndex: 1000,
            fontFamily: 'monospace',
            opacity: isVisible ? 1 : 0,
            transform: isVisible ? 'translateX(0)' : 'translateX(20px)',
            transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
            overflow: 'hidden'
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

            {/* Outcome Section */}
            {lastOutcome && (
                <div style={{
                    padding: '10px 12px',
                    fontSize: '11px',
                    color: colors.text.muted,
                    borderBottom: '1px solid rgba(0, 255, 136, 0.1)',
                    backgroundColor: 'rgba(0, 255, 136, 0.03)',
                    fontStyle: 'italic'
                }}>
                    <div style={{ color: colors.text.highlight, fontSize: '9px', marginBottom: '2px', opacity: 0.7 }}>ANALYSIS OF PREVIOUS CYCLE:</div>
                    "{lastOutcome}"
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
                {suggestions.map((s, idx) => (
                    <div
                        key={idx}
                        onClick={() => onSuggestClick?.(s)}
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
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)'
                            e.currentTarget.style.borderColor = 'rgba(0, 255, 136, 0.15)'
                            e.currentTarget.style.boxShadow = 'none'
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
                ))}
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
