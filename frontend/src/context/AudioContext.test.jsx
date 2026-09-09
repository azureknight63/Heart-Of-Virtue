import { render, screen, fireEvent, act, renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.unmock('./AudioContext');
vi.unmock('./PreferencesContext');
import { AudioProvider, useAudio } from './AudioContext';
import { PreferencesProvider } from './PreferencesContext';
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

/**
 * AudioProvider reads its volumes from PreferencesProvider, so every render
 * here nests the pair. Preferences are seeded through localStorage — the same
 * route a real session takes — rather than by injecting a fake context, so
 * these tests exercise the wiring between the two providers instead of
 * assuming it.
 */
const Providers = ({ children }) => (
    <PreferencesProvider>
        <AudioProvider>{children}</AudioProvider>
    </PreferencesProvider>
);

/**
 * Seed a preference the way a returning player's browser does.
 *
 * Mutes and volumes are no longer AudioProvider's own state, so a test cannot
 * set one through `useAudio()`. Writing the stored blob before render is the
 * honest substitute: it goes through `loadPreferences`, so these tests keep
 * proving that a stored mute actually reaches the media element rather than
 * that a hand-injected context value does.
 */
const withPreferences = (prefs) =>
    localStorage.setItem('audioPreferences', JSON.stringify(prefs));

const TestComponent = () => {
    const { playBGM, stopBGM, playSFX } = useAudio();
    return (
        <div>
            <button onClick={() => playBGM('adventure')}>Play BGM</button>
            <button onClick={() => stopBGM()}>Stop BGM</button>
            <button onClick={() => playSFX('click')}>Play SFX</button>
        </div>
    );
};

describe('AudioContext', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        localStorage.clear();
        global.__audioInstances = [];
    });

    it('plays and stops BGM', () => {
        // This test had NO assertions at all — it clicked both buttons and
        // ended. Every line of playBGM/stopBGM could have been deleted and it
        // would still have passed. It now pins what those two actually do to
        // the shared <audio> element: load the track, start it, and on stop
        // pause it and clear the current-track state.
        render(
            <Providers>
                <TestComponent />
            </Providers>
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

    it.each([
        ['jambos_tent', 'Jambo Heals U.mp3'],
        ['iron_and_oath', 'We Got The Gear.mp3'],
    ])('loads the titled asset for the %s location track', (trackName, filename) => {
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playBGM(trackName); });

        const bgmElement = global.__audioInstances[0];
        expect(bgmElement.src).toContain(`sounds/bgm/${filename}`);
        expect(bgmElement.play).toHaveBeenCalledTimes(1);
    });

    it('ignores a request to play the track that is already playing', () => {
        // The early-return guard is what stops a re-render from restarting the
        // map theme from the top on every poll.
        render(
            <Providers>
                <TestComponent />
            </Providers>
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
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
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

    it('does not restart a track that is already playing', () => {
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
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
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
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
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
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
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
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
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playSting('fanfare'); });
        const bgmEl = global.__audioInstances[0];
        expect(bgmEl.loop).toBe(false);

        act(() => { result.current.stopBGM(); });

        expect(bgmEl.loop).toBe(true);
        expect(bgmEl.onended).toBeNull();
    });

    it('does not restore the previous BGM if it changed during the sting', () => {
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
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

    it('silences BGM playback when the stored preference is muted', () => {
        withPreferences({ isMusicMuted: true });
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playBGM('battle'); });

        const bgmInstance = global.__audioInstances.find(a => a.src.includes('Crossing Blades.mp3'));
        expect(bgmInstance.volume).toBe(0);
    });

    it('fades a BGM up towards the stored volume when not muted', () => {
        // The positive control for the test above: without it, a provider that
        // silenced everything unconditionally would satisfy the mute test.
        // playBGM fades in from 0, so the observable is that the fade RUNS and
        // climbs, not the volume on the first frame.
        vi.useFakeTimers();
        withPreferences({ isMusicMuted: false, musicVolume: 0.4 });
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playBGM('battle'); });
        act(() => { vi.advanceTimersByTime(1000); });

        const bgmInstance = global.__audioInstances.find(a => a.src.includes('Crossing Blades.mp3'));
        expect(bgmInstance.volume).toBeCloseTo(0.4, 5);
        vi.useRealTimers();
    });

    it('silences the sting when the stored preference is muted', () => {
        withPreferences({ isMusicMuted: true });
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playSting('fanfare'); });

        const stingInstance = global.__audioInstances.find(a => a.src.includes('bgm_fanfare'));
        expect(stingInstance.volume).toBe(0);
    });

    it('builds a fallback path for a BGM track not in BGM_MAP', () => {
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
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
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playSting('custom_sting'); });
        const instance = global.__audioInstances.find(a => a.src.includes('bgm_custom_sting'));
        expect(instance).toBeDefined();
        expect(instance.src).toMatch(/\/assets\/sounds\/bgm_custom_sting\.wav$/);
        // A sting is one-shot: it must clear `loop` on the shared element.
        expect(instance.loop).toBe(false);
    });

    it('mutes SFX volume when the stored preference is muted', () => {
        withPreferences({ isSfxMuted: true });
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        // The old assertion was `isSfxMuted === true` — i.e. it re-read the
        // state it had just set, and would have passed with the mute flag
        // ignored by playSFX entirely. What matters is the element's volume.
        act(() => { result.current.playSFX('click'); });
        const muted = global.__audioInstances[global.__audioInstances.length - 1];
        expect(muted.src).toContain('sounds/sfx/click.wav');
        expect(muted.volume).toBe(0);
        expect(muted.play).toHaveBeenCalledTimes(1);

    });

    it('plays SFX at the stored volume when not muted', () => {
        // The positive control for the test above: a provider that silenced
        // every cue unconditionally would satisfy the mute assertion alone.
        withPreferences({ isSfxMuted: false, sfxVolume: 0.3 });
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playSFX('click'); });

        const cue = global.__audioInstances[global.__audioInstances.length - 1];
        expect(cue.src).toContain('sounds/sfx/click.wav');
        expect(cue.volume).toBe(0.3);
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

        const wrapper = ({ children }) => <Providers>{children}</Providers>;
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
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
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
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
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

    it('fully releases an evicted SFX element: onended detached, src cleared', () => {
        // "Paused and released" must be literal. Leaving `onended` and `src`
        // set keeps the callback closure and the loaded resource pinned to a
        // media element that is only waiting for GC — an evicted element must
        // hold neither.
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => {
            for (let i = 0; i < 17; i++) result.current.playSFX('attack_hit');
        });

        const sfx = global.__audioInstances.slice(1); // instance 0 is BGM
        const evicted = sfx[0];
        expect(evicted.pause).toHaveBeenCalled();
        expect(evicted.onended).toBeNull();
        expect(evicted.src).toBe('');
        // The survivors are untouched.
        const newest = sfx[sfx.length - 1];
        expect(typeof newest.onended).toBe('function');
        expect(newest.src).toContain('sounds/sfx/attack_hit.wav');
    });

    it('defaults SFX playbackRate to 1x with pitch preserved', () => {
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playSFX('click'); });
        const sfxInstance = global.__audioInstances[global.__audioInstances.length - 1];

        expect(sfxInstance.playbackRate).toBe(1);
        expect(sfxInstance.preservesPitch).toBe(true);
    });

    it('sets playbackRate from the passed combat-speed multiplier (issue #460)', () => {
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playSFX('attack_swipe', 2); });
        const sfxInstance = global.__audioInstances[global.__audioInstances.length - 1];

        expect(sfxInstance.playbackRate).toBe(2);
        expect(sfxInstance.preservesPitch).toBe(true);
    });

    it('normalizes an invalid speed to 1x rather than setting a zero/negative playbackRate', () => {
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playSFX('attack_swipe', 0); });
        expect(global.__audioInstances[global.__audioInstances.length - 1].playbackRate).toBe(1);

        act(() => { result.current.playSFX('attack_swipe', -2); });
        expect(global.__audioInstances[global.__audioInstances.length - 1].playbackRate).toBe(1);
    });

    it('exposes no-op defaults when used outside an AudioProvider', () => {
        const { result } = renderHook(() => useAudio());

        expect(result.current.currentBGM).toBeNull();

        // These are no-ops, so "doesn't throw" was the whole assertion — but a
        // no-op that silently constructs an <audio> element, or that mutates
        // the context it was told not to, is exactly the leak this default
        // exists to prevent. Assert both halves. (The preference half of this
        // guard now lives in PreferencesContext.test.jsx, with the setters.)
        global.__audioInstances = [];
        act(() => {
            result.current.playBGM('adventure');
            result.current.stopBGM();
            result.current.playSFX('click');
            result.current.playSting('memory_flash');
        });

        expect(global.__audioInstances).toHaveLength(0);
        expect(result.current.currentBGM).toBeNull();
    });
});
