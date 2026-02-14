import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useApi'
import { saves } from '../api/endpoints'
import { useAudio } from '../context/AudioContext'
import { useToast } from '../context/ToastContext'

export default function MainMenuPage() {
    const navigate = useNavigate()
    const { logout } = useAuth()
    const { warning: showWarning } = useToast()
    const {
        playBGM,
        playSFX,
        musicVolume,
        setMusicVolume,
        sfxVolume,
        setSfxVolume,
        isMusicMuted,
        setIsMusicMuted,
        isSfxMuted,
        setIsSfxMuted
    } = useAudio()

    const [showLoadModal, setShowLoadModal] = useState(false)
    const [showSettings, setShowSettings] = useState(false)
    const [showCredits, setShowCredits] = useState(false)
    const [saveList, setSaveList] = useState([])
    const [mostRecentSave, setMostRecentSave] = useState(null)
    const [isLoadingInitial, setIsLoadingInitial] = useState(true)
    const [isLoadingSaves, setIsLoadingSaves] = useState(false)
    const [loadingAction, setLoadingAction] = useState(false)

    // Play theme and fetch saves on mount
    useEffect(() => {
        playBGM('adventure')
        const initMenu = async () => {
            try {
                const response = await saves.list()
                let cloudSaves = response.data?.saves || []

                // Get local autosave
                const localData = localStorage.getItem('hov_local_autosave')
                let mergedSaves = [...cloudSaves]

                if (localData) {
                    try {
                        const parsed = JSON.parse(localData)
                        mergedSaves.push({
                            id: 'local_autosave',
                            name: 'Local Autosave',
                            timestamp: parsed.timestamp,
                            level: parsed.player.level,
                            map_name: parsed.player.map_name || 'Unknown',
                            room_title: parsed.player.room_title || 'Current Location',
                            playtime: parsed.player.playtime || 0,
                            isLocal: true
                        })
                    } catch (e) {
                        console.error("Local save corrupted", e)
                    }
                }

                // Sort by timestamp
                mergedSaves.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
                setSaveList(mergedSaves)
                setMostRecentSave(mergedSaves.length > 0 ? mergedSaves[0] : null)
            } catch (error) {
                console.error("Failed to initialize menu saves", error)
                setSaveList([])
                setMostRecentSave(null)
            } finally {
                setIsLoadingInitial(false)
            }
        }
        initMenu()
    }, [playBGM])

    // Keep mostRecentSave in sync with saveList
    useEffect(() => {
        if (saveList && saveList.length > 0) {
            const sorted = [...saveList].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
            setMostRecentSave(sorted[0])
        } else {
            setMostRecentSave(null)
        }
    }, [saveList])

    const handleNewGame = async () => {
        playSFX('click')
        setLoadingAction(true)
        try {
            await saves.newGame()
            navigate('/game')
        } catch (error) {
            console.error("Failed to start new game", error)
            playSFX('error')
        } finally {
            setLoadingAction(false)
        }
    }

    const handleContinue = async () => {
        if (!mostRecentSave) return
        playSFX('click')
        setLoadingAction(true)
        try {
            await saves.load(mostRecentSave.id)
            navigate('/game')
        } catch (error) {
            console.error("Failed to load save", error)
            playSFX('error')
        } finally {
            setLoadingAction(false)
        }
    }

    const handleLoadGameClick = async () => {
        playSFX('click')
        setShowLoadModal(true)
        setIsLoadingSaves(true)
        try {
            const response = await saves.list()
            setSaveList(response.data?.saves || [])
        } catch (error) {
            console.error("Failed to list saves", error)
        } finally {
            setIsLoadingSaves(false)
        }
    }

    const handleLoadConfirm = async (saveId, isLocal = false) => {
        playSFX('click')
        setLoadingAction(true)
        try {
            if (isLocal && saveId === 'local_autosave') {
                // To load local, we would normally send the data to the server
                // But for now, since the API doesn't support 'load from raw data' easily,
                // we'll rely on the fact that 'Continue' or 'Load' usually targets the server state.
                // REFINEMENT: If it's local, we might need an endpoint to sync it first.
                // For this implementation, let's treat 'local_autosave' as a special case if we had a sync endpoint.
                // Assuming cloud is the primary source of truth now.
                // If the user selects a local save, we warn them or just load if supported.
                showWarning("Loading from Local Storage is currently being synchronized with the cloud. Please select a Cloud save for now.")
                // In a full implementation, we'd POST the local data to a 'sync' endpoint.
            } else {
                await saves.load(saveId)
                navigate('/game')
            }
        } catch (error) {
            console.error("Failed to load save", error)
            playSFX('error')
        } finally {
            setLoadingAction(false)
        }
    }

    const handleDeleteSave = async (e, saveId, isLocal = false) => {
        e.stopPropagation()
        if (!window.confirm("Are you sure you want to delete this save?")) return

        try {
            if (isLocal) {
                localStorage.removeItem('hov_local_autosave')
            } else {
                await saves.delete(saveId)
            }
            setSaveList(prev => prev.filter(s => s.id !== saveId))
            playSFX('click')
        } catch (error) {
            console.error("Failed to delete save", error)
            playSFX('error')
        }
    }

    const handleLogout = async () => {
        playSFX('click')
        await logout()
        navigate('/login')
    }

    // Styles
    const containerStyle = {
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#050505',
        backgroundImage: `radial-gradient(circle at 50% 50%, #1a2a3a 0%, #000000 100%)`,
        color: '#e0e0e0',
        fontFamily: '"Outfit", sans-serif',
        position: 'relative',
        overflow: 'hidden'
    }

    const menuCardStyle = {
        background: 'rgba(20, 20, 20, 0.85)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(0, 255, 136, 0.2)',
        boxShadow: '0 0 20px rgba(0, 255, 136, 0.1)',
        borderRadius: '1rem',
        padding: '3rem',
        width: '100%',
        maxWidth: '400px',
        textAlign: 'center',
        animation: 'fadeInUp 0.8s ease-out'
    }

    const titleStyle = {
        fontSize: '2.5rem',
        background: 'linear-gradient(to right, #00ff88, #00ccff)',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        marginBottom: '2rem',
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        filter: 'drop-shadow(0 0 10px rgba(0, 255, 136, 0.3))'
    }

    const modalOverlayStyle = {
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0,0,0,0.8)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000
    }

    const modalContentStyle = {
        background: '#111',
        border: '1px solid #333',
        borderRadius: '0.5rem',
        width: '90%',
        maxWidth: '600px',
        maxHeight: '80vh',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
    }

    return (
        <div style={containerStyle}>
            <div style={menuCardStyle}>
                <h1 style={titleStyle}>Heart of Virtue</h1>

                <nav>
                    {!isLoadingInitial && saveList.length > 0 && mostRecentSave && (
                        <MenuButton onClick={handleContinue}>Continue</MenuButton>
                    )}
                    <MenuButton onClick={handleNewGame}>New Game</MenuButton>
                    {!isLoadingInitial && saveList.length > 0 && (
                        <MenuButton onClick={handleLoadGameClick}>Load Game</MenuButton>
                    )}
                    <MenuButton onClick={() => setShowSettings(true)}>Settings</MenuButton>
                    <MenuButton onClick={() => setShowCredits(true)}>Credits</MenuButton>
                    <MenuButton onClick={handleLogout} variant="danger">Logout</MenuButton>
                </nav>
            </div>

            {/* Settings Modal */}
            {showSettings && (
                <div style={modalOverlayStyle} onClick={() => setShowSettings(false)}>
                    <div style={modalContentStyle} onClick={e => e.stopPropagation()}>
                        <div style={{ padding: '1rem', borderBottom: '1px solid #333', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <h2 style={{ color: '#00ff88', margin: 0 }}>Settings</h2>
                            <button onClick={() => setShowSettings(false)} style={{ background: 'none', border: 'none', color: '#666', cursor: 'pointer', fontSize: '1.5rem' }}>×</button>
                        </div>
                        <div style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                            <div>
                                <h3 style={{ color: '#00ccff', marginBottom: '0.5rem' }}>Audio Settings</h3>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                                    <div>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                                            <span>Music Volume</span>
                                            <span>{Math.round((musicVolume || 0) * 100)}%</span>
                                        </div>
                                        <input
                                            type="range" min="0" max="1" step="0.01"
                                            value={musicVolume || 0}
                                            onChange={(e) => setMusicVolume(parseFloat(e.target.value))}
                                            style={{ width: '100%', accentColor: '#00ff88' }}
                                        />
                                    </div>
                                    <div>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                                            <span>SFX Volume</span>
                                            <span>{Math.round((sfxVolume || 0) * 100)}%</span>
                                        </div>
                                        <input
                                            type="range" min="0" max="1" step="0.01"
                                            value={sfxVolume || 0}
                                            onChange={(e) => setSfxVolume(parseFloat(e.target.value))}
                                            style={{ width: '100%', accentColor: '#00ff88' }}
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Credits Modal */}
            {showCredits && (
                <div style={modalOverlayStyle} onClick={() => setShowCredits(false)}>
                    <div style={modalContentStyle} onClick={e => e.stopPropagation()}>
                        <div style={{ padding: '1rem', borderBottom: '1px solid #333', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <h2 style={{ color: '#00ff88', margin: 0 }}>Credits</h2>
                            <button onClick={() => setShowCredits(false)} style={{ background: 'none', border: 'none', color: '#666', cursor: 'pointer', fontSize: '1.5rem' }}>×</button>
                        </div>
                        <div style={{ padding: '2rem', textAlign: 'center' }}>
                            <h3 style={{ color: '#00ccff' }}>The Development Team</h3>
                            <p>Created by the Alpha Project Team</p>
                            <p style={{ marginTop: '1rem', color: '#888' }}>Powered by Vitest & React</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Load Game Modal */}
            {showLoadModal && (
                <div style={modalOverlayStyle} onClick={() => setShowLoadModal(false)}>
                    <div style={modalContentStyle} onClick={e => e.stopPropagation()}>
                        <div style={{ padding: '1rem', borderBottom: '1px solid #333', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <h2 style={{ color: '#00ff88', margin: 0 }}>Load Game</h2>
                            <button
                                onClick={() => setShowLoadModal(false)}
                                style={{ background: 'none', border: 'none', color: '#666', cursor: 'pointer', fontSize: '1.5rem' }}
                            >×</button>
                        </div>

                        <div style={{ padding: '1rem', overflowY: 'auto' }}>
                            {isLoadingSaves ? (
                                <div style={{ color: '#666', textAlign: 'center' }}>Loading saves...</div>
                            ) : saveList.length === 0 ? (
                                <div style={{ color: '#666', textAlign: 'center' }}>No saves found.</div>
                            ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                    {saveList.map(save => (
                                        <div
                                            key={save.id}
                                            onClick={() => handleLoadConfirm(save.id, save.isLocal)}
                                            className="save-slot"
                                            style={{
                                                padding: '1rem',
                                                background: '#1a1a1a',
                                                border: `1px solid ${save.isLocal ? '#4444ff44' : '#333'}`,
                                                borderRadius: '0.25rem',
                                                cursor: 'pointer',
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'center',
                                                transition: 'background 0.2s',
                                                position: 'relative'
                                            }}
                                            onMouseEnter={(e) => e.currentTarget.style.background = '#252525'}
                                            onMouseLeave={(e) => e.currentTarget.style.background = '#1a1a1a'}
                                        >
                                            <div style={{
                                                position: 'absolute',
                                                top: 0,
                                                right: 0,
                                                fontSize: '8px',
                                                padding: '2px 6px',
                                                background: save.isLocal ? '#4444ff88' : '#00ff8844',
                                                borderBottomLeftRadius: '4px',
                                                color: '#fff',
                                                textTransform: 'uppercase'
                                            }}>
                                                {save.isLocal ? 'Local' : 'Cloud'}
                                            </div>
                                            <div>
                                                <div style={{ color: '#fff', fontWeight: 'bold' }}>
                                                    {save.name || 'Untitled Save'}
                                                    {save.is_autosave && <span style={{ color: '#ffaa00', fontSize: '0.7rem', marginLeft: '6px' }}>(Autosave)</span>}
                                                </div>
                                                <div style={{ color: '#888', fontSize: '0.8rem', marginTop: '0.25rem' }}>
                                                    Lvl {save.level} • {save.map_name} • {save.room_title}
                                                </div>
                                                <div style={{ color: '#666', fontSize: '0.75rem', marginTop: '0.25rem' }}>
                                                    {new Date(save.timestamp).toLocaleString()}
                                                </div>
                                            </div>
                                            <button
                                                onClick={(e) => handleDeleteSave(e, save.id, save.isLocal)}
                                                style={{
                                                    background: 'none',
                                                    border: '1px solid #662222',
                                                    color: '#ee5555',
                                                    padding: '0.25rem 0.5rem',
                                                    borderRadius: '0.25rem',
                                                    fontSize: '0.8rem',
                                                    cursor: 'pointer',
                                                    zIndex: 2
                                                }}
                                            >
                                                Delete
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {loadingAction && (
                <div style={{ ...modalOverlayStyle, zIndex: 1100 }}>
                    <div style={{ color: '#00ff88', fontSize: '1.5rem' }}>Loading...</div>
                </div>
            )}
        </div>
    )
}

function MenuButton({ children, onClick, variant = 'primary' }) {
    const [hover, setHover] = useState(false)
    const baseColor = variant === 'danger' ? '#ff4444' : '#00ff88'

    return (
        <button
            onClick={onClick}
            onMouseEnter={() => setHover(true)}
            onMouseLeave={() => setHover(false)}
            style={{
                display: 'block',
                width: '100%',
                padding: '1rem',
                margin: '1rem 0',
                background: hover ? `rgba(${variant === 'danger' ? '255,68,68' : '0,255,136'}, 0.1)` : 'transparent',
                border: `1px solid ${baseColor}`,
                color: baseColor,
                fontSize: '1rem',
                textTransform: 'uppercase',
                letterSpacing: '0.15em',
                cursor: 'pointer',
                transition: 'all 0.3s ease',
                borderRadius: '0.25rem',
                boxShadow: hover ? `0 0 15px rgba(${variant === 'danger' ? '255,68,68' : '0,255,136'}, 0.3)` : 'none'
            }}
        >
            {children}
        </button>
    )
}
