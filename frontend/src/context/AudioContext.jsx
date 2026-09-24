import { createContext, useContext, useState, useRef, useEffect, useCallback } from 'react';
import { normalizeSpeed } from '../utils/combatTiming';
import { usePreferences } from './PreferencesContext';
import { lookupOr } from '../utils/lookup';

/**
 * Audio playback: the crossfading BGM element pool, one-shot SFX, and stings.
 *
 * Playback only. The volumes and mutes it obeys are player *preferences* and
 * live in `PreferencesContext`, which this provider reads — as do the pacing
 * settings that used to sit here (`combatSpeed`, `textSpeed`, `autoAdvance`)
 * and are not audio at all. Consumers that only want to make a sound call
 * `useAudio()`; consumers that want a setting call `usePreferences()`.
 */

const AudioContext = createContext({
    playBGM: () => {},
    stopBGM: () => {},
    playSFX: () => {},
    playSting: () => {},
    currentBGM: null,
});

export const useAudio = () => useContext(AudioContext);

const getAssetPath = (path) => {
    const base = import.meta.env.BASE_URL.replace(/\/$/, '');
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    return `${base}${cleanPath}`;
};

// Ceiling on live one-shot SFX elements. A layered impact burst (the combat
// path caps a batch at 12 layers, each with an SFX chain) — or an `onended`
// that never fires — must not pile up media elements without bound. Past the
// cap the OLDEST still-active one-shot is paused and released; the newest cue
// always plays, because the most recent sound is the one that matches what is
// on screen.
const MAX_CONCURRENT_SFX = 16;

// BGM crossfade pacing (issue #662). Each tick moves the incoming track up and
// the outgoing track down by one step, simultaneously, so a crossfade at full
// volume takes (1 / 0.05) * 50ms = 1s with both tracks audible throughout.
const BGM_FADE_STEP = 0.05;
const BGM_FADE_INTERVAL_MS = 50;

const BGM_MAP = {
    'adventure': getAssetPath('/assets/sounds/bgm/Virtue Quest.mp3'),
    'battle': getAssetPath('/assets/sounds/bgm/Crossing Blades.mp3'),
    'dark_grotto': getAssetPath('/assets/sounds/dark_grotto.mp3'),
    'dungeon': getAssetPath('/assets/sounds/bgm_dungeon.mp3'),
    'eastern_descent': getAssetPath('/assets/sounds/bgm_eastern_descent.mp3'),
    'fanfare': getAssetPath('/assets/sounds/bgm_fanfare.wav'),
    'grondia': getAssetPath('/assets/sounds/bgm_grondia.mp3'),
    'memory_flash': getAssetPath('/assets/sounds/memory_flash.mp3'),
    'mineral_pools': getAssetPath('/assets/sounds/bgm_mineral_pools.wav'),
    'nomad_camp': getAssetPath('/assets/sounds/bgm_nomad_camp.mp3'),
    'jambos_tent': getAssetPath('/assets/sounds/bgm/Jambo Heals U.mp3'),
    'iron_and_oath': getAssetPath('/assets/sounds/bgm/We Got The Gear.mp3'),
    'dream_space': getAssetPath('/assets/sounds/bgm_dream_space.wav'),
};

const bgmPath = (trackName) =>
    lookupOr(BGM_MAP, trackName, getAssetPath(`/assets/sounds/bgm_${trackName}.wav`));

/**
 * Return a pool element to its looping-BGM state.
 *
 * A sting borrows the active element, setting `loop = false` and an `onended`
 * handler. Leaving either behind means the next BGM plays exactly once and the
 * map goes silent — the bug this reset exists to prevent. Every path that
 * hands an element back to BGM duty (load, crossfade-out, release, stop, the
 * sting's own `onended`) calls this one helper.
 */
const clearStingState = (element) => {
    element.loop = true;
    element.onended = null;
};

/**
 * The two-element BGM pool (issue #662).
 *
 * `elements[active]` holds the current track. The other slot is either idle
 * (`tracks[slot] === null`, src released) or holds the OUTGOING track while it
 * fades out. A track change loads the incoming track into the idle slot, so
 * outgoing and incoming overlap instead of sharing one element and passing
 * through silence. `tracks` records what each slot has loaded, which is what
 * lets a track re-requested mid-fade-out be faded back in rather than reloaded.
 */
const createBgmPool = () => ({
    elements: [new Audio(), new Audio()],
    tracks: [null, null],
    // The volume each slot was last SET to. The fade steps and compares these,
    // never `element.volume`: iOS Safari ignores writes to media volume and
    // always reads back 1, so a fade that read the element would never finish
    // and never release the outgoing track.
    volumes: [0, 0],
    active: 0,
});

const setSlotVolume = (pool, slot, volume) => {
    pool.volumes[slot] = volume;
    pool.elements[slot].volume = volume;
};

