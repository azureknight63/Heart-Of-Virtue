import React, { createContext, useContext, useState, useRef, useEffect, useCallback } from 'react';
import { DEFAULT_COMBAT_SPEED, normalizeSpeed } from '../utils/combatTiming';

const AudioContext = createContext({
    playBGM: () => {},
    stopBGM: () => {},
    playSFX: () => {},
    playSting: () => {},
    musicVolume: 0.5,
    setMusicVolume: () => {},
    sfxVolume: 0.5,
    setSfxVolume: () => {},
    isMusicMuted: false,
    setIsMusicMuted: () => {},
    isSfxMuted: false,
    setIsSfxMuted: () => {},
    currentBGM: null,
    combatSpeed: DEFAULT_COMBAT_SPEED,
    setCombatSpeed: () => {},
});

export const useAudio = () => useContext(AudioContext);

// Helper functions for localStorage
const loadAudioPreferences = () => {
    try {
        const saved = localStorage.getItem('audioPreferences');
        if (saved) {
            return JSON.parse(saved);
        }
    } catch (error) {
        console.warn('Failed to load audio preferences:', error);
    }
    return {
        musicVolume: 0.5,
        sfxVolume: 0.5,
        isMusicMuted: false,
        isSfxMuted: false,
        combatSpeed: DEFAULT_COMBAT_SPEED
    };
};

const saveAudioPreferences = (preferences) => {
    try {
        localStorage.setItem('audioPreferences', JSON.stringify(preferences));
    } catch (error) {
        console.warn('Failed to save audio preferences:', error);
    }
};

const getAssetPath = (path) => {
    const base = import.meta.env.BASE_URL.replace(/\/$/, '');
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    return `${base}${cleanPath}`;
};

const BGM_MAP = {
    'adventure': getAssetPath('/assets/sounds/bgm_adventure.wav'),
    'battle': getAssetPath('/assets/sounds/bgm_battle.mp3'),
    'dark_grotto': getAssetPath('/assets/sounds/dark_grotto.mp3'),
    'dungeon': getAssetPath('/assets/sounds/bgm_dungeon.mp3'),
    'eastern_descent': getAssetPath('/assets/sounds/bgm_eastern_descent.mp3'),
    'fanfare': getAssetPath('/assets/sounds/bgm_fanfare.wav'),
    'grondia': getAssetPath('/assets/sounds/bgm_grondia.mp3'),
    'memory_flash': getAssetPath('/assets/sounds/memory_flash.mp3'),
    'mineral_pools': getAssetPath('/assets/sounds/bgm_mineral_pools.wav'),
    'nomad_camp': getAssetPath('/assets/sounds/bgm_nomad_camp.mp3'),
    'jambos_tent': getAssetPath('/assets/sounds/bgm_jambos_tent.mp3'),
    'dream_space': getAssetPath('/assets/sounds/bgm_dream_space.wav'),
};

