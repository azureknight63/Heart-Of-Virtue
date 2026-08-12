import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

function useEmbers() {
  useEffect(() => {
    const canvas = document.getElementById('menu-embers')
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
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
import { readLocalSave, compareSavesByRecency, formatSaveTimestamp } from '../utils/localSave'

/**
 * How recently the local autosave must have been written for Continue to treat
 * it as a live session worth resuming. Generous on purpose: a player taking a
 * break with the tab open should still resume rather than silently load an
 * older cloud save, while a blob from days ago belongs to a server session that
 * is certainly gone.
 */
const LOCAL_SESSION_FRESHNESS_MS = 12 * 60 * 60 * 1000

/**
 * Fetch the cloud saves only, newest first.
 *
 * The local autosave is deliberately NOT folded in here: it cannot be
 * restored (see utils/localSave), so it must never appear as a selectable
 * row in the Load Game list. It is still consulted separately — see
 * resolveContinueTarget — so Continue keeps resuming the live session
 * instead of loading a cloud save out from under it.
 */
async function fetchCloudSaves() {
    const response = await saves.list()
    const cloudSaves = [...(response.data?.saves || [])]
    return cloudSaves.sort(compareSavesByRecency)
}

/**
 * Decide what the Continue button should do: resume the live server session
 * (the local autosave is the more recent activity, or the only activity) or
 * load a specific cloud save.
 *
 * The local entry returned here is a decision input ONLY — it is never
 * written into `saveList`/the Load Game modal. Comparing cloud saves alone
 * would silently re-target Continue at the newest cloud save whenever a local
 * autosave is more recent, overwriting the live in-memory session with an
 * older one. That is the exact progress-loss bug this function guards
 * against, so it re-reads the local blob on every call rather than trusting
 * a value computed before the blob may have changed.
 */
function resolveContinueTarget(cloudSaves) {
    const localEntry = readLocalSave()

    // Deliberately NOT a recency comparison against the cloud rows. The local
    // blob's timestamp comes from the browser clock (`new Date()` in
    // useAutosave), while a cloud row's timestamp_ms comes from SQLite's
    // CURRENT_TIMESTAMP — the server clock. Ranking one against the other means
    // a browser running a few minutes slow makes every cloud autosave look
    // newer than the live session, sending Continue down the saves.load() path
    // and replacing the in-memory session with a snapshot up to 20 ticks old.
    //
    // Freshness is measured against the same clock that wrote it, so the
    // comparison is internally consistent. A blob older than the window means
    // the tab has been gone long enough that its server session is almost
    // certainly dead, and the newest cloud save is the better target.
    if (localEntry && Date.now() - localEntry.timestampMs < LOCAL_SESSION_FRESHNESS_MS) {
        return localEntry
    }
    return cloudSaves.length > 0 ? [...cloudSaves].sort(compareSavesByRecency)[0] : null
}

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

    useEffect(() => {
        playBGM('adventure')
    }, [playBGM])

    // Fetch the save list once, on mount. This is deliberately NOT keyed on
    // playBGM: that callback is recreated on every music-volume/mute change, so
    // sharing an effect with the theme made a single volume-slider drag fire
    // ~30 GET /saves requests.
    useEffect(() => {
        const initMenu = async () => {
            try {
                const cloudSaves = await fetchCloudSaves()
                setSaveList(cloudSaves)
                setMostRecentSave(resolveContinueTarget(cloudSaves))
            } catch (error) {
                console.error("Failed to initialize menu saves", error)
                setSaveList([])
                setMostRecentSave(null)
            } finally {
                setIsLoadingInitial(false)
            }
        }
        initMenu()
    }, [])

    // Keep mostRecentSave in sync with saveList (cloud saves only — see
    // resolveContinueTarget for why the local autosave is folded back in here
    // rather than living in saveList itself).
    useEffect(() => {
        setMostRecentSave(resolveContinueTarget(saveList))
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
            // Cloud saves only — the local autosave never becomes a row (see
            // fetchCloudSaves). The sync effect on saveList re-derives
            // mostRecentSave via resolveContinueTarget right after this call,
            // which folds the local blob back in for the Continue decision, so
            // opening/closing this modal can no longer re-point Continue at an
            // older cloud save.
            setSaveList(await fetchCloudSaves())
        } catch (error) {
            console.error("Failed to list saves", error)
        } finally {
            setIsLoadingSaves(false)
        }
    }

    const handleLoadConfirm = async (saveId) => {
        // Rows in this modal are always cloud saves now (the local autosave is
        // excluded from saveList — see fetchCloudSaves), so there is no local
        // branch here to worry about.
        playSFX('click')
        setLoadingAction(true)
        try {
            await saves.load(saveId)
            navigate('/game')
        } catch (error) {
            console.error("Failed to load save", error)
            playSFX('error')
        } finally {
            setLoadingAction(false)
        }
    }

    const handleDeleteSave = async (e, saveId) => {
        // No local branch: the local autosave is never a row in saveList (see
        // fetchCloudSaves), so every save reaching this handler is a cloud save.
        e.stopPropagation()
        if (!window.confirm("Are you sure you want to delete this save?")) return

        try {
            await saves.delete(saveId)
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
                        <GameButton onClick={handleContinue} size="large" style={{ width: '100%' }}>
                            {/* Honest labelling: a local autosave can't be "loaded" like a
                                save file — it just resumes whatever session is still live
                                on the server. Only the label changes; the click handler
                                already branches on mostRecentSave.isLocal. */}
                            {mostRecentSave.isLocal ? 'Continue (Resume Session)' : 'Continue'}
                        </GameButton>
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
                                        onClick={() => handleLoadConfirm(save.id)}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter' || e.key === ' ') {
                                                e.preventDefault();
                                                handleLoadConfirm(save.id);
                                            }
                                        }}
                                        style={{
                                            padding: spacing.lg,
                                            background: colors.bg.panelLight,
                                            border: `1px solid ${colors.border.light}`,
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
                                            e.currentTarget.style.borderColor = colors.border.light;
                                        }}
                                    >
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
                                                {formatSaveTimestamp(save)}
                                            </GameText>
                                        </div>
                                        <GameButton
                                            onClick={(e) => handleDeleteSave(e, save.id)}
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
