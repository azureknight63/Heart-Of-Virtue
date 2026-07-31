import { useAudio } from '../context/AudioContext'
import { colors } from '../styles/theme'
import { COMBAT_SPEED_STEPS } from '../utils/combatTiming'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'

export default function AudioControlDialog({ onClose }) {
    const {
        musicVolume,
        setMusicVolume,
        sfxVolume,
        setSfxVolume,
        isMusicMuted,
        setIsMusicMuted,
        isSfxMuted,
        setIsSfxMuted,
        combatSpeed,
        setCombatSpeed
    } = useAudio()

    return (
        <BaseDialog title="🔊 Audio Settings" onClose={onClose}>
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
                        <div style={{ color: colors.accent, fontSize: '14px', fontWeight: 'bold' }}>
                            MUSIC
                        </div>
                        <button
                            onClick={() => setIsMusicMuted(!isMusicMuted)}
                            style={{
                                padding: '4px 8px',
                                backgroundColor: isMusicMuted ? colors.dangerDark : colors.primaryDark,
                                color: isMusicMuted ? colors.gold : colors.text.inverse,
                                border: `1px solid ${colors.text.inverse}`,
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
                        <span style={{ color: colors.primary, fontSize: '12px' }}>0%</span>
                        <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.05"
                            value={musicVolume}
                            onChange={(e) => setMusicVolume(parseFloat(e.target.value))}
                            style={{
                                flex: 1,
                                accentColor: colors.primary,
                                cursor: 'pointer'
                            }}
                            disabled={isMusicMuted}
                        />
                        <span style={{ color: colors.primary, fontSize: '12px' }}>100%</span>
                    </div>
                    <div style={{ textAlign: 'center', color: colors.primary, fontSize: '12px', marginTop: '5px' }}>
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
                        <div style={{ color: colors.accent, fontSize: '14px', fontWeight: 'bold' }}>
                            SOUND EFFECTS
                        </div>
                        <button
                            onClick={() => setIsSfxMuted(!isSfxMuted)}
                            style={{
                                padding: '4px 8px',
                                backgroundColor: isSfxMuted ? colors.dangerDark : colors.primaryDark,
                                color: isSfxMuted ? colors.gold : colors.text.inverse,
                                border: `1px solid ${colors.text.inverse}`,
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
                        <span style={{ color: colors.primary, fontSize: '12px' }}>0%</span>
                        <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.05"
                            value={sfxVolume}
                            onChange={(e) => setSfxVolume(parseFloat(e.target.value))}
                            style={{
                                flex: 1,
                                accentColor: colors.primary,
                                cursor: 'pointer'
                            }}
                            disabled={isSfxMuted}
                        />
                        <span style={{ color: colors.primary, fontSize: '12px' }}>100%</span>
                    </div>
                    <div style={{ textAlign: 'center', color: colors.primary, fontSize: '12px', marginTop: '5px' }}>
                        {Math.round(sfxVolume * 100)}%
                    </div>
                </div>

                {/* Combat Speed Control (issue #460) */}
                <div style={{ marginBottom: '15px' }}>
                    <div style={{ color: colors.accent, fontSize: '14px', fontWeight: 'bold', marginBottom: '10px' }}>
                        COMBAT SPEED
                    </div>
                    <div style={{ display: 'flex', gap: '6px' }}>
                        {COMBAT_SPEED_STEPS.map((step) => (
                            <button
                                key={step}
                                onClick={() => setCombatSpeed(step)}
                                aria-pressed={combatSpeed === step}
                                style={{
                                    flex: 1,
                                    padding: '6px 4px',
                                    backgroundColor: combatSpeed === step ? colors.primary : colors.primaryDark,
                                    color: combatSpeed === step ? '#000000' : colors.text.inverse,
                                    border: `1px solid ${colors.text.inverse}`,
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    fontSize: '12px',
                                    fontWeight: 'bold',
                                }}
                            >
                                {step}x
                            </button>
                        ))}
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
                <GameButton onClick={onClose} variant="secondary">
                    Close
                </GameButton>
            </div>
        </BaseDialog>
    )
}
