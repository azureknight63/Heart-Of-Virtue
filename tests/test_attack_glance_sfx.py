"""Design contract for the glancing-blow combat cue (``sfx/attack_glance.wav``).

A glance deals *half* damage: it must not be confusable with either neighbour.
Mistaking it for ``attack_hit`` under-reads the deflection; mistaking it for
``attack_parry`` reads as no damage at all. These tests pin the measurable
properties that keep the three apart, so a later tweak to the synthesis cannot
quietly collapse the glance into one of them.

The scrape layer is white noise, so every render differs. Assertions are
therefore bounds and ratios, never exact sample values, and the clipping check
renders repeatedly rather than trusting one lucky draw.
"""
import math
import struct

import pytest

from tools.audio_engine.core import save_wav  # noqa: F401  (import-health check)
from tools.generate_audio import SONG_LIST
from tools.songs.sfx import AttackGlanceSFX, AttackHitSFX, AttackParrySFX

SAMPLE_RATE = 44100
FULL_SCALE = 32767


def _samples(data):
    """Decode 16-bit little-endian mono PCM bytes to a list of ints."""
    return list(struct.unpack("<%dh" % (len(data) // 2), data))


def _rms(values):
    return math.sqrt(sum(v * v for v in values) / len(values)) if values else 0.0


def _lowpass(values, cutoff_hz, poles=2):
    """Cheap two-pole RC low-pass — a numpy-free stand-in for a band analyser."""
    dt = 1.0 / SAMPLE_RATE
    rc = 1.0 / (2 * math.pi * cutoff_hz)
    alpha = dt / (rc + dt)
    for _ in range(poles):
        out, prev = [], 0.0
        for value in values:
            prev += alpha * (value - prev)
            out.append(prev)
        values = out
    return values


def _low_band_share(values):
    """Fraction of the cue's energy sitting below ~200 Hz (i.e. 'thud weight')."""
    total = _rms(values)
    return _rms(_lowpass(values, 200.0)) / total if total else 0.0


@pytest.fixture(scope="module")
def glance():
    return _samples(AttackGlanceSFX().render())


@pytest.fixture(scope="module")
def hit():
    return _samples(AttackHitSFX().render())


@pytest.fixture(scope="module")
def parry():
    return _samples(AttackParrySFX().render())


def test_registered_for_rendering():
    """The cue must be in SONG_LIST or `generate_audio.py` never writes the WAV."""
    glances = [s for s in SONG_LIST if isinstance(s, AttackGlanceSFX)]
    assert len(glances) == 1
    assert glances[0].filename == "sfx/attack_glance.wav"
    assert glances[0].title == "SFX: Attack Glance"


def test_duration_is_short_and_undercuts_both_neighbours(glance, hit, parry):
    """~120 ms: snappier than the thud, far shorter than the parry's ring.

    This fires on roughly 10% of hits in a fast combat loop, so length is a
    fatigue budget, not a taste call.
    """
    ms = len(glance) / SAMPLE_RATE * 1000
    assert 100 <= ms <= 140, ms
    assert len(glance) < len(hit) < len(parry)


def test_does_not_clip(glance):
    """Peak must stay under full scale; the mix has no limiter behind it."""
    assert max(abs(v) for v in glance) < FULL_SCALE


def test_repeated_renders_never_clip():
    """The noise layer is unseeded, so clip-safety needs headroom, not luck."""
    for _ in range(6):
        peak = max(abs(v) for v in _samples(AttackGlanceSFX().render()))
        assert peak < FULL_SCALE, peak


def test_peak_is_comparable_to_the_hit_cue(glance, hit):
    """Within ~6 dB of the hit's peak: a glance is lighter, not distant."""
    ratio = max(abs(v) for v in glance) / max(abs(v) for v in hit)
    assert 0.5 <= ratio <= 1.0, ratio


def test_carries_almost_none_of_the_hit_cue_low_end(glance, hit):
    """The anti-'quiet hit' guard.

    ``attack_hit`` is a 90 Hz sawtooth thud and puts over half its energy below
    200 Hz. The glance's tonal core starts at 880 Hz and only bleeds down to
    300 Hz, so it must stay far clear of that band — otherwise a glance reads
    as the same blow heard from further away.
    """
    assert _low_band_share(glance) < _low_band_share(hit) / 4


def test_keeps_more_body_than_the_parry_ring(glance, parry):
    """The anti-'parry' guard.

    A parry means nothing landed; a glance means half of it did. The glance
    keeps audible low-mid contact weight that the 1200 Hz ring does not.
    """
    assert _low_band_share(glance) > _low_band_share(parry) * 1.2


def test_tempo_scale_shortens_the_cue():
    fast = AttackGlanceSFX().render(tempo_scale=2.0)
    normal = AttackGlanceSFX().render()
    assert len(fast) < len(normal)


def test_pitch_shift_renders_a_different_cue_of_equal_length():
    shifted = AttackGlanceSFX().render(pitch_shift=12)
    normal = AttackGlanceSFX().render()
    assert len(shifted) == len(normal)
    assert shifted != normal
