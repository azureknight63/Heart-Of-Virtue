"""
Patch Validation — Rules-as-Code Module

Shared vocabulary for judging whether a *fix* actually fixed anything. Used by
the code-scrubber and code-review skills, and referenced by issue-triage and
devops-review. Lives beside code_review_rules.py / code_scrubber_rules.py and
follows the same contract: both Claude Code on the web and the CLI clone this
repo fresh, so nothing here may depend on a local machine's global config.

The definitions are not invented. They are taken from Mierczuk, Michaels &
Hoodlet, "Frontier Models' Vulnerability Patches are Often F.L.A.W.E.D. —
Fix-Like Artifacts With Embedded Defects" (Off-by-1 Labs / 1Password, 2026),
which measured 6,080 LLM patch attempts against six recent multi-path CVEs and
found 26.0% clean fixes, 20.1% fixes that moved application behaviour, 51.5%
fail-to-fix, 4.5% introducing a new vulnerability, and 37.5% of the *successful*
patches fragile. Two of the definitions below (clean-fix path coverage, and what
counts as a behaviour defect) are the authors' rubric as *corrected* by their own
human review — the naive versions systematically misclassify, and the correction
is the whole value. Do not "simplify" them back.

Rationale and the full analysis: docs/development/flawed-patch-review-hardening-plan.md

To change a value, update this file, test_patch_validation.py, and the skill
docs that cite it together, then re-run:
  python -m pytest .claude/skills/_shared/review_rules/test_patch_validation.py -v
"""

# ---------------------------------------------------------------------------
# Outcome Vocabulary
# ---------------------------------------------------------------------------
# Local names for the paper's S1-S5 scale. Ordered best to worst. A review that
# reports "fixes applied: N" without saying which of these N were is reporting
# activity, not outcomes.

PATCH_OUTCOMES: list[str] = [
    "fixed",                    # S1: root cause closed on every path, behaviour intact
    "fixed-behaviour-changed",  # S2: closed, but behaviour moved (20.1% of attempts)
    "not-fixed",                # S3: at least one path still reachable (49.3%)
    "fixed-new-defect",         # S4: closed, but the patch introduced a defect
    "not-fixed-new-defect",     # S5: neither closed nor clean — worst case
]

OUTCOME_TO_SCENARIO: dict[str, str] = {
    "fixed": "S1",
    "fixed-behaviour-changed": "S2",
    "not-fixed": "S3",
    "fixed-new-defect": "S4",
    "not-fixed-new-defect": "S5",
}

# Only a clean fix closes a finding. Everything else — including a fix that
# worked but moved behaviour — stays open for a human.
CLOSING_OUTCOMES: frozenset = frozenset({"fixed"})


def outcome_blocks_closure(outcome: str) -> bool:
    """Return True if this outcome leaves the finding open.

    Fails closed: an unrecognised outcome blocks closure rather than reading as
    success. A typo must never promote a patch.
    """
    return outcome not in CLOSING_OUTCOMES


# ---------------------------------------------------------------------------
# Fragility
# ---------------------------------------------------------------------------
# 37.5% of the patches the paper graded as successful were fragile: the immediate
# vulnerability was unexploitable, but the vulnerable code survived and stayed
# reachable. A fix that "fully removes or replaces the vulnerable code" is not
# fragile; one that merely gates it is.

FRAGILE_BLOCKS_CLOSURE: bool = True

FRAGILE_FIX_SHAPES: dict[str, str] = {
    "input-filter": (
        "Blocks the specific input the reproduction used. The root cause is "
        "untouched, so an alternative input resurfaces the bug."
    ),
    "caller-gated": (
        "Adds a check in a calling function while the vulnerable primitive stays "
        "callable. Any other caller — present or future — reopens the hole."
    ),
}


def finding_is_closed(outcome: str, fragile: bool) -> bool:
    """Return True only for a clean, non-fragile fix."""
    if outcome_blocks_closure(outcome):
        return False
    return not (fragile and FRAGILE_BLOCKS_CLOSURE)


# ---------------------------------------------------------------------------
# Path Coverage — the corrected clean-fix definition
# ---------------------------------------------------------------------------
# The single most consequential error the paper's human review caught: the
# validator read "the reproducer no longer triggers the bug" as "the bug is
# fixed". A reproducer exercises one path; the vulnerabilities were multi-path.
# Corrected rubric: "fixed" means fixed across every path the finding covers, so
# a partial fix can never grade clean no matter what the reproduction says.

def classify_path_coverage(paths_total: int, paths_fixed: int) -> str:
    """Return "complete", "partial", or "none" for enumerated path coverage."""
    if paths_total <= 0 or paths_fixed <= 0:
        return "none"
    if paths_fixed >= paths_total:
        return "complete"
    return "partial"


def is_clean_fix_eligible(paths_total: int, paths_fixed: int) -> bool:
    """Return True only if every enumerated path is covered.

    An empty enumeration is not eligible. A scan that found no paths approves of
    everything — the same non-vacuity rule the scrubber's Step 4.25 applies to
    test guards, applied here to the fix itself.
    """
    return classify_path_coverage(paths_total, paths_fixed) == "complete"


