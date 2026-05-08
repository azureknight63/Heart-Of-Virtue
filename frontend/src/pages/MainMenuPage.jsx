import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

function useEmbers() {
  useEffect(() => {
    const canvas = document.getElementById('menu-embers')
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let raf
    let particles = []

    const resize = () => {
      canvas.width = window.innerWidth * window.devicePixelRatio
      canvas.height = window.innerHeight * window.devicePixelRatio
      canvas.style.width = window.innerWidth + 'px'
      canvas.style.height = window.innerHeight + 'px'
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
    }
    resize()
    window.addEventListener('resize', resize)

    const spawn = () => ({
      x: Math.random() * window.innerWidth,
      y: window.innerHeight + Math.random() * 40,
      vy: -0.15 - Math.random() * 0.35,
      vx: (Math.random() - 0.5) * 0.15,
      r: 0.6 + Math.random() * 1.4,
      life: 0,
      maxLife: 400 + Math.random() * 900,
      hue: Math.random() < 0.25 ? 'ember' : 'dust',
    })

    for (let i = 0; i < 60; i++) {
      const p = spawn()
      p.y = Math.random() * window.innerHeight
      p.life = Math.random() * p.maxLife
      particles.push(p)
    }

    const tick = () => {
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight)
      particles.forEach((p) => {
        p.x += p.vx
        p.y += p.vy
        p.life += 1
        const alpha = Math.sin((p.life / p.maxLife) * Math.PI) * 0.5
        ctx.fillStyle =
          p.hue === 'ember'
            ? `rgba(200,170,130,${alpha * 0.7})`
            : `rgba(232,228,216,${alpha * 0.4})`
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fill()
      })
      particles = particles.filter((p) => p.life < p.maxLife && p.y > -20)
      while (particles.length < 60) particles.push(spawn())
      raf = requestAnimationFrame(tick)
    }
    tick()

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
    }
  }, [])
}
import { useAuth } from '../hooks/useApi'
import { saves } from '../api/endpoints'
import { useAudio } from '../context/AudioContext'
import { useToast } from '../context/ToastContext'
import { colors, spacing, fonts, shadows } from '../styles/theme'
import GameButton from '../components/GameButton'
import GamePanel from '../components/GamePanel'
import GameText from '../components/GameText'
import BaseDialog from '../components/BaseDialog'

