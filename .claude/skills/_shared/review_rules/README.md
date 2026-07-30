# Review Rules — Shared Constants

Single source of truth for the `code-review` and `code-scrubber` skills
(`../code-review/SKILL.md`, `../code-scrubber/SKILL.md`) and the seven
dimension/adversary subagents in `../../agents/code-scrubber-*.md`.

Everything here lives **in this repo**, not a global user-config folder —
Claude Code on the web clones this repo fresh for every session, so any
value a skill depends on must be checked in here to behave identically in
the cloud and in the CLI.

## Files

| File | Purpose |
|---|---|
| `code_review_rules.py` | Dimensions, grades, severity tiers, diff-size routing thresholds. Generic — no project-specific content. |
| `code_scrubber_rules.py` | Chunking/wave/model constants for large-diff review. Imports `code_review_rules` and adds the `Alignment` dimension. |
| `test_code_review_rules.py` / `test_code_scrubber_rules.py` | Pin every constant above to an exact value. |

## Changing a value

1. Edit the constant in the `.py` file.
2. Update the corresponding table in the skill's `SKILL.md` (and the
   relevant `.claude/agents/code-scrubber-*.md` file if it's a model or
   agent-name mapping).
3. Re-run the tests:
   ```
   python -m pytest .claude/skills/_shared/review_rules -v
   ```

These tests are **not** part of the default `python -m pytest -q` run —
`.claude/` is excluded via `pytest.ini`'s `norecursedirs`, so they don't
count against the project's 85% coverage gate or its test-count target.
Run them manually whenever you touch a constant here.

## Why two files instead of one

`code_review_rules.py` is deliberately generic (six dimensions, grading
scale, diff-size thresholds) so both skills — and any future one — can
depend on it without pulling in scrubber-specific concepts like chunk
waves or adversary routing. `code_scrubber_rules.py` extends it the same
way any consumer would: import the base dimensions, add `Alignment` on
top. Don't duplicate a constant that already exists in the other file.
