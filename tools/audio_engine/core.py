import wave
import math
import random
import struct
import os

OUTPUT_DIR = "frontend/public/assets/sounds"

def generate_tone(frequency, duration, volume=0.5, sample_rate=44100, wave_type='square',
                  attack_time=0.01, decay_time=0.0, sustain_level=1.0, release_time=0.01,
                  vibrato_rate=0.0, vibrato_depth=0.0):
    """Generate a single tone with full ADSR envelope and optional vibrato.

    Parameters
    ----------
    frequency : float
        Oscillator frequency in Hz. Ignored for ``wave_type='noise'``.
    duration : float
        Total duration in seconds (includes release tail).
    volume : float
        Peak amplitude (0.0–1.0).
    wave_type : str
        ``'sine'``, ``'square'``, ``'sawtooth'``, ``'triangle'``, or ``'noise'``.
    attack_time : float
        Seconds to ramp from 0 → 1.
    decay_time : float
        Seconds to ramp from 1 → sustain_level after the attack peak.
    sustain_level : float
        Amplitude (0.0–1.0) held after decay until release begins.
    release_time : float
        Seconds to ramp from sustain_level → 0 at the end.
    vibrato_rate : float
        Vibrato LFO frequency in Hz (0 = disabled).
    vibrato_depth : float
        Vibrato depth as a fraction of the base frequency (e.g. 0.02 = ±2 %).

    Notes
    -----
    ADSR regions are evaluated in order: attack → decay → release → sustain.
    If ``attack_time + decay_time > duration - release_time``, the release
    region overlaps the decay region and the envelope will be cut off before
    it reaches ``sustain_level``.  Keep ``attack + decay + release < duration``
    to guarantee a proper sustain tail.
    """
    n_samples = int(sample_rate * duration)
    attack_samples = int(sample_rate * attack_time)
    decay_samples = int(sample_rate * decay_time)
    release_samples = int(sample_rate * release_time)

    data = []
    for i in range(n_samples):
        t = float(i) / sample_rate

        # Vibrato: modulate instantaneous frequency via phase accumulation
        if vibrato_rate > 0 and vibrato_depth > 0 and frequency > 0:
            freq = frequency * (1.0 + vibrato_depth * math.sin(2 * math.pi * vibrato_rate * t))
        else:
            freq = frequency

        if wave_type == 'square':
            val = 1.0 if math.sin(2 * math.pi * freq * t) > 0 else -1.0
        elif wave_type == 'sawtooth':
            val = 2.0 * (t * freq - math.floor(t * freq + 0.5))
        elif wave_type == 'triangle':
            val = 2.0 * abs(2.0 * (t * freq - math.floor(t * freq + 0.5))) - 1.0
        elif wave_type == 'noise':
            val = random.uniform(-1, 1)
        else:  # sine
            val = math.sin(2 * math.pi * freq * t)

        # ADSR envelope
        if i < attack_samples:
            envelope = i / attack_samples if attack_samples > 0 else 1.0
        elif i < attack_samples + decay_samples:
            decay_progress = (i - attack_samples) / decay_samples if decay_samples > 0 else 1.0
            envelope = 1.0 - decay_progress * (1.0 - sustain_level)
        elif i > n_samples - release_samples:
            release_progress = (n_samples - i) / release_samples if release_samples > 0 else 0.0
            envelope = sustain_level * release_progress
        else:
            envelope = sustain_level

        packed_val = struct.pack('h', int(val * volume * envelope * 32767.0))
        data.append(packed_val)
    return b''.join(data)

def generate_tone_sweep(freq_start, freq_end, duration, volume=0.5, sample_rate=44100,
                        wave_type='sine', attack_time=0.01, release_time=0.01):
    """Generate a tone that glides linearly from ``freq_start`` to ``freq_end``.

    Useful for laser zaps, level-up sweeps, and dramatic hit impacts.
    """
    n_samples = int(sample_rate * duration)
    attack_samples = int(sample_rate * attack_time)
    release_samples = int(sample_rate * release_time)

    data = []
    phase = 0.0
    for i in range(n_samples):
        t = float(i) / sample_rate
        progress = t / duration if duration > 0 else 1.0
        freq = freq_start + (freq_end - freq_start) * progress

        # Accumulate phase to avoid discontinuities during sweep
        phase += 2 * math.pi * freq / sample_rate

        if wave_type == 'square':
            val = 1.0 if math.sin(phase) > 0 else -1.0
        elif wave_type == 'sawtooth':
            norm = (phase / (2 * math.pi)) % 1.0
            val = 2.0 * norm - 1.0
        elif wave_type == 'triangle':
            norm = (phase / (2 * math.pi)) % 1.0
            val = 2.0 * abs(2.0 * norm - 1.0) - 1.0
        else:  # sine
            val = math.sin(phase)

        envelope = 1.0
        if i < attack_samples:
            envelope = i / attack_samples if attack_samples > 0 else 1.0
        elif i > n_samples - release_samples:
            envelope = (n_samples - i) / release_samples if release_samples > 0 else 0.0

        packed_val = struct.pack('h', int(val * volume * envelope * 32767.0))
        data.append(packed_val)
    return b''.join(data)


