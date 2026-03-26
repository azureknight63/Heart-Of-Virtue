from ..audio_engine.song import Song
from ..audio_engine.core import generate_tone, generate_chord, mix_layers, generate_percussion_pattern

class AdventureSong(Song):
    def __init__(self):
        super().__init__("Adventure Theme", "bgm_adventure.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        # Modifiers
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))

        # --- Musical Building Blocks ---

        # Theme A: Heroic & Uplifting (Staccato, Flute-like) - TIGHTENED (Double Speed)
        theme_a = [
            [(523, 0.25), (587, 0.25), (659, 0.5), (784, 0.5), (659, 0.25), (587, 0.25)],
            [(523, 0.25), (659, 0.25), (784, 0.5), (880, 0.5), (784, 0.25), (659, 0.25)],
            [(587, 0.25), (659, 0.25), (784, 0.5), (1047, 1.0)],
            [(880, 0.25), (784, 0.25), (659, 0.25), (587, 0.5), (523, 0.75)], # Extended last note to complete 8.0s
        ]

        # Fallback Melody (Rhythmic filler) - Improved flow
        fallback_melody = [
            [(523, 0.5), (659, 0.25), (784, 0.25)], # C-E-G
            [(659, 0.5), (523, 0.25), (392, 0.25)], # E-C-G
            [(440, 0.25), (523, 0.25), (659, 0.25), (523, 0.25)], # A-C-E-C
            [(392, 0.5), (330, 0.25), (294, 0.25)], # G-E-D
        ]

        # Theme B: Gentle & Reflective (Lower octave, slower)
        theme_b = [
            [(392, 0.6), (440, 0.6), (349, 1.2)],
            [(392, 0.6), (440, 0.6), (523, 1.2)],
            [(440, 0.6), (392, 0.6), (349, 0.6), (330, 0.6)],
            [(294, 1.2), (262, 1.2)],
        ]

        # Theme C: Driving & Adventurous (Faster, arpeggiated) - Modified resolution
        theme_c = [
            [(523, 0.15), (659, 0.15), (784, 0.15), (523, 0.15), (659, 0.15), (784, 0.15)],
            [(587, 0.15), (740, 0.15), (880, 0.15), (587, 0.15), (740, 0.15), (880, 0.15)],
            [(659, 0.15), (830, 0.15), (987, 0.15), (659, 0.15), (830, 0.15), (987, 0.15)],
            [(523, 0.15), (659, 0.15), (784, 0.15), (1047, 0.45)], # C Major run (C-E-G-C)
        ]

        # Chord Progressions (Adjusted for faster Theme A)
        prog_a = [([262, 330, 392], 1.0), ([294, 370, 440], 1.0), ([220, 262, 330], 1.0), ([175, 220, 262], 1.0)] # C-G-Am-F
        prog_b = [([175, 220, 262], 2.4), ([262, 330, 392], 2.4), ([294, 370, 440], 2.4), ([220, 262, 330], 2.4)] # F-C-G-Am (Slower)
        prog_c = [([220, 262, 330], 0.9), ([175, 220, 262], 0.9), ([262, 330, 392], 0.9), ([294, 370, 440], 0.9)] # Am-F-C-G (Faster)

        # Bass Lines (Adjusted for faster Theme A)
        bass_a = [(131, 0.5), (131, 0.5), (147, 0.5), (147, 0.5), (110, 0.5), (110, 0.5), (87, 0.5), (87, 0.5)]
        bass_b = [(87, 2.4), (131, 2.4), (147, 2.4), (110, 2.4)]
        bass_c = [(110, 0.3), (110, 0.3), (110, 0.3), (87, 0.3), (87, 0.3), (87, 0.3), (131, 0.3), (131, 0.3), (131, 0.3), (147, 0.9)]

        all_sections = b''

        # --- Section 1: Intro (Shortened) ---
        intro_chords = [([262, 330, 392], 2.4), ([175, 220, 262], 2.4)] # Only once
        intro_layer = b''
        for chord, dur in intro_chords:
            intro_layer += generate_chord([fr(c) for c in chord], d(dur), volume=0.2, wave_type='sine')
        all_sections += mix_layers([intro_layer])

        # Main Loop x 2
        for _ in range(2):
            # --- Section 2: Theme A (The Call) x 2 with Fallback ---
            for _ in range(2):
                mel, harm, chd, bss = b'', b'', b'', b''
                # Main Theme
                for phrase in theme_a:
                    # Staccato phrasing: play 70%, rest 30%
                    for f, dur in phrase:
                        play_dur = d(dur) * 0.7
                        rest_dur = d(dur) * 0.3
                        mel += generate_tone(fr(f), play_dur, 0.35, wave_type='sine') # Boosted melody
                        mel += b'\x00\x00' * int(44100 * rest_dur)

                    for f, dur in phrase: harm += generate_tone(fr(f*1.25), d(dur), 0.15, wave_type='triangle')

                # Fallback Melody (Filler)
                for phrase in fallback_melody:
                    for f, dur in phrase: mel += generate_tone(fr(f), d(dur), 0.25, wave_type='triangle')

                # Harmony/Bass/Chords cover both Main Theme + Fallback
                # Calculate total duration of Theme A + Fallback
                dur_theme = sum(d(dur) for p in theme_a for _, dur in p)
                dur_fallback = sum(d(dur) for p in fallback_melody for _, dur in p)
                total_dur = dur_theme + dur_fallback

                # Extend accompaniment to cover full duration
                current_dur = 0
                while current_dur < total_dur:
                    for c, dur in prog_a:
                        if current_dur >= total_dur: break
                        chd += generate_chord([fr(x) for x in c], min(d(dur), total_dur - current_dur), 0.2, wave_type='triangle')
                        current_dur += d(dur)

                current_dur = 0
                while current_dur < total_dur:
                    for f, dur in bass_a:
                        if current_dur >= total_dur: break
                        bss += generate_tone(fr(f), min(d(dur), total_dur - current_dur), 0.18, wave_type='triangle')
                        current_dur += d(dur)

                perc = generate_percussion_pattern([1, 0, 1, 0, 1, 0, 1, 1] * int(total_dur * 2), total_dur) # Light snare

                section_mix = mix_layers([mel, harm, chd, bss, perc])
                all_sections += section_mix

            # --- Transition to Theme B ---
            # A short C Major chord swell to resolve the F from Theme A and lead into F of Theme B
            trans_chord = generate_chord([fr(x) for x in [262, 330, 392]], d(1.5), 0.05, wave_type='sine') # C Major
            trans_bass = generate_tone(fr(131), d(1.5), 0.1, wave_type='sawtooth') # C Bass
            trans_perc = generate_percussion_pattern([1, 1, 1, 1], d(1.5)) # Roll
            all_sections += mix_layers([trans_chord, trans_bass, trans_perc])

            # --- Section 3: Theme B (Reflective Bridge) x 2 ---
            for _ in range(2):
                mel, chd, bss = b'', b'', b''
                for phrase in theme_b:
                    for f, dur in phrase: mel += generate_tone(fr(f), d(dur), 0.45, wave_type='triangle') # Louder melody
                for c, dur in prog_b: chd += generate_chord([fr(x) for x in c], d(dur), 0.2, wave_type='sine')
                for f, dur in bass_b: bss += generate_tone(fr(f), d(dur), 0.18, wave_type='triangle')

                # Martial percussion - slow, steady march fitting somber mood
                # "Roll, roll, tap, tap" pattern (da-da da-da DA DA)
                dur_section = sum(d(dur) for p in theme_b for _, dur in p)
                march_pattern = [1, 1, 1, 1, 1, 0, 1, 0] * 4 # 4 phrases in theme_b

                perc = generate_percussion_pattern(march_pattern, dur_section)

                all_sections += mix_layers([mel, chd, bss, perc])

            # --- Section 4: Theme C (The Challenge) x 2 (Shortened) - Ethereal Version ---
            for _ in range(2):
                mel, chd, bss = b'', b'', b''
                for phrase in theme_c:
                    # Ethereal: Sine wave, gradual volume increase (crescendo) within each phrase
                    num_notes = len(phrase)
                    for i, (f, dur) in enumerate(phrase):
                        # Start at 0.04, ramp to 0.12
                        vol = 0.04 + (0.21 * (i / (num_notes - 1))) if num_notes > 1 else 0.25
                        mel += generate_tone(fr(f), d(dur), vol, wave_type='sine', attack_time=0.03)
                # Softer, smoother chords and bass
                for c, dur in prog_c * 2: chd += generate_chord([fr(x) for x in c], d(dur), 0.1, wave_type='sine', attack_time=0.05)
                for f, dur in bass_c * 2: bss += generate_tone(fr(f), d(dur), 0.08, wave_type='triangle', attack_time=0.05)

                total_dur = sum(d(dur) for p in theme_c for _, dur in p) * 2 # Match the chord/bass duration
                # Sparse, light percussion
                perc = generate_percussion_pattern([1, 0, 0, 0] * 16, total_dur)
                all_sections += mix_layers([mel, chd, bss, perc])

        # --- Section 5: Theme A Reprise (Grand Finale) x 2 ---
        for _ in range(2):
            mel, harm, chd, bss, sub = b'', b'', b'', b'', b''
            for phrase in theme_a:
                for f, dur in phrase: mel += generate_tone(fr(f), d(dur), 0.35, wave_type='triangle') # Switched to triangle for softer high end
                for f, dur in phrase: harm += generate_tone(fr(f*1.5), d(dur), 0.2, wave_type='triangle') # Fifths, reduced vol
                # Sub-bass for gravity
                for f, dur in phrase: sub += generate_tone(fr(f*0.5), d(dur), 0.2, wave_type='sine') # Reduced sub volume

            # Accompaniment
            dur_theme = sum(d(dur) for p in theme_a for _, dur in p)

            # Loop prog/bass to match theme duration
            current_dur = 0
            while current_dur < dur_theme:
                for c, dur in prog_a:
                    if current_dur >= dur_theme: break
                    chd += generate_chord([fr(x) for x in c], min(d(dur), dur_theme - current_dur), 0.3, wave_type='sawtooth')
                    current_dur += d(dur)

            current_dur = 0
            while current_dur < dur_theme:
                for f, dur in bass_a:
                    if current_dur >= dur_theme: break
                    bss += generate_tone(fr(f), min(d(dur), dur_theme - current_dur), 0.2, wave_type='triangle') # Reduced bass volume
                    current_dur += d(dur)

            # Heavier percussion (Kick/Snare/Hats)
            perc = generate_percussion_pattern([1, 1, 1, 1, 1, 1, 1, 1] * int(dur_theme * 2), dur_theme)
            all_sections += mix_layers([mel, harm, chd, bss, sub, perc])

        return all_sections

