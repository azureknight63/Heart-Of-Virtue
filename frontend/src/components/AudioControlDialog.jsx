import { useAudio } from '../context/AudioContext'

export default function AudioControlDialog({ onClose }) {
    const {
        musicVolume,
        setMusicVolume,
        sfxVolume,
        setSfxVolume,
        isMusicMuted,
        setIsMusicMuted,
        isSfxMuted,
        setIsSfxMuted
    } = useAudio()

    return (
        <div
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: 'rgba(0, 0, 0, 0.7)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 1000,
            }}
            onClick={onClose}
        >
            <div
                style={{
                    backgroundColor: '#1a1a2e',
                    border: '3px solid #00ff88',
                    borderRadius: '8px',
                    padding: '24px',
                    maxWidth: '400px',
                    width: '90%',
                    boxShadow: '0 0 20px #00ff88',
                    fontFamily: 'monospace',
                }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Title */}
                <div
                    style={{
                        fontSize: '20px',
                        fontWeight: 'bold',
                        color: '#00ff88',
                        marginBottom: '20px',
                        textAlign: 'center',
                        borderBottom: '2px solid #00ff88',
                        paddingBottom: '10px',
                    }}
                >
                    🔊 Audio Settings
                </div>

                {/* Content */}
                <div style={{ marginBottom: '20px' }}>

                    {/* Music Control */}
                    <div style={{ marginBottom: '20px' }}>
                        <div style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            marginBottom: '10px'
                        }}>
                            <div style={{ color: '#00ccff', fontSize: '14px', fontWeight: 'bold' }}>
                                MUSIC
                            </div>
                            <button
                                onClick={() => setIsMusicMuted(!isMusicMuted)}
                                style={{
                                    padding: '4px 8px',
                                    backgroundColor: isMusicMuted ? '#cc0000' : '#00cc66',
                                    color: isMusicMuted ? '#ffff00' : '#000000',
                                    border: '1px solid #000000',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    fontSize: '12px',
                                    fontWeight: 'bold',
                                }}
                            >
                                {isMusicMuted ? 'MUTED' : 'ON'}
                            </button>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span style={{ color: '#00ff88', fontSize: '12px' }}>0%</span>
                            <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.05"
                                value={musicVolume}
                                onChange={(e) => setMusicVolume(parseFloat(e.target.value))}
                                style={{
                                    flex: 1,
                                    accentColor: '#00ff88',
                                    cursor: 'pointer'
                                }}
                                disabled={isMusicMuted}
                            />
                            <span style={{ color: '#00ff88', fontSize: '12px' }}>100%</span>
                        </div>
                        <div style={{ textAlign: 'center', color: '#00ff88', fontSize: '12px', marginTop: '5px' }}>
                            {Math.round(musicVolume * 100)}%
                        </div>
                    </div>

                    {/* SFX Control */}
                    <div style={{ marginBottom: '15px' }}>
                        <div style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            marginBottom: '10px'
                        }}>
                            <div style={{ color: '#00ccff', fontSize: '14px', fontWeight: 'bold' }}>
                                SOUND EFFECTS
                            </div>
                            <button
                                onClick={() => setIsSfxMuted(!isSfxMuted)}
                                style={{
                                    padding: '4px 8px',
                                    backgroundColor: isSfxMuted ? '#cc0000' : '#00cc66',
                                    color: isSfxMuted ? '#ffff00' : '#000000',
                                    border: '1px solid #000000',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    fontSize: '12px',
                                    fontWeight: 'bold',
                                }}
                            >
                                {isSfxMuted ? 'MUTED' : 'ON'}
                            </button>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span style={{ color: '#00ff88', fontSize: '12px' }}>0%</span>
                            <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.05"
                                value={sfxVolume}
                                onChange={(e) => setSfxVolume(parseFloat(e.target.value))}
                                style={{
                                    flex: 1,
                                    accentColor: '#00ff88',
                                    cursor: 'pointer'
                                }}
                                disabled={isSfxMuted}
                            />
                            <span style={{ color: '#00ff88', fontSize: '12px' }}>100%</span>
                        </div>
                        <div style={{ textAlign: 'center', color: '#00ff88', fontSize: '12px', marginTop: '5px' }}>
                            {Math.round(sfxVolume * 100)}%
                        </div>
                    </div>

                </div>

                {/* Buttons */}
                <div
                    style={{
                        display: 'flex',
                        gap: '10px',
                        justifyContent: 'flex-end',
                    }}
                >
                    <button
                        onClick={onClose}
                        style={{
                            padding: '8px 16px',
                            backgroundColor: 'transparent',
                            color: '#00ccff',
                            border: '2px solid #00ccff',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontFamily: 'monospace',
                            fontSize: '14px',
                            fontWeight: 'bold',
                            transition: 'all 0.2s',
                        }}
                        onMouseEnter={(e) => {
                            e.target.style.backgroundColor = 'rgba(0, 204, 255, 0.2)'
                        }}
                        onMouseLeave={(e) => {
                            e.target.style.backgroundColor = 'transparent'
                        }}
                    >
                        Close
                    </button>
                </div>
            </div>
        </div>
    )
}
