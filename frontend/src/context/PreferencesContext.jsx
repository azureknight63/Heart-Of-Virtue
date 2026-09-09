import { createContext, useContext, useEffect, useState } from 'react';

import { DEFAULT_COMBAT_SPEED, normalizeSpeed } from '../utils/combatTiming';
import { DEFAULT_TEXT_SPEED, normalizeTextSpeed } from '../utils/textPacing';

/**
 * The player's persisted settings — volumes, mutes, and the two pacing
 * controls.
 *
 * Split out of `AudioContext`, which had grown to hold `combatSpeed`,
 * `textSpeed` and `autoAdvance`: none of those are audio, and a container
 * named for one of the things inside it misdescribes the rest. `AudioContext`
 * now owns playback only and reads its volumes from here, so each name
 * describes its contents and there is still exactly one place a preference
 * lives.
 *
 * The storage key stays `audioPreferences` deliberately — renaming it would
 * silently reset every existing player's settings for no gain.
 */

const STORAGE_KEY = 'audioPreferences';

/**
 * Every persisted preference and its default, in one place.
 *
 * Adding one used to mean editing five unlinked literal lists — the context
 * default, the load fallback, a `useState` initializer, the save effect's
 * object AND its dependency array — so the sixth was going to miss one.
 * Everything that can be derived from this now is.
 */
export const DEFAULT_PREFERENCES = {
    musicVolume: 0.5,
    sfxVolume: 0.5,
    isMusicMuted: false,
    isSfxMuted: false,
    combatSpeed: DEFAULT_COMBAT_SPEED,
    textSpeed: DEFAULT_TEXT_SPEED,
    autoAdvance: false,
};

/**
 * Clamp a persisted volume to the 0–1 range `HTMLMediaElement.volume` accepts.
 *
 * Load-bearing, not defensive dressing: this value goes straight onto a media
 * element, which throws `TypeError` for a non-number and `IndexSizeError` for
 * anything outside 0–1. The app has no error boundary, so a hand-edited or
 * corrupted `audioPreferences` blob would blank the whole SPA on every load —
 * and stay blanked, because the bad value is re-read from localStorage each
 * time.
 */
export function normalizeVolume(value, fallback) {
    // Type-checked BEFORE clamping, not coerced: `Number(null)`, `Number('')`,
    // `Number(false)` and `Number([])` are all `0` and all finite, so coercing
    // first would turn a missing or junk value into a silently MUTED game
    // rather than into the default.
    if (typeof value !== 'number' || !Number.isFinite(value)) return fallback;
    return Math.min(1, Math.max(0, value));
}

/** Read the saved preferences, falling back to defaults key by key. */
export function loadPreferences() {
    let parsed = null;
    try {
        const saved = localStorage.getItem(STORAGE_KEY);
        parsed = saved ? JSON.parse(saved) : null;
    } catch (error) {
        console.warn('Failed to load preferences:', error);
    }
    // Spread OVER the defaults, and only for a real object: a blob saved before
    // a preference existed is missing that key, and `JSON.parse` happily
    // returns `null`, a number or an array for a hand-edited one — any of which
    // would otherwise arrive as the whole preference set.
    const stored =
        parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
    const merged = { ...DEFAULT_PREFERENCES, ...stored };
    // Every value is normalized on the way in rather than at each point of use,
    // so a consumer can treat what it reads here as already valid.
    return {
        ...merged,
        musicVolume: normalizeVolume(merged.musicVolume, DEFAULT_PREFERENCES.musicVolume),
        sfxVolume: normalizeVolume(merged.sfxVolume, DEFAULT_PREFERENCES.sfxVolume),
        isMusicMuted: Boolean(merged.isMusicMuted),
        isSfxMuted: Boolean(merged.isSfxMuted),
        combatSpeed: normalizeSpeed(merged.combatSpeed),
        textSpeed: normalizeTextSpeed(merged.textSpeed),
        autoAdvance: Boolean(merged.autoAdvance),
    };
}

function savePreferences(preferences) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
    } catch (error) {
        console.warn('Failed to save preferences:', error);
    }
}

const PreferencesContext = createContext({
    ...DEFAULT_PREFERENCES,
    setMusicVolume: () => {},
    setSfxVolume: () => {},
    setIsMusicMuted: () => {},
    setIsSfxMuted: () => {},
    setCombatSpeed: () => {},
    setTextSpeed: () => {},
    setAutoAdvance: () => {},
});

export const usePreferences = () => useContext(PreferencesContext);

export const PreferencesProvider = ({ children }) => {
    const initial = loadPreferences();

    const [musicVolume, setMusicVolume] = useState(initial.musicVolume);
    const [sfxVolume, setSfxVolume] = useState(initial.sfxVolume);
    const [isMusicMuted, setIsMusicMuted] = useState(initial.isMusicMuted);
    const [isSfxMuted, setIsSfxMuted] = useState(initial.isSfxMuted);
    const [combatSpeed, setCombatSpeed] = useState(initial.combatSpeed);
    const [textSpeed, setTextSpeed] = useState(initial.textSpeed);
    const [autoAdvance, setAutoAdvance] = useState(initial.autoAdvance);

    useEffect(() => {
        savePreferences({
            musicVolume,
            sfxVolume,
            isMusicMuted,
            isSfxMuted,
            combatSpeed,
            textSpeed,
            autoAdvance,
        });
    }, [musicVolume, sfxVolume, isMusicMuted, isSfxMuted, combatSpeed, textSpeed, autoAdvance]);

    const value = {
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
        setAutoAdvance,
    };

    return (
        <PreferencesContext.Provider value={value}>
            {children}
        </PreferencesContext.Provider>
    );
};
