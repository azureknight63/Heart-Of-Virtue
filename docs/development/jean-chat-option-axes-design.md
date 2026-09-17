# Jean's chat options: a second axis beyond mood (design note for #591)

Status: proposal, not implemented. Filed from the 2026-09-16 triage pass after the
maintainer chose "design doc first" over implementing in the batch; revised
2026-09-17 in a working session with the maintainer, which changed the shape of
the proposal substantially (see *What changed in revision 2*).

## Today

Jean's reply options in NPC chat are generated per round by the LLM and are
purely an emotional register: `JEAN_TONES = ("direct", "guarded", "open")`
(`ai/llm_client.py:371`, mirrored in `src/npc/_chat_llm.py:141`). The count is
pinned to that tuple (`_JEAN_OPTION_COUNT = len(JEAN_TONES)`,
`src/npc/_chat_llm.py:647`), the generation prompt asks for one option per tone,
and the QC pipeline (`_qc_jean_options`, `_top_up_jean_options`) validates tone
membership, length and pairwise similarity. A playtester asked for options that
follow the subject, ask about lore, or ask about the NPC's character or
profession, not only a mood.

What `tone` actually drives, end to end: `TONE_EMOTIONS`
(`frontend/src/hooks/useNpcChat.js:29`) maps the three tones onto three of the
eight portrait emotions, and `toneEmotion()` picks the portrait Jean wears while
delivering the line. The `[{option.tone}]` label on each button
(`NpcChatPanel.jsx:622`) is the only other consumer, and it is cosmetic.

## Proposal: two orthogonal axes

| axis  | question it answers        | vocabulary                        | owner          |
|-------|----------------------------|-----------------------------------|----------------|
| tone  | *How does Jean look saying it?* | the eight portrait emotions   | `JEAN_TONES`   |
| kind  | *What is Jean going to talk about?* | an open, editable pool    | `JEAN_KINDS`   |

The count stays at **three options per round**. The model picks three `kind`
values from the pool and a `tone` for each. Neither axis changes the option
count, the panel layout, or the 44px row budget on phones.

### tone becomes the portrait emotion

`JEAN_TONES` widens from the three registers to the eight emotions Jean has art
for — `neutral`, `happy`, `sad`, `angry`, `surprised`, `skeptical`, `concerned`,
`curious` (`frontend/src/utils/portraits.js:30`; all eight PNGs exist under
`frontend/public/assets/portraits/jean/`).

This is a net deletion on the client. `TONE_EMOTIONS` stops existing: the tone
*is* the emotion, so `toneEmotion()` collapses into the `normalizeEmotion()`
already in `utils/portraits.js`, and the test that pins the table's keys against
the Python source (`useNpcChat.test.js:316`) retargets to pin `EMOTIONS` against
`JEAN_TONES` instead — same guard, same machinery, one less indirection.

**Tone collisions are explicitly fine.** Two options may wear the same emotion.
That reverses the tone re-keying in `_qc_jean_options`
(`src/npc/_chat_llm.py:3490-3510`), which exists so the player never sees two
buttons labelled `[direct]` and none labelled `[guarded]` — a *legibility* bug,
not a mechanics one. It is safe to reverse only because `kind` becomes the
visible label (below); with the kind shown, two options sharing a portrait
emotion are still plainly different choices. The test `test_a_mid_list_drop_still_offers_three_distinct_tones`
(`tests/test_npc_chat_turn_pipeline.py:186`) becomes the kinds version of itself.

Tone is still validated against the vocabulary server-side rather than left to
`normalizeEmotion`, which silently coerces anything unknown to `neutral` and
would hide model drift.

### kind is an editable pool

`JEAN_KINDS` is an ordered mapping of name → short gloss, living beside
`JEAN_TONES` in `ai/llm_client.py` and mirrored into `src/npc/_chat_llm.py` the
way the tones already are. The prompt builder renders its vocabulary lines *from*
the mapping rather than hardcoding them, so adding, renaming or removing a kind
is a one-line edit that propagates to the prompt, the validator and the wire
contract at once.

Proposed starting pool:

