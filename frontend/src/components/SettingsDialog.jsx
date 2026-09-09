import { usePreferences } from '../context/PreferencesContext'
import { colors, accessibility } from '../styles/theme'
import { useMobile } from '../hooks/useMobile'
import { COMBAT_SPEED_OPTIONS } from '../utils/combatTiming'
import { TEXT_SPEED_OPTIONS } from '../utils/textPacing'
import { FEATURE_FLAGS, setFlag, useFeatureFlag } from '../utils/featureFlags'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'

/**
 * A labelled ON/OFF preference with a line of explanation.
 *
 * Shared by the feature-flag rows and the story auto-advance toggle, which
 * were style-for-style copies of each other.
 */
function ToggleRow({ label, description, enabled, onToggle, ariaLabel, buttonStyle = {} }) {
    return (
        <div style={{ marginBottom: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px' }}>
                <div style={{ color: colors.text.main, fontSize: '12px' }}>{label}</div>
                <button
                    onClick={onToggle}
                    aria-pressed={enabled}
                    aria-label={ariaLabel}
                    style={{
                        padding: '4px 8px',
                        backgroundColor: enabled ? colors.primaryDark : colors.bg.panel,
                        color: enabled ? colors.text.inverse : colors.text.muted,
                        border: `1px solid ${enabled ? colors.text.inverse : colors.border.main}`,
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '12px',
                        fontWeight: 'bold',
                        flexShrink: 0,
                        ...buttonStyle,
                    }}
                >
                    {enabled ? 'ON' : 'OFF'}
                </button>
            </div>
            <div style={{ color: colors.text.muted, fontSize: '11px', marginTop: '4px', lineHeight: 1.4 }}>
                {description}
            </div>
        </div>
    )
}

/**
 * A heading over a row of mutually-exclusive step buttons — COMBAT SPEED and
 * TEXT SPEED. Stepped rather than a slider so an end-stop (INSTANT) can be a
 * named choice rather than the far end of a scale.
 */
function SegmentedRow({ heading, options, value, onSelect, buttonStyle = {}, fontSize = '12px' }) {
    return (
        <div style={{ marginBottom: '15px' }}>
            <div style={{ color: colors.accent, fontSize: '14px', fontWeight: 'bold', marginBottom: '10px' }}>
                {heading}
            </div>
            {/* The segments name their own value ("1x") but not what it
                sets, and the heading above them carried no association to them
                at all (issue #563 item 2). The group's name is derived from
                `heading` rather than passed in, so COMBAT SPEED and TEXT SPEED
                are both covered without a second list to keep in step. */}
            <div
                role="group"
                aria-label={heading.charAt(0) + heading.slice(1).toLowerCase()}
                style={{ display: 'flex', gap: '6px' }}
            >
                {options.map((option) => {
                    const selected = value === option.value
                    return (
                        <button
                            key={option.label}
                            onClick={() => onSelect(option.value)}
                            aria-pressed={selected}
                            style={{
                                flex: 1,
                                padding: '6px 4px',
                                backgroundColor: selected ? colors.primary : colors.primaryDark,
                                color: selected ? '#000000' : colors.text.inverse,
                                border: `1px solid ${colors.text.inverse}`,
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize,
                                fontWeight: 'bold',
                                ...buttonStyle,
                            }}
                        >
                            {option.label}
                        </button>
                    )
                })}
            </div>
        </div>
    )
}

// One row per registered flag. Rendered from the registry rather than written
// out per flag, so adding an entry to FEATURE_FLAGS is the only step needed to
// surface a new toggle here.
function FeatureFlagRow({ name, label, description }) {
    const enabled = useFeatureFlag(name)
    return (
        <ToggleRow
            label={label}
            description={description}
            enabled={enabled}
            onToggle={() => setFlag(name, !enabled)}
            // issue #563 item 2: without this the flag rows are three
            // identically-named ON/OFF buttons, the only distinguishing text
            // being the sibling div above. Named from the same `label` rather
            // than by giving that div an id, so the row's DOM shape (which
            // SettingsDialog.test.jsx walks) is untouched.
            ariaLabel={label}
        />
    )
}

export default function SettingsDialog({ onClose }) {
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
        setCombatSpeed,
        textSpeed,
        setTextSpeed,
        autoAdvance,
        setAutoAdvance
    } = usePreferences()
    const isMobile = useMobile()
    // issue #542: measured 31x28px (MUSIC/SFX mute toggles) and 56x32px
    // (combat-speed segments) on a 375px viewport — both below the 44px
    // touch-target minimum. Mobile-only so desktop's compact settings layout
    // is untouched.
    const mobileTouchTarget = isMobile
        ? { minWidth: accessibility.touchTarget, minHeight: accessibility.touchTarget }
        : {}
    const mobileTouchHeight = isMobile
        ? { minHeight: accessibility.touchTarget }
        : {}

    return (
        <BaseDialog title="⚙️ SETTINGS" onClose={onClose}>
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
                            // "ON" was the whole accessible name, and the SFX
                            // toggle below announced identically — two buttons
                            // with one name on a single screen.
                            aria-label="Mute music"
                            aria-pressed={isMusicMuted}
                            style={{
                                padding: '4px 8px',
                                backgroundColor: isMusicMuted ? colors.dangerDark : colors.primaryDark,
                                color: isMusicMuted ? colors.gold : colors.text.inverse,
                                border: `1px solid ${colors.text.inverse}`,
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '12px',
                                fontWeight: 'bold',
                                ...mobileTouchTarget,
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
                            // Announced as a bare "slider, 0.5" before this.
                            // Not `htmlFor` on the MUSIC heading above: that
                            // heading heads the mute button too, so tying it
                            // to the slider alone would announce the slider as
                            // "MUSIC" and leave the button beside it "ON".
                            aria-label="Music volume"
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
                            aria-label="Mute sound effects"
                            aria-pressed={isSfxMuted}
                            style={{
                                padding: '4px 8px',
                                backgroundColor: isSfxMuted ? colors.dangerDark : colors.primaryDark,
                                color: isSfxMuted ? colors.gold : colors.text.inverse,
                                border: `1px solid ${colors.text.inverse}`,
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '12px',
                                fontWeight: 'bold',
                                ...mobileTouchTarget,
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
                            aria-label="Sound effects volume"
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
                <SegmentedRow
                    heading="COMBAT SPEED"
                    options={COMBAT_SPEED_OPTIONS}
                    value={combatSpeed}
                    onSelect={setCombatSpeed}
                    buttonStyle={mobileTouchHeight}
                />

                {/* Text Speed — the story is the game's primary delivery
                    vehicle, and until now it was the only paced thing with no
                    control at all (issue #538 item 1). */}
                <SegmentedRow
                    heading="TEXT SPEED"
                    options={TEXT_SPEED_OPTIONS}
                    value={textSpeed}
                    onSelect={setTextSpeed}
                    buttonStyle={mobileTouchHeight}
                    fontSize="11px"
                />

                <div style={{ marginBottom: '15px' }}>
                    <div style={{ color: colors.accent, fontSize: '14px', fontWeight: 'bold', marginBottom: '10px' }}>
                        STORY
                    </div>
                    <ToggleRow
                        label="Auto-advance story"
                        description={
                            'Move to the next line on its own once it has finished, after a ' +
                            'pause scaled to its length. Clicking still advances immediately.'
                        }
                        enabled={autoAdvance}
                        onToggle={() => setAutoAdvance(!autoAdvance)}
                        ariaLabel="Auto-advance story"
                        buttonStyle={mobileTouchTarget}
                    />
                </div>

                {/* Experimental display toggles */}
                <div style={{ marginBottom: '15px' }}>
                    <div style={{ color: colors.accent, fontSize: '14px', fontWeight: 'bold', marginBottom: '10px' }}>
                        EXPERIMENTAL
                    </div>
                    {Object.entries(FEATURE_FLAGS).map(([name, flag]) => (
                        <FeatureFlagRow
                            key={name}
                            name={name}
                            label={flag.label}
                            description={flag.description}
                        />
                    ))}
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
                    CLOSE
                </GameButton>
            </div>
        </BaseDialog>
    )
}
