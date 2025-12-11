import React from 'react';
import { useAudio } from '../context/AudioContext';

const CombatMovePanel = ({ moves, category, onMoveClick, onClose }) => {
    const { playSFX } = useAudio();
    const filteredMoves = moves.filter(move => {
        if (category === 'Miscellaneous') {
            return move.category === 'Miscellaneous' || move.category === 'Utility';
        }
        if (category === 'Special') {
            return move.category === 'Special' || move.category === 'Spiritual' || move.category === 'Supernatural';
        }
        return move.category === category;
    });

    return (
        <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            backgroundColor: 'rgba(0, 0, 0, 0.9)',
            border: '2px solid #ffaa00',
            borderRadius: '8px',
            padding: '16px',
            zIndex: 100,
            minWidth: '300px',
            maxWidth: '400px',
            color: '#fff',
            fontFamily: 'monospace',
            boxShadow: '0 0 20px rgba(255, 170, 0, 0.3)',
        }}>
            <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '16px',
                borderBottom: '1px solid #444',
                paddingBottom: '8px',
            }}>
                <h3 style={{ margin: 0, color: '#ffaa00', textTransform: 'uppercase' }}>{category} MOVES</h3>
                <button
                    onClick={onClose}
                    style={{
                        background: 'none',
                        border: 'none',
                        color: '#888',
                        cursor: 'pointer',
                        fontSize: '16px',
                    }}
                >
                    ✕
                </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {filteredMoves.length === 0 ? (
                    <div style={{ color: '#888', fontStyle: 'italic', textAlign: 'center' }}>No moves available in this category.</div>
                ) : (
                    filteredMoves.map((move, index) => {
                        const isAvailable = move.available !== false;
                        const reason = move.reason || '';

                        return (
                            <button
                                key={index}
                                onClick={() => {
                                    if (isAvailable) {
                                        playSFX('attack');
                                        onMoveClick(move);
                                    }
                                }}
                                disabled={!isAvailable}
                                title={!isAvailable ? reason : ''}
                                style={{
                                    backgroundColor: isAvailable ? 'rgba(255, 255, 255, 0.05)' : 'rgba(100, 100, 100, 0.05)',
                                    border: `1px solid ${isAvailable ? '#444' : '#333'}`,
                                    borderRadius: '4px',
                                    padding: '10px',
                                    textAlign: 'left',
                                    cursor: isAvailable ? 'pointer' : 'not-allowed',
                                    transition: 'all 0.2s ease',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: '4px',
                                    opacity: isAvailable ? 1 : 0.5,
                                }}
                                onMouseEnter={(e) => {
                                    if (isAvailable) {
                                        e.currentTarget.style.backgroundColor = 'rgba(255, 170, 0, 0.1)';
                                        e.currentTarget.style.borderColor = '#ffaa00';
                                    }
                                }}
                                onMouseLeave={(e) => {
                                    if (isAvailable) {
                                        e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                                        e.currentTarget.style.borderColor = '#444';
                                    }
                                }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                                    <span style={{ fontWeight: 'bold', color: isAvailable ? '#eee' : '#666' }}>{move.name}</span>
                                    {move.fatigue_cost > 0 && (
                                        <span style={{ fontSize: '10px', color: '#aaa' }}>
                                            Fatigue: {move.fatigue_cost}
                                        </span>
                                    )}
                                </div>
                                <span style={{ fontSize: '12px', color: isAvailable ? '#888' : '#555' }}>{move.description}</span>
                                {!isAvailable && reason && (
                                    <span style={{ fontSize: '11px', color: '#ff6666', fontStyle: 'italic' }}>
                                        ⚠ {reason}
                                    </span>
                                )}
                            </button>
                        );
                    })
                )}
            </div>
        </div>
    );
};

export default CombatMovePanel;
