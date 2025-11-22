import { useState, useEffect } from 'react'

export default function InteractPanel({ location, onClose }) {
    const [targets, setTargets] = useState([])
    const [selectedTarget, setSelectedTarget] = useState(null)
    const [interactionOutput, setInteractionOutput] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    useEffect(() => {
        if (location) {
            const npcs = (location.npcs || []).map(n => ({ ...n, type: 'npc' }))
            const objects = (location.objects || []).map(o => ({ ...o, type: 'object' }))

            // Filter out hidden entities if the API sends them
            const allTargets = [...npcs, ...objects].filter(t => !t.hidden)
            setTargets(allTargets)
        }
    }, [location])

    const handleTargetClick = (target) => {
        setSelectedTarget(target)
        setError(null)
    }

    const handleActionClick = async (action) => {
        setLoading(true)
        try {
            const token = localStorage.getItem('authToken')
            const response = await fetch('http://localhost:5000/api/world/interact', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify({
                    target_id: selectedTarget.id,
                    action: action
                })
            })

            const data = await response.json()
            if (response.ok) {
                setInteractionOutput(data.message)
            } else {
                setError(data.error || 'Interaction failed')
            }
        } catch (err) {
            console.error('Interaction error:', err)
            setError('Network error')
        } finally {
            setLoading(false)
        }
    }

    const handleBack = () => {
        setSelectedTarget(null)
        setError(null)
    }

    const closeOutput = () => {
        setInteractionOutput(null)
    }

    return (
        <div style={{
            backgroundColor: 'rgba(50, 20, 0, 0.3)',
            border: '2px solid #ffaa00',
            borderRadius: '6px',
            padding: '8px',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
            position: 'relative', // For absolute positioning of popup if needed, though fixed might be better
            minHeight: '200px',
        }}>
            {/* Header */}
            <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                borderBottom: '2px solid #ffaa00',
                paddingBottom: '4px',
                marginBottom: '2px',
            }}>
                <div style={{
                    color: '#ffff00',
                    fontWeight: 'bold',
                    fontSize: '13px',
                    fontFamily: 'monospace',
                }}>
                    👋 INTERACT
                </div>
                <button
                    onClick={onClose}
                    style={{
                        padding: '2px 6px',
                        backgroundColor: '#cc4400',
                        color: '#ffff00',
                        border: '1px solid #ff6600',
                        borderRadius: '3px',
                        cursor: 'pointer',
                        fontSize: '10px',
                        fontFamily: 'monospace',
                        fontWeight: 'bold',
                    }}
                >
                    ✕
                </button>
            </div>

            {/* Error State */}
            {error && (
                <div style={{
                    color: '#ff6666',
                    fontSize: '10px',
                    fontFamily: 'monospace',
                    padding: '8px',
                    backgroundColor: 'rgba(100, 0, 0, 0.2)',
                    borderRadius: '3px',
                }}>
                    {error}
                </div>
            )}

            {/* Content Area */}
            {!selectedTarget ? (
                // Target List
                <div style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    overflowY: 'auto',
                    maxHeight: '300px',
                }}>
                    {targets.length === 0 ? (
                        <div style={{
                            color: '#666666',
                            fontSize: '11px',
                            fontStyle: 'italic',
                            textAlign: 'center',
                            padding: '8px',
                        }}>
                            Nothing to interact with here.
                        </div>
                    ) : (
                        targets.map((target, idx) => (
                            <button
                                key={idx}
                                onClick={() => handleTargetClick(target)}
                                style={{
                                    padding: '8px',
                                    backgroundColor: 'rgba(100, 50, 0, 0.3)',
                                    border: '1px solid #ff9933',
                                    borderRadius: '3px',
                                    color: '#ffcc88',
                                    fontFamily: 'monospace',
                                    fontSize: '12px',
                                    cursor: 'pointer',
                                    textAlign: 'left',
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                }}
                                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(150, 80, 0, 0.5)'}
                                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'rgba(100, 50, 0, 0.3)'}
                            >
                                <span>{target.name}</span>
                                <span style={{ fontSize: '10px', color: '#aa8855' }}>
                                    {target.type === 'npc' ? 'NPC' : 'OBJ'}
                                </span>
                            </button>
                        ))
                    )}
                </div>
            ) : (
                // Action Selection
                <div style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                }}>
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        borderBottom: '1px solid #664400',
                        paddingBottom: '4px',
                    }}>
                        <button
                            onClick={handleBack}
                            style={{
                                padding: '2px 6px',
                                backgroundColor: 'transparent',
                                color: '#ffcc88',
                                border: '1px solid #ff9933',
                                borderRadius: '3px',
                                cursor: 'pointer',
                                fontSize: '10px',
                                fontFamily: 'monospace',
                            }}
                        >
                            ← Back
                        </button>
                        <span style={{
                            color: '#ffff00',
                            fontWeight: 'bold',
                            fontSize: '12px',
                            fontFamily: 'monospace',
                        }}>
                            {selectedTarget.name}
                        </span>
                    </div>

                    <div style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: '4px',
                    }}>
                        {selectedTarget.keywords && selectedTarget.keywords.length > 0 ? (
                            selectedTarget.keywords.map((keyword, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => handleActionClick(keyword)}
                                    disabled={loading}
                                    style={{
                                        padding: '8px 14px',
                                        backgroundColor: 'rgba(100, 50, 0, 0.3)',
                                        border: '1px solid #ff9933',
                                        borderRadius: '3px',
                                        color: '#ffcc88',
                                        fontFamily: 'monospace',
                                        fontSize: '12px',
                                        cursor: loading ? 'wait' : 'pointer',
                                        textTransform: 'uppercase',
                                        opacity: loading ? 0.7 : 1,
                                    }}
                                    onMouseEnter={(e) => !loading && (e.target.style.backgroundColor = 'rgba(150, 80, 0, 0.5)')}
                                    onMouseLeave={(e) => !loading && (e.target.style.backgroundColor = 'rgba(100, 50, 0, 0.3)')}
                                >
                                    {keyword}
                                </button>
                            ))
                        ) : (
                            <div style={{ color: '#999', fontSize: '11px', fontStyle: 'italic' }}>
                                No obvious actions.
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Output Popup Dialog */}
            {interactionOutput && (
                <div style={{
                    position: 'fixed',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    backgroundColor: 'rgba(20, 10, 5, 0.95)',
                    border: '2px solid #ffaa00',
                    borderRadius: '8px',
                    padding: '16px',
                    zIndex: 2000,
                    maxWidth: '80vw',
                    maxHeight: '80vh',
                    overflowY: 'auto',
                    boxShadow: '0 0 20px rgba(0, 0, 0, 0.8)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                }}>
                    <div style={{
                        color: '#ffcc88',
                        fontFamily: 'monospace',
                        fontSize: '14px',
                        lineHeight: '1.5',
                        whiteSpace: 'pre-wrap', // Preserve newlines
                    }}>
                        {interactionOutput}
                    </div>
                    <button
                        onClick={closeOutput}
                        style={{
                            alignSelf: 'center',
                            padding: '8px 24px',
                            backgroundColor: '#cc4400',
                            color: '#ffff00',
                            border: '1px solid #ff6600',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontFamily: 'monospace',
                            fontWeight: 'bold',
                            marginTop: '8px',
                        }}
                        onMouseEnter={(e) => e.target.style.backgroundColor = '#ff6600'}
                        onMouseLeave={(e) => e.target.style.backgroundColor = '#cc4400'}
                    >
                        Close
                    </button>
                </div>
            )}

            {/* Backdrop for popup */}
            {interactionOutput && (
                <div
                    onClick={closeOutput}
                    style={{
                        position: 'fixed',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        backgroundColor: 'rgba(0, 0, 0, 0.5)',
                        zIndex: 1999,
                    }}
                />
            )}
        </div>
    )
}
