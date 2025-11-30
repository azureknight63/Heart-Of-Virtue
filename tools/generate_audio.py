import os
import sys

# Add project root to path so imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.audio_engine.core import save_wav, OUTPUT_DIR
from tools.songs.adventure import AdventureSong, ThemeSnippet
from tools.songs.battle import BattleSong
from tools.songs.dungeon import DungeonSong
from tools.songs.sfx import ClickSFX, MoveSFX, ErrorSFX, CombatStartSFX, AttackSFX

SONG_LIST = [
    AdventureSong(),
    ThemeSnippet(),
    BattleSong(),
    DungeonSong(),
    ClickSFX(),
    MoveSFX(),
    ErrorSFX(),
    CombatStartSFX(),
    AttackSFX()
]

if __name__ == "__main__":
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    print("Generating Audio Assets...")
    for song in SONG_LIST:
        print(f"Generating {song.filename}...")
        data = song.render()
        save_wav(song.filename, data)
    print("Done!")
