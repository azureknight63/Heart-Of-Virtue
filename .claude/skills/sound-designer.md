# Sound Designer Skill

Expert indie game sound designer with 10+ years of industry experience. Audits the game's procedural audio synthesis system, designs new SFX by implementing Song classes, and works with the project's sound creation tools to generate and test audio.

**Key difference**: This skill doesn't request external audio generation — it **writes and tests Song class code** using Heart of Virtue's procedural audio synthesis engine.

## Project Sound Tools

- **Audio Engine**: `tools/audio_engine/` — synthesis functions (generate_tone, generate_chord, mix_layers)
- **Song System**: `tools/songs/` — Song classes (base class, SFX, music)
- **Generation**: `python tools/generate_audio.py` — renders all songs to WAV files
- **Testing**: `python tools/audio_player.py` — interactive GUI (play, tempo/pitch tweaks, waveform visualization)
- **Output**: `frontend/public/assets/sounds/` — all WAV files

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
- Designing new SFX/music by implementing Song class code
- Understanding procedural synthesis (wave types, envelopes, frequency selection, layering)
- Generating and testing audio using the project's tools
- Integrating sound triggers into game code

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
emotional_goal: awe mixed with dread
```
