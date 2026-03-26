# TODOS

Items deferred from active development. Organized by component. Priority: P0 (blocker) → P4 (nice-to-have).

---

## Audio

### Completed
- ✅ ADSR envelope (attack/decay/sustain/release) in `generate_tone` (feat/audio, 2026-03)
- ✅ Vibrato LFO modulation in `generate_tone` (feat/audio, 2026-03)
- ✅ `generate_tone_sweep` pitch-slide function (feat/audio, 2026-03)
- ✅ `MineralPoolsSong` ambient BGM (feat/audio, 2026-03)
- ✅ `DreamSpaceSong` ambient BGM (feat/audio, 2026-03)
- ✅ `LevelUpSFX`, `QuestCompleteSFX`, `ItemUseSFX`, `HealSFX`, `StatusHitSFX`, `PlayerDeathSFX` (feat/audio, 2026-03)
- ✅ Frontend wiring for all 6 new SFX (VictoryDialog, DefeatDialog, LeftPanel, MovementStar) (feat/audio, 2026-03)

### P3 — Nice to Have
- `generate_tone` ADSR: warn when attack+decay > duration-release (currently documented in docstring only)
- Unit tests for `generate_tone_sweep` edge cases (zero-length, start==end, very short durations)
- BGM tracks for locations beyond mineral pools / dream space (Wailing Badlands, new Chapter 2 maps)

---

## Combat

### Completed
- ✅ Cooldown drain bug: cooldowns now only tick in active combat beats (not rest/move)
- ✅ Combat testing arena (`src/resources/maps/combat-testing-arena.json`)
- ✅ `TheAdjutant` and `StatusDummy` NPCs for testing

---

## API / Backend

### P2 — Should Fix
- CI: auth regression tests (`test_auth_config_masking_regression_1.py`) require Flask not in default pytest env — consider adding `requirements-api.txt` to CI test matrix

---

## Frontend

### P3 — Nice to Have
- React Router v6→v7 future-flag warnings (tracked upstream, not our change)

---

*Last updated: 2026-03-26. Append new items; never delete completed ones.*
