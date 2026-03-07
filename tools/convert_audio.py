
import os
import subprocess
import imageio_ffmpeg
import glob

def convert_wav_to_mp3(wav_path):
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    mp3_path = wav_path.replace('.wav', '.mp3')
    
    print(f"Converting {wav_path} to {mp3_path}...")
    
    # -y to overwrite if exists (though user said create copies, so if mp3 exists we might be overwriting a previous run, distinct from the wav)
    # -q:a 2 is roughly 190kbps VBR (standard high quality)
    cmd = [
        ffmpeg_exe, 
        '-y', 
        '-i', wav_path, 
        '-codec:a', 'libmp3lame', 
        '-q:a', '2', 
        mp3_path
    ]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Successfully created {mp3_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error converting {wav_path}: {e}")
        print(f"Stderr: {e.stderr.decode()}")

def main():
    # Define the directory
    sound_dir = os.path.join(os.getcwd(), 'frontend', 'public', 'assets', 'sounds')
    
    # Find all bgm_*.wav files recursively and theme_snippet.wav
    wav_files = glob.glob(os.path.join(sound_dir, '**', 'bgm_*.wav'), recursive=True)
    wav_files.extend(glob.glob(os.path.join(sound_dir, 'theme_snippet.wav')))
    
    print(f"Found {len(wav_files)} files to convert.")
    
    for wav_file in wav_files:
        convert_wav_to_mp3(wav_file)

if __name__ == "__main__":
    main()
