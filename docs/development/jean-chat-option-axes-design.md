# Jean's chat options: a second axis beyond mood (design note for #591)

Status: proposal, not implemented. Filed from the 2026-09-16 triage pass after the
maintainer chose "design doc first" over implementing in the batch.

## Today

Jean's reply options in NPC chat are generated per round by the LLM and are
purely an emotional register: `JEAN_TONES = ("direct", "guarded", "open")`
(`ai/llm_client.py`, mirrored in `src/npc/_chat_llm.py`). The count is pinned to
that tuple (`_JEAN_OPTION_COUNT = len(JEAN_TONES)`), the generation prompt asks
for one option per tone, and the QC pipeline (`_qc_jean_options`,
`_top_up_jean_options`) validates tone membership, length and pairwise
similarity. A playtester asked for options that follow the subject, ask about
lore, or ask about the NPC's character or profession, not only a mood.

## Proposal: a `kind` axis alongside `tone`

Each generated option carries two labels instead of one:

| axis  | values                                                | owner          |
|-------|-------------------------------------------------------|----------------|
| tone  | direct, guarded, open (unchanged)                     | `JEAN_TONES`   |
| kind  | reply, follow-up, ask-lore, ask-npc                    | new `JEAN_KINDS` |

- **reply** answers what the NPC just said (today's behaviour).
- **follow-up** presses the current subject one step further.
- **ask-lore** asks about a place, faction or event the NPC has mentioned or
  that `world_facts.json` marks as known to them.
- **ask-npc** asks about the NPC themself: trade, history, opinion.

Rules:
1. The option set is still small. Target **four** options per round: the three
   tones as replies plus one non-reply kind, chosen by the generator from the
   context (a merchant gets `ask-npc` more often, a story NPC `ask-lore`). Five
   is the hard cap; the client renders a vertical list on phones and the 44px
   rows already fill the panel at five.
2. `tone` stays mandatory on every option so the reputation/loquacity deltas
   keyed on tone keep working; `kind` defaults to `reply` when absent, so an
   older adapter or a fallback pool is still valid.
3. The QC pipeline gains one check: at most one option per non-reply `kind`,
   and a non-reply option must name a subject that appears in the NPC's last
   two lines or the NPC's allowed proper nouns (prevents invented lore).
4. Prompt cost: one extra line in the option-generation prompt and roughly
   +40 output tokens per round. Measure with
   `python tools/measure_llm_tokens.py --outputs` before and after (Aug 2026
   baseline: NPC chat round ~1,279 in / ~160 out) and keep the round under the
   Groq free-tier budget noted in `.claude/rules/llm-prompts.md`.
5. Wire: options already ship as `{tone, text}`; add `kind`. Add the field to
   the wire-field contract test with its client read site, and render a small
   glyph prefix per kind (text, not colour) so the axis is visible.

## Open questions for the maintainer

- Should `ask-lore` be gated on the NPC's `known_facts` only, or may an NPC
  admit ignorance ("I wouldn't know") as a valid answer?
- Does Jean's arc (pillar 2) want a fifth kind, `confide`, that lets her
  volunteer something of her own? It would need per-chapter authored beats.

## Out of scope

Reworking the three tones, changing the per-round token budget, or authoring
NPC-specific option pools.
