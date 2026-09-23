import { render, screen, fireEvent, act, renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.unmock('./AudioContext');
vi.unmock('./PreferencesContext');
import { AudioProvider, useAudio } from './AudioContext';
import { PreferencesProvider, usePreferences } from './PreferencesContext';
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

    it('switches tracks by crossfading, not by fading out first (#662)', () => {
        // This used to pin the sequential fade-out -> swap -> fade-in, i.e.
        // the silence gap #662 removed. The new track now takes over at once
        // on the second pool element while the old one fades beneath it; the
        // overlap itself is pinned in the crossfade suite below.
        vi.useFakeTimers();
        const wrapper = ({ children }) => <Providers>{children}</Providers>;
        const { result } = renderHook(() => useAudio(), { wrapper });

        act(() => { result.current.playBGM('battle'); });
        act(() => { vi.advanceTimersByTime(1000); });

        act(() => { result.current.playBGM('dungeon'); });
        expect(result.current.currentBGM).toBe('dungeon');
        const [first, second] = global.__audioInstances;
        expect(second.src).toContain('bgm_dungeon.mp3');
        expect(first.src).toContain('Crossing Blades.mp3');

        act(() => { vi.advanceTimersByTime(2000); });
        expect(first.src).toBe('');

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

        // The BGM pool is created lazily, once, on first render, so its active
        // slot (where the first track and this sting land) is instance 0.
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

        // Instances 0 and 1 are the provider's BGM crossfade pool; SFX start at 2.
        const sfx = global.__audioInstances.slice(2);
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

        const sfx = global.__audioInstances.slice(2); // instances 0-1 are the BGM pool
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

/**
 * Issue #662: BGM changes on room change / teleport are a true crossfade.
 *
 * The provider keeps a two-element pool. The outgoing track fades out on one
 * element WHILE the incoming track fades in on the other, so there is never a
 * silent gap; the outgoing element is paused and its src released once it
 * reaches zero. Pool instances are the first two constructed Audio objects.
 */
describe('AudioContext BGM crossfade (#662)', () => {
    const wrapper = ({ children }) => <Providers>{children}</Providers>;
    const useBoth = () => ({ audio: useAudio(), prefs: usePreferences() });
    const pool = () => global.__audioInstances.slice(0, 2);
    const playing = () => pool().filter(a => a.src !== '' && a.__playing);

    beforeEach(() => {
        vi.clearAllMocks();
        localStorage.clear();
        global.__audioInstances = [];
        vi.useFakeTimers();
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    // Track pause/play so "is this element audible" is observable.
    const instrument = () => {
        pool().forEach(a => {
            a.__playing = false;
            a.play.mockImplementation(() => { a.__playing = true; return Promise.resolve(); });
            a.pause.mockImplementation(() => { a.__playing = false; });
        });
    };

    it('overlaps the outgoing fade-out with the incoming fade-in on the other element', () => {
        withPreferences({ musicVolume: 0.8 });
        const { result } = renderHook(() => useAudio(), { wrapper });
        instrument();
        const [first, second] = pool();

        act(() => { result.current.playBGM('battle'); });
        act(() => { vi.advanceTimersByTime(2000); });
        expect(first.volume).toBeCloseTo(0.8, 5);

        act(() => { result.current.playBGM('dungeon'); });
        // The incoming track starts on the OTHER element immediately.
        expect(second.src).toContain('bgm_dungeon.mp3');
        expect(second.play).toHaveBeenCalledTimes(1);
        expect(result.current.currentBGM).toBe('dungeon');

        // A few ticks in, both are audible at once: no silence gap.
        act(() => { vi.advanceTimersByTime(200); });
        expect(first.volume).toBeGreaterThan(0);
        expect(first.volume).toBeLessThan(0.8);
        expect(second.volume).toBeGreaterThan(0);
        expect(first.pause).not.toHaveBeenCalled();
        expect(playing()).toHaveLength(2);

        // After the fade: outgoing paused and released, incoming at full target.
        act(() => { vi.advanceTimersByTime(2000); });
        expect(first.pause).toHaveBeenCalled();
        expect(first.src).toBe('');
        expect(second.volume).toBeCloseTo(0.8, 5);
        expect(playing()).toEqual([second]);
    });

    it('treats a re-request of the incoming track mid-crossfade as a no-op', () => {
        const { result } = renderHook(() => useAudio(), { wrapper });
        instrument();
        const [, second] = pool();

        act(() => { result.current.playBGM('battle'); });
        act(() => { vi.advanceTimersByTime(2000); });
        act(() => { result.current.playBGM('dungeon'); });
        act(() => { vi.advanceTimersByTime(300); });
        const midVolume = second.volume;

        act(() => { result.current.playBGM('dungeon'); });
        expect(second.play).toHaveBeenCalledTimes(1);
        expect(second.volume).toBe(midVolume);
    });

    it('never leaves two tracks playing or a stuck partial volume after rapid changes', () => {
        withPreferences({ musicVolume: 0.6 });
        const { result } = renderHook(() => useAudio(), { wrapper });
        instrument();

        act(() => { result.current.playBGM('battle'); });
        act(() => { vi.advanceTimersByTime(2000); });
        for (const track of ['dungeon', 'grondia', 'nomad_camp', 'dungeon']) {
            act(() => { result.current.playBGM(track); });
            act(() => { vi.advanceTimersByTime(150); });
            // Never more than the two pool elements audible mid-flight.
            expect(playing().length).toBeLessThanOrEqual(2);
        }
        act(() => { vi.advanceTimersByTime(3000); });

        const live = playing();
        expect(live).toHaveLength(1);
        expect(live[0].src).toContain('bgm_dungeon.mp3');
        expect(live[0].volume).toBeCloseTo(0.6, 5);
        const other = pool().find(a => a !== live[0]);
        expect(other.src).toBe('');
        expect(result.current.currentBGM).toBe('dungeon');
    });

    it('fades the outgoing track back in when it is re-requested mid-crossfade', () => {
        withPreferences({ musicVolume: 1 });
        const { result } = renderHook(() => useAudio(), { wrapper });
        instrument();
        const [first, second] = pool();

        act(() => { result.current.playBGM('battle'); });
        act(() => { vi.advanceTimersByTime(2000); });
        act(() => { result.current.playBGM('dungeon'); });
        act(() => { vi.advanceTimersByTime(200); });
        act(() => { result.current.playBGM('battle'); });
        act(() => { vi.advanceTimersByTime(3000); });

        expect(first.src).toContain('Crossing Blades.mp3');
        expect(first.volume).toBeCloseTo(1, 5);
        expect(second.src).toBe('');
        expect(playing()).toEqual([first]);
    });

    it('fades the incoming track to a volume changed mid-crossfade', () => {
        withPreferences({ musicVolume: 1 });
        const { result } = renderHook(() => useBoth(), { wrapper });
        instrument();
        const [, second] = pool();

        act(() => { result.current.audio.playBGM('battle'); });
        act(() => { vi.advanceTimersByTime(2000); });
        act(() => { result.current.audio.playBGM('dungeon'); });
        // Incoming is already above the new target: it must settle DOWN to it.
        act(() => { vi.advanceTimersByTime(500); });
        expect(second.volume).toBeGreaterThan(0.3);
        act(() => { result.current.prefs.setMusicVolume(0.3); });
        act(() => { vi.advanceTimersByTime(3000); });

        expect(second.volume).toBeCloseTo(0.3, 5);
    });

    it('applies a volume change directly once no fade is running', () => {
        const { result } = renderHook(() => useBoth(), { wrapper });
        const [first] = pool();

        act(() => { result.current.audio.playBGM('battle'); });
        act(() => { vi.advanceTimersByTime(2000); });
        act(() => { result.current.prefs.setMusicVolume(0.2); });

        expect(first.volume).toBe(0.2);
    });

    it('stops the fade ticker when the provider unmounts', () => {
        const { result, unmount } = renderHook(() => useAudio(), { wrapper });

        const [first] = pool();

        act(() => { result.current.playBGM('battle'); });
        act(() => { vi.advanceTimersByTime(100); });
        const volumeAtUnmount = first.volume;
        expect(volumeAtUnmount).toBeGreaterThan(0);
        unmount();
        vi.advanceTimersByTime(1000);
        expect(first.volume).toBe(volumeAtUnmount);
    });

    it('crossfades out of a sting when a new track takes over mid-sting', () => {
        const { result } = renderHook(() => useAudio(), { wrapper });
        instrument();
        const [first, second] = pool();

        act(() => { result.current.playBGM('battle'); });
        act(() => { vi.advanceTimersByTime(2000); });
        act(() => { result.current.playSting('fanfare'); });
        act(() => { result.current.playBGM('dungeon'); });

        // The fading sting can no longer fire its restore-previous handler.
        expect(first.onended).toBeNull();
        expect(first.loop).toBe(true);
        act(() => { vi.advanceTimersByTime(2000); });
        expect(playing()).toEqual([second]);
        expect(result.current.currentBGM).toBe('dungeon');
    });

    it('silences both elements when muted mid-crossfade', () => {
        const { result } = renderHook(() => useBoth(), { wrapper });
        instrument();
        const [first, second] = pool();

        act(() => { result.current.audio.playBGM('battle'); });
        act(() => { vi.advanceTimersByTime(2000); });
        act(() => { result.current.audio.playBGM('dungeon'); });
        act(() => { vi.advanceTimersByTime(200); });
        act(() => { result.current.prefs.setIsMusicMuted(true); });

        expect(first.volume).toBe(0);
        expect(second.volume).toBe(0);
        act(() => { vi.advanceTimersByTime(3000); });
        expect(second.volume).toBe(0);
        expect(first.src).toBe('');
    });

    it('warns rather than throws when the incoming track is autoplay-blocked', async () => {
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
        const { result } = renderHook(() => useAudio(), { wrapper });
        const [, second] = pool();

        act(() => { result.current.playBGM('battle'); });
        act(() => { vi.advanceTimersByTime(2000); });
        second.play.mockRejectedValueOnce(new Error('NotAllowedError'));
        await act(async () => {
            result.current.playBGM('dungeon');
            await Promise.resolve();
        });

        expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('Audio play failed'), expect.any(Error));
        expect(result.current.currentBGM).toBe('dungeon');
        warnSpy.mockRestore();
    });

    it('stopBGM mid-crossfade pauses and releases the outgoing element too', () => {
        const { result } = renderHook(() => useAudio(), { wrapper });
        instrument();
        const [first, second] = pool();

        act(() => { result.current.playBGM('battle'); });
        act(() => { vi.advanceTimersByTime(2000); });
        act(() => { result.current.playBGM('dungeon'); });
        act(() => { vi.advanceTimersByTime(200); });
        act(() => { result.current.stopBGM(); });

        expect(playing()).toHaveLength(0);
        expect(first.src).toBe('');
        expect(second.pause).toHaveBeenCalled();
        expect(result.current.currentBGM).toBeNull();
    });
});
