from ..audio_engine.song import Song
from ..audio_engine.core import generate_tone, generate_chord, mix_layers, generate_percussion_pattern

class DungeonSong(Song):
    def __init__(self):
        super().__init__("Dungeon Theme", "bgm_dungeon.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))

        # Theme A: Creeping Dread
        theme_a = [[(220, 0.8), (233, 0.8), (196, 0.8), (220, 1.6)], [(262, 0.8), (247, 0.8), (220, 0.8), (196, 1.6)]]
        # Theme B: Unsettling Arpeggios
        theme_b = [[(220, 0.4), (262, 0.4), (330, 0.4), (262, 0.4)], [(196, 0.4), (247, 0.4), (294, 0.4), (247, 0.4)]]

        prog_a = [([220, 262, 330], 3.2), ([196, 247, 294], 3.2)]
        bass_a = [(110, 3.2), (98, 3.2)]

        all_sections = b''

        # --- Section 1: Ambient Intro ---
        intro_drone = generate_tone(fr(110), d(8.0), 0.4, wave_type='sawtooth')
        intro_atm = generate_tone(fr(220), d(8.0), 0.2, wave_type='sine')
        all_sections += mix_layers([intro_drone, intro_atm])

        # --- Section 2: Creeping Dread (Theme A) x 4 ---
        for _ in range(4):
            mel, chd, bss = b'', b'', b''
            for phrase in theme_a:
                for f, dur in phrase: mel += generate_tone(fr(f), d(dur), 0.3, wave_type='triangle')
            for c, dur in prog_a: chd += generate_chord([fr(x) for x in c], d(dur), 0.2, wave_type='sawtooth')
            for f, dur in bass_a: bss += generate_tone(fr(f), d(dur), 0.4, wave_type='sawtooth')

            dur = 6.4
            perc = generate_percussion_pattern([1, 0, 0, 0, 0, 0, 1, 0], d(dur))
            all_sections += mix_layers([mel, chd, bss, perc])

        # --- Section 3: Tension Build (Theme B) x 8 ---
        for _ in range(8):
            mel, chd = b'', b''
            for phrase in theme_b:
                for f, dur in phrase: mel += generate_tone(fr(f), d(dur), 0.25, wave_type='square')
            for c, dur in prog_a: chd += generate_chord([fr(x) for x in c], d(dur), 0.25, wave_type='triangle')

            dur = 3.2
            perc = generate_percussion_pattern([1, 0, 1, 0], d(dur))
            all_sections += mix_layers([mel, chd, perc])

        # --- Section 4: Deep Darkness (Drone + Random Noises) ---
        drone = generate_tone(fr(55), d(16.0), 0.5, wave_type='sawtooth')
        noise = generate_tone(0, d(16.0), 0.15, wave_type='noise')
        all_sections += mix_layers([drone, noise])

        # --- Section 5: Theme A Reprise (Heavier) x 4 ---
        for _ in range(4):
            mel, chd, bss = b'', b'', b''
            for phrase in theme_a:
                for f, dur in phrase: mel += generate_tone(fr(f), d(dur), 0.35, wave_type='sawtooth')
            for c, dur in prog_a: chd += generate_chord([fr(x) for x in c], d(dur), 0.3, wave_type='square')
            for f, dur in bass_a: bss += generate_tone(fr(f), d(dur), 0.5, wave_type='square')

            dur = 6.4
            perc = generate_percussion_pattern([1, 1, 0, 1, 1, 0, 1, 0], d(dur))
            all_sections += mix_layers([mel, chd, bss, perc])

        return all_sections
