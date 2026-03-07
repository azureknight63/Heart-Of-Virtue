from ..audio_engine.song import Song
from ..audio_engine.core import generate_tone, generate_chord, mix_layers

class ClickSFX(Song):
    def __init__(self):
        super().__init__("SFX: Click", "sfx_click.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        return generate_tone(fr(880), d(0.05), volume=0.6, wave_type='square')

class MoveSFX(Song):
    def __init__(self):
        super().__init__("SFX: Move", "sfx_move.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        return generate_tone(fr(150), d(0.1), volume=0.6, wave_type='triangle')

class ErrorSFX(Song):
    def __init__(self):
        super().__init__("SFX: Error", "sfx_error.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        return generate_tone(fr(100), d(0.3), volume=0.6, wave_type='sawtooth')

class CombatStartSFX(Song):
    def __init__(self):
        super().__init__("SFX: Combat Start", "sfx_combat_start.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        data = b''
        # Descending pattern with lower frequencies for a foreboding feel
        for f in [220, 185, 147, 110]:
            data += generate_tone(fr(f), d(0.15), volume=0.5, wave_type='sawtooth')
        return data

class AttackSFX(Song):
    def __init__(self):
        super().__init__("SFX: Attack", "sfx_attack.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        # Noise doesn't really have frequency to shift in this simple implementation
        return generate_tone(0, d(0.15), volume=0.7, wave_type='noise')
