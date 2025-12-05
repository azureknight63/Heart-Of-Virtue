import React from 'react';

const CombatCheckDialog = ({ checkData, onClose }) => {
    if (!checkData || checkData.length === 0) {
        return null;
    }

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
        }}>
            <div style={{
                backgroundColor: '#1a1a1a',
                border: '2px solid #ffaa00',
                borderRadius: '8px',
                padding: '24px',
                maxWidth: '600px',
                width: '90%',
                maxHeight: '80vh',
                overflow: 'auto',
                color: '#fff',
                fontFamily: 'monospace',
                boxShadow: '0 0 30px rgba(255, 170, 0, 0.4)',
            }}>
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '20px',
                    borderBottom: '1px solid #444',
                    paddingBottom: '12px',
                }}>
                    <h2 style={{ margin: 0, color: '#ffaa00', textTransform: 'uppercase' }}>
                        Battlefield Status
                    </h2>
                    <button
                        onClick={onClose}
                        style={{
                            background: 'none',
                            border: 'none',
                            color: '#888',
                            cursor: 'pointer',
                            fontSize: '20px',
                            padding: '4px 8px',
                        }}
                    >
                        ✕
                    </button>
                </div>

                <div style={{
                    marginBottom: '16px',
                    color: '#aaa',
                    fontSize: '14px',
                }}>
                    {checkData.length} combatant{checkData.length !== 1 ? 's' : ''} detected (sorted by distance)
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {checkData.map((combatant, index) => (
                        <div
                            key={index}
                            style={{
                                backgroundColor: combatant.is_ally ? 'rgba(0, 200, 100, 0.1)' : 'rgba(200, 0, 0, 0.1)',
                                border: `1px solid ${combatant.is_ally ? '#00c864' : '#c80000'}`,
                                borderRadius: '6px',
                                padding: '12px',
                            }}
                        >
                            <div style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                marginBottom: '8px',
                            }}>
                                <span style={{
                                    fontWeight: 'bold',
                                    fontSize: '16px',
                                    color: combatant.is_ally ? '#00ff88' : '#ff6666',
                                }}>
                                    {combatant.name}
                                </span>
                                <span style={{
                                    fontSize: '12px',
                                    color: '#888',
                                    backgroundColor: 'rgba(0, 0, 0, 0.3)',
                                    padding: '2px 8px',
                                    borderRadius: '4px',
                                }}>
                                    {combatant.is_ally ? 'ALLY' : 'ENEMY'}
                                </span>
                            </div>

                            <div style={{
                                display: 'grid',
                                gridTemplateColumns: '1fr 1fr',
                                gap: '8px',
                                fontSize: '14px',
                            }}>
                                <div>
                                    <span style={{ color: '#888' }}>Distance: </span>
                                    <span style={{ color: '#fff' }}>{combatant.distance} ft</span>
                                </div>

                                {combatant.direction_from_player && (
                                    <div>
                                        <span style={{ color: '#888' }}>Direction: </span>
                                        <span style={{ color: '#fff' }}>{combatant.direction_from_player}</span>
                                    </div>
                                )}

                                {combatant.facing && (
                                    <div>
                                        <span style={{ color: '#888' }}>Facing: </span>
                                        <span style={{ color: '#fff' }}>{combatant.facing}</span>
                                    </div>
                                )}

                                {combatant.current_move && (
                                    <div style={{ gridColumn: '1 / -1' }}>
                                        <span style={{ color: '#888' }}>Current Move: </span>
                                        <span style={{ color: '#ffaa00', fontWeight: 'bold' }}>
                                            {combatant.current_move}
                                        </span>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>

                <div style={{
                    marginTop: '20px',
                    paddingTop: '12px',
                    borderTop: '1px solid #444',
                    textAlign: 'center',
                }}>
                    <button
                        onClick={onClose}
                        style={{
                            backgroundColor: '#ffaa00',
                            border: 'none',
                            borderRadius: '4px',
                            padding: '10px 24px',
                            color: '#000',
                            fontWeight: 'bold',
                            cursor: 'pointer',
                            fontSize: '14px',
                            transition: 'all 0.2s ease',
                        }}
                        onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = '#ffcc00';
                            e.currentTarget.style.transform = 'scale(1.05)';
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = '#ffaa00';
                            e.currentTarget.style.transform = 'scale(1)';
                        }}
                    >
                        Close
                    </button>
                </div>
            </div>
        </div>
    );
};

export default CombatCheckDialog;
