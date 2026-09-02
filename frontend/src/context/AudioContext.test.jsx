import { render, screen, fireEvent, act, renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.unmock('./AudioContext');
import { AudioProvider, useAudio } from './AudioContext';
import React from 'react';

// Mock Audio constructor
class MockAudio {
    // The real HTMLAudioElement takes the source URL as a constructor argument,
    // and playSFX/playSting rely on that form (`new Audio(path)`). The mock used
    // to drop it and hardcode `src = ''`, so no test could ever prove an SFX
    // loaded the right file — every assertion about which sound plays was
    // unprovable by construction.
    constructor(src = '') {
        this.play = vi.fn().mockResolvedValue();
        this.pause = vi.fn();
        this.src = src;
        this.volume = 1;
        this.loop = false;
        this.currentTime = 0;
        this.playbackRate = 1;
        this.preservesPitch = false;
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
        // This test had NO assertions at all — it clicked both buttons and
        // ended. Every line of playBGM/stopBGM could have been deleted and it
        // would still have passed. It now pins what those two actually do to
        // the shared <audio> element: load the track, start it, and on stop
        // pause it and clear the current-track state.
        render(
            <AudioProvider>
                <TestComponent />
            </AudioProvider>
        );
        const bgmElement = global.__audioInstances[0];

        fireEvent.click(screen.getByText('Play BGM'));
        // BGM_MAP resolves the logical track name ('adventure') to a titled
        // file under sounds/bgm/, so assert the path actually loaded rather
        // than the lookup key.
        expect(bgmElement.src).toContain('sounds/bgm/');
        expect(bgmElement.src).toContain('Virtue Quest.mp3');
        expect(bgmElement.play).toHaveBeenCalledTimes(1);

        fireEvent.click(screen.getByText('Stop BGM'));
        expect(bgmElement.pause).toHaveBeenCalledTimes(1);

        // currentBGM was reset, so re-playing the same track is not swallowed
        // by playBGM's `if (currentBGMRef.current === trackName) return` guard.
        fireEvent.click(screen.getByText('Play BGM'));
        expect(bgmElement.play).toHaveBeenCalledTimes(2);
    });

    it('ignores a request to play the track that is already playing', () => {
        // The early-return guard is what stops a re-render from restarting the
        // map theme from the top on every poll.
        render(
            <AudioProvider>
                <TestComponent />
            </AudioProvider>
        );
        const bgmElement = global.__audioInstances[0];

        fireEvent.click(screen.getByText('Play BGM'));
        fireEvent.click(screen.getByText('Play BGM'));

        expect(bgmElement.play).toHaveBeenCalledTimes(1);
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
        expect(screen.getByTestId('sfx-volume').textContent).toBe('0.5');
        // Naming the message and the payload: a bare toHaveBeenCalled() passed
        // even when the warning came from an unrelated code path.
        expect(warnSpy).toHaveBeenCalledWith('Failed to load audio preferences:', expect.any(SyntaxError));
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
        const bgmElement = global.__audioInstances[0];
        const timeAfterFirstPlay = bgmElement.currentTime;
        act(() => { result.current.playBGM('battle'); });

        // The old assertion (`currentBGM === 'battle'`) held even if the second
        // call restarted the track from 0 — which is the actual bug the guard
        // exists to prevent, since GamePage re-runs its BGM effect on every poll.
        expect(bgmElement.play).toHaveBeenCalledTimes(1);
        expect(bgmElement.currentTime).toBe(timeAfterFirstPlay);
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

    it('restores looping when a new BGM takes over mid-sting', () => {
        vi.useFakeTimers();
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playSting('fanfare'); });
        const bgmEl = global.__audioInstances[0];
        expect(bgmEl.loop).toBe(false);

        // A track change during the sting: the sting's own onended would bail
        // out (its currentBGM guard fails), so switchTrack has to do the reset —
        // otherwise the incoming track plays once and the map goes silent.
        act(() => {
            result.current.playBGM('battle');
            vi.advanceTimersByTime(2000);
        });

        expect(bgmEl.loop).toBe(true);
        expect(bgmEl.onended).toBeNull();
        vi.useRealTimers();
    });

    it('restores looping when the BGM is stopped mid-sting', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playSting('fanfare'); });
        const bgmEl = global.__audioInstances[0];
        expect(bgmEl.loop).toBe(false);

        act(() => { result.current.stopBGM(); });

        expect(bgmEl.loop).toBe(true);
        expect(bgmEl.onended).toBeNull();
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

        const bgmInstance = global.__audioInstances.find(a => a.src.includes('Crossing Blades.mp3'));
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
        // Pin the whole filename, not "some element mentions it": a fallback
        // that built `bgm_custom_track` without the `.wav` extension, or under
        // the wrong directory, would 404 in the browser and still pass a
        // substring check.
        const instance = global.__audioInstances.find(a => a.src.includes('bgm_custom_track'));
        expect(instance).toBeDefined();
        expect(instance.src).toMatch(/\/assets\/sounds\/bgm_custom_track\.wav$/);
        expect(instance.play).toHaveBeenCalledTimes(1);
    });

    it('builds a fallback path for a sting not in BGM_MAP', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playSting('custom_sting'); });
        const instance = global.__audioInstances.find(a => a.src.includes('bgm_custom_sting'));
        expect(instance).toBeDefined();
        expect(instance.src).toMatch(/\/assets\/sounds\/bgm_custom_sting\.wav$/);
        // A sting is one-shot: it must clear `loop` on the shared element.
        expect(instance.loop).toBe(false);
    });

    it('mutes SFX volume when isSfxMuted is set', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        // The old assertion was `isSfxMuted === true` — i.e. it re-read the
        // state it had just set, and would have passed with the mute flag
        // ignored by playSFX entirely. What matters is the element's volume.
        act(() => { result.current.setIsSfxMuted(true); });
        act(() => { result.current.playSFX('click'); });
        const muted = global.__audioInstances[global.__audioInstances.length - 1];
        expect(muted.src).toContain('sounds/sfx/click.wav');
        expect(muted.volume).toBe(0);
        expect(muted.play).toHaveBeenCalledTimes(1);

        // Unmuting restores the configured sfxVolume on the NEXT cue.
        act(() => { result.current.setIsSfxMuted(false); });
        act(() => { result.current.setSfxVolume(0.3); });
        act(() => { result.current.playSFX('click'); });
        const unmuted = global.__audioInstances[global.__audioInstances.length - 1];
        expect(unmuted).not.toBe(muted);
        expect(unmuted.volume).toBe(0.3);
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

    it('wires an onended cleanup handler onto each SFX instance', () => {
        // `activeSFXRef` is read by the concurrency cap (see the eviction
        // test), so onended's removal now has an observable consequence: an
        // ended cue no longer counts toward the cap. This test pins that the
        // handler is installed on the right instance and is safe to fire more
        // than once, which is what a browser can do on seek/replay.
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playSFX('click'); });
        const sfxInstance = global.__audioInstances[global.__audioInstances.length - 1];

        expect(typeof sfxInstance.onended).toBe('function');
        expect(sfxInstance.src).toContain('sounds/sfx/click.wav');
        sfxInstance.onended();
        sfxInstance.onended();
        // Double-firing must not resurrect playback or raise.
        expect(sfxInstance.play).toHaveBeenCalledTimes(1);
    });

    it('caps concurrent one-shot SFX elements, dropping the oldest', () => {
        // A layered impact burst (or a stuck onended) must not pile up an
        // unbounded number of live media elements: past the cap the oldest
        // still-active one-shot is paused and released before a new one starts.
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => {
            for (let i = 0; i < 20; i++) result.current.playSFX('attack_hit');
        });

        // Instance 0 is the provider's shared BGM element; SFX start at 1.
        const sfx = global.__audioInstances.slice(1);
        expect(sfx).toHaveLength(20);
        const paused = sfx.filter((a) => a.pause.mock.calls.length > 0);
        expect(paused).toHaveLength(4); // 20 played, cap 16 → 4 oldest evicted
        expect(paused).toEqual(sfx.slice(0, 4)); // oldest-first, never the newest
    });

    it('defaults SFX playbackRate to 1x with pitch preserved', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playSFX('click'); });
        const sfxInstance = global.__audioInstances[global.__audioInstances.length - 1];

        expect(sfxInstance.playbackRate).toBe(1);
        expect(sfxInstance.preservesPitch).toBe(true);
    });

    it('sets playbackRate from the passed combat-speed multiplier (issue #460)', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playSFX('attack_swipe', 2); });
        const sfxInstance = global.__audioInstances[global.__audioInstances.length - 1];

        expect(sfxInstance.playbackRate).toBe(2);
        expect(sfxInstance.preservesPitch).toBe(true);
    });

    it('normalizes an invalid speed to 1x rather than setting a zero/negative playbackRate', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playSFX('attack_swipe', 0); });
        expect(global.__audioInstances[global.__audioInstances.length - 1].playbackRate).toBe(1);

        act(() => { result.current.playSFX('attack_swipe', -2); });
        expect(global.__audioInstances[global.__audioInstances.length - 1].playbackRate).toBe(1);
    });

    it('defaults combatSpeed to 1x and persists changes via setCombatSpeed', () => {
        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        expect(result.current.combatSpeed).toBe(1);

        act(() => { result.current.setCombatSpeed(1.5); });
        expect(result.current.combatSpeed).toBe(1.5);

        const saved = JSON.parse(localStorage.getItem('audioPreferences'));
        expect(saved.combatSpeed).toBe(1.5);
    });

    it('normalizes a corrupted stored combatSpeed (0/negative/non-numeric) to the 1x default', () => {
        localStorage.setItem('audioPreferences', JSON.stringify({
            musicVolume: 0.5,
            sfxVolume: 0.5,
            isMusicMuted: false,
            isSfxMuted: false,
            combatSpeed: 0
        }));

        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        expect(result.current.combatSpeed).toBe(1);
    });

    it('loads combatSpeed from localStorage', () => {
        localStorage.setItem('audioPreferences', JSON.stringify({
            musicVolume: 0.5,
            sfxVolume: 0.5,
            isMusicMuted: false,
            isSfxMuted: false,
            combatSpeed: 2
        }));

        const wrapper = ({ children }) => <AudioProvider>{children}</AudioProvider>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        expect(result.current.combatSpeed).toBe(2);
    });

    it('exposes no-op defaults when used outside an AudioProvider', () => {
        const { result } = renderHook(() => useAudio());

        expect(result.current.musicVolume).toBe(0.5);
        expect(result.current.sfxVolume).toBe(0.5);
        expect(result.current.isMusicMuted).toBe(false);
        expect(result.current.isSfxMuted).toBe(false);
        expect(result.current.currentBGM).toBeNull();
        expect(result.current.combatSpeed).toBe(1);

        // These are no-ops, so "doesn't throw" was the whole assertion — but a
        // no-op that silently constructs an <audio> element, or that mutates
        // the context it was told not to, is exactly the leak this default
        // exists to prevent. Assert both halves.
        global.__audioInstances = [];
        act(() => {
            result.current.playBGM('adventure');
            result.current.stopBGM();
            result.current.playSFX('click');
            result.current.playSting('memory_flash');
            result.current.setMusicVolume(0.2);
            result.current.setSfxVolume(0.2);
            result.current.setIsMusicMuted(true);
            result.current.setIsSfxMuted(true);
            result.current.setCombatSpeed(2);
        });

        expect(global.__audioInstances).toHaveLength(0);
        expect(result.current.musicVolume).toBe(0.5);
        expect(result.current.sfxVolume).toBe(0.5);
        expect(result.current.isMusicMuted).toBe(false);
        expect(result.current.isSfxMuted).toBe(false);
        expect(result.current.combatSpeed).toBe(1);
        expect(result.current.currentBGM).toBeNull();
    });
});
