# Portrait-Dialog Rollout — Tracking

Reference checklist for extending the portrait-dialog / staged-conversation feature
(prototyped in `Ch01_Memory_Amelia`) to all story events with character dialogue,
including internal thoughts. Check items off as they're converted.

Legend: 🗣 spoken dialogue beat(s) · 💭 internal-thought beat candidate

Scope: narrative story events only (`src/story/ch01.py`, `ch02.py`, `ch03.py`,
`src/story/effects.py`). Ambient/flavor NPC pools (`gorran_flavor.py`,
`_eastern_descent.py`, `_friends.py`, `_merchants.py`) are explicitly out of scope
per rollout decision — do not convert these without a separate go-ahead.

No portrait art exists yet for anyone but Jean — everyone else renders the
placeholder silhouette until art is commissioned. Not a blocker.

---

## Phase 0 — Foundation (schema + component)

- [x] Add `thought` param to `narration.say()` (`src/narration.py`)
- [x] Propagate `seg["thought"]` through `_capture_conversation()` (`src/api/services/game_service.py`)
- [x] `ConversationStage.jsx`: thought beats render italic, no quote-mark stripping needed since authors won't quote them; speaker portrait stays fully active (same as spoken); reactions render exactly as for spoken beats (author opts in per-beat via existing `reactions` dict — no default suppression)

## Phase 1 — `src/story/ch01.py` (Pattern B → `say()`)

- [x] **Ch01_Memory_Amelia** (ch01.py:37-149) — REFERENCE IMPLEMENTATION, already portrait-ready. Cast: Jean, Amelia. No work needed.
- [x] **AfterTheRumblerFight** (ch01.py:761-828) 🗣 — Gorran's naming scene. Cast: Jean, Rock-Man/Gorran. Jean:789 ("I suppose I should thank you..."), Gorran:802 ("Mmmmm... Go-rra-nnnnnn..."), Jean:803-808 ("Go... rran? Well, thank you...").
- [x] **AfterGorranIntro** (ch01.py:830-865) 💭 optional — Jean's threshold noticing ("A faint current of air presses against his face...", 852-854). No spoken dialogue (Gorran is wordless here).
- [x] **Ch01GorranFirstWord** (ch01.py:967-1051) 🗣💭 — Gorran's first spoken word, "Stop." (line 1027). Cast: Jean, Gorran. Internal-thought candidate: Jean's reaction "He'd expected a rumble, a sound, the usual. Not that." (1033-1035) — emotion: surprised.

## Phase 1 — `src/story/ch03.py` (Pattern B → `say()`)

- [x] **EasternRoadTurnbackEvent** (ch03.py:56-102) 💭 — Jean's internal resolve, "South. That's where this goes." (line 91, currently unattributed `colored()` text). Solo thought; Gorran present but silent, no reaction expected.
- [x] **MaraFirstContactEvent** (ch03.py:144-192) 🗣 — Mara: "Crossing west?" (179). Cast: Mara, Jean (silent listener).
- [x] **LissObservingEvent** (ch03.py:244-295) 🗣 — Liss: "Does the Golemite sleep? He doesn't look like he's sleeping. But I think he might be." (274-278). Cast: Liss, Gorran (listener — no reaction: prose is explicit that Gorran doesn't react), Jean.
- [x] **MaraObservationEvent** (ch03.py:298-371) 🗣 — Exchange: Mara "That's religious kit." / "You were a man of the church." (351 or 358, branch), Jean "It was." (362). Cast: Mara, Jean.

## Phase 2 — `src/story/ch02.py` (Pattern C: restructure `self.description` → `say()`/`narrate()`)

- [ ] **Ch02GuideToCitadel stages 4–7** (ch02.py:210-359) 🗣💭 — Votha Krr introduction & quest offer. Cast: Jean, Votha Krr (Gorran present partway through stage 4, then exits). Multi-stage exchange. Internal-thought candidates: stage 3 "Jean's first thought was not of the carvings..." (199-201) and stage 5 "Jean was quiet, but his mind was already moving..." (317-320).
- [ ] **Ch02KingSlimeMemoryFlash** (ch02.py:843-926) 💭 — Currently an untagged `MemoryFlash` (Pattern A infra already in place, but zero speaker tags). High-value internal-thought candidate: the entire flashback is Jean's traumatic sensory memory with no external speaker — convert key lines to Jean `thought` beats with shifting emotion (surprised → sad/fear).
- [ ] **AfterDefeatingKingSlime** (ch02.py:369-507) 💭 optional/low-priority — Jean's reflection, "He didn't know what to do with his hands when they weren't needed." (422).
- [ ] **AfterKingSlimeReturn stages 1–6** (ch02.py:929-1077) 🗣 — Votha Krr accepts the fragment and sends Jean to the Echoing Caves. Cast: Jean, Votha Krr. Jean's spoken lines are driven by his stage-2 choice (a/b/c).

## Optional / lower priority (mystical, non-humanoid voices — revisit later)

- [ ] **StMichael shrine voice** (`src/story/effects.py:394-531`) 🗣 — "CHILD, THY FAITH PRESERVES THEE..." Speaker: a disembodied/divine voice. No sensible portrait art. Leave on legacy typewriter unless a placeholder treatment (e.g. no portrait, text-only stylized speaker) is designed later.
- [ ] **WhisperingStatue** (`src/story/effects.py:700-784`) 🗣 — riddle + response lines from "the voice." Same consideration as above.

## Explicitly out of scope (confirmed with user — do not convert)

- `src/story/gorran_flavor.py` — combat/ambient one-liners
- `src/npc/_eastern_descent.py` — nomad camp NPC `_TALK_LINES` pools
- `src/npc/_friends.py` — Grondite NPC TALK responses
- `src/npc/_merchants.py` — shop flavor text
