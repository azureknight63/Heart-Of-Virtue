import React, { createContext, useContext, useState, useRef, useEffect } from 'react';

const AudioContext = createContext();

export const useAudio = () => useContext(AudioContext);

export const AudioProvider = ({ children }) => {
    const [volume, setVolume] = useState(0.5);
    const [isMuted, setIsMuted] = useState(false);
    const [currentBGM, setCurrentBGM] = useState(null);

    const bgmRef = useRef(new Audio());
    const sfxPool = useRef({});

    useEffect(() => {
        bgmRef.current.loop = true;
        bgmRef.current.volume = isMuted ? 0 : volume;
    }, [volume, isMuted]);

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
        audio.volume = isMuted ? 0 : volume;
        audio.play().catch(e => console.warn("SFX play failed:", e));
    };

    const value = {
        playBGM,
        stopBGM,
        playSFX,
        volume,
        setVolume,
        isMuted,
        setIsMuted,
        currentBGM
    };

    return (
        <AudioContext.Provider value={value}>
            {children}
        </AudioContext.Provider>
    );
};
