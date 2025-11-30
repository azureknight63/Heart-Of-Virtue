import React, { createContext, useContext, useState, useRef, useEffect } from 'react';

const AudioContext = createContext();

export const useAudio = () => useContext(AudioContext);

export const AudioProvider = ({ children }) => {
    const [musicVolume, setMusicVolume] = useState(0.5);
    const [sfxVolume, setSfxVolume] = useState(0.5);
    const [isMusicMuted, setIsMusicMuted] = useState(false);
    const [isSfxMuted, setIsSfxMuted] = useState(false);
    const [currentBGM, setCurrentBGM] = useState(null);

    const bgmRef = useRef(new Audio());
    const sfxPool = useRef({});

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
