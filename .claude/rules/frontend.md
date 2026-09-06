---
paths:
  - "frontend/src/**"
  - "frontend/scripts/**"
  - "frontend/vite.config.js"
---

# Frontend rules (React 18 + Vite)

Conventions: functional components only; stateful logic in custom hooks (`hooks/useApi.js`, `useCombat`, …) — never inline API calls in components; Tailwind utilities plus tokens from `styles/theme.js` (`colors.primary` lime `#00ff88`, `accent` cyan `#00ccff`, `secondary` orange `#ffaa00`, `danger` `#ff4444`, `special` purple `#9944ff`, on `#0a0a0a`). Coverage threshold is 95% on lines/statements/functions/branches (`vite.config.js`) — the build fails below it. Vitest + React Testing Library: `cd frontend && npm test -- --run`.

## Wire-field-name drift — this codebase's dominant bug class
The client reads a field name the serializer never emits; because reads sit behind `??`/`||` chains, the miss is swallowed and the feature quietly does nothing — no error, no failing test. Five shipped instances: `combat.turn_number`/`combat_id` (neither existed client-side), `weight_tolerance` (the *engine* attribute, not a serialized key), `duration_remaining` vs `beats_left`, `hit_chance` rescaled to 0–1 when the engine sends an integer percentage, and `BattlefieldGrid`'s `combat_id` pan-reset dep. **Every one was invisible because the test fixtures encoded the same wrong name as the component** — a mock cannot catch a mock agreeing with itself. `tests/test_wire_field_contract.py` builds payloads from *real* engine objects and asserts the frontend's declared field list is a subset of what comes back. **When adding a client read of an API field, add it there.**

## `transformCombatData` drops top-level keys
`useApi.js`'s `transformCombatData` spreads `data.battle_state` and then whitelists a fixed set of top-level keys; anything else at the top level of the combat payload never reaches the client (two of the five drift bugs). New per-poll combat fields go **inside `battle_state`**; extend the whitelist only for genuinely top-level concerns.

## `ConversationStage` reset trap
`ConversationStage.jsx` renders staged (portrait) dialogue, tracking position with `beatIndex` (`useState`) and a `completedRef` (`useRef`) that gates `onComplete` to fire exactly once. `EventDialog.jsx` mounts it with no `key`, so React reuses the instance across re-renders. Events that call `begin_conversation()` more than once across stages (multiple `process_event_input` round-trips, e.g. `Ch02GuideToCitadel`, `AfterKingSlimeReturn`) hand the *same mounted instance* a fresh `segments` array per stage — without a reset the next stage resumed at the stale `beatIndex` and `completedRef` was already `true`, so `onComplete` never fired again: a soft-lock. `ConversationStage` now has a `useEffect` keyed on `segments` that resets both (each API response builds a fresh array, so reference-equality fires once per stage). **Any new component holding per-conversation/per-stage state across a `segments`/`conversation` prop change needs the same reset-on-prop-change guard.**

## One source of truth for move-category → button routing
`CATEGORY_GROUPS` + `movesInGroup`/`groupHasMoves` in `utils/categories.js` feed both `LeftPanel` (button gating) and `CombatMovePanel` (panel contents). They were once duplicated and drifted; `tests/test_move_categories_ui_contract.py` AST-parses `src/moves/` and fails if a castable category maps to no group or a group filters for a category the engine never emits. `MOVE_CATEGORY_COLOR/_GLOW/_ICON` intentionally carry `Special`/`Supernatural` entries with no moves yet.

## Saves and session
- Sort saves with `compareSavesByRecency` (`utils/localSave.js`), never raw `Date` arithmetic: the display string is `"%Y-%m-%d %H:%M:%S %Z"` and `Date.parse` returns `Invalid Date` for most non-US zone abbreviations (CET, CEST, JST, IST, AEST, PKT), which once sorted every row as `NaN` and could point "Continue" at the wrong save. `list_saves` emits `timestamp_ms`; the comparator prefers it.
- There is **no local autosave** (`hov_local_autosave` was retired — it was write-only, nothing ever restored from it). `useAutosave` triggers a cloud autosave every `AUTOSAVE_TICK_THRESHOLD` (3) movement/combat transitions; a failed cloud save must surface via `useToast`, not `console.error` alone. Continue always targets the newest cloud save. Don't write game state to `localStorage`; `utils/localSave.js` keeps only the ordering helpers.
- Soft-lock guard: any `isSubmitting`-style flag that gates affordances must be cleared on failure paths too — a never-cleared flag after a failed event submission was an unrecoverable soft-lock.
- Logout must clear every per-account client artifact (a local autosave once survived logout and leaked across accounts).

## Mobile and accessibility (pillar 5)
`useMobile` switches at `(max-width: 767px)` (initializer and `matchMedia` handler must agree); `MobileTabBar` is fixed 56px (`MOBILE_TAB_BAR_HEIGHT`, exported — don't duplicate the number); all interactive elements get `touch-action: manipulation`, ≥44px touch targets, 16px inputs (prevents iOS zoom); modals `maxHeight: 85vh` + `overflowY: auto`. Never convey state by color alone — pair with icon/text. Status/passive icons render below the hero image on mobile, not floated off-screen. Header titles truncate with ellipsis rather than pushing buttons off-screen.

## Build-time checks (`npm run build` → `prebuild`)
- `scripts/check-changelog-freshness.mjs`: the newest `CHANGELOG.md` version must appear in `src/data/changelog.js` (login-screen changelog panel) — prepend a `{ version, date, highlights }` entry when you cut a release.
- `scripts/generate-sfx-durations.mjs --check`: `utils/sfxDurations.js` must match the WAVs in `public/assets/sounds/sfx/` — run `npm run sfx:durations` after adding or regenerating sounds.

## Gotchas
- Style math on tokens: `spacing.sm` is the string `'8px'`; `-spacing.sm` is `NaN` (React warns "NaN is an invalid css value"). Use a template string: `` `-${spacing.sm}` ``.
- Known browser noise, not bugs: `fonts.googleapis.com`/`fonts.gstatic.com` failures offline; React Router v6→v7 future-flag warnings.
- The frontend polls `GET /combat/status` after each attribute allocation so a deferred combat (level-up dialog open) auto-resumes — keep that poll if you touch `useAttributeAllocation`/`AttributePointAllocator`.
- Shared pieces to reuse rather than re-create: `useAttributeAllocation`/`AttributePointAllocator`, `ItemStatGrid`/`ItemSection`, `formatWeight` + `WEIGHT_UNIT`, `CollapsibleRoomDescription`, `useMobile`.
- Tests must exercise real component behaviour — 63 tests that rendered inline `<div>` literals and asserted React's own semantics were deleted as vacuous. Don't write those.
