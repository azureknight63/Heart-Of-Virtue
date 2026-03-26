# TODOS

## Pre-existing Test Failures (noticed on claude/add-feedback-form-KS9HM)

**Priority:** P0

- [ ] `tests/test_auth_config_masking_regression_1.py` — 6 setup errors (Flask app context fixture); noticed on branch `claude/add-feedback-form-KS9HM`, unrelated to feedback form changes
- [ ] `tests/test_animations.py::test_animate_to_main_screen_gif` and `test_animate_to_main_screen_function` — `io.UnsupportedOperation`; likely terminal emulation issue in CI
- [ ] `tests/test_attack_facing_updates.py::TestAttackMovesFacing::test_attack_faces_target_east` — failing; unrelated to feedback changes
- [ ] `tests/test_combat_event_safety.py` — 3 failures in `TestAPICombatEventEvaluation`; unrelated to feedback changes
- [ ] `tests/test_ensure_weapon_exp.py::test_attack_integration_creates_exp_entries` — failing; unrelated to feedback changes
- [ ] `tests/test_moves_attack.py::test_attack_execute_applies_damage` — `io.UnsupportedOperation`; likely same root cause as animation failures

## Completed

<!-- Completed items moved here by /ship or /document-release -->
