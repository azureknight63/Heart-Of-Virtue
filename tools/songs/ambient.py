from ..audio_engine.song import Song
from ..audio_engine.core import (
    generate_tone, generate_tone_sweep, generate_chord,
    mix_layers, generate_percussion_pattern,
)


class MineralPoolsSong(Song):
    """BGM for the Grondelith Mineral Pools — slow, luminescent, ceremonial.

    Design intent: The mineral pools are sacred Golemite territory, lit by blue
    bioluminescence.  The music should feel ancient, reverent, and subtly alien —
    like walking through living crystal.

    Structure:
      - Slow arpeggio drone in D minor (modal feel)
      - Shimmering sine overtones to suggest water and light
      - Sparse, irregular percussion (stone drops into water)
      - No melodic tension; pure atmosphere
    """

    def __init__(self):
        super().__init__("Mineral Pools", "bgm_mineral_pools.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))

        all_sections = b''

        # ── Intro: Rising shimmer ─────────────────────────────────────────────
        shimmer_freqs = [fr(293.66), fr(369.99), fr(440), fr(554.37)]  # D4, F#4, A4, C#5
        intro = b''
        for freq in shimmer_freqs:
            intro += generate_tone(
                freq, d(1.2), volume=0.18, wave_type='sine',
                attack_time=d(0.5), decay_time=d(0.2), sustain_level=0.6,
                release_time=d(0.4),
            )
        all_sections += intro

        # ── Main loop x 6 (~3 min) ────────────────────────────────────────────
        # Drone: low D + perfect fifth A, triangle wave for softness
        drone_d  = generate_tone(fr(73.42), d(8.0), volume=0.30, wave_type='triangle',
                                 attack_time=d(1.5), sustain_level=0.85, release_time=d(1.5))
        drone_a  = generate_tone(fr(110.0), d(8.0), volume=0.18, wave_type='sine',
                                 attack_time=d(2.0), sustain_level=0.75, release_time=d(2.0))

        # Arpeggio pattern (slow, floaty) — D minor pentatonic
        arp_pattern = [
            (fr(293.66), d(1.6)),   # D4
            (fr(349.23), d(1.6)),   # F4
            (fr(440.00), d(1.6)),   # A4
            (fr(523.25), d(1.6)),   # C5
            (fr(440.00), d(1.6)),   # A4 (descent)
        ]

        # Shimmer layer — high sine overtones, very quiet
        shimmer_freqs_hi = [fr(880), fr(1108.73), fr(1318.51)]  # A5, C#6, E6
        shimmer_durs     = [d(3.2), d(4.0), d(3.6)]

        # Water-drop percussion: rare, short noise burst with long decay
        # 16-beat pattern; 1 = drop, 0 = silence
        drop_pattern = [1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0]

        for loop_i in range(6):
            arp_data = b''
            for freq, dur in arp_pattern:
                arp_data += generate_tone(
                    freq, dur, volume=0.22, wave_type='triangle',
                    attack_time=dur * 0.25, decay_time=dur * 0.1,
                    sustain_level=0.7, release_time=dur * 0.35,
                    vibrato_rate=3.5, vibrato_depth=0.004,
                )

            shimmer_data = b''
            for freq, dur in zip(shimmer_freqs_hi, shimmer_durs):
                shimmer_data += generate_tone(
                    freq, dur, volume=0.07, wave_type='sine',
                    attack_time=dur * 0.4, sustain_level=0.5,
                    release_time=dur * 0.4,
                )

            loop_dur = sum(dur for _, dur in arp_pattern)
            perc = generate_percussion_pattern(drop_pattern, loop_dur)

            all_sections += mix_layers([drone_d, drone_a, arp_data, shimmer_data, perc])

        # ── Outro: fade to silence ────────────────────────────────────────────
        outro = generate_tone(fr(73.42), d(4.0), volume=0.20, wave_type='triangle',
                              attack_time=d(0.5), sustain_level=0.6, release_time=d(3.0))
        all_sections += outro

        return all_sections


class DreamSpaceSong(Song):
    """BGM for the Combat Testing Arena — liminal, slightly uncanny, dreamlike.

    Design intent: The arena exists outside normal geography; it's a testing space
    that feels constructed, purposeful, slightly ominous.  Like a training ground
    that exists between waking and sleep.

    Structure:
      - Slow, dissonant chord pads (augmented / sus2 voicings)
      - Pitch-sweep "memory flashes" on a long cycle
      - Minimal pulse — no strong beat, just rhythm felt in the tension
    """

    def __init__(self):
        super().__init__("Dream Space", "bgm_dream_space.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))

        all_sections = b''

        # ── Pad chords (slow, overlapping) ───────────────────────────────────
        # Augmented C chord — dissonant but not harsh
        pad_aug_c   = [fr(130.81), fr(164.81), fr(207.65)]   # C3, E3, G#3
        # Sus2 on A
        pad_sus2_a  = [fr(110.00), fr(123.47), fr(164.81)]   # A2, B2, E3

        # ── Pulse tone (soft square, slow) ────────────────────────────────────
        pulse_freq  = fr(55.0)  # A1 — felt more than heard

        # ── Sweep accent — occasional pitch glide ─────────────────────────────
        sweep_up   = generate_tone_sweep(fr(220), fr(880), d(1.8),
                                         volume=0.12, wave_type='sine',
                                         attack_time=d(0.3), release_time=d(1.0))
        sweep_down = generate_tone_sweep(fr(660), fr(110), d(2.5),
                                         volume=0.10, wave_type='sine',
                                         attack_time=d(0.1), release_time=d(1.2))
        silence_long = b'\x00\x00' * int(44100 * d(6.0))

        # Main loop x 5
        for loop_i in range(5):
            chord_freqs = pad_aug_c if loop_i % 2 == 0 else pad_sus2_a
            pad = generate_chord(
                chord_freqs, d(12.0),
                volume=0.22, wave_type='sine',
                attack_time=d(2.5), release_time=d(3.5),
            )
            pulse = generate_tone(
                pulse_freq, d(12.0), volume=0.18, wave_type='square',
                attack_time=d(3.0), decay_time=d(2.0), sustain_level=0.5,
                release_time=d(3.0),
            )
            # Add sweep accent every other loop
            accent = (sweep_up if loop_i % 2 == 0 else sweep_down) + silence_long
            all_sections += mix_layers([pad, pulse, accent])

        return all_sections
