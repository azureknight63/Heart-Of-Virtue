import wave
import math
import random
import struct
import os

OUTPUT_DIR = "frontend/public/assets/sounds"

def generate_tone(frequency, duration, volume=0.5, sample_rate=44100, wave_type='square'):
    n_samples = int(sample_rate * duration)
    data = []
    for i in range(n_samples):
        t = float(i) / sample_rate
        if wave_type == 'square':
            val = 1.0 if math.sin(2 * math.pi * frequency * t) > 0 else -1.0
        elif wave_type == 'sawtooth':
            val = 2.0 * (t * frequency - math.floor(t * frequency + 0.5))
        elif wave_type == 'triangle':
            val = 2.0 * abs(2.0 * (t * frequency - math.floor(t * frequency + 0.5))) - 1.0
        elif wave_type == 'noise':
            val = random.uniform(-1, 1)
        else: # sine
            val = math.sin(2 * math.pi * frequency * t)
        
        packed_val = struct.pack('h', int(val * volume * 32767.0))
        data.append(packed_val)
    return b''.join(data)

def save_wav(filename, data, sample_rate=44100):
    filepath = os.path.join(OUTPUT_DIR, filename)
    with wave.open(filepath, 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(data)
    print(f"Generated {filepath}")

def generate_bgm_adventure():
    # Simple cheerful melody
    melody = [
        (440, 0.4), (554, 0.4), (659, 0.4), (554, 0.4), 
        (440, 0.4), (554, 0.4), (659, 0.4), (554, 0.4),
        (587, 0.4), (740, 0.4), (880, 0.4), (740, 0.4),
        (587, 0.4), (740, 0.4), (880, 0.4), (740, 0.4)
    ]
    data = b''
    # Loop it a few times to make it longer
    for _ in range(16): 
        for freq, dur in melody:
            data += generate_tone(freq, dur, volume=0.3, wave_type='square')
    save_wav("bgm_adventure.wav", data)

def generate_bgm_dungeon():
    # Lower, slower, more ominous
    melody = [
        (110, 0.8), (123, 0.8), (110, 0.8), (103, 0.8),
        (110, 0.8), (130, 0.8), (110, 0.8), (98, 0.8)
    ]
    data = b''
    for _ in range(16):
        for freq, dur in melody:
            data += generate_tone(freq, dur, volume=0.4, wave_type='triangle')
    save_wav("bgm_dungeon.wav", data)

def generate_bgm_battle():
    # Faster, more energetic
    melody = [
        (220, 0.2), (220, 0.2), (261, 0.2), (220, 0.2),
        (330, 0.2), (293, 0.2), (261, 0.2), (247, 0.2)
    ]
    data = b''
    for _ in range(32):
        for freq, dur in melody:
            data += generate_tone(freq, dur, volume=0.4, wave_type='sawtooth')
    save_wav("bgm_battle.wav", data)

def generate_sfx():
    # Click - short high blip
    save_wav("sfx_click.wav", generate_tone(880, 0.05, volume=0.6, wave_type='square'))
    
    # Move - lower thud
    save_wav("sfx_move.wav", generate_tone(150, 0.1, volume=0.6, wave_type='triangle'))
    
    # Error - buzzing
    save_wav("sfx_error.wav", generate_tone(100, 0.3, volume=0.6, wave_type='sawtooth'))
    
    # Combat Start - rapid ascending arpeggio
    data = b''
    for f in [440, 554, 659, 880]:
        data += generate_tone(f, 0.1, volume=0.5, wave_type='square')
    save_wav("sfx_combat_start.wav", data)
    
    # Attack - noise burst
    save_wav("sfx_attack.wav", generate_tone(0, 0.15, volume=0.7, wave_type='noise'))

if __name__ == "__main__":
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    print("Generating BGM...")
    generate_bgm_adventure()
    generate_bgm_dungeon()
    generate_bgm_battle()
    
    print("Generating SFX...")
    generate_sfx()
    print("Done!")