export const AudioProvider = ({ children }) => {
    // Load initial preferences from localStorage
    const initialPrefs = loadAudioPreferences();

    const [musicVolume, setMusicVolume] = useState(initialPrefs.musicVolume);
    const [sfxVolume, setSfxVolume] = useState(initialPrefs.sfxVolume);
    const [isMusicMuted, setIsMusicMuted] = useState(initialPrefs.isMusicMuted);
    const [isSfxMuted, setIsSfxMuted] = useState(initialPrefs.isSfxMuted);
    const [combatSpeed, setCombatSpeed] = useState(normalizeSpeed(initialPrefs.combatSpeed));
    const [currentBGM, setCurrentBGM] = useState(null);

    const bgmRef = useRef(new Audio());
    const trackProgress = useRef({}); // Stores currentTime for each track ID
    const fadeIntervalRef = useRef(null);
    const activeSFXRef = useRef(new Set());
    // Ref mirrors currentBGM state so playBGM/stopBGM can read it without
    // closing over state (which would force new function references on every
    // track change and trigger unrelated useEffects in consumers).
    const currentBGMRef = useRef(null);

    /**
     * Return the shared audio element to its looping-BGM state.
     *
     * A sting borrows the same element, setting `loop = false` and an `onended`
     * handler. Leaving either behind means the next BGM plays exactly once and
     * the map goes silent — the bug this reset exists to prevent. Three
     * separate paths need it (track switch, explicit stop, and the sting's own
     * `onended`), and it lived as a copy-pasted pair of lines in all three, so
     * a future addition to the reset would have had three places to miss.
     */
    const clearStingState = useCallback(() => {
        bgmRef.current.loop = true;
        bgmRef.current.onended = null;
    }, []);

    // Save preferences whenever they change
    useEffect(() => {
        saveAudioPreferences({
            musicVolume,
            sfxVolume,
            isMusicMuted,
            isSfxMuted,
            combatSpeed
        });
    }, [musicVolume, sfxVolume, isMusicMuted, isSfxMuted, combatSpeed]);

    useEffect(() => {
        bgmRef.current.loop = true;
        // Only update volume directly if not currently fading
        if (!fadeIntervalRef.current) {
            bgmRef.current.volume = isMusicMuted ? 0 : musicVolume;
        }
    }, [musicVolume, isMusicMuted]);

    const playBGM = useCallback((trackName) => {
        if (currentBGMRef.current === trackName) return;

        const targetVolume = isMusicMuted ? 0 : musicVolume;
        const fadeStep = 0.05;
        const fadeInterval = 50;

        // Clear any existing fade
        if (fadeIntervalRef.current) {
            clearInterval(fadeIntervalRef.current);
        }

        const switchTrack = () => {
            // A sting leaves the shared element non-looping with an onended
            // handler that bails out once another track takes over. Reset both
            // here or the next BGM plays exactly once and the map goes silent.
            clearStingState();

            // Save progress of current track
            if (currentBGMRef.current) {
                trackProgress.current[currentBGMRef.current] = bgmRef.current.currentTime;
            }

            const path = BGM_MAP[trackName] || getAssetPath(`/assets/sounds/bgm_${trackName}.wav`);
            bgmRef.current.src = path;

            // Restore progress
            const savedTime = trackProgress.current[trackName] || 0;
            bgmRef.current.currentTime = savedTime;

            bgmRef.current.play().catch(e => console.warn("Audio play failed (user interaction needed):", e));
            currentBGMRef.current = trackName;
            setCurrentBGM(trackName);

            // Fade In
            bgmRef.current.volume = 0;
            fadeIntervalRef.current = setInterval(() => {
                const nextVolume = Math.min(bgmRef.current.volume + fadeStep, targetVolume);
                bgmRef.current.volume = nextVolume;
                if (nextVolume >= targetVolume) {
                    clearInterval(fadeIntervalRef.current);
                    fadeIntervalRef.current = null;
                }
            }, fadeInterval);
        };

        // Fade Out current track if playing
        if (currentBGMRef.current && bgmRef.current.volume > 0) {
            fadeIntervalRef.current = setInterval(() => {
                const nextVolume = Math.max(bgmRef.current.volume - fadeStep, 0);
                bgmRef.current.volume = nextVolume;
                if (nextVolume <= 0) {
                    clearInterval(fadeIntervalRef.current);
                    switchTrack();
                }
            }, fadeInterval);
        } else {
            switchTrack();
        }
    }, [isMusicMuted, musicVolume, clearStingState]);

    const stopBGM = useCallback(() => {
        if (currentBGMRef.current) {
            trackProgress.current[currentBGMRef.current] = bgmRef.current.currentTime;
        }
        bgmRef.current.pause();
        // Same reset as switchTrack: never leave a sting's one-shot state
        // stranded on the shared element for whatever plays next.
        clearStingState();
        currentBGMRef.current = null;
        setCurrentBGM(null);
    }, [clearStingState]);

    // `speed` (issue #460): combat-speed multiplier for this one-shot cue.
    // playbackRate scales tempo; preservesPitch keeps it from sounding
    // chipmunked/slowed — browser-native pitch-preserving time-stretch, no DSP.
    const playSFX = useCallback((sfxName, speed = 1) => {
        const path = getAssetPath(`/assets/sounds/sfx_${sfxName}.wav`);
        const audio = new Audio(path);
        audio.volume = isSfxMuted ? 0 : sfxVolume;
        // normalizeSpeed guards against a corrupted/garbage combatSpeed (e.g. a
        // hand-edited localStorage value of 0 or negative) — playbackRate must
        // stay a positive finite number or HTMLMediaElement rejects the set.
        audio.playbackRate = normalizeSpeed(speed);
        audio.preservesPitch = true;
        audio.webkitPreservesPitch = true;
        audio.mozPreservesPitch = true;
        activeSFXRef.current.add(audio);
        audio.onended = () => activeSFXRef.current.delete(audio);
        audio.play().catch(e => {
            console.warn("SFX play failed:", e);
            activeSFXRef.current.delete(audio);
        });
    }, [isSfxMuted, sfxVolume]);

    const playSting = useCallback((trackName) => {
        const previousBGM = currentBGMRef.current;
        const path = BGM_MAP[trackName] || getAssetPath(`/assets/sounds/bgm_${trackName}.wav`);

        // Save progress of current track before switching
        if (currentBGMRef.current) {
            trackProgress.current[currentBGMRef.current] = bgmRef.current.currentTime;
        }

        bgmRef.current.loop = false; // One-shot
        bgmRef.current.src = path;
        bgmRef.current.currentTime = 0;
        bgmRef.current.volume = isMusicMuted ? 0 : musicVolume;
        bgmRef.current.play().catch(e => console.warn("Sting play failed:", e));
        currentBGMRef.current = trackName;
        setCurrentBGM(trackName);

        // When sting ends, restore loop and switch back to previous BGM.
        // Guard: only restore if no external track switch happened during the sting
        // (i.e., currentBGMRef still points to this sting track).
        bgmRef.current.onended = () => {
            clearStingState();
            if (previousBGM && previousBGM !== trackName
                    && currentBGMRef.current === trackName) {
                playBGM(previousBGM);
            }
        };
    }, [isMusicMuted, musicVolume, playBGM, clearStingState]);

    const value = {
        playBGM,
        stopBGM,
        playSFX,
        playSting,
        musicVolume,
        setMusicVolume,
        sfxVolume,
        setSfxVolume,
        isMusicMuted,
        setIsMusicMuted,
        isSfxMuted,
        setIsSfxMuted,
        currentBGM,
        combatSpeed,
        setCombatSpeed
    };

    return (
        <AudioContext.Provider value={value}>
            {children}
        </AudioContext.Provider>
    );
};
