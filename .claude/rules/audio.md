---
paths:
  - "tools/audio_engine/**"
  - "tools/songs/**"
  - "tools/generate_audio.py"
  - "tools/audio_player.py"
  - "tools/convert_audio.py"
  - "frontend/public/assets/sounds/**"
  - "frontend/src/utils/combatSfx.js"
  - "frontend/src/utils/sfxDurations.js"
  - "frontend/src/context/**"
---

# Audio rules

All SFX and BGM are **procedurally synthesized** by the Wave Synthesis Engine (`tools/audio_engine/core.py`) via Song classes in `tools/songs/` — no external AI audio generation for SFX. Render with `python tools/generate_audio.py` → `frontend/public/assets/sounds/`; audition with `python tools/audio_player.py` (tempo/pitch/waveform GUI).

- Engine: `generate_tone` (ADSR + vibrato LFO), `generate_tone_sweep` (phase-accumulator sweep, all waveforms), `generate_chord` (ADSR, ZeroDivision-guarded for very short envelopes), `mix_layers`, `generate_percussion_pattern`; waveforms sine/square/sawtooth/triangle/noise. The sound designer has authority to extend the engine when a design needs it — add tests for new synthesis functions.
- Songs: `sfx.py` (AttackHit/Miss/Parry/Swipe, EnemyDeath, Move, LevelUp, QuestComplete, ItemUse, Heal, StatusHit, PlayerDeath), `ambient.py` (MineralPools, DreamSpace), `adventure.py`, `battle.py`, `dungeon.py`.
- **After adding or regenerating a WAV, run `cd frontend && npm run sfx:durations`** — `prebuild` runs `generate-sfx-durations.mjs --check` and fails the production build if `utils/sfxDurations.js` is stale. Combat SFX mapping lives in `utils/combatSfx.js`; move animations reference sfx through `ANIMATION_CONFIGS`.
- Use `/sound-designer` (Song class design and audits) and `/music-designer` (BGM blueprints and generator prompts). Open audio TODOs are in `TODOS.md`.
