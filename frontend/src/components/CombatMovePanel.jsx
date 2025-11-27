import React from 'react';

const CombatMovePanel = ({ moves, category, onMoveClick, onClose }) => {
    const filteredMoves = moves.filter(move => move.category === category);

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
                    filteredMoves.map((move, index) => (
                        <button
                            key={index}
                            onClick={() => onMoveClick(move)}
                            style={{
                                backgroundColor: 'rgba(255, 255, 255, 0.05)',
                                border: '1px solid #444',
                                borderRadius: '4px',
                                padding: '10px',
                                textAlign: 'left',
                                cursor: 'pointer',
                                transition: 'all 0.2s ease',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '4px',
                            }}
                            onMouseEnter={(e) => {
                                e.currentTarget.style.backgroundColor = 'rgba(255, 170, 0, 0.1)';
                                e.currentTarget.style.borderColor = '#ffaa00';
                            }}
                            onMouseLeave={(e) => {
                                e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                                e.currentTarget.style.borderColor = '#444';
                            }}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                                <span style={{ fontWeight: 'bold', color: '#eee' }}>{move.name}</span>
                                {move.cost && (
                                    <span style={{ fontSize: '10px', color: '#aaa' }}>
                                        {move.cost.stamina > 0 && `Fatigue: ${move.cost.stamina}`}
                                    </span>
                                )}
                            </div>
                            <span style={{ fontSize: '12px', color: '#888' }}>{move.description}</span>
                        </button>
                    ))
                )}
            </div>
        </div>
    );
};

export default CombatMovePanel;
