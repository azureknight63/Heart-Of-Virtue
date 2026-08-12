# Frontend code scrub — open decisions

Items surfaced by the `claude/frontend-code-scrub-122zm5` review that need a
human call. Everything here was **deliberately not actioned**: each is either an
architectural change to pre-existing code, a visual/product choice, or a policy
question — not a defect with an obvious right answer.

Defects found by the same review were fixed on the branch and are not listed
here. Items are ordered by how much they cost to leave open.

Branch base: `aa09858`. Last updated: 2026-08-09.

---

## 1. `LeftPanel.jsx` is 930 lines doing four unrelated jobs

**Tracked as [#490](https://github.com/azureknight63/Heart-Of-Virtue/issues/490).**

**Raised by:** DRY/Maintainability × C4 (Major, confidence 80)

The component mixes combat-log playback pacing, keyword-based SFX dispatch,
`ResizeObserver` auto-scale math for `HeroPanel`, and orchestration of ~10 modal
panels. Several `useEffect`s have interdependent deps on `isProcessingLog`,
`pendingLogEntries` and `combat?.*`, and a comment block in the file records the
original author's own uncertainty about one dependency array.

**Suggested shape:** extract `useCombatLogPlayback(combat)` and
`useHeroAutoScale(containerRef)`; optionally move panel visibility into a
`usePanelVisibility()` reducer, leaving the component as orchestration only.

**Why it was not done:** this is a restructure of pre-existing code, not a fix
for a defect the scrub found. It carries real regression risk in the combat log
pacing path, and folding it into a scrub commit would make the branch harder to
review and to revert.

**Note on the stated rationale:** part of the review's argument was that the SFX
keyword matcher re-implements a classification the backend already expresses via
`entry.type`. That is **incorrect** — `ApiCombatAdapter` only emits coarse types
(`system`, `animation`, and the default), with no per-event attack/miss/parry/
heal classification to reuse. The keyword matcher is doing work nothing else
does. Decide on the split for the size and coupling reasons alone.

**Options:** (a) do it now on this branch; (b) do it as a follow-up branch with
its own review; (c) leave it and revisit when the panel next needs a feature.

---

## 2. The 11 remaining `react-hooks` lint errors

**Tracked as [#491](https://github.com/azureknight63/Heart-Of-Virtue/issues/491).**

**Status:** open from earlier in the scrub (12 were fixed; 11 remain).

`npm run lint` currently reports 11 errors and 129 warnings. The errors are
`react-hooks` rule violations; `exhaustive-deps` is deliberately set to `warn`
so intentional omissions do not fail the build.

**Options:**
- **Fix all 11** — highest confidence, but some are intentional omissions where
  adding the dep would re-run an effect that must be mount-only.
- **Downgrade the rule to `warn`** — makes the lint run green, hides real ones.
- **Baseline them** with targeted `eslint-disable-next-line` comments carrying a
  one-line justification each — keeps the rule at `error` for new code and
  documents why each existing case is safe.

**Recommendation:** the baseline option. It is the only one that keeps future
violations failing while making the current state honest.

---

## 3. `HeroPanel` vital-bar tooltip glows are inconsistent

**Tracked as [#494](https://github.com/azureknight63/Heart-Of-Virtue/issues/494).**

**Raised by:** noticed while extracting `VitalBar` (commit `1cc1753`).

The HP tooltip uses a colour-matched shadow (`0 0 8px ${colors.danger}99`); the
Fatigue tooltip uses the orange `shadows.glow` token
(`0 0 15px rgba(255, 170, 0, 0.2)`) despite having a cyan border. It reads as an
oversight, but it is what ships today.

`VitalBar` takes `tooltipShadow` as a prop specifically so the extraction stayed
purely structural and changed no pixels.

**Decision:** leave as-is, or unify both on a colour-matched shadow (a one-line
change: drop the prop and derive from `color`).

---

## 4. No Content-Security-Policy anywhere

**Tracked as [#492](https://github.com/azureknight63/Heart-Of-Virtue/issues/492).**

**Raised by:** Security × C5 (flagged as a cross-file follow-up, no finding filed)

`frontend/index.html` has no `http-equiv` CSP meta and no CSP header is set
server-side. Given the app stores a bearer session token in `localStorage` and
has one `dangerouslySetInnerHTML` site (`CombatLog.jsx`, DOMPurify-sanitised),
the security reviewer called a CSP "the single highest-leverage missing control
for this app."

**Why it was not done:** out of scope for a frontend correctness scrub, and it
needs deployment-side coordination (which directives, report-only first, and
whether the Vite dev server needs a looser policy).

**Suggested:** a dedicated follow-up. Start in `Content-Security-Policy-Report-Only`
mode to find violations without breaking play.

---

## 5. Bearer token in `localStorage`

**Tracked as [#493](https://github.com/azureknight63/Heart-Of-Virtue/issues/493).**

**Raised by:** Security × C5 (architectural, pre-existing, unchanged by this branch)

`api/client.js` reads the session token from `localStorage`, which is
XSS-exfiltratable by design. An `httpOnly`, `SameSite=Lax` cookie would remove
that exposure — and would also shrink the blast radius of the logger-redaction
issue tracked on the branch.

**Why it was not done:** changes the auth flow end to end (Flask session
handling, CORS credentials, the Socket.IO handshake, and the test-session
bypass). Not a scrub-sized change.

**Related, already handled:** `hov_local_autosave` is cleared on logout and on
401, and login/register clear it *before* writing the new token, so
cross-account separation no longer depends on a clean teardown.

---

## 6. `hov_local_autosave` retention on shared machines

**No separate issue — subsumed by [#489](https://github.com/azureknight63/Heart-Of-Virtue/issues/489)**, which retires the blob entirely. If that lands, this settles by deletion.

**Raised by:** Security × C5 (Nit, confidence 85)

The blob (character/inventory/location state, verified to contain no email or
user id) persists after a tab close. Only logout, a 401, or the next login
clears it, so on a shared machine it is readable via devtools until someone
signs in.

**Options:** namespace the key by username and refuse a blob whose username does
not match the logged-in user; clear on `visibilitychange`/`beforeunload`; or
accept it, since the contents are game state with no PII.

**Context:** this is entangled with issues **#487** (the blob is write-only —
nothing restores from it) and **#489** (Tier B: close the cloud-autosave gap
server-side). If #489 lands, the local blob may be removable entirely, which
would settle this by deletion.

---

## 7. Should this branch open a PR? — RESOLVED

Yes. The fanout and both adversary passes are complete; the PR is open.

---

## Scrub status — complete

All 25 dimension cells (5 chunks x Security / Alignment / DRY+Maintainability /
Optimization / CleanCode+AIFriendliness) plus both adversary passes are done.
Every Major found has been fixed except item 1 above, which is a decision.

Chunk diffs used by the review agents were pre-extracted to the session
scratchpad. Note for anyone re-running this: dimension subagents have
Read/Grep/Glob but **no Bash**, so they cannot run `git diff` — the orchestrator
must extract each chunk's diff to a file and give them the path.