class ThemeSnippet(Song):
    def __init__(self):
        super().__init__("Theme Snippet", "theme_snippet.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))

        theme_a = [
            [(523, 0.25), (587, 0.25), (659, 0.5), (784, 0.5), (659, 0.25), (587, 0.25)],
            [(523, 0.25), (659, 0.25), (784, 0.5), (880, 0.5), (784, 0.25), (659, 0.25)],
            [(587, 0.25), (659, 0.25), (784, 0.5), (1047, 1.0)],
            [(880, 0.25), (784, 0.25), (659, 0.25), (587, 0.5), (523, 0.5)],
        ]
        prog_a = [([262, 330, 392], 1.0), ([294, 370, 440], 1.0), ([220, 262, 330], 1.0), ([175, 220, 262], 1.0)]
        bass_a = [(131, 0.5), (131, 0.5), (147, 0.5), (147, 0.5), (110, 0.5), (110, 0.5), (87, 0.5), (87, 0.5)]

        mel, harm, chd, bss = b'', b'', b'', b''
        for phrase in theme_a:
            # Staccato phrasing for snippet too
            for f, dur in phrase:
                play_dur = d(dur) * 0.7
                rest_dur = d(dur) * 0.3
                mel += generate_tone(fr(f), play_dur, 0.3, wave_type='sine')
                mel += b'\x00\x00' * int(44100 * rest_dur)

            for f, dur in phrase: harm += generate_tone(fr(f*1.25), d(dur), 0.15, wave_type='triangle')

        # Accompaniment loop
        dur_theme = sum(d(dur) for p in theme_a for _, dur in p)

        current_dur = 0
        while current_dur < dur_theme:
            for c, dur in prog_a:
                if current_dur >= dur_theme: break
                chd += generate_chord([fr(x) for x in c], min(d(dur), dur_theme - current_dur), 0.2, wave_type='triangle')
                current_dur += d(dur)

        current_dur = 0
        while current_dur < dur_theme:
            for f, dur in bass_a:
                if current_dur >= dur_theme: break
                bss += generate_tone(fr(f), min(d(dur), dur_theme - current_dur), 0.3, wave_type='sawtooth')
                current_dur += d(dur)

        perc = generate_percussion_pattern([1, 0, 1, 0, 1, 0, 1, 1] * int(dur_theme * 2), dur_theme)

        return mix_layers([mel, harm, chd, bss, perc])


class FanareSong(Song):
    """Short triumphant victory fanfare (C-major, ~3s, loops cleanly).

    Structure:
      1. Rising G4-G4-C5-E5-G5-C6 arpeggio with parallel bass octave
      2. Brief silence
      3. Sustained G5 melody over a C-major chord swell
    """
    def __init__(self):
        super().__init__("Victory Fanfare", "bgm_fanfare.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))

        # --- Rising arpeggio ---
        melody_pitches = [
            (fr(392), d(0.10)),   # G4
            (fr(392), d(0.10)),   # G4
            (fr(523), d(0.15)),   # C5
            (fr(659), d(0.15)),   # E5
            (fr(784), d(0.15)),   # G5
            (fr(1047), d(0.5)),   # C6 — held
        ]
        bass_pitches = [
            (fr(196), d(0.10)),   # G3
            (fr(196), d(0.10)),   # G3
            (fr(261), d(0.15)),   # C4
            (fr(329), d(0.15)),   # E4
            (fr(392), d(0.15)),   # G4
            (fr(523), d(0.5)),    # C5 — held
        ]

        melody_arp = b''.join(
            generate_tone(f, dur, volume=0.6, wave_type='square', attack_time=0.01, release_time=0.02)
            for f, dur in melody_pitches
        )
        bass_arp = b''.join(
            generate_tone(f, dur, volume=0.4, wave_type='sawtooth', attack_time=0.01, release_time=0.02)
            for f, dur in bass_pitches
        )
        arpeggio = mix_layers([melody_arp, bass_arp])

        silence = b'\x00\x00' * int(44100 * d(0.25))

        # --- Sustained resolution chord ---
        swell_dur = d(1.2)
        melody_swell = generate_tone(fr(784), swell_dur, volume=0.55, wave_type='square',
                                     attack_time=0.05, release_time=0.4)
        chord_swell = generate_chord(
            [fr(261), fr(329), fr(392)],
            swell_dur, volume=0.35, wave_type='sawtooth',
            attack_time=0.05, release_time=0.4
        )
        swell = mix_layers([melody_swell, chord_swell])

        return arpeggio + silence + swell