- **reply** — answers what the NPC just said (today's behaviour).
- **follow-up** — presses the current subject one step further.
- **ask-lore** — asks about a place, faction or event.
- **ask-npc** — asks about the NPC themself: trade, history, opinion.
- **challenge** — doubts or tests what the NPC just claimed.
- **redirect** — returns to a subject the NPC raised earlier.

Kinds are speech acts, never registers. The two axes must stay orthogonal or the
prompt defines the same word twice: "deflect" is already the prompt's gloss for
the `guarded` tone, which is why it is not a kind.

`close` was considered and rejected — the player ends a conversation by
dismissing the dialog, so a `close` option is a second and worse path to an
affordance that already exists.

### Rules

1. **Three options, distinct kinds.** The kind axis takes over the uniqueness
   the tone axis used to carry. The re-key loop in `_qc_jean_options` moves to
   the kind axis nearly verbatim, and its "duplicates and holes always balance"
   arithmetic gets *safer*: it relied on `_JEAN_OPTION_COUNT == len(JEAN_TONES)`
   being exactly equal, and the kind pool is strictly larger than the option
   count.
2. **At least one option is a `reply`.** Three questions in a row leave the NPC's
   last line unanswered and read as interrogation rather than conversation. If
   the kept set contains no `reply` after validation, the last option is replaced
   from the fallback pool, which is all replies.
3. **The fallback pool is tagged `reply`** (`_JEAN_FALLBACK_POOL`,
   `src/npc/_chat_llm.py:1452`). A degraded round is all-replies; that is the
   honest failure mode, and it satisfies rule 2 for free. Its tones migrate
   through the table being deleted: `direct`→`neutral`, `guarded`→`skeptical`,
   `open`→`curious`.
4. **A non-reply option must name a subject** that appears in the NPC's last two
   lines or in the world-level `allowed_proper_nouns`, so the model cannot invent
   lore. See the open question below — this list is world-level, not per-NPC.
5. **Wire and UI.** Options already ship as `{tone, text}`; add `kind`. Add the
   field to the wire-field contract test with its client read site. Render the
   **kind** in the button's label slot and drop the tone label — the portrait
   already conveys the emotion, so a two-part `[skeptical · ask-lore]` label is
   both redundant and cramped at phone width. Text, not colour.

### Implementation traps

- `_JEAN_OPTIONS_SKELETON` (`ai/llm_client.py:408`) builds the JSON skeleton by
  iterating `JEAN_TONES`, one slot per tone. Widening that tuple to eight
  emotions would silently ask the model for eight options. It must become three
  fixed slots, each carrying `tone` and `kind`.
- `_clean_jean_options` (`ai/llm_client.py:3313`) defaults a missing tone
  positionally with `JEAN_TONES[len(cleaned) % len(JEAN_TONES)]`. Harmless with
  a wider tuple, but it now picks from eight emotions rather than cycling three
  registers — default to `neutral` explicitly instead.
- `src/api/routes/npc_chat.py:210,233` documents and defaults `jean_tone` as
  `"direct"`. The default becomes `"neutral"`.
- `frontend/src/test/citations.test.js:53-60` anchors cross-file citation guards
  on `JEAN_TONES` and on the claim that the suite pins `TONE_EMOTIONS` against
  the Python source. Both claims change with this work.
- `kind` defaults to `reply` when absent, so an older adapter or a fallback pool
  entry without the field stays valid.

### Cost

Roughly **+30 prompt tokens and +12 completion tokens per round**, estimated,
not measured. The tone vocabulary gets *cheaper*: three hand-written gloss lines
(`ai/llm_client.py:3857-3859`) become eight self-describing emotion names that
need no gloss. The kind vocabulary adds six short glosses. Completion grows by
one short field on each of three options — the option count does not change,
which is where the previous revision of this note spent its budget.

System prompts are re-sent on every call, so vocabulary prose is paid once per
beat forever (`.claude/rules/llm-prompts.md`). Measure with
`python tools/measure_llm_tokens.py --outputs` before and after — Aug 2026
baseline: NPC chat round ~1,279 in / ~160 out — and keep the round inside the
Groq free-tier budget. Per the same rules file, a prompt change is a behaviour
change: run the live A/B (`HOV_LIVE_LLM=1 python -m pytest tests/integration/ -q`),
confirming any failure 3× on each side.

## Open questions for the maintainer

- **`ask-lore` gating.** Rule 4 leans on `allowed_proper_nouns`, which is a
  single world-level list (`ai/llm_client.py:3033`), not per-NPC. As written, any
  NPC can be asked about any noun in the world — the rule prevents invented lore
  but not a blacksmith being asked about a faction they have never heard of. The
  honest fix is per-NPC `known_facts`, which is authored content across every
  conversational NPC and belongs in its own issue. Ship with the world-level list
  and accept the looseness, or gate non-reply options on the NPC's own last two
  lines only?
- **`challenge` and `redirect`** are proposed, not requested. Keep, or start with
  `reply` / `follow-up` / `ask-lore` / `ask-npc` alone?
- **`confide`** — a kind that lets Jean volunteer something of his own — is
  deferred rather than rejected. It wants per-chapter authored beats to avoid
  generic confession, so it is story-content work. The pool is designed to make
  it a one-line addition later.
- **Field naming.** `tone` now carries emotion values, and
  `src/api/services/game_service.py` already calls this concept `emotion` for
  staged conversation segments. Renaming the wire key to `emotion` is more honest
  but touches the route contract and the citation guards; keeping `tone` is
  cheaper. Recommend keeping `tone` unless the inconsistency grates.

## What changed in revision 2

- The original note claimed `tone` had to stay mandatory "so the reputation/
  loquacity deltas keyed on tone keep working". **Nothing is keyed on tone.**
  `chat_respond` (`src/npc/_chat_llm.py:4520`) documents `jean_tone` as
  "accepted for API shape only and deliberately unused"; the deltas come back
  from the model in the turn response. Tone stays mandatory for the portrait.
- The original note targeted **four** options per round. That silently broke the
  tone-uniqueness invariant in `_qc_jean_options`, whose own comment states the
  arithmetic holds *because* `_JEAN_OPTION_COUNT == len(JEAN_TONES)`. At four,
  the free-tone pool empties and the fourth option falls through to a positional
  modulo — reproducing the exact shipped bug ("two 'direct' replies and no
  'guarded'") that comment was written to close. The count stays at three.
- Uniqueness moved from the tone axis to the kind axis, and tone widened to the
  full portrait emotion set.

## Out of scope

Reworking how the NPC's own portrait emotion is chosen (that comes from
`conversation_quality`, untouched), changing the per-round option count,
authoring NPC-specific option pools, and per-NPC `known_facts`.
