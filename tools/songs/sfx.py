from ..audio_engine.song import Song
from ..audio_engine.core import generate_tone, generate_chord, mix_layers


# ── UI / Menu SFX (retro chiptune aesthetic) ─────────────────────────────────

class ClickSFX(Song):
    """Crisp two-note upward chirp for button presses."""
    def __init__(self):
        super().__init__("SFX: Click", "sfx_click.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        low = generate_tone(fr(440), d(0.025), volume=0.55, wave_type='square',
                            attack_time=0.002, release_time=0.005)
        high = generate_tone(fr(880), d(0.03), volume=0.5, wave_type='square',
                             attack_time=0.002, release_time=0.01)
        return low + high


class MoveSFX(Song):
    """Soft triangle step sound for cursor/world movement."""
    def __init__(self):
        super().__init__("SFX: Move", "sfx_move.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        return generate_tone(fr(220), d(0.08), volume=0.45, wave_type='triangle',
                             attack_time=0.01, release_time=0.05)


class ErrorSFX(Song):
    """Descending sawtooth tones for invalid actions."""
    def __init__(self):
        super().__init__("SFX: Error", "sfx_error.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        data = b''
        for f in [350, 280, 220]:
            data += generate_tone(fr(f), d(0.1), volume=0.6, wave_type='sawtooth',
                                  attack_time=0.005, release_time=0.02)
        return data


class UiConfirmSFX(Song):
    """Ascending C-E-G arpeggio for confirming a move/selection."""
    def __init__(self):
        super().__init__("SFX: UI Confirm", "sfx_ui_confirm.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        data = b''
        # C5 – E5 – G5
        for f in [523, 659, 784]:
            data += generate_tone(fr(f), d(0.06), volume=0.55, wave_type='square',
                                  attack_time=0.005, release_time=0.01)
        return data


# ── Combat SFX (dramatic synthesized, more visceral) ─────────────────────────

class CombatStartSFX(Song):
    """Low power-chord stab followed by a rising alarm arpeggio."""
    def __init__(self):
        super().__init__("SFX: Combat Start", "sfx_combat_start.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        low = generate_tone(fr(110), d(0.2), volume=0.5, wave_type='sawtooth',
                            attack_time=0.01, release_time=0.05)
        mid = generate_tone(fr(165), d(0.2), volume=0.4, wave_type='square',
                            attack_time=0.01, release_time=0.05)
        stab = mix_layers([low, mid])
        silence = b'\x00\x00' * int(44100 * d(0.05))
        alarm = b''
        for f in [220, 293, 369, 440]:
            alarm += generate_tone(fr(f), d(0.12), volume=0.55, wave_type='square',
                                   attack_time=0.005, release_time=0.02)
        return stab + silence + alarm


class AttackSFX(Song):
    """Short downward chirp played when selecting an attack move."""
    def __init__(self):
        super().__init__("SFX: Attack", "sfx_attack.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        high = generate_tone(fr(660), d(0.04), volume=0.55, wave_type='square',
                             attack_time=0.003, release_time=0.01)
        low = generate_tone(fr(440), d(0.06), volume=0.5, wave_type='square',
                            attack_time=0.003, release_time=0.02)
        return high + low


class AttackSwipeSFX(Song):
    """Noise whoosh for the moment an attack is launched."""
    def __init__(self):
        super().__init__("SFX: Attack Swipe", "sfx_attack_swipe.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        # Fast attack, long release gives the 'whoosh' tail
        return generate_tone(0, d(0.2), volume=0.75, wave_type='noise',
                             attack_time=0.01, release_time=0.14)


class AttackHitSFX(Song):
    """Low sawtooth thud + noise burst — heavy impact sound."""
    def __init__(self):
        super().__init__("SFX: Attack Hit", "sfx_attack_hit.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        thud = generate_tone(fr(90), d(0.15), volume=0.8, wave_type='sawtooth',
                             attack_time=0.005, release_time=0.1)
        impact = generate_tone(0, d(0.12), volume=0.7, wave_type='noise',
                               attack_time=0.002, release_time=0.08)
        return mix_layers([thud, impact])


class AttackMissSFX(Song):
    """Soft fading noise — air whoosh with no impact."""
    def __init__(self):
        super().__init__("SFX: Attack Miss", "sfx_attack_miss.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        return generate_tone(0, d(0.25), volume=0.35, wave_type='noise',
                             attack_time=0.02, release_time=0.2)


class AttackParrySFX(Song):
    """High-pitched square ring + noise clang — metallic parry clash."""
    def __init__(self):
        super().__init__("SFX: Attack Parry", "sfx_attack_parry.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        ring = generate_tone(fr(1200), d(0.2), volume=0.6, wave_type='square',
                             attack_time=0.002, release_time=0.15)
        clang = generate_tone(0, d(0.1), volume=0.65, wave_type='noise',
                              attack_time=0.002, release_time=0.07)
        return mix_layers([ring, clang])


class EnemyDeathSFX(Song):
    """Descending sawtooth steps into a fading noise tail."""
    def __init__(self):
        super().__init__("SFX: Enemy Death", "sfx_enemy_death.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        data = b''
        for f in [300, 240, 190, 140, 100]:
            data += generate_tone(fr(f), d(0.1), volume=0.6, wave_type='sawtooth',
                                  attack_time=0.005, release_time=0.05)
        data += generate_tone(0, d(0.3), volume=0.4, wave_type='noise',
                              attack_time=0.01, release_time=0.25)
        return data


class LowHealthWarningSFX(Song):
    """Three rapid urgent beeps — warning when HP is critical."""
    def __init__(self):
        super().__init__("SFX: Low Health Warning", "sfx_low_health_warning.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        silence = b'\x00\x00' * int(44100 * d(0.04))
        data = b''
        for _ in range(3):
            data += generate_tone(fr(880), d(0.07), volume=0.75, wave_type='square',
                                  attack_time=0.005, release_time=0.01)
            data += silence
        return data