export default function MainMenuPage() {
    const navigate = useNavigate()
    const { logout } = useAuth()
    useEmbers()
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

    // Keep mostRecentSave in sync with saveList (cloud and local)
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
        // Local autosave = active session still in server memory; just navigate.
        if (mostRecentSave.isLocal) {
            navigate('/game')
            return
        }
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
                // Local autosave means the server session is (likely) still alive.
                // Navigate to the game; if the session has expired the game page will redirect.
                navigate('/game')
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

    return (
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: '#0d0d10',
            color: colors.text.main,
            fontFamily: fonts.main,
            position: 'relative',
            overflow: 'hidden'
        }}>
            <canvas
                id="menu-embers"
                style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 2 }}
            />
            <div style={{
                position: 'fixed',
                bottom: 0, left: 0, right: 0,
                height: '320px',
                background: 'radial-gradient(ellipse at 50% 100%, rgba(168,192,212,0.07), transparent 70%)',
                pointerEvents: 'none',
                zIndex: 1,
            }} />
            <div style={{ position: 'relative', zIndex: 3, width: '100%', maxWidth: '400px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <GamePanel
                padding="xxl"
                borderVariant="success"
                glow
                style={{
                    width: '100%',
                    maxWidth: '400px',
                    textAlign: 'center',
                    backgroundColor: colors.bg.panelHeavy,
                    backdropFilter: 'blur(10px)',
                }}
            >
                <GameText
                    variant="primary"
                    size="xxl"
                    weight="bold"
                    align="center"
                    style={{
                        marginBottom: spacing.xxl,
                        letterSpacing: '0.1em',
                        textTransform: 'uppercase',
                        filter: `drop-shadow(0 0 10px ${colors.primary}44)`
                    }}
                >
                    Heart of Virtue
                </GameText>

                <nav style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
                    {!isLoadingInitial && mostRecentSave && (
                        <GameButton onClick={handleContinue} size="large" style={{ width: '100%' }}>Continue</GameButton>
                    )}
                    <GameButton onClick={handleNewGame} size="large" style={{ width: '100%' }}>New Game</GameButton>
                    {!isLoadingInitial && saveList.length > 0 && (
                        <GameButton onClick={handleLoadGameClick} size="large" style={{ width: '100%' }}>Load Game</GameButton>
                    )}
                    <GameButton onClick={() => setShowSettings(true)} size="large" style={{ width: '100%' }}>Settings</GameButton>
                    <GameButton onClick={() => setShowCredits(true)} size="large" style={{ width: '100%' }}>Credits</GameButton>
                    <GameButton onClick={handleLogout} variant="danger" size="large" style={{ width: '100%' }}>Logout</GameButton>
                </nav>

                <div style={{ marginTop: spacing.xl, textAlign: 'center' }}>
                    <a
                        href="https://nexusfidei.dev"
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                            color: colors.text.dim,
                            fontFamily: fonts.main,
                            fontSize: '11px',
                            textDecoration: 'underline',
                            transition: 'color 0.2s',
                        }}
                        onMouseEnter={(e) => e.target.style.color = colors.text.muted}
                        onMouseLeave={(e) => e.target.style.color = colors.text.dim}
                    >
                        Nexus Fidei
                    </a>
                </div>
            </GamePanel>

            <div style={{ marginTop: spacing.xl, textAlign: 'center' }}>
                <button
                    onClick={() => navigate('/landing')}
                    style={{
                        background: 'none',
                        border: 'none',
                        color: '#8a8578',
                        cursor: 'pointer',
                        fontFamily: 'monospace',
                        fontSize: '11px',
                        padding: 0,
                        transition: 'color 0.2s',
                    }}
                    onMouseEnter={(e) => e.target.style.color = '#b8b2a3'}
                    onMouseLeave={(e) => e.target.style.color = '#8a8578'}
                >
                    ← Back to home
                </button>
            </div>
            </div>{/* end column wrapper */}

            {/* Settings Modal */}
            {showSettings && (
                <BaseDialog title="Settings" onClose={() => setShowSettings(false)} maxWidth="500px">
                    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.xl }}>
                        <div style={{ textAlign: 'center' }}>
                            <GameText variant="accent" size="md" weight="bold" style={{ marginBottom: spacing.sm, textAlign: 'center' }}>
                                Audio Settings
                            </GameText>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
                                <div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: spacing.xs }}>
                                        <GameText size="sm">Music Volume</GameText>
                                        <GameText size="sm" variant="primary">{Math.round((musicVolume || 0) * 100)}%</GameText>
                                    </div>
                                    <input
                                        type="range" min="0" max="1" step="0.01"
                                        value={musicVolume || 0}
                                        onChange={(e) => setMusicVolume(parseFloat(e.target.value))}
                                        style={{ width: '100%', accentColor: colors.primary }}
                                    />
                                </div>
                                <div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: spacing.xs }}>
                                        <GameText size="sm">SFX Volume</GameText>
                                        <GameText size="sm" variant="primary">{Math.round((sfxVolume || 0) * 100)}%</GameText>
                                    </div>
                                    <input
                                        type="range" min="0" max="1" step="0.01"
                                        value={sfxVolume || 0}
                                        onChange={(e) => setSfxVolume(parseFloat(e.target.value))}
                                        style={{ width: '100%', accentColor: colors.primary }}
                                    />
                                </div>
                            </div>
                        </div>
                    </div>
                </BaseDialog>
            )}

            {/* Credits Modal */}
            {showCredits && (
                <BaseDialog title="Credits" onClose={() => setShowCredits(false)} maxWidth="500px">
                    <div style={{ padding: spacing.xl, textAlign: 'center', display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
                        <div>
                            <GameText variant="accent" size="lg" weight="bold">The Development Team</GameText>
                            <GameText size="md" style={{ marginTop: spacing.xs }}>Created by Alex Egbert</GameText>
                        </div>
                        <GameText variant="muted" size="sm">Powered by Claude, Gemini, Vitest & React</GameText>
                    </div>
                </BaseDialog>
            )}

            {/* Load Game Modal */}
            {showLoadModal && (
                <BaseDialog title="Load Game" onClose={() => setShowLoadModal(false)} maxWidth="600px">
                    <div style={{ padding: spacing.sm, overflowY: 'auto', maxHeight: '60vh' }}>
                        {isLoadingSaves ? (
                            <div style={{ textAlign: 'center', padding: spacing.xl }}>
                                <GameText variant="muted">Loading saves...</GameText>
                            </div>
                        ) : saveList.length === 0 ? (
                            <div style={{ textAlign: 'center', padding: spacing.xl }}>
                                <GameText variant="muted">No saves found.</GameText>
                            </div>
                        ) : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
                                {saveList.map(save => (
                                    <div
                                        key={save.id}
                                        role="button"
                                        tabIndex={0}
                                        onClick={() => handleLoadConfirm(save.id, save.isLocal)}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter' || e.key === ' ') {
                                                e.preventDefault();
                                                handleLoadConfirm(save.id, save.isLocal);
                                            }
                                        }}
                                        style={{
                                            padding: spacing.lg,
                                            background: colors.bg.panelLight,
                                            border: `1px solid ${save.isLocal ? colors.accent : colors.border.light}`,
                                            borderRadius: '6px',
                                            cursor: 'pointer',
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            alignItems: 'center',
                                            transition: 'all 0.2s ease',
                                            position: 'relative',
                                            overflow: 'hidden'
                                        }}
                                        onMouseEnter={(e) => {
                                            e.currentTarget.style.background = colors.bg.panel;
                                            e.currentTarget.style.borderColor = colors.primary;
                                        }}
                                        onMouseLeave={(e) => {
                                            e.currentTarget.style.background = colors.bg.panelLight;
                                            e.currentTarget.style.borderColor = save.isLocal ? colors.accent : colors.border.light;
                                        }}
                                    >
                                        <div style={{
                                            position: 'absolute',
                                            top: 0,
                                            right: 0,
                                            fontSize: '9px',
                                            padding: '2px 8px',
                                            background: save.isLocal ? `${colors.accent}44` : `${colors.primary}44`,
                                            borderBottomLeftRadius: '4px',
                                            color: '#fff',
                                            textTransform: 'uppercase',
                                            fontWeight: 'bold',
                                            letterSpacing: '0.5px'
                                        }}>
                                            {save.isLocal ? 'Local' : 'Cloud'}
                                        </div>
                                        <div>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
                                                <GameText variant="bright" weight="bold">
                                                    {save.name || 'Untitled Save'}
                                                </GameText>
                                                {save.is_autosave && (
                                                    <GameText variant="warning" size="xs">(Autosave)</GameText>
                                                )}
                                            </div>
                                            <GameText variant="muted" size="sm" style={{ marginTop: spacing.xs }}>
                                                Lvl {save.level} • {save.map_name} • {save.room_title}
                                            </GameText>
                                            <GameText variant="dim" size="xs" style={{ marginTop: spacing.xs }}>
                                                {new Date(save.timestamp).toLocaleString()}
                                            </GameText>
                                        </div>
                                        <GameButton
                                            onClick={(e) => handleDeleteSave(e, save.id, save.isLocal)}
                                            variant="secondary"
                                            size="small"
                                            style={{ color: colors.danger, borderColor: `${colors.danger}44` }}
                                        >
                                            Delete
                                        </GameButton>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </BaseDialog>
            )}

            {loadingAction && (
                <div style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 2000
                }}>
                    <GameText variant="primary" size="xl">Loading...</GameText>
                </div>
            )}
        </div>
    )
}