def generate_chord(frequencies, duration, volume=0.3, sample_rate=44100, wave_type='square', attack_time=0.01, release_time=0.01):
    """Generate a chord by mixing multiple frequencies"""
    n_samples = int(sample_rate * duration)
    attack_samples = int(sample_rate * attack_time)
    release_samples = int(sample_rate * release_time)
    
    n_freqs = len(frequencies)
    data = []
    for i in range(n_samples):
        t = float(i) / sample_rate
        val = 0.0
        for freq in frequencies:
            if wave_type == 'square':
                val += (1.0 if math.sin(2 * math.pi * freq * t) > 0 else -1.0) / n_freqs
            elif wave_type == 'sawtooth':
                val += (2.0 * (t * freq - math.floor(t * freq + 0.5))) / n_freqs
            elif wave_type == 'triangle':
                val += (2.0 * abs(2.0 * (t * freq - math.floor(t * freq + 0.5))) - 1.0) / n_freqs
            else:  # sine
                val += math.sin(2 * math.pi * freq * t) / n_freqs
        
        # Apply Envelope
        envelope = 1.0
        if i < attack_samples:
            envelope = i / attack_samples if attack_samples > 0 else 1.0
        elif i > n_samples - release_samples:
            envelope = (n_samples - i) / release_samples if release_samples > 0 else 0.0
            
        packed_val = struct.pack('h', int(val * volume * envelope * 32767.0))
        data.append(packed_val)
    return b''.join(data)

def mix_layers(layers, sample_rate=44100):
    """Mix multiple audio layers together by adding their waveforms"""
    if not layers:
        return b''
    
    # Find the longest layer
    max_length = max(len(layer) for layer in layers)
    
    # Pad shorter layers with silence
    padded_layers = []
    for layer in layers:
        if len(layer) < max_length:
            padding = b'\x00\x00' * ((max_length - len(layer)) // 2)
            padded_layers.append(layer + padding)
        else:
            padded_layers.append(layer)
    
    # Mix by adding samples
    mixed = []
    for i in range(0, max_length, 2):
        sample_sum = 0
        for layer in padded_layers:
            if i + 1 < len(layer):
                sample = struct.unpack('h', layer[i:i+2])[0]
                sample_sum += sample
        
        # Normalize to prevent clipping
        sample_sum = int(sample_sum * 0.7)  # Reduce volume to prevent distortion
        sample_sum = max(-32767, min(32767, sample_sum))
        mixed.append(struct.pack('h', sample_sum))
    
    return b''.join(mixed)

def generate_percussion_pattern(pattern, duration, sample_rate=44100):
    """Generate a percussion pattern using noise bursts"""
    data = []
    beat_duration = duration / len(pattern)
    
    for beat in pattern:
        beat_samples = int(sample_rate * beat_duration)
        if beat == 1:  # Hit
            for i in range(beat_samples):
                # Short decay envelope
                envelope = max(0, 1.0 - (i / beat_samples) * 3)
                val = random.uniform(-1, 1) * envelope * 0.4
                data.append(struct.pack('h', int(val * 32767.0)))
        else:  # Rest
            for _ in range(beat_samples):
                data.append(b'\x00\x00')
    
    return b''.join(data)

def save_wav(filename, data, sample_rate=44100):
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    filepath = os.path.join(OUTPUT_DIR, filename)
    try:
        f = wave.open(filepath, 'w')
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(data)
        f.close()
        print(f"Generated {filepath}")
    except Exception as e:
        print(f"Error saving {filename}: {e}")
        import traceback
        traceback.print_exc()
