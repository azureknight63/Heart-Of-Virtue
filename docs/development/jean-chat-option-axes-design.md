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
- **confide** — Jean volunteers something of his own.
- **ask-guidance** — Jean asks the NPC's counsel on his own situation.

`ask-guidance` is adopted in a **constrained** form (2026-09-17): the NPC may
offer a view on Jean's state of mind or his predicament, never an objective.
"Go to the Echoing Caves and find the smith" is out of scope for it, because
nothing in the prompt knows whether that is true — see the grounding note below.
The gloss sent to the model has to say so, or the model will invent quest steps.

`confide` is in the starting pool by maintainer decision (2026-09-17). It carries
the risk the first revision deferred it over — generic confession — and the
mitigation is a prompt constraint rather than authored beats: Jean may only
confide something already in JEAN'S KNOWN CONTEXT, never a new fact about
himself. Per-chapter authored beats remain the better answer and remain out of
scope here.

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
4. **Natural logic on both sides of the exchange** (maintainer decision,
   2026-09-17). Jean may ask about anything *he* knows; the NPC answers from what
   *they* know; "I wouldn't know" is a valid answer. No per-NPC `known_facts`
   table is needed, because ignorance is an answer rather than a gap.

   Jean's half already exists: the turn prompt forbids referencing anything
   outside "JEAN'S KNOWN CONTEXT, the WORLD facts, and this conversation"
   (`ai/llm_client.py:3691`). **The NPC's half does not** — nothing in either
   prompt currently permits an NPC to admit ignorance, so a model asked about
   something outside its brief will confabulate rather than decline. That
   permission is new prompt text this work has to add, and it is the one place
   where "natural logic" is not already the behaviour.

   Note the asymmetry trap in the *other* generator: the standalone
   `generate_jean_options` prompt (`ai/llm_client.py:3855-3866`) carries the
   identity and merchant rules but **not** the KNOWN CONTEXT clause. Options
   minted on that path are ungated today, which nobody notices while every option
   is a mood. The moment `ask-lore` exists, that path can invent a faction. The
   clause has to be added there too.
5. **Wire and UI.** Options already ship as `{tone, text}`; add `kind`. Add the
   field to the wire-field contract test with its client read site. Render the
   **kind** in the button's label slot and drop the tone label — the portrait
   already conveys the emotion, so a two-part `[skeptical · ask-lore]` label is
   both redundant and cramped at phone width. Text, not colour, and **plain, not
   tinted** (maintainer decision, 2026-09-17).
6. **The player never sees the machine name.** `ask-lore` and `ask-npc` are
   schema vocabulary; the button shows player-facing copy. The wire keeps the
   machine name and the frontend owns a `KIND_LABELS` map beside the other
   conversation vocabulary in `utils/conversationSegment.js` — display copy is a
   presentation concern and belongs on the client, not in a route or serializer.

   | kind | label |
   |---|---|
   | `reply` | Answer |
   | `follow-up` | Press further |
   | `ask-lore` | Ask about the world |
   | `ask-npc` | Ask about *{NPC name}* |
   | `challenge` | Push back |
   | `redirect` | Change the subject |
   | `confide` | Share something |
   | `ask-guidance` | Ask *{NPC name}*'s advice |

   `ask-npc` interpolates the NPC's display name, which the panel already holds —
   "Ask about Mara" costs nothing on the wire. Doing the same for `ask-lore`
   ("Ask about the Warden") would need the model to emit a `subject` field, and
   is deliberately **not** proposed: rule 4 already makes the option text name
   its subject, so the label would restate the sentence directly above it.

   This map needs the guard the tone table used to have. A kind added to
   `JEAN_KINDS` with no entry in `KIND_LABELS` renders an unlabelled button, so
   the contract test that pins `EMOTIONS` against `JEAN_TONES` gains a sibling
   pinning `KIND_LABELS`' keys against `JEAN_KINDS`.

### What a kind may ask for is bounded by what the prompt knows

A kind is only safe if the NPC can answer it from context the prompt actually
carries. `_build_system_prompt` (`src/npc/_chat_llm.py:2196-2210`) assembles
world facts, character, trade, combat knowledge, conduct and Jean's context —
**and nothing else**. There is no map block, no tile or player position, no exit
graph, and no quest or story-flag state. `world_facts.json`'s `geography` is
eight bare place names ("the river", "the Echoing Caves", "Grondia") with no
adjacency, direction or distance between them.

That bounds the pool:

- **`ask-way` is NOT adopted** (2026-09-17). Asked for a route, the model has
  place names and no topology, so any "east past the foothills, then north" is
  invented — and a player acts on directions. It needs a map-context block
  feeding real adjacency and exits into the prompt, which is its own issue. An
  NPC deliberately misdirecting Jean is a story device and also a separate
  concern; it is not what an ungrounded model produces, which is noise rather
  than a lie with intent.
- **`ask-guidance` is adopted constrained**, per above: counsel, never
  objectives. Advice about Jean's situation needs only the conversation and the
  NPC's persona, both of which the prompt has. Advice about what to *do* next
  needs quest state, which it does not.

The general rule for anyone extending `JEAN_KINDS` later: name the block that
answers it. If no block does, the kind either waits for that block or is
constrained to what the existing ones support.

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

- **`offer-help`** — Jean offers something of himself to the NPC — is the one
  candidate not yet ruled on. It is the only kind that can open a diegetic route
  into a quest, which is its appeal and also its grounding problem: an offer the
  engine cannot honour is a promise to the player it will not keep. Adoptable in
  the same constrained shape as `ask-guidance` (Jean may offer, the NPC may
  accept in words, nothing is wired to quest state), or deferred with `ask-way`
  until there is state to wire it to.

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

## Settled in revision 3 (mockup review, 2026-09-17)

- Kind labels are plain, not tinted.
- `challenge`, `redirect` and `confide` all ship in the starting pool.
- `ask-lore` gates on natural logic rather than a noun allow-list, and an NPC may
  answer "I wouldn't know" — which is new prompt text, not existing behaviour.
- The wire key stays `tone` although it now carries emotion values.
- The player-facing label layer (`KIND_LABELS`) was added after review found the
  raw schema names too obscure on the button.
- `ask-guidance` adopted constrained to counsel; `ask-way` rejected for now
  because nothing in the prompt can ground a route. The reviewer's condition —
  "provided their related data referencing holds" — is what these turn on, and
  checking it produced the grounding rule above.
- Repeating the previous round's kinds is fine; no anti-repeat nudge in the
  prompt.

## Out of scope

Reworking how the NPC's own portrait emotion is chosen (that comes from
`conversation_quality`, untouched), changing the per-round option count,
authoring NPC-specific option pools, and per-NPC `known_facts`.
