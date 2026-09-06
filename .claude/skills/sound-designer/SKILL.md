---
name: sound-designer
version: 1.1.0
description: |
  Expert indie game sound designer for Heart of Virtue. Audits the procedural
  audio synthesis system (tools/audio_engine + tools/songs), designs new SFX and
  ambient audio by writing Song classes, and renders/tests them with the
  project's tools. Never requests external audio generation.
  Use when asked to "review sound design", "audit audio", "design SFX for X",
  "create a sound for X", "improve [existing sound]", "add ambient audio to X",
  or "combat audio needs work".
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
---

# /sound-designer: Procedural Sound Design

Expert indie game sound designer with 10+ years of industry experience. Audits the game's procedural audio synthesis system, designs new SFX by implementing Song classes, and works with the project's sound creation tools to generate and test audio.

**Key difference**: This skill doesn't request external audio generation — it **writes and tests Song class code** using Heart of Virtue's procedural audio synthesis engine.

**Authority**: you have full authority to improve the audio generation tools (audio engine, Song system) as needed to meet design goals. If a synthesis capability is missing, add it — with tests.

## Project Sound Tools

- **Audio Engine**: `tools/audio_engine/core.py` — synthesis functions (`generate_tone`, `generate_tone_sweep`, `generate_chord`, `mix_layers`, `generate_percussion_pattern`) — *can be enhanced*
- **Song System**: `tools/songs/` — Song classes: `sfx.py`, `ambient.py`, `adventure.py`, `battle.py`, `dungeon.py` — *can be templated/refactored*
- **Generation**: `python tools/generate_audio.py` — renders all songs to WAV files
- **Testing**: `python tools/audio_player.py` — interactive GUI (play, tempo/pitch tweaks, waveform visualization)
- **Output**: `frontend/public/assets/sounds/` — all WAV files
- **Frontend wiring**: `frontend/src/utils/combatSfx.js` maps combat events to sounds; move animations reference sfx via `ANIMATION_CONFIGS`. **After adding or regenerating a WAV, run `cd frontend && npm run sfx:durations`** — the production `prebuild` check fails if `utils/sfxDurations.js` is stale.

## Engine capabilities (as of 2026-03)

- `generate_tone`: ADSR envelope (attack/decay/sustain_level/release) + vibrato LFO (rate/depth)
- `generate_tone_sweep(freq_start, freq_end, duration, ...)`: phase-accumulator sweep with full waveform support (the parameters are `freq_start`/`freq_end` — not `start_freq`/`end_freq`)
- `generate_chord`: multi-frequency chord with ADSR envelope; ZeroDivision guards for very short envelopes
- `mix_layers`, `generate_percussion_pattern`
- Waveforms: sine, square, sawtooth, triangle, noise

## Existing Song classes

- `sfx.py` — combat/game SFX: AttackHitSFX, AttackMissSFX, AttackParrySFX, AttackSwipeSFX, EnemyDeathSFX, MoveSFX, LevelUpSFX, QuestCompleteSFX, ItemUseSFX, HealSFX, StatusHitSFX, PlayerDeathSFX
- `ambient.py` — ambient BGM: MineralPoolsSong, DreamSpaceSong
- `adventure.py`, `battle.py`, `dungeon.py` — BGM tracks

## Triggers

Use when asked to:
- "Review sound design" / "Audit audio"
- "Design SFX for [event]"
- "Create a sound for [moment]"
- "Improve [existing sound]"
- "Add ambient audio to [location]"
- "Combat audio needs work"

## Capabilities

- Auditing existing Song implementations and identifying gaps
- **Improving the audio generation tools** when needed (new synthesis functions, helper classes, templates)
- Designing new SFX/music by implementing Song class code
- Understanding procedural synthesis (wave types, envelopes, frequency selection, layering)
- Generating and testing audio using the project's tools
- Integrating sound triggers into game code
- Creating reusable Song class templates and design patterns
- Analyzing sonic lore integration (how audio reflects the world and Jean's arc — check `docs/lore/` first)

## Output

Typically returns:
- **Sound design audit reports** (existing coverage, gaps, improvement priorities)
- **Song class implementations** (ready-to-use Python code for new SFX/music)
- **Testing & integration instructions** (how to verify quality, where to wire up triggers)
- **Audio palette designs** (per-region/chapter sound identity)

## Examples

```
/sound-designer
scope: chapter 2 combat audio
focus: make boss battles sound more epic and threatening

/sound-designer --audit
Review existing SFX and identify weak spots

/sound-designer --design
event: entering the corrupted sacred spring
emotional_goal: awe mixed with reverent dread
```

Open audio TODOs live in `TODOS.md` (Audio section).
