import React, { createContext, useContext, useState, useRef, useEffect, useCallback } from 'react';

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
        isSfxMuted: false
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
    'fanfare': getAssetPath('/assets/sounds/bgm_fanfare.wav'),
    'memory_flash': getAssetPath('/assets/sounds/memory_flash.mp3'),
    'mineral_pools': getAssetPath('/assets/sounds/bgm_mineral_pools.wav'),
    'dream_space': getAssetPath('/assets/sounds/bgm_dream_space.wav'),
};

export const AudioProvider = ({ children }) => {
    // Load initial preferences from localStorage
    const initialPrefs = loadAudioPreferences();

    const [musicVolume, setMusicVolume] = useState(initialPrefs.musicVolume);
    const [sfxVolume, setSfxVolume] = useState(initialPrefs.sfxVolume);
    const [isMusicMuted, setIsMusicMuted] = useState(initialPrefs.isMusicMuted);
    const [isSfxMuted, setIsSfxMuted] = useState(initialPrefs.isSfxMuted);
    const [currentBGM, setCurrentBGM] = useState(null);

    const bgmRef = useRef(new Audio());
    const trackProgress = useRef({}); // Stores currentTime for each track ID
    const fadeIntervalRef = useRef(null);
    const activeSFXRef = useRef(new Set());
    // Ref mirrors currentBGM state so playBGM/stopBGM can read it without
    // closing over state (which would force new function references on every
    // track change and trigger unrelated useEffects in consumers).
    const currentBGMRef = useRef(null);

    // Save preferences whenever they change
    useEffect(() => {
        saveAudioPreferences({
            musicVolume,
            sfxVolume,
            isMusicMuted,
            isSfxMuted
        });
    }, [musicVolume, sfxVolume, isMusicMuted, isSfxMuted]);

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
    }, [isMusicMuted, musicVolume]);

    const stopBGM = useCallback(() => {
        if (currentBGMRef.current) {
            trackProgress.current[currentBGMRef.current] = bgmRef.current.currentTime;
        }
        bgmRef.current.pause();
        currentBGMRef.current = null;
        setCurrentBGM(null);
    }, []);

    const playSFX = useCallback((sfxName) => {
        const path = getAssetPath(`/assets/sounds/sfx_${sfxName}.wav`);
        const audio = new Audio(path);
        audio.volume = isSfxMuted ? 0 : sfxVolume;
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
            bgmRef.current.loop = true;
            bgmRef.current.onended = null;
            if (previousBGM && previousBGM !== trackName
                    && currentBGMRef.current === trackName) {
                playBGM(previousBGM);
            }
        };
    }, [isMusicMuted, musicVolume, playBGM]);

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
        currentBGM
    };

    return (
        <AudioContext.Provider value={value}>
            {children}
        </AudioContext.Provider>
    );
};
