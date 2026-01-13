import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AudioProvider, useAudio } from './AudioContext';
import React from 'react';

// Mock Audio constructor
class MockAudio {
    constructor() {
        this.play = vi.fn().mockResolvedValue();
        this.pause = vi.fn();
        this.src = '';
        this.volume = 1;
        this.loop = false;
        this.currentTime = 0;
    }
}
global.Audio = MockAudio;

const TestComponent = () => {
    const { playBGM, stopBGM, playSFX, musicVolume, sfxVolume } = useAudio();
    return (
        <div>
            <button onClick={() => playBGM('adventure')}>Play BGM</button>
            <button onClick={() => stopBGM()}>Stop BGM</button>
            <button onClick={() => playSFX('click')}>Play SFX</button>
            <div data-testid="music-volume">{musicVolume}</div>
            <div data-testid="sfx-volume">{sfxVolume}</div>
        </div>
    );
};

describe('AudioContext', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        localStorage.clear();
    });

    it('provides music and sfx controls', () => {
        render(
            <AudioProvider>
                <TestComponent />
            </AudioProvider>
        );

        expect(screen.getByTestId('music-volume').textContent).toBe('0.5');
        expect(screen.getByTestId('sfx-volume').textContent).toBe('0.5');
    });

    it('plays and stops BGM', () => {
        render(
            <AudioProvider>
                <TestComponent />
            </AudioProvider>
        );

        fireEvent.click(screen.getByText('Play BGM'));
        fireEvent.click(screen.getByText('Stop BGM'));
    });

    it('loads preferences from localStorage', () => {
        const prefs = {
            musicVolume: 0.8,
            sfxVolume: 0.2,
            isMusicMuted: true,
            isSfxMuted: false
        };
        localStorage.setItem('audioPreferences', JSON.stringify(prefs));

        render(
            <AudioProvider>
                <TestComponent />
            </AudioProvider>
        );

        expect(screen.getByTestId('music-volume').textContent).toBe('0.8');
        expect(screen.getByTestId('sfx-volume').textContent).toBe('0.2');
    });
});
