from ..audio_engine.song import Song
from ..audio_engine.core import generate_tone, generate_chord, mix_layers, generate_percussion_pattern

class BattleSong(Song):
    def __init__(self):
        super().__init__("Battle Theme", "bgm_battle.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        
        # --- Musical Building Blocks ---
        
        # Theme A: The Skirmish (Syncopated Riff in A Minor)
        # A3, C4, E4, A3, G3, A3 (Driving)
        theme_a = [
            [(220, 0.2), (262, 0.2), (330, 0.2), (220, 0.2), (196, 0.2), (220, 0.2)], # Measure 1
            [(220, 0.2), (262, 0.2), (330, 0.2), (392, 0.2), (330, 0.2), (262, 0.2)], # Measure 2
            [(220, 0.2), (262, 0.2), (330, 0.1), (349, 0.1), (330, 0.1), (349, 0.1), (330, 0.2), (262, 0.2)], # Measure 3 (Trill E-F-E-F)
            [(196, 0.2), (220, 0.2), (262, 0.2), (196, 0.2), (175, 0.4)], # Measure 4
        ]
        
        # Theme B: The Hero's Turn (Trumpet-like, Noble)
        # C Major / F Major lift
        theme_b = [
            [(523, 0.6), (587, 0.2), (659, 0.4), (523, 0.4), (659, 0.8)], # C-D-E-C-E
            [(698, 0.6), (659, 0.2), (587, 0.4), (523, 0.4), (587, 0.8)], # F-E-D-C-D
            [(659, 0.6), (784, 0.2), (880, 0.4), (659, 0.4), (1047, 0.8)], # E-G-A-E-C
            [(988, 0.6), (880, 0.2), (784, 0.4), (698, 0.4), (659, 0.8)], # B-A-G-F-E
        ]
        
        # Theme C: The Enemy Strikes (Crisis, Chromatic)
        # Chromatic descent
        theme_c = [
            [(440, 0.15), (415, 0.15), (392, 0.15), (370, 0.15)] * 2,
            [(349, 0.15), (330, 0.15), (311, 0.15), (294, 0.15)] * 2,
        ]
        
        # Theme D: Victory in Sight (Major Key Climax)
        # A Major lift
        theme_d = [
            [(554, 0.3), (440, 0.3), (554, 0.3), (659, 0.3)], # C#-A-C#-E
            [(740, 0.3), (659, 0.3), (554, 0.6)], # F#-E-C#
            [(880, 0.3), (740, 0.3), (659, 0.3), (554, 0.3)], # A-F#-E-C#
            [(494, 0.3), (554, 0.3), (659, 0.6)], # B-C#-E (Transition back to A minor)
        ]

        # Progressions
        prog_a = [([220, 262, 330], 1.2), ([196, 247, 294], 1.2)] # Am - G
        prog_b = [([262, 330, 392], 2.4), ([349, 440, 523], 2.4)] # C - F
        prog_c = [([220, 262, 311], 1.2), ([208, 247, 294], 1.2)] # Am(dim) - G#(dim)
        prog_d = [([440, 554, 659], 1.2), ([294, 370, 440], 1.2)] # A Major - D Major

        # Bass
        bass_a = [(110, 0.6), (110, 0.6)]
        bass_b = [(131, 2.4), (175, 2.4)]
        bass_c = [(110, 0.3), (104, 0.3), (98, 0.3), (92, 0.3)]
        bass_d = [(220, 0.6), (147, 0.6)]

        all_sections = b''

        # --- Section 1: Intro Fanfare + Crescendo ---
        fanfare_chords = [([440, 554, 659], 0.2), ([440, 554, 659], 0.2), ([440, 554, 659], 0.2), ([440, 554, 659], 0.6)]
        intro_layer = b''
        for c, dur in fanfare_chords:
            intro_layer += generate_chord([fr(x) for x in c], d(dur), 0.4, wave_type='sawtooth')
        
        # Percussion build up (Snare roll)
        intro_dur = sum(d(dur) for c, dur in fanfare_chords)
        intro_perc = generate_percussion_pattern([1, 1, 1, 1, 1, 1, 1, 1], intro_dur)
        
        all_sections += mix_layers([intro_layer, intro_perc])

        # Main Loop x 4 (To reach ~3-4 mins)
        for loop_idx in range(4):
            # --- Section 2: Theme A (The Skirmish) x 2 ---
            for _ in range(2):
                mel, chd, bss = b'', b'', b''
                for phrase in theme_a:
                    for f, dur in phrase: mel += generate_tone(fr(f), d(dur), 0.35, wave_type='sawtooth')
                
                # Accompaniment
                dur = sum(d(dur) for p in theme_a for _, dur in p)
                current_dur = 0
                while current_dur < dur:
                    for c, dur_c in prog_a:
                        if current_dur >= dur: break
                        chd += generate_chord([fr(x) for x in c], min(d(dur_c), dur - current_dur), 0.25, wave_type='square')
                        current_dur += d(dur_c)
                
                current_dur = 0
                while current_dur < dur:
                    for f, dur_f in bass_a:
                        if current_dur >= dur: break
                        bss += generate_tone(fr(f), min(d(dur_f), dur - current_dur), 0.4, wave_type='square') # Punchy bass
                        current_dur += d(dur_f)
                
                # Driving Percussion
                perc = generate_percussion_pattern([1, 0, 1, 1, 1, 0, 1, 0] * int(dur), dur)
                all_sections += mix_layers([mel, chd, bss, perc])

            # --- Section 3: Theme B (The Hero's Turn) x 2 ---
            for _ in range(2):
                mel, harm, chd, bss = b'', b'', b'', b''
                for phrase in theme_b:
                    for f, dur in phrase: mel += generate_tone(fr(f), d(dur), 0.4, wave_type='sawtooth') # Trumpet-like
                    for f, dur in phrase: harm += generate_tone(fr(f*0.75), d(dur), 0.15, wave_type='square') # Counter-melody (lower 4th/5th)
                
                dur = sum(d(dur) for p in theme_b for _, dur in p)
                current_dur = 0
                while current_dur < dur:
                    for c, dur_c in prog_b:
                        if current_dur >= dur: break
                        chd += generate_chord([fr(x) for x in c], min(d(dur_c), dur - current_dur), 0.2, wave_type='sawtooth')
                        current_dur += d(dur_c)
                
                current_dur = 0
                while current_dur < dur:
                    for f, dur_f in bass_b:
                        if current_dur >= dur: break
                        bss += generate_tone(fr(f), min(d(dur_f), dur - current_dur), 0.3, wave_type='triangle')
                        current_dur += d(dur_f)
                
                perc = generate_percussion_pattern([1, 0, 1, 0] * int(dur), dur)
                all_sections += mix_layers([mel, harm, chd, bss, perc])

            # --- Section 4: Theme C (The Enemy Strikes) x 2 ---
            for _ in range(2):
                mel, chd, bss = b'', b'', b''
                for phrase in theme_c:
                    for f, dur in phrase: mel += generate_tone(fr(f), d(dur), 0.3, wave_type='sawtooth')
                
                dur = sum(d(dur) for p in theme_c for _, dur in p)
                current_dur = 0
                while current_dur < dur:
                    for c, dur_c in prog_c:
                        if current_dur >= dur: break
                        chd += generate_chord([fr(x) for x in c], min(d(dur_c), dur - current_dur), 0.25, wave_type='sawtooth') # Discordant
                        current_dur += d(dur_c)
                
                current_dur = 0
                while current_dur < dur:
                    for f, dur_f in bass_c:
                        if current_dur >= dur: break
                        bss += generate_tone(fr(f), min(d(dur_f), dur - current_dur), 0.5, wave_type='square') # Heavy Bass
                        current_dur += d(dur_f)
                
                # Chaotic Percussion
                perc = generate_percussion_pattern([1, 1, 1, 0, 1, 1, 0, 1] * int(dur * 2), dur)
                all_sections += mix_layers([mel, chd, bss, perc])

            # --- Section 5: Theme D (Victory / Climax) x 2 ---
            for _ in range(2):
                mel, chd, bss = b'', b'', b''
                for phrase in theme_d:
                    for f, dur in phrase: mel += generate_tone(fr(f), d(dur), 0.4, wave_type='square')
                
                dur = sum(d(dur) for p in theme_d for _, dur in p)
                current_dur = 0
                while current_dur < dur:
                    for c, dur_c in prog_d:
                        if current_dur >= dur: break
                        chd += generate_chord([fr(x) for x in c], min(d(dur_c), dur - current_dur), 0.3, wave_type='sawtooth')
                        current_dur += d(dur_c)
                
                current_dur = 0
                while current_dur < dur:
                    for f, dur_f in bass_d:
                        if current_dur >= dur: break
                        bss += generate_tone(fr(f), min(d(dur_f), dur - current_dur), 0.35, wave_type='sawtooth')
                        current_dur += d(dur_f)
                
                perc = generate_percussion_pattern([1, 1, 1, 1] * int(dur), dur)
                all_sections += mix_layers([mel, chd, bss, perc])

        return all_sections
