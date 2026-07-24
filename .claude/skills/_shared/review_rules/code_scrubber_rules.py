"""
Code Scrubber — Rules-as-Code Module

Single source of truth for the code-scrubber skill (large-diff, chunked,
multi-agent review). Lives in-repo alongside code_review_rules.py so both
Claude Code on the web and the CLI see identical values — both clone this
repo fresh, so nothing here may depend on a local machine's global config.

To change a value, update this file, its test (test_code_scrubber_rules.py),
and ../../code-scrubber/SKILL.md together, then re-run:
  python -m pytest .claude/skills/_shared/review_rules/test_code_scrubber_rules.py -v
"""

# ---------------------------------------------------------------------------
# Model → Chunk-Size Map
# ---------------------------------------------------------------------------

# Keys are lowercase fragments that appear in the Agent tool's `model` value
# (sonnet | opus | haiku | fable). Evaluated in order; first match wins.
# "fable" has no dedicated tier yet — falls through to CHUNK_SIZE_FALLBACK
# until its context/quality profile for this kind of review is established.
MODEL_CHUNK_SIZES: list[tuple[str, int]] = [
    ("haiku",  300),
    ("sonnet", 600),
    ("opus",   1000),
]

CHUNK_SIZE_FALLBACK: int = 400


def get_chunk_size(model_name: str) -> int:
    """Return the line-budget for a given model name string."""
    lower = model_name.lower()
    for fragment, size in MODEL_CHUNK_SIZES:
        if fragment in lower:
            return size
    return CHUNK_SIZE_FALLBACK


# ---------------------------------------------------------------------------
# Chunk Guard Constants
# ---------------------------------------------------------------------------

SOFT_CAP_PCT: float = 1.10          # A chunk may land up to 110% of target
HARD_CAP_PCT: float = 2.00          # A chunk must never exceed 200% of target
MAX_CHUNK_COUNT: int = 15           # Plans exceeding this need a safety flag (see below)
MAX_BUDGET_MULTIPLIER: float = 2.0  # Single chunk exceeding 2x target needs a safety flag
CHUNK_WAVE_SIZE: int = 5            # Max chunks reviewed in parallel per wave (5 subagents x wave_size dispatched simultaneously)


def chunk_requires_confirmation(chunk_lines: int, target: int, total_chunks: int) -> tuple[bool, str]:
    """
    Return (True, reason) if the chunk plan exceeds a normal safety threshold.

    NOTE: the skill runs as a background-dispatched Agent (see SKILL.md
    "Invocation Mode"), which cannot pause to ask the user mid-task. A True
    result here does not block the run — it means the orchestrator must
    proceed and record an "AUTO-PROCEEDED (needs review)" flag with this
    reason in the final report instead of asking before starting.
    """
    if total_chunks > MAX_CHUNK_COUNT:
        return True, f"Chunk count {total_chunks} exceeds MAX_CHUNK_COUNT ({MAX_CHUNK_COUNT})"
    if chunk_lines > target * MAX_BUDGET_MULTIPLIER:
        return True, (
            f"Chunk size {chunk_lines} lines exceeds {MAX_BUDGET_MULTIPLIER}x "
            f"model budget ({target} lines)"
        )
    return False, ""


def chunk_is_oversized(chunk_lines: int, target: int) -> bool:
    """Return True if the chunk is unacceptably large (above HARD_CAP_PCT)."""
    return chunk_lines > target * HARD_CAP_PCT


# ---------------------------------------------------------------------------
# Iteration Cap
# ---------------------------------------------------------------------------

MAX_ITERATIONS_PER_CHUNK: int = 3


# ---------------------------------------------------------------------------
# Grading Rubric Dimensions, Grades, and Severity Levels
# ---------------------------------------------------------------------------
# Imported from the code-review skill's rules module — single source of truth.
# To change these values, update code_review_rules.py (this directory).

from code_review_rules import (
    DIMENSION_KEYS as _CORE_DIMENSIONS,
    VALID_GRADES,
    validate_grades as _validate_grades_core,
    all_a_grade as _all_a_grade_core,
    SEVERITY_TIERS as SEVERITY_LEVELS,
)

# Code Scrubber adds the Alignment dimension on top of the core code-review dimensions.
SCRUBBER_DIMENSION_ADDITIONS: list[str] = ["Alignment"]
GRADING_DIMENSIONS: list[str] = _CORE_DIMENSIONS + SCRUBBER_DIMENSION_ADDITIONS


def validate_grades(grades: dict) -> list:
    """Scrubber-aware grade validator. Validates against GRADING_DIMENSIONS (7 keys)."""
    errors: list = []
    for key in GRADING_DIMENSIONS:
        if key not in grades:
            errors.append(f"Missing grade for dimension '{key}'")
        elif grades[key] not in VALID_GRADES:
            errors.append(
                f"Invalid grade '{grades[key]}' for dimension '{key}' "
                f"(expected one of {sorted(VALID_GRADES)})"
            )
    for key in grades:
        if key not in GRADING_DIMENSIONS:
            errors.append(f"Unknown dimension '{key}' in grades dict")
    return errors