# ---------------------------------------------------------------------------
# Behaviour-Proof Scope
# ---------------------------------------------------------------------------
# Which paths are semantically load-bearing enough that a fix touching them owes
# an observed before/after, not just a green suite. Deliberately a short list: a
# gate that fires on every file is one reviewers learn to skip. It mirrors the
# hot-path set /code-review already uses to weight Optimization, plus the two
# persistence paths where a silent behaviour change is least recoverable.

BEHAVIOUR_PROOF_PATHS: tuple = (
    "src/moves/",
    "src/combatant.py",
    "src/api/combat_adapter.py",
    "src/save_format.py",
    "src/secure_pickle.py",
    "src/story/",
)


# Roots that contain a `src/` segment but are not the Python engine. The SPA lives
# at frontend/src/, so a `story/` or `moves/` component added there must not be
# mistaken for src/story/ or src/moves/ and demand an engine behaviour proof. A
# gate that fires on the wrong files loses its authority as surely as one that
# misses the right ones.
NON_ENGINE_ROOTS: tuple = ("frontend/",)


def fix_requires_behaviour_proof(changed_paths) -> bool:
    """Return True if any changed path is semantically load-bearing.

    Accepts repo-relative, absolute and Windows-style paths. Paths under a
    NON_ENGINE_ROOTS tree are skipped rather than aborting the scan, so a
    changeset mixing frontend and engine files still requires the proof.
    """
    for raw in changed_paths:
        path = str(raw).replace("\\", "/")
        if any(root in path for root in NON_ENGINE_ROOTS):
            continue
        if any(path.startswith(prefix) or f"/{prefix}" in path
               for prefix in BEHAVIOUR_PROOF_PATHS):
            return True
    return False


# ---------------------------------------------------------------------------
# Behaviour Defects — the corrected definition
# ---------------------------------------------------------------------------
# The other correction worth copying exactly. Flagging *any* deviation from
# pre-fix behaviour misfiled clean fixes as behaviour-changing, because a good
# patch often changes behaviour on purpose. A behaviour defect is new behaviour
# matching NEITHER the pre-fix behaviour NOR the intended post-fix behaviour.
# Drop the second clause and the gate fires constantly, which teaches reviewers
# to ignore it.

def is_behaviour_defect(matches_pre_fix: bool, matches_intended_post_fix: bool) -> bool:
    """Return True only when observed behaviour matches neither baseline."""
    return not matches_pre_fix and not matches_intended_post_fix


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------
# The paper's validator also conflated "unchanged code that is still vulnerable"
# with "a vulnerability this patch introduced", misfiling S3 as S5. Their fix: a
# new defect is one in code the patch *added or directly modified*. Severity says
# how bad a finding is; provenance says whose fault it is. They are different
# axes and collapsing them loses real information in both directions.

PROVENANCE: frozenset = frozenset({"pre-existing", "introduced-by-this-diff"})

NEW_DEFECT_PROVENANCE: str = "introduced-by-this-diff"


def is_new_defect(provenance: str) -> bool:
    """Return True only for a defect in code this diff added or modified.

    Unknown provenance is not treated as new — claiming a diff introduced
    something it may predate is the error this axis exists to prevent.
    """
    return provenance == NEW_DEFECT_PROVENANCE


# ---------------------------------------------------------------------------
# Confirmation Gates
# ---------------------------------------------------------------------------
# The project's existing rule escalates a fix to the user below ~80% confidence
# or when behaviour could move. That is kept. What is added is that a
# Critical/Major Security fix escalates *regardless of confidence*, because the
# paper's central finding is that model confidence does not track patch
# correctness on security work — so confidence is the wrong instrument here.

SECURITY_FIX_ALWAYS_CONFIRMS: bool = True
SECURITY_SEVERITIES_REQUIRING_CONFIRMATION: frozenset = frozenset({"Critical", "Major"})
BEHAVIOUR_CHANGE_REQUIRES_CONFIRMATION: bool = True
CONFIDENCE_CONFIRM_BELOW: int = 80


def fix_requires_user_confirmation(dimension: str, severity: str,
                                   changes_behaviour: bool,
                                   confidence: int) -> tuple[bool, str]:
    """Return (True, reason) if this fix must be put to the user before applying.

    Checked in order of how strongly the paper supports each gate, so the reason
    returned is the most defensible one.
    """
    if (SECURITY_FIX_ALWAYS_CONFIRMS
            and dimension == "Security"
            and severity in SECURITY_SEVERITIES_REQUIRING_CONFIRMATION):
        return True, (
            f"{severity} Security fix: confidence does not predict patch "
            f"correctness for security work — a human decides"
        )
    if changes_behaviour and BEHAVIOUR_CHANGE_REQUIRES_CONFIRMATION:
        return True, "Fix changes observable behaviour"
    if confidence < CONFIDENCE_CONFIRM_BELOW:
        return True, f"Confidence {confidence} below threshold {CONFIDENCE_CONFIRM_BELOW}"
    return False, ""


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def summarise_outcomes(outcomes: list) -> dict:
    """Count a list of outcome labels, with every known outcome present at zero.

    Unrecognised labels land in "unclassified" rather than being dropped — a
    silently discarded outcome is how a bad patch disappears from a report.
    """
    counts = {outcome: 0 for outcome in PATCH_OUTCOMES}
    counts["unclassified"] = 0
    for outcome in outcomes:
        key = outcome if outcome in counts else "unclassified"
        counts[key] += 1
    return counts
