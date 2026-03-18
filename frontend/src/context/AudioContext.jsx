import React, { createContext, useContext, useState, useRef, useEffect, useCallback } from 'react';

const AudioContext = createContext();

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

const BGM_MAP = {
    'adventure': '/assets/sounds/bgm_adventure.wav',
    'battle': '/assets/sounds/bgm_battle.mp3',
    'dark_grotto': '/assets/sounds/dark_grotto.mp3',
    'dungeon': '/assets/sounds/bgm_dungeon.mp3',
    'fanfare': '/assets/sounds/bgm_fanfare.wav',
    'memory_flash': '/assets/sounds/memory_flash.mp3',
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
        if (currentBGM === trackName) return;

        const targetVolume = isMusicMuted ? 0 : musicVolume;
        const fadeStep = 0.05;
        const fadeInterval = 50;

        // Clear any existing fade
        if (fadeIntervalRef.current) {
            clearInterval(fadeIntervalRef.current);
        }

        const switchTrack = () => {
            // Save progress of current track
            if (currentBGM) {
                trackProgress.current[currentBGM] = bgmRef.current.currentTime;
            }

            const path = BGM_MAP[trackName] || `/assets/sounds/bgm_${trackName}.wav`;
            bgmRef.current.src = path;

            // Restore progress
            const savedTime = trackProgress.current[trackName] || 0;
            bgmRef.current.currentTime = savedTime;

            bgmRef.current.play().catch(e => console.warn("Audio play failed (user interaction needed):", e));
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
        if (currentBGM && bgmRef.current.volume > 0) {
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
    }, [currentBGM, isMusicMuted, musicVolume]);

    const stopBGM = useCallback(() => {
        if (currentBGM) {
            trackProgress.current[currentBGM] = bgmRef.current.currentTime;
        }
        bgmRef.current.pause();
        setCurrentBGM(null);
    }, [currentBGM]);

    const playSFX = useCallback((sfxName) => {
        const path = `/assets/sounds/sfx_${sfxName}.wav`;
        const audio = new Audio(path);
        audio.volume = isSfxMuted ? 0 : sfxVolume;
        audio.play().catch(e => console.warn("SFX play failed:", e));
    }, [isSfxMuted, sfxVolume]);

    const value = {
        playBGM,
        stopBGM,
        playSFX,
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
