from ..audio_engine.song import Song
from ..audio_engine.core import generate_tone, generate_tone_sweep, generate_chord, mix_layers


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


# ── Progression / Reward SFX ─────────────────────────────────────────────────

class LevelUpSFX(Song):
    """Rising arpeggio sweep + sparkle overtone — character levels up."""
    def __init__(self):
        super().__init__("SFX: Level Up", "sfx_level_up.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        # Rising C major arpeggio two octaves
        arp = b''
        notes = [fr(f) for f in [262, 330, 392, 523, 659, 784, 1047]]
        for i, f in enumerate(notes):
            dur = d(0.07) if i < len(notes) - 1 else d(0.35)
            arp += generate_tone(f, dur, volume=0.55, wave_type='square',
                                 attack_time=0.003, release_time=d(0.03))
        # Sparkle: a bright sine sweep overlay
        sweep = generate_tone_sweep(fr(1047), fr(2093), d(0.5),
                                    volume=0.25, wave_type='sine',
                                    attack_time=d(0.05), release_time=d(0.3))
        return mix_layers([arp, sweep])


class QuestCompleteSFX(Song):
    """Two-chord resolution stab — quest milestone achieved."""
    def __init__(self):
        super().__init__("SFX: Quest Complete", "sfx_quest_complete.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        # IV → I in C major (F maj → C maj): classic resolution
        chord_f = generate_chord([fr(349), fr(440), fr(523)], d(0.18),
                                 volume=0.55, wave_type='square',
                                 attack_time=0.005, release_time=0.04)
        silence = b'\x00\x00' * int(44100 * d(0.04))
        chord_c = generate_chord([fr(262), fr(330), fr(392)], d(0.55),
                                 volume=0.60, wave_type='square',
                                 attack_time=0.005, release_time=d(0.3))
        # High melody note over the resolution
        melody = b'\x00\x00' * int(44100 * d(0.22))  # wait for the F chord + pause
        melody += generate_tone(fr(1047), d(0.55), volume=0.4, wave_type='sine',
                                attack_time=0.01, release_time=d(0.3))
        return mix_layers([chord_f + silence + chord_c, melody])


class ItemUseSFX(Song):
    """Soft shimmer + warm thud — using an item from inventory."""
    def __init__(self):
        super().__init__("SFX: Item Use", "sfx_item_use.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        # Gentle descending shimmer
        shimmer = generate_tone_sweep(fr(880), fr(440), d(0.25),
                                      volume=0.35, wave_type='sine',
                                      attack_time=d(0.03), release_time=d(0.15))
        # Soft thud underneath
        thud = generate_tone(fr(120), d(0.18), volume=0.45, wave_type='triangle',
                             attack_time=0.005, decay_time=0.04, sustain_level=0.3,
                             release_time=0.12)
        return mix_layers([shimmer, thud])


class HealSFX(Song):
    """Warm ascending tone + soft chord — HP restored."""
    def __init__(self):
        super().__init__("SFX: Heal", "sfx_heal.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        # Ascending sine tones with vibrato — warm and organic
        notes = [fr(f) for f in [262, 330, 392, 523]]
        melody = b''
        for f in notes:
            melody += generate_tone(f, d(0.12), volume=0.4, wave_type='sine',
                                    attack_time=d(0.02), release_time=d(0.06),
                                    vibrato_rate=5.0, vibrato_depth=0.015)
        # Chord swell underneath
        chord = generate_chord([fr(262), fr(330), fr(392)], d(0.6),
                               volume=0.25, wave_type='sine',
                               attack_time=d(0.1), release_time=d(0.35))
        return mix_layers([melody, chord])


class StatusHitSFX(Song):
    """Buzzing square warble — a status effect lands on a target."""
    def __init__(self):
        super().__init__("SFX: Status Hit", "sfx_status_hit.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        # Dissonant wobble: square wave with fast vibrato
        warble = generate_tone(fr(220), d(0.22), volume=0.55, wave_type='square',
                               attack_time=0.004, release_time=d(0.1),
                               vibrato_rate=18.0, vibrato_depth=0.06)
        # High crackle accent
        crackle = generate_tone(fr(880), d(0.08), volume=0.4, wave_type='square',
                                attack_time=0.002, release_time=0.06)
        return mix_layers([warble, crackle])


class PlayerDeathSFX(Song):
    """Slow descending sawtooth drone — Jean is defeated."""
    def __init__(self):
        super().__init__("SFX: Player Death", "sfx_player_death.wav")

    def render(self, tempo_scale=1.0, pitch_shift=0) -> bytes:
        def d(dur): return dur / tempo_scale
        def fr(freq): return freq * (2 ** (pitch_shift / 12))
        # Slow descending sweep — falling
        fall = generate_tone_sweep(fr(330), fr(55), d(1.8),
                                   volume=0.65, wave_type='sawtooth',
                                   attack_time=d(0.05), release_time=d(0.8))
        # Low noise rumble underneath
        rumble = generate_tone(0, d(1.8), volume=0.3, wave_type='noise',
                               attack_time=d(0.1), release_time=d(1.0))
        return mix_layers([fall, rumble])
