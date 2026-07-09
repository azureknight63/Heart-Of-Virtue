import { render, screen, fireEvent, act, renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.unmock('./AudioContext');
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
        global.__audioInstances = global.__audioInstances || [];
        global.__audioInstances.push(this);
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
        global.__audioInstances = [];
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

    it('playBGM reference stays stable after switching tracks (regression: battle BGM override bug)', () => {
        // When playBGM('memory_flash') is called it used to update currentBGM state,
        // which recreated the playBGM function reference, which retriggered the BGM
        // useEffect in GamePage (mode === 'combat') and called playBGM('battle') again.
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        const firstRef = result.current.playBGM;

        act(() => { result.current.playBGM('battle'); });
        const afterBattle = result.current.playBGM;

        act(() => { result.current.playBGM('memory_flash'); });
        const afterMemoryFlash = result.current.playBGM;

        // Reference must be the same object throughout — any change would
        // retrigger consumer effects that list playBGM as a dependency.
        expect(afterBattle).toBe(firstRef);
        expect(afterMemoryFlash).toBe(firstRef);
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

    it('falls back to defaults when stored preferences are corrupt JSON', () => {
        localStorage.setItem('audioPreferences', '{not valid json');
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

        render(
            <AudioProvider>
                <TestComponent />
            </AudioProvider>
        );

        expect(screen.getByTestId('music-volume').textContent).toBe('0.5');
        expect(warnSpy).toHaveBeenCalled();
        warnSpy.mockRestore();
    });

    it('does not throw when localStorage.setItem fails while saving preferences', () => {
        const setItemSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
            throw new Error('quota exceeded');
        });
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

        expect(() => {
            render(
                <AudioProvider>
                    <TestComponent />
                </AudioProvider>
            );
        }).not.toThrow();

        expect(warnSpy).toHaveBeenCalledWith('Failed to save audio preferences:', expect.any(Error));
        warnSpy.mockRestore();
        setItemSpy.mockRestore();
    });

    it('does not restart a track that is already playing', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playBGM('battle'); });
        const audioInstance = result.current;
        act(() => { result.current.playBGM('battle'); });

        expect(result.current.currentBGM).toBe('battle');
    });

    it('fades out the current track before switching, then fades in the new one', () => {
        vi.useFakeTimers();
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playBGM('battle'); });
        expect(result.current.currentBGM).toBe('battle');

        // Let the fade-in complete so bgmRef.current.volume > 0, which is the
        // precondition for the fade-OUT branch to trigger on the next switch.
        act(() => { vi.advanceTimersByTime(1000); });

        act(() => { result.current.playBGM('dungeon'); });
        // Still fading out the old track — switch hasn't happened yet.
        expect(result.current.currentBGM).toBe('battle');

        act(() => { vi.advanceTimersByTime(2000); });
        expect(result.current.currentBGM).toBe('dungeon');

        vi.useRealTimers();
    });

    it('plays a sting and restores the previous BGM when it ends', () => {
        vi.useFakeTimers();
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playBGM('battle'); });
        act(() => { vi.advanceTimersByTime(1000); }); // let the fade-in settle
        act(() => { result.current.playSting('fanfare'); });
        expect(result.current.currentBGM).toBe('fanfare');

        // bgmRef.current is created once via useRef(new Audio()) on first render
        // and never replaced, so it's always the first instance constructed —
        // later re-renders also evaluate `new Audio()` but React discards them.
        const bgmEl = global.__audioInstances[0];

        // Simulate the underlying <audio> element firing its native 'ended' event.
        // Restoring the previous BGM fades back in, which runs on a setInterval.
        act(() => {
            bgmEl.onended();
            vi.advanceTimersByTime(1000);
        });

        expect(result.current.currentBGM).toBe('battle');
        vi.useRealTimers();
    });

    it('does not restore the previous BGM if it changed during the sting', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playBGM('battle'); });
        act(() => { result.current.playSting('fanfare'); });
        act(() => { result.current.stopBGM(); });

        const bgmEl = global.__audioInstances[0];
        act(() => {
            bgmEl.onended?.();
        });

        expect(result.current.currentBGM).toBeNull();
    });

    it('mutes BGM volume when isMusicMuted is set', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.setIsMusicMuted(true); });
        expect(result.current.isMusicMuted).toBe(true);
    });

    it('silences BGM playback when isMusicMuted is set', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.setIsMusicMuted(true); });
        act(() => { result.current.playBGM('battle'); });

        const bgmInstance = global.__audioInstances.find(a => a.src.includes('bgm_battle'));
        expect(bgmInstance.volume).toBe(0);
    });

    it('silences the sting when isMusicMuted is set', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.setIsMusicMuted(true); });
        act(() => { result.current.playSting('fanfare'); });

        const stingInstance = global.__audioInstances.find(a => a.src.includes('bgm_fanfare'));
        expect(stingInstance.volume).toBe(0);
    });

    it('builds a fallback path for a BGM track not in BGM_MAP', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playBGM('custom_track'); });
        const instance = global.__audioInstances.find(a => a.src.includes('bgm_custom_track'));
        expect(instance).toBeDefined();
    });

    it('builds a fallback path for a sting not in BGM_MAP', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playSting('custom_sting'); });
        const instance = global.__audioInstances.find(a => a.src.includes('bgm_custom_sting'));
        expect(instance).toBeDefined();
    });

    it('mutes SFX volume when isSfxMuted is set', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.setIsSfxMuted(true); });
        act(() => { result.current.playSFX('click'); });
        expect(result.current.isSfxMuted).toBe(true);
    });

    it('updates music and sfx volume via setters', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.setMusicVolume(0.9); });
        act(() => { result.current.setSfxVolume(0.1); });

        expect(result.current.musicVolume).toBe(0.9);
        expect(result.current.sfxVolume).toBe(0.1);
    });

    it('warns but does not throw when SFX playback fails', async () => {
        const originalAudio = global.Audio;
        global.Audio = class {
            constructor() {
                this.play = vi.fn().mockRejectedValue(new Error('blocked'));
                this.pause = vi.fn();
                this.src = '';
                this.volume = 1;
                this.loop = false;
                this.currentTime = 0;
            }
        };
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        await act(async () => {
            result.current.playSFX('click');
            await Promise.resolve();
            await Promise.resolve();
        });

        expect(warnSpy).toHaveBeenCalledWith('SFX play failed:', expect.any(Error));
        warnSpy.mockRestore();
        global.Audio = originalAudio;
    });

    it('removes an SFX instance from the active set once playback ends', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playSFX('click'); });
        const sfxInstance = global.__audioInstances[global.__audioInstances.length - 1];

        expect(typeof sfxInstance.onended).toBe('function');
        expect(() => sfxInstance.onended()).not.toThrow();
    });

    it('exposes no-op defaults when used outside an AudioProvider', () => {
        const { result } = renderHook(() => useAudio());

        expect(result.current.musicVolume).toBe(0.5);
        expect(result.current.sfxVolume).toBe(0.5);
        expect(result.current.isMusicMuted).toBe(false);
        expect(result.current.isSfxMuted).toBe(false);
        expect(result.current.currentBGM).toBeNull();

        expect(() => result.current.playBGM('adventure')).not.toThrow();
        expect(() => result.current.stopBGM()).not.toThrow();
        expect(() => result.current.playSFX('click')).not.toThrow();
        expect(() => result.current.playSting('memory_flash')).not.toThrow();
        expect(() => result.current.setMusicVolume(0.2)).not.toThrow();
        expect(() => result.current.setSfxVolume(0.2)).not.toThrow();
        expect(() => result.current.setIsMusicMuted(true)).not.toThrow();
        expect(() => result.current.setIsSfxMuted(true)).not.toThrow();
    });
});
