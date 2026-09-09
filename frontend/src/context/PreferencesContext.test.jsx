import { render, screen, act, renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.unmock('./PreferencesContext');
import {
    DEFAULT_PREFERENCES,
    PreferencesProvider,
    loadPreferences,
    normalizeVolume,
    usePreferences,
} from './PreferencesContext';
import { INSTANT_TEXT_SPEED } from '../utils/textPacing';

// These moved here with the preferences themselves: they were in
// AudioContext.test.jsx while `AudioContext` still owned persistence, and they
// were never about audio playback — only about what is stored, what is loaded
// back, and what happens when the stored blob is not what it should be.

const wrapper = ({ children }) => <PreferencesProvider>{children}</PreferencesProvider>;

const Readout = () => {
    const { musicVolume, sfxVolume } = usePreferences();
    return (
        <div>
            <div data-testid="music-volume">{musicVolume}</div>
            <div data-testid="sfx-volume">{sfxVolume}</div>
        </div>
    );
};

const store = (prefs) => localStorage.setItem('audioPreferences', JSON.stringify(prefs));

beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
});

describe('PreferencesContext', () => {
    it('starts every preference at its default', () => {
        const { result } = renderHook(() => usePreferences(), { wrapper });

        for (const [key, value] of Object.entries(DEFAULT_PREFERENCES)) {
            expect(result.current[key]).toBe(value);
        }
    });

    it('loads stored preferences', () => {
        store({ musicVolume: 0.8, sfxVolume: 0.2, isMusicMuted: true, isSfxMuted: false });

        render(<PreferencesProvider><Readout /></PreferencesProvider>);

        expect(screen.getByTestId('music-volume').textContent).toBe('0.8');
        expect(screen.getByTestId('sfx-volume').textContent).toBe('0.2');
    });

    it('persists a change back to localStorage', () => {
        const { result } = renderHook(() => usePreferences(), { wrapper });

        act(() => { result.current.setMusicVolume(0.9); });
        act(() => { result.current.setSfxVolume(0.1); });

        expect(result.current.musicVolume).toBe(0.9);
        expect(result.current.sfxVolume).toBe(0.1);
        const saved = JSON.parse(localStorage.getItem('audioPreferences'));
        expect(saved.musicVolume).toBe(0.9);
        expect(saved.sfxVolume).toBe(0.1);
    });

    it('keeps the storage key it has always used', () => {
        // Renaming it would silently reset every existing player's settings.
        renderHook(() => usePreferences(), { wrapper });
        expect(localStorage.getItem('audioPreferences')).not.toBeNull();
    });

    describe('a stored blob that is not what it should be', () => {
        it('falls back to defaults on corrupt JSON, and says so', () => {
            localStorage.setItem('audioPreferences', '{not valid json');
            const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

            render(<PreferencesProvider><Readout /></PreferencesProvider>);

            expect(screen.getByTestId('music-volume').textContent).toBe('0.5');
            // Naming the message and the payload: a bare toHaveBeenCalled()
            // passed even when the warning came from an unrelated code path.
            expect(warnSpy).toHaveBeenCalledWith('Failed to load preferences:', expect.any(SyntaxError));
            warnSpy.mockRestore();
        });

        it.each([['null', 'null'], ['a scalar', '7'], ['an array', '[1,2]']])(
            'falls back to defaults when the blob is %s',
            (_label, raw) => {
                // Each of these parses cleanly and would otherwise arrive as
                // the entire preference set.
                localStorage.setItem('audioPreferences', raw);
                const { result } = renderHook(() => usePreferences(), { wrapper });
                expect(result.current.musicVolume).toBe(DEFAULT_PREFERENCES.musicVolume);
            }
        );

        it('fills in a preference the stored blob predates', () => {
            // A save written before TEXT SPEED existed has no textSpeed key.
            store({ musicVolume: 0.8 });
            const { result } = renderHook(() => usePreferences(), { wrapper });

            expect(result.current.musicVolume).toBe(0.8);
            expect(result.current.textSpeed).toBe(DEFAULT_PREFERENCES.textSpeed);
            expect(result.current.autoAdvance).toBe(false);
        });

        it('does not throw when saving fails', () => {
            const setItemSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
                throw new Error('quota exceeded');
            });
            const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

            expect(() => {
                render(<PreferencesProvider><Readout /></PreferencesProvider>);
            }).not.toThrow();

            expect(warnSpy).toHaveBeenCalledWith('Failed to save preferences:', expect.any(Error));
            warnSpy.mockRestore();
            setItemSpy.mockRestore();
        });
    });

    describe('normalizing on the way in', () => {
        it.each([
            ['above the range', 5, 1],
            ['below the range', -3, 0],
            ['at the top', 1, 1],
            ['at the bottom', 0, 0],
        ])('clamps a volume %s', (_label, stored, expected) => {
            // Load-bearing: this value is assigned straight to
            // HTMLMediaElement.volume, which throws IndexSizeError outside
            // 0-1 — and with no error boundary that blanks the whole SPA on
            // every load, permanently, because the bad value is re-read each
            // time.
            expect(normalizeVolume(stored, 0.5)).toBe(expected);
        });

        it.each([
            ['a string', 'loud'],
            ['null', null],
            ['NaN', NaN],
            // These three coerce to 0 — finite, in range, and silently MUTED.
            // Falling back is the only correct answer for a value the UI
            // cannot have written.
            ['an empty string', ''],
            ['false', false],
            ['an empty array', []],
        ])('falls back for a non-numeric volume (%s)', (_label, stored) => {
            expect(normalizeVolume(stored, 0.5)).toBe(0.5);
        });

        it('clamps a hostile stored volume rather than handing it to the media element', () => {
            store({ musicVolume: 5, sfxVolume: -3 });
            const { result } = renderHook(() => usePreferences(), { wrapper });

            expect(result.current.musicVolume).toBe(1);
            expect(result.current.sfxVolume).toBe(0);
        });

        it('normalizes a corrupted combatSpeed to the 1x default', () => {
            store({ combatSpeed: 0 });
            const { result } = renderHook(() => usePreferences(), { wrapper });
            expect(result.current.combatSpeed).toBe(1);
        });

        it('loads a valid combatSpeed unchanged', () => {
            store({ combatSpeed: 2 });
            const { result } = renderHook(() => usePreferences(), { wrapper });
            expect(result.current.combatSpeed).toBe(2);
        });

        it('normalizes an off-step textSpeed to the default', () => {
            // 1e-5 passes any "finite and positive" check and would ask the
            // typewriter for ~42 minutes per character.
            store({ textSpeed: 1e-5 });
            const { result } = renderHook(() => usePreferences(), { wrapper });
            expect(result.current.textSpeed).toBe(DEFAULT_PREFERENCES.textSpeed);
        });

        it('loads the instant text-speed sentinel unchanged', () => {
            // The reason the sentinel is 0 and not Infinity: it has to survive
            // a JSON round trip.
            store({ textSpeed: INSTANT_TEXT_SPEED });
            const { result } = renderHook(() => usePreferences(), { wrapper });
            expect(result.current.textSpeed).toBe(INSTANT_TEXT_SPEED);
        });

        it('coerces a non-boolean autoAdvance', () => {
            store({ autoAdvance: 'yes' });
            const { result } = renderHook(() => usePreferences(), { wrapper });
            expect(result.current.autoAdvance).toBe(true);
        });
    });

    it('persists the pacing settings alongside the audio ones', () => {
        const { result } = renderHook(() => usePreferences(), { wrapper });

        act(() => { result.current.setCombatSpeed(1.5); });
        act(() => { result.current.setTextSpeed(INSTANT_TEXT_SPEED); });
        act(() => { result.current.setAutoAdvance(true); });

        const saved = JSON.parse(localStorage.getItem('audioPreferences'));
        expect(saved.combatSpeed).toBe(1.5);
        expect(saved.textSpeed).toBe(INSTANT_TEXT_SPEED);
        expect(saved.autoAdvance).toBe(true);
    });

    it('exposes defaults and no-op setters outside a provider', () => {
        const { result } = renderHook(() => usePreferences());

        for (const [key, value] of Object.entries(DEFAULT_PREFERENCES)) {
            expect(result.current[key]).toBe(value);
        }
        expect(() => {
            result.current.setMusicVolume(0.9);
            result.current.setTextSpeed(2);
            result.current.setAutoAdvance(true);
        }).not.toThrow();
        // A no-op that quietly wrote to storage would defeat the point.
        expect(localStorage.getItem('audioPreferences')).toBeNull();
    });

    it('loadPreferences is the single reader the provider uses', () => {
        store({ musicVolume: 0.25, textSpeed: 2 });
        expect(loadPreferences()).toMatchObject({ musicVolume: 0.25, textSpeed: 2 });
    });
});
