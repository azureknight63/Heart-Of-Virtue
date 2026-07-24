"""
Code Review Skill — Rules-as-Code Module

Single source of truth for review dimensions, grades, and severity tiers.
Lives in-repo (not a global user-prompts folder) so it behaves identically
in Claude Code on the web and in the CLI — both clone this repo fresh.

Also imported by code_scrubber_rules.py to eliminate duplication.

To change a value, update this file, its test (test_code_review_rules.py),
and the dimension tables in ../../code-review/SKILL.md together, then re-run:
  python -m pytest .claude/skills/_shared/review_rules/test_code_review_rules.py -v
"""

# ---------------------------------------------------------------------------
# Review Dimensions
# ---------------------------------------------------------------------------

# (display_name, packet_key) — order is the canonical review order
REVIEW_DIMENSIONS: list[tuple[str, str]] = [
    ("DRY",             "DRY"),
    ("Clean Code",      "CleanCode"),
    ("Optimization",    "Optimization"),
    ("Maintainability", "Maintainability"),
    ("Security",        "Security"),
    ("AI-Friendliness", "AIFriendliness"),
]

# Machine keys used in subagent packets (e.g. DRY=A  CleanCode=B ...)
DIMENSION_KEYS: list[str] = [key for _, key in REVIEW_DIMENSIONS]

# Human-readable names used in narrative review output
DIMENSION_DISPLAY_NAMES: list[str] = [name for name, _ in REVIEW_DIMENSIONS]


# ---------------------------------------------------------------------------
# Grading Scale
# ---------------------------------------------------------------------------

VALID_GRADES: set[str] = {"A", "B", "C", "D", "F"}

# Maps each grade to the maximum severity of finding it tolerates
GRADE_SEVERITY_FLOOR: dict[str, str] = {
    "A": "Nit",       # Nit at most
    "B": "Minor",     # Minor at most
    "C": "Major",     # one or more Major
    "D": "Major",     # pervasive Major findings
    "F": "Critical",  # one or more Critical
}


# ---------------------------------------------------------------------------
# Severity Tiers (ordered high → low)
# ---------------------------------------------------------------------------

SEVERITY_TIERS: list[str] = ["Critical", "Major", "Minor", "Nit"]


# ---------------------------------------------------------------------------
# Diff-Size Thresholds (lines) — drives routing between code-review and
# code-scrubber (see ../../code-review/SKILL.md Step 0).
# ---------------------------------------------------------------------------

DIFF_STANDARD_THRESHOLD: int = 50       # <= this: full-depth single-pass
DIFF_FOCUSED_THRESHOLD: int = 300       # <= this: standard review, all dimensions
DIFF_REDIRECT_THRESHOLD: int = 1_000    # > this: redirect to code-scrubber skill


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def validate_grades(grades: dict[str, str]) -> list[str]:
    """
    Validate a per-dimension grades dict returned by a subagent.
    Returns a list of error strings; empty list means valid.
    """
    errors: list[str] = []
    for key in DIMENSION_KEYS:
        if key not in grades:
            errors.append(f"Missing grade for dimension '{key}'")
        elif grades[key] not in VALID_GRADES:
            errors.append(
                f"Invalid grade '{grades[key]}' for dimension '{key}' "
                f"(expected one of {sorted(VALID_GRADES)})"
            )
    for key in grades:
        if key not in DIMENSION_KEYS:
            errors.append(f"Unknown dimension '{key}' in grades dict")
    return errors


def all_a_grade(grades: dict[str, str]) -> bool:
    """Return True if every graded dimension is A."""
    return all(grades.get(dim) == "A" for dim in DIMENSION_KEYS)


def grade_from_severity(highest_severity: str) -> str:
    """
    Return the minimum grade implied by the highest-severity finding in a dimension.
    Critical -> F; Major -> C; Minor -> B; Nit or no findings -> A.
    """
    mapping: dict[str, str] = {
        "Critical": "F",
        "Major":    "C",
        "Minor":    "B",
        "Nit":      "A",
    }
    return mapping.get(highest_severity, "A")


def review_depth_for_diff_size(diff_lines: int) -> str:
    """
    Return the recommended review approach label for a given diff size.

    Returns one of:
      'full-depth'            -- <= DIFF_STANDARD_THRESHOLD
      'standard'              -- <= DIFF_FOCUSED_THRESHOLD
      'focused'               -- <= DIFF_REDIRECT_THRESHOLD
      'redirect-to-scrubber'  -- above DIFF_REDIRECT_THRESHOLD
    """
    if diff_lines <= DIFF_STANDARD_THRESHOLD:
        return "full-depth"
    if diff_lines <= DIFF_FOCUSED_THRESHOLD:
        return "standard"
    if diff_lines <= DIFF_REDIRECT_THRESHOLD:
        return "focused"
    return "redirect-to-scrubber"
