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

### P0 — Failing Tests (noticed on claude/add-feedback-form-KS9HM, pre-existing)
- [ ] `tests/test_auth_config_masking_regression_1.py` — 6 setup errors (Flask app context fixture)
- [ ] `tests/test_animations.py::test_animate_to_main_screen_gif` and `test_animate_to_main_screen_function` — `io.UnsupportedOperation`; likely terminal emulation issue in CI
- [ ] `tests/test_attack_facing_updates.py::TestAttackMovesFacing::test_attack_faces_target_east` — failing
- [ ] `tests/test_combat_event_safety.py` — 3 failures in `TestAPICombatEventEvaluation`
- [ ] `tests/test_ensure_weapon_exp.py::test_attack_integration_creates_exp_entries` — failing
- [ ] `tests/test_moves_attack.py::test_attack_execute_applies_damage` — `io.UnsupportedOperation`; likely same root cause as animation failures

### P2 — Should Fix
- CI: auth regression tests (`test_auth_config_masking_regression_1.py`) require Flask not in default pytest env — consider adding `requirements-api.txt` to CI test matrix

---

## Frontend

### P3 — Nice to Have
- React Router v6→v7 future-flag warnings (tracked upstream, not our change)

---

*Last updated: 2026-03-26. Append new items; never delete completed ones.*
