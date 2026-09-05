"""Design contract for the glancing-blow combat cue (``sfx/attack_glance.wav``).

A glance deals *half* damage: it must not be confusable with either neighbour.
Mistaking it for ``attack_hit`` under-reads the deflection; mistaking it for
``attack_parry`` reads as no damage at all. These tests pin the measurable
properties that keep the three apart, so a later tweak to the synthesis cannot
quietly collapse the glance into one of them.

The scrape layer is white noise, so every *unseeded* render differs. Assertions
are therefore bounds and ratios, never exact sample values -- and every render
below is taken against a pinned draw of the RNG that supplies that noise.

Why the seeding is not optional
-------------------------------
``tools.audio_engine.core`` draws its noise from the process-global stdlib
``random`` (``random.uniform(-1, 1)`` in the ``'noise'`` branch of
``generate_tone``); nothing else on the render path is random. Left unseeded,
``test_keeps_more_body_than_the_parry_ring`` compared the sub-200 Hz share of
two *independent* draws, and that share varies enough per draw (~6 % relative
spread for the glance, ~9 % for the parry) that the pair landed under the 1.2
ratio in roughly one run in a thousand. ``--randomly-seed=897`` reproduces
exactly that failure against the pre-seeding version of this file.

The claim itself was never in doubt -- the ratio averages ~1.65 -- only the
sample size was wrong. So the two band-share assertions now average over
``SAMPLE_SEEDS`` instead of trusting a single draw, and the clipping sweep
walks the same spread. **Do not answer a failure here by widening a bound**:
these means are stable to within a few percent across seed blocks, so a mean
that has moved is an SFX that has moved.
"""
import math
import random
import struct
from contextlib import contextmanager

import pytest

from tools.audio_engine.core import save_wav  # noqa: F401  (import-health check)
from tools.generate_audio import SONG_LIST
from tools.songs.sfx import AttackGlanceSFX, AttackHitSFX, AttackParrySFX

SAMPLE_RATE = 44100
FULL_SCALE = 32767

#: The single draw the one-render fixtures are pinned to. Arbitrary, but fixed.
RENDER_SEED = 4242

#: The spread the band-share means average over, and the clipping check sweeps.
#: Twelve draws is enough to make the choice of block immaterial: the mean
#: glance/parry ratio over 100 disjoint blocks of 12 spans 1.58-1.74, where the
#: same statistic from single draws spans 1.40-1.99 (and 1.12 when the glance
#: and parry draws are independent, which is what used to fail).
#:
#: Deliberately disjoint from ``RENDER_SEED``: the clipping sweep and
#: ``test_does_not_clip`` would otherwise cover overlapping draws, and the
#: latter could never fail on its own.
SAMPLE_SEEDS = tuple(range(RENDER_SEED + 1, RENDER_SEED + 13))


@contextmanager
def _seeded(seed):
    """Run a render against a pinned global RNG, restoring the state after.

    Restoring matters as much as seeding: the suite runs under
    ``pytest-randomly``, which reseeds per test, and a leaked seed would
    silently pin whatever ran next.

    This mirrors ``tests/_combat_fixtures.seeded`` rather than importing it on
    purpose — that module pulls in ``src.items``/``src.npc``/``src.player``,
    and instantiating those mutates module-level registries (see CLAUDE.md).
    An audio test has no business dragging the engine in for six lines.
    """
    state = random.getstate()
    random.seed(seed)
    try:
        yield
    finally:
        random.setstate(state)


def _samples(data):
    """Decode 16-bit little-endian mono PCM bytes to a list of ints."""
    return list(struct.unpack("<%dh" % (len(data) // 2), data))


def _render(song, seed=RENDER_SEED, **kwargs):
    """Decode one render of ``song`` taken against a pinned noise draw."""
    with _seeded(seed):
        return _samples(song.render(**kwargs))


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


def _mean_low_band_share(song_cls):
    """Mean :func:`_low_band_share` of ``song_cls`` across ``SAMPLE_SEEDS``.

    The per-draw spread of this statistic is what made a single-render ratio
    flaky; averaging measures the synthesis rather than the draw.
    """
    shares = [_low_band_share(_render(song_cls(), seed)) for seed in SAMPLE_SEEDS]
    return sum(shares) / len(shares)


@pytest.fixture(scope="module")
def glance():
    return _render(AttackGlanceSFX())


@pytest.fixture(scope="module")
def hit():
    return _render(AttackHitSFX())


@pytest.fixture(scope="module")
def parry():
    return _render(AttackParrySFX())


@pytest.fixture(scope="module")
def glance_low_band():
    return _mean_low_band_share(AttackGlanceSFX)


@pytest.fixture(scope="module")
def hit_low_band():
    return _mean_low_band_share(AttackHitSFX)


@pytest.fixture(scope="module")
def parry_low_band():
    return _mean_low_band_share(AttackParrySFX)


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
    """Clip-safety must hold across noise draws, not only the pinned one.

    Peak headroom is the thinnest margin in this file — the loudest of 400
    sampled draws still reached 92 % of full scale — so this walks the whole
    seed spread rather than re-checking the fixture's single render.
    """
    for seed in SAMPLE_SEEDS:
        peak = max(abs(v) for v in _render(AttackGlanceSFX(), seed))
        assert peak < FULL_SCALE, (seed, peak)


def test_peak_is_comparable_to_the_hit_cue(glance, hit):
    """Within ~6 dB of the hit's peak: a glance is lighter, not distant."""
    ratio = max(abs(v) for v in glance) / max(abs(v) for v in hit)
    assert 0.5 <= ratio <= 1.0, ratio


def test_carries_almost_none_of_the_hit_cue_low_end(glance_low_band, hit_low_band):
    """The anti-'quiet hit' guard.

    ``attack_hit`` is a 90 Hz sawtooth thud and puts over half its energy below
    200 Hz. The glance's tonal core starts at 880 Hz and only bleeds down to
    300 Hz, so it must stay far clear of that band — otherwise a glance reads
    as the same blow heard from further away.
    """
    assert glance_low_band < hit_low_band / 4


def test_keeps_more_body_than_the_parry_ring(glance_low_band, parry_low_band):
    """The anti-'parry' guard.

    A parry means nothing landed; a glance means half of it did. The glance
    keeps audible low-mid contact weight that the 1200 Hz ring does not.
    """
    assert glance_low_band > parry_low_band * 1.2


def test_tempo_scale_shortens_the_cue():
    fast = _render(AttackGlanceSFX(), tempo_scale=2.0)
    normal = _render(AttackGlanceSFX())
    assert len(fast) < len(normal)


def test_pitch_shift_renders_a_different_cue_of_equal_length():
    """Both renders share one noise draw, so only the tonal layers can differ.

    Unseeded this passed vacuously: the scrape grains alone make any two
    renders unequal, whether or not ``pitch_shift`` ever reaches the sweeps.
    """
    shifted = _render(AttackGlanceSFX(), pitch_shift=12)
    normal = _render(AttackGlanceSFX())
    assert len(shifted) == len(normal)
    assert shifted != normal
