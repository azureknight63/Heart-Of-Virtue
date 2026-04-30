# Beta Launch Checklist

Pre-flight checklist for the Heart of Virtue friend/community playtest.
Work items are ordered by priority. All BLOCKERs must be cleared before sharing the link.

---

## BLOCKER — Fix P0 Test Failures

Run `python -m pytest -q` after each fix to confirm progress.

| Status | Test | Action |
|--------|------|--------|
| [ ] | `tests/test_combat_event_safety.py` (3 failures in `TestAPICombatEventEvaluation`) | **FIX** — highest live risk; mid-combat 500s |
| [ ] | `tests/test_attack_facing_updates.py::test_attack_faces_target_east` | **FIX** — combat facing logic |
| [ ] | `tests/test_ensure_weapon_exp.py::test_attack_integration_creates_exp_entries` | **FIX** — silent weapon XP bug |
| [ ] | `tests/test_animations.py`, `tests/test_moves_attack.py` (`io.UnsupportedOperation`) | **VERIFY** locally — close if confirmed CI-only terminal emulation |
| [ ] | `tests/test_auth_config_masking_regression_1.py` (6 setup errors) | **VERIFY** — likely Flask context fixture issue, not a live bug |

> If `test_combat_event_safety.py` failures aren't isolated to a single call site,
> escalate your effort estimate before committing to a deploy date.

---

## BLOCKER — QA Feedback Pipeline End-to-End

The feedback route requires `GITHUB_TOKEN` on the production server. Without it,
every tester submission silently returns a 503.

- [ ] `GITHUB_TOKEN` set in production environment (scopes: `repo` + `issues:write`)
- [ ] Submit a test **bug report** → confirm GitHub issue created with `bug` + `player-report` labels
- [ ] Submit a test **general feedback** → confirm star ratings render correctly in issue body
- [ ] Submit a test **feature request** → confirm `enhancement` + `player-report` labels
- [ ] Hit rate limit (10 submissions in one hour) → confirm 429 response shown in UI
- [ ] Walk through: `BetaEndDialog` → "Send Feedback" → `FeedbackDialog` (general tab) → submit → confirm issue created

---

## HIGH — Write Tester Brief

- [ ] Write `docs/beta-brief.md` (≤300 words, plain language)
- [ ] Draft Discord announcement post (links to live URL + brief)

The brief must cover:
- What content is available and how long it takes
- That the game **intentionally ends** after the Lurker (the in-game dialog confirms this)
- That progress is lost if the browser is closed **or** the server restarts — play in one sitting
- How to use the in-game feedback button and what to report

---

## MEDIUM — Add Session Persistence Warning

- [ ] Add a visible notice on the game start/new-game screen:
  > "Your progress is not saved between sessions. Play in one sitting — progress will be lost
  > if you close the browser or the server restarts."

Estimated frontend effort: ~30 minutes.

---

## MEDIUM — Deployment Verification Smoke Test

Run this after deploying to production. Use the real registration flow (not the test session bypass).

- [ ] Register a new account on the live URL
- [ ] Start a new game
- [ ] Walk to `(4,2)`, talk to Ferdie, complete combat
- [ ] Reach `(7,1)`, complete wave combats, trigger Gorran rescue
- [ ] Make a choice in the Gorran dialog (any option)
- [ ] Follow the story to Verdette Caverns
- [ ] Navigate to `(8,8)`, defeat the Lurker
- [ ] Confirm **END OF BETA** dialog appears
- [ ] Click "Send Feedback", submit a general feedback entry
- [ ] Confirm GitHub issue is created in `azureknight63/heart-of-virtue`

---

## LOW — Distribution

- [ ] Decide: open registration or soft invite (recommendation: soft invite)
- [ ] Prepare Discord announcement message (include: live URL, beta brief link, what you're looking for)
- [ ] Share link with testers

---

## After Beta (not required before launch)

- [ ] Set up itch.io page for broader indie RPG community reach
- [ ] Review feedback issues in GitHub and triage for next release
- [ ] Decide what ships in v1.1 based on tester input
