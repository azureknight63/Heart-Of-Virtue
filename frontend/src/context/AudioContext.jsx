import React, { createContext, useContext, useState, useRef, useEffect } from 'react';

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

export const AudioProvider = ({ children }) => {
    // Load initial preferences from localStorage
    const initialPrefs = loadAudioPreferences();

    const [musicVolume, setMusicVolume] = useState(initialPrefs.musicVolume);
    const [sfxVolume, setSfxVolume] = useState(initialPrefs.sfxVolume);
    const [isMusicMuted, setIsMusicMuted] = useState(initialPrefs.isMusicMuted);
    const [isSfxMuted, setIsSfxMuted] = useState(initialPrefs.isSfxMuted);
    const [currentBGM, setCurrentBGM] = useState(null);

    const bgmRef = useRef(new Audio());
    const sfxPool = useRef({});

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
        bgmRef.current.volume = isMusicMuted ? 0 : musicVolume;
    }, [musicVolume, isMusicMuted]);

    const playBGM = (trackName) => {
        if (currentBGM === trackName) return;

        const path = `/assets/sounds/bgm_${trackName}.wav`;
        bgmRef.current.src = path;
        bgmRef.current.play().catch(e => console.warn("Audio play failed (user interaction needed):", e));
        setCurrentBGM(trackName);
    };

    const stopBGM = () => {
        bgmRef.current.pause();
        bgmRef.current.currentTime = 0;
        setCurrentBGM(null);
    };

    const playSFX = (sfxName) => {
        const path = `/assets/sounds/sfx_${sfxName}.wav`;
        const audio = new Audio(path);
        audio.volume = isSfxMuted ? 0 : sfxVolume;
        audio.play().catch(e => console.warn("SFX play failed:", e));
    };

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