def all_a_grade(grades: dict) -> bool:
    """Return True if every graded dimension (all 7) is A."""
    return all(grades.get(dim) == "A" for dim in GRADING_DIMENSIONS)

# ---------------------------------------------------------------------------
# Security Subagent Model Override
# ---------------------------------------------------------------------------

SECURITY_SUBAGENT_MODEL: str = "opus"

# ---------------------------------------------------------------------------
# Adversary Subagent Models and Routing
# ---------------------------------------------------------------------------

ADVERSARY_STYLE_MODEL: str = "haiku"
ADVERSARY_SECURITY_MODEL: str = "opus"

ADVERSARY_STYLE_AGENT: str = "code-scrubber-adversary-style"
ADVERSARY_SECURITY_AGENT: str = "code-scrubber-adversary-security"

# Dimensions covered by each adversary (must be disjoint and cover all GRADING_DIMENSIONS + Correctness)
ADVERSARY_STYLE_DIMENSIONS: frozenset = frozenset({"DRY", "CleanCode", "Optimization", "Maintainability", "AIFriendliness"})
ADVERSARY_SECURITY_DIMENSIONS: frozenset = frozenset({"Security", "Alignment", "Correctness"})


def get_adversary_for_dimension(dimension: str) -> "tuple[str, str] | None":
    """
    Return (agent_name, model_override) for the adversary that covers the given dimension.
    Returns None if the dimension is not recognised.
    """
    if dimension in ADVERSARY_STYLE_DIMENSIONS:
        return (ADVERSARY_STYLE_AGENT, ADVERSARY_STYLE_MODEL)
    if dimension in ADVERSARY_SECURITY_DIMENSIONS:
        return (ADVERSARY_SECURITY_AGENT, ADVERSARY_SECURITY_MODEL)
    return None

# ---------------------------------------------------------------------------
# Alignment Context Fallback
# ---------------------------------------------------------------------------

ALIGNMENT_FALLBACK_BRIEF: str = (
    "Does the code meet the highest professional software development standards?"
)

# ---------------------------------------------------------------------------
# Dimension → Subagent Mapping
# ---------------------------------------------------------------------------
# Values are Claude Code custom agent names (.claude/agents/<name>.md, matches
# the Agent tool's subagent_type parameter).

DIMENSION_SUBAGENTS: dict[str, str] = {
    "DRY":             "code-scrubber-dry-maintainability",
    "Maintainability": "code-scrubber-dry-maintainability",
    "CleanCode":       "code-scrubber-clean-ai",
    "AIFriendliness":  "code-scrubber-clean-ai",
    "Optimization":    "code-scrubber-optimization",
    "Security":        "code-scrubber-security",
    "Alignment":       "code-scrubber-alignment-correctness",
    "Correctness":     "code-scrubber-alignment-correctness",
}


def get_unique_subagents() -> list[str]:
    """Return the distinct list of dimension subagent names (5 total), in stable order."""
    return list(dict.fromkeys(DIMENSION_SUBAGENTS.values()))


def get_subagent_model_override(subagent_name: str) -> "str | None":
    """Return the model override string if the subagent requires one, else None."""
    if subagent_name == DIMENSION_SUBAGENTS["Security"]:
        return SECURITY_SUBAGENT_MODEL
    return None


# ---------------------------------------------------------------------------
# Finding Severity Levels
# ---------------------------------------------------------------------------

# Maps severity label → sort key (lower = higher priority)
SEVERITY_ORDER: dict[str, int] = {s: i for i, s in enumerate(SEVERITY_LEVELS)}


def sort_findings_by_severity(findings: list[dict]) -> list[dict]:
    """
    Sort a list of finding dicts (each with a 'severity' key) highest-first.
    Findings with unrecognised severities are sorted to the end.
    """
    return sorted(
        findings,
        key=lambda f: SEVERITY_ORDER.get(f.get("severity", ""), len(SEVERITY_LEVELS)),
    )


# ---------------------------------------------------------------------------
# Splitting Strategy Labels (for plan output / tests)
# ---------------------------------------------------------------------------

SPLIT_STRATEGIES: list[str] = [
    "by_file",
    "by_symbol",
    "by_hunk",
]


# ---------------------------------------------------------------------------
# Project Test Suite Commands
# ---------------------------------------------------------------------------
# Heart of Virtue's actual canonical commands (see CLAUDE.md "Running Tests").
# Use `python -m pytest`, never bare `pytest` — the venv may not expose the
# `pytest` binary on PATH, which causes silent import failures.

TEST_SUITE_COMMANDS: list[str] = [
    "python -m pytest -q",
    "cd frontend && npm test -- --run",
]