const activeElement = (pool) => pool.elements[pool.active];
const spareSlot = (pool) => 1 - pool.active;

export const AudioProvider = ({ children }) => {
    // Volumes and mutes are preferences, owned and persisted by
    // PreferencesProvider, which must therefore wrap this one (see App.jsx).
    const { musicVolume, sfxVolume, isMusicMuted, isSfxMuted } = usePreferences();
    const [currentBGM, setCurrentBGM] = useState(null);

    // Created once, lazily: `useRef(createBgmPool())` would construct (and
    // throw away) two fresh media elements on every render.
    const poolRef = useRef(null);
    if (poolRef.current === null) {
        poolRef.current = createBgmPool();
    }
    const trackProgress = useRef({}); // Stores currentTime for each track ID
    const fadeIntervalRef = useRef(null);
    const activeSFXRef = useRef(new Set());
    // Ref mirrors currentBGM state so playBGM/stopBGM can read it without
    // closing over state (which would force new function references on every
    // track change and trigger unrelated useEffects in consumers).
    const currentBGMRef = useRef(null);
    // The live music volume target. The fade ticker reads it on every step, so
    // a volume change mid-crossfade lands on the incoming track instead of
    // being overwritten by a target captured when the fade began.
    const targetVolumeRef = useRef(isMusicMuted ? 0 : musicVolume);

    // Save a slot's playback position so returning to that track resumes it.
    const saveProgress = useCallback((slot) => {
        const pool = poolRef.current;
        const track = pool.tracks[slot];
        if (track) {
            trackProgress.current[track] = pool.elements[slot].currentTime;
        }
    }, []);

    // Pause a slot and drop its source: nothing keeps the outgoing track's
    // audio resource pinned once it has faded out.
    const releaseSlot = useCallback((slot) => {
        const pool = poolRef.current;
        const element = pool.elements[slot];
        saveProgress(slot);
        element.pause();
        clearStingState(element);
        element.src = '';
        setSlotVolume(pool, slot, 0);
        pool.tracks[slot] = null;
    }, [saveProgress]);

    const stopFade = useCallback(() => {
        if (fadeIntervalRef.current) {
            clearInterval(fadeIntervalRef.current);
            fadeIntervalRef.current = null;
        }
    }, []);

    /**
     * Run the crossfade. One ticker drives both halves: the active element
     * climbs (or settles) toward the live target while the spare slot, if it
     * still holds an outgoing track, falls to zero and is released. The ticker
     * stops only when both have arrived, so however many track changes land
     * mid-fade, the result is one track at full target and the other released
     * — never two tracks playing, never one stranded at a partial volume.
     */
    const startFade = useCallback(() => {
        if (fadeIntervalRef.current) return; // the running ticker reads live state
        fadeIntervalRef.current = setInterval(() => {
            const pool = poolRef.current;
            const target = targetVolumeRef.current;
            const current = pool.volumes[pool.active];
            if (current < target) {
                setSlotVolume(pool, pool.active, Math.min(current + BGM_FADE_STEP, target));
            } else if (current > target) {
                setSlotVolume(pool, pool.active, Math.max(current - BGM_FADE_STEP, target));
            }

            const spare = spareSlot(pool);
            if (pool.tracks[spare] !== null) {
                const next = Math.max(pool.volumes[spare] - BGM_FADE_STEP, 0);
                setSlotVolume(pool, spare, next);
                if (next <= 0) releaseSlot(spare);
            }

            if (pool.volumes[pool.active] === target && pool.tracks[spare] === null) {
                stopFade();
            }
        }, BGM_FADE_INTERVAL_MS);
    }, [releaseSlot, stopFade]);

    // Never leave a ticker running against an unmounted provider.
    useEffect(() => stopFade, [stopFade]);

    useEffect(() => {
        const target = isMusicMuted ? 0 : musicVolume;
        targetVolumeRef.current = target;
        const pool = poolRef.current;
        if (isMusicMuted) {
            // Muted means silent now, not after a fade — both slots, so an
            // in-flight outgoing track does not keep sounding.
            pool.elements.forEach((_, slot) => setSlotVolume(pool, slot, 0));
        } else if (!fadeIntervalRef.current) {
            // Mid-fade, the ticker picks up the new target on its next step.
            setSlotVolume(pool, pool.active, target);
        }
    }, [musicVolume, isMusicMuted]);

    // Load a track into a slot, silent, resumed from its saved position.
    const loadTrack = useCallback((slot, trackName) => {
        const pool = poolRef.current;
        const element = pool.elements[slot];
        clearStingState(element);
        element.src = bgmPath(trackName);
        // `lookupOr` rather than `|| 0`: this ref holds a plain object, so a
        // track named `constructor` would resolve to a FUNCTION, and assigning
        // that to `currentTime` throws on a non-finite double. Same shape as
        // the BGM_MAP lookup above; see utils/lookup.js.
        element.currentTime = lookupOr(trackProgress.current, trackName, 0);
        setSlotVolume(pool, slot, 0);
        pool.tracks[slot] = trackName;
        element.play().catch(e => console.warn("Audio play failed (user interaction needed):", e));
    }, []);

    const playBGM = useCallback((trackName) => {
        if (currentBGMRef.current === trackName) return;

        const pool = poolRef.current;
        if (currentBGMRef.current === null) {
            // Nothing playing: fade the track in on the active slot.
            loadTrack(pool.active, trackName);
        } else {
            const outgoing = activeElement(pool);
            const spare = spareSlot(pool);
            if (pool.tracks[spare] !== trackName) {
                // Only two tracks may ever sound. Whatever still occupies the
                // spare slot (an earlier outgoing track, mid-fade) is cut now
                // to make room for the incoming one.
                if (pool.tracks[spare] !== null) releaseSlot(spare);
                loadTrack(spare, trackName);
            }
            // else: the requested track is the one still fading out — swap
            // roles and fade it back up from where it is, with no reload.
            pool.active = spare;
            // The outgoing track must not end mid-fade and fire a sting's
            // restore handler (or stop dead) while it fades.
            clearStingState(outgoing);
        }

        currentBGMRef.current = trackName;
        setCurrentBGM(trackName);
        startFade();
    }, [loadTrack, releaseSlot, startFade]);

    const stopBGM = useCallback(() => {
        stopFade();
        const pool = poolRef.current;
        const active = activeElement(pool);
        saveProgress(pool.active);
        active.pause();
        // Never leave a sting's one-shot state stranded on the element for
        // whatever plays next.
        clearStingState(active);
        // A crossfade in flight: its outgoing half stops too.
        if (pool.tracks[spareSlot(pool)] !== null) releaseSlot(spareSlot(pool));
        currentBGMRef.current = null;
        setCurrentBGM(null);
    }, [stopFade, saveProgress, releaseSlot]);

    // `speed` (issue #460): combat-speed multiplier for this one-shot cue.
    // playbackRate scales tempo; preservesPitch keeps it from sounding
    // chipmunked/slowed — browser-native pitch-preserving time-stretch, no DSP.
    const playSFX = useCallback((sfxName, speed = 1) => {
        // Evict the oldest live one-shots down to the cap. Sets iterate in
        // insertion order, so the first entry is the longest-running cue.
        while (activeSFXRef.current.size >= MAX_CONCURRENT_SFX) {
            const oldest = activeSFXRef.current.values().next().value;
            oldest.pause();
            // "Released" literally: detach the handler and drop the source so
            // the evicted element pins neither a callback closure nor its
            // loaded audio resource while it waits for GC. pause() alone left
            // both attached.
            oldest.onended = null;
            oldest.src = '';
            activeSFXRef.current.delete(oldest);
        }
        const path = getAssetPath(`/assets/sounds/sfx/${sfxName}.wav`);
        const audio = new Audio(path);
        audio.volume = isSfxMuted ? 0 : sfxVolume;
        // normalizeSpeed guards against a corrupted/garbage combatSpeed (e.g. a
        // hand-edited localStorage value of 0 or negative) — playbackRate must
        // stay a positive finite number or HTMLMediaElement rejects the set.
        audio.playbackRate = normalizeSpeed(speed);
        audio.preservesPitch = true;
        audio.webkitPreservesPitch = true;
        audio.mozPreservesPitch = true;
        activeSFXRef.current.add(audio);
        audio.onended = () => activeSFXRef.current.delete(audio);
        audio.play().catch(e => {
            console.warn("SFX play failed:", e);
            activeSFXRef.current.delete(audio);
        });
    }, [isSfxMuted, sfxVolume]);

    const playSting = useCallback((trackName) => {
        const previousBGM = currentBGMRef.current;
        const pool = poolRef.current;
        const element = activeElement(pool);

        // Save progress of current track before switching
        saveProgress(pool.active);

        element.loop = false; // One-shot
        element.src = bgmPath(trackName);
        element.currentTime = 0;
        setSlotVolume(pool, pool.active, targetVolumeRef.current);
        pool.tracks[pool.active] = trackName;
        element.play().catch(e => console.warn("Sting play failed:", e));
        currentBGMRef.current = trackName;
        setCurrentBGM(trackName);

        // When sting ends, restore loop and switch back to previous BGM.
        // Guard: only restore if no external track switch happened during the sting
        // (i.e., currentBGMRef still points to this sting track).
        element.onended = () => {
            clearStingState(element);
            if (previousBGM && previousBGM !== trackName
                    && currentBGMRef.current === trackName) {
                playBGM(previousBGM);
            }
        };
    }, [saveProgress, playBGM]);

    const value = {
        playBGM,
        stopBGM,
        playSFX,
        playSting,
        currentBGM,
    };

    return (
        <AudioContext.Provider value={value}>
            {children}
        </AudioContext.Provider>
    );
};
