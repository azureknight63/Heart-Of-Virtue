# Triage handoff — 2026-09-24 (resume after the session limit)

**Branch:** `triage/qa-2026-09-24` in the Alpha worktree, NOT pushed. Tip: `c090e391`
(`wip(triage): code-scrubber fixes, iterations 1-2`). Base: `origin/master` @ `37f76a7c`.

## Where the pass stands (issue-triage skill)

- Step 1–3 done: 18 open issues sorted; 8 read-only diagnoses; 9 worktree implementers,
  all merged (`f11aeeb9` … `b112605f`), each with red → green → revert-proof shown.
- #682 CLOSED (already fixed by `f778d2a1`; verified, comment posted).
- Decisions taken by the maintainer this session: #683 server-side delivery at collect-loot;
  #684 failed turn drains the reduced (3) amount; #685 "I draft, you review"; keep
  `/combat/start`; #692 interiors → Grondia BGM; #694/#695 mechanical text only; #681 left open.
- Not touched on purpose: #638, #679 (security design needing a human), #677 (needs prod
  access), #681 (open), #685's Votha Krr / Gorran drafts (unwired, for review).
- Step 5 (review gate): the combined diff is ~4.1k lines → `/code-scrubber`.
  Wave 1 (25 dimension agents + 2 adversaries) and iteration 2 (5 correctness re-reviews)
  are done; their fixes are in `c090e391`. C4 reached A/A; C1/C2/C3/C5 were at B on the
  last re-review, and every finding from it has since been fixed.

## Resume here, in order

1. **bug_hunt baseline.** `python tools/bug_hunt.py --scenario combat --headless` on the tip
   reported **21** findings (saved in that session's scratchpad as `bh_combat_after.json`), while the implementers
   saw 0 before/after — probably a different config. Re-run on the base (check out 37f76a7c in
   a scratch worktree) with the SAME command and config, diff the two JSONs, and investigate
   anything new before calling the branch clean.
2. **Scrub iteration 3** (the last allowed): re-dispatch `code-scrubber-alignment-correctness`
   for C1, C2, C3, C5 against fresh diffs (`git diff 37f76a7c -- <chunk paths>`; the chunk
   file lists are in the Step 2.5 command of this session). Anything still < A → Escalations.
3. **Architecture pass:** the scrubber has no Architecture dimension. Run `/code-review` over the
   architecture-touching subset (`src/api/`, `game_service.py`, serializers, `combat_adapter.py`).
   Known candidate: `routes/inventory.py` `get_currency` calls `get_gold(player.inventory)` from a
   route — should be a GameService method (CLAUDE.md "routes never reach into player").
4. **Open decisions for the maintainer** (batch into one question):
   - #690: should `POST /saves` (create a save) and `collect_combat_loot` refuse a dead player?
     (Adversary: not exploitable; it's a policy call.)
   - #684: should a deadline-cut provider call bench the model when its timeout wasn't clipped?
   - #685: review the three drafted voice files and the 11 judgement calls I9 listed; the
     `world_facts.json` change alters every NPC prompt → `.claude/rules/llm-prompts.md` requires
     a live A/B run (`HOV_LIVE_LLM=1 python -m pytest tests/integration/ -q`) before merge.
5. **Final gates on the tip:** `python -m pytest -q -n 6` (expected: only the 12 local-env failures
   — 4 missing `openai`, 8 `test_unpickler_fresh_objects` on Python 3.11.3; CI is green on
   both), `cd frontend && npx vitest run`, both `tests/api` files run individually, flake8.
   Last measured (after iteration 1): backend 15,988 passed; frontend 4,030 passed. The runs
   started after iteration 2 were still going when the session wound down — re-run.
6. **Land it:** amend nothing; push the branch, open the PR against `master` with a `## Closes`
   section (one `Closes #N` per line: 683, 684, 686, 687, 688, 689, 690, 691, 692, 693, 694,
   695 — **not** 685 until the maintainer approves the drafts, and not the partially-handled
   parts of 695). Verify `closingIssuesReferences` before merge, re-query every issue after.
   Master's red CI was fixed separately (an exemption in `test_instruction_files_are_accurate`);
   this branch rewords the report instead (`48be5647`) and drops that now-stale exemption.

## Findings worth surfacing in the final report

- #683's filed symptom was partly a tester artefact (O1's own status GETs consumed the scene);
  the real defect is the destructive GET. My original "client drops it" verdict was wrong.
- X2 (pending events under Victory): I first declared it "not reproduced" from a test that never
  exercised the path (instant mock batched the loading flag). The iteration-2 reviewer caught it;
  with a real round-trip delay it reproduced and is now fixed. Lesson: assert the path ran.
- #691: the implementer narrowed a guard (`test_a_listed_move_never_falls_back_to_the_generic_code`)
  with a `continue`; un-narrowed by returning `NO_OPPONENTS`.
- Follow-up issues to file: doubled WARNING+ log lines (two root-logger setups in `app.py`);
  Tidal Surge "overshoot" needs an engine `beats_until_ready`; prompt's INCOMING alert unaware of
  `target_id`; Gorran draft's "Great Quiet" needs an allowed noun when wired.
