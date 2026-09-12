"""
Tests for patch_validation.py — the F.L.A.W.E.D.-derived patch outcome rules.

Source of the definitions under test: Mierczuk, Michaels & Hoodlet, "Frontier
Models' Vulnerability Patches are Often F.L.A.W.E.D.", Off-by-1 Labs / 1Password
2026. See docs/development/flawed-patch-review-hardening-plan.md.

Run: python -m pytest .claude/skills/_shared/review_rules/test_patch_validation.py -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import patch_validation as pv  # noqa: E402


# --- Outcome vocabulary ----------------------------------------------------

def test_outcome_keys_cover_the_papers_five_scenarios():
    """S1-S5 must each have exactly one local name, plus the fragile modifier."""
    assert pv.PATCH_OUTCOMES == [
        "fixed",
        "fixed-behaviour-changed",
        "not-fixed",
        "fixed-new-defect",
        "not-fixed-new-defect",
    ]


def test_every_outcome_maps_to_a_paper_scenario():
    assert set(pv.OUTCOME_TO_SCENARIO) == set(pv.PATCH_OUTCOMES)
    assert sorted(pv.OUTCOME_TO_SCENARIO.values()) == ["S1", "S2", "S3", "S4", "S5"]


def test_only_fixed_outcomes_close_a_finding():
    closing = {o for o in pv.PATCH_OUTCOMES if not pv.outcome_blocks_closure(o)}
    assert closing == {"fixed"}


def test_behaviour_changed_does_not_close():
    """S2 fixed the bug but moved behaviour — 20.1% of patches. Not closed."""
    assert pv.outcome_blocks_closure("fixed-behaviour-changed") is True


def test_unknown_outcome_blocks_closure():
    """Fail closed: an unrecognised outcome must never read as success."""
    assert pv.outcome_blocks_closure("probably-fine") is True
    assert pv.outcome_blocks_closure("") is True


# --- Fragility (37.5% of successful patches) -------------------------------

def test_fragile_fix_does_not_close_even_when_outcome_is_fixed():
    assert pv.FRAGILE_BLOCKS_CLOSURE is True
    assert pv.finding_is_closed("fixed", fragile=False) is True
    assert pv.finding_is_closed("fixed", fragile=True) is False


def test_fragile_shapes_are_named():
    """The two shapes the paper describes must be enumerated, not implied."""
    assert set(pv.FRAGILE_FIX_SHAPES) == {"input-filter", "caller-gated"}
    for shape, description in pv.FRAGILE_FIX_SHAPES.items():
        assert description.strip(), f"{shape} needs a description reviewers can apply"


# --- The corrected rubric definitions -------------------------------------

def test_partial_path_coverage_is_never_a_clean_fix():
    """The paper's most significant validator error: a passing reproducer on one
    path of a multi-path bug read as fully fixed."""
    assert pv.classify_path_coverage(paths_total=3, paths_fixed=1) == "partial"
    assert pv.classify_path_coverage(paths_total=3, paths_fixed=3) == "complete"
    assert pv.is_clean_fix_eligible(paths_total=3, paths_fixed=1) is False
    assert pv.is_clean_fix_eligible(paths_total=3, paths_fixed=3) is True


def test_zero_enumerated_paths_is_not_eligible():
    """A scan that found no paths approves of everything — same non-vacuity rule
    as Step 4.25. Never treat an empty enumeration as full coverage."""
    assert pv.is_clean_fix_eligible(paths_total=0, paths_fixed=0) is False


def test_behaviour_change_requires_matching_neither_baseline():
    """Corrected rubric: a behaviour change is new behaviour matching NEITHER the
    pre-fix nor the intended post-fix behaviour. Without the second clause the
    gate fires on every deliberate change."""
    # Deliberate, intended change — not a behaviour defect.
    assert pv.is_behaviour_defect(matches_pre_fix=False, matches_intended_post_fix=True) is False
    # Unchanged behaviour — not a defect.
    assert pv.is_behaviour_defect(matches_pre_fix=True, matches_intended_post_fix=False) is False
    # Matches neither — this is the S2 case.
    assert pv.is_behaviour_defect(matches_pre_fix=False, matches_intended_post_fix=False) is True


# --- Provenance (M6) ------------------------------------------------------

def test_provenance_values_separate_preexisting_from_introduced():
    assert set(pv.PROVENANCE) == {"pre-existing", "introduced-by-this-diff"}


def test_preexisting_defect_is_not_a_new_defect():
    """The authors' validator misfiled S3 as S5 by counting unchanged vulnerable
    code as newly introduced. Provenance is about whether the diff touched it."""
    assert pv.is_new_defect("introduced-by-this-diff") is True
    assert pv.is_new_defect("pre-existing") is False


def test_unknown_provenance_is_not_silently_new():
    assert pv.is_new_defect("unknown") is False


# --- Confirmation gates ---------------------------------------------------

def test_major_security_fix_always_confirms_regardless_of_confidence():
    """Model confidence does not track patch correctness on security work, so
    confidence is the wrong gate for this dimension."""
    assert pv.SECURITY_FIX_ALWAYS_CONFIRMS is True
    needed, reason = pv.fix_requires_user_confirmation(
        dimension="Security", severity="Major",
        changes_behaviour=False, confidence=99,
    )
    assert needed is True
    assert "Security" in reason


def test_critical_security_fix_always_confirms():
    needed, _ = pv.fix_requires_user_confirmation(
        dimension="Security", severity="Critical",
        changes_behaviour=False, confidence=100,
    )
    assert needed is True


def test_minor_security_fix_follows_ordinary_confidence_rules():
    needed, _ = pv.fix_requires_user_confirmation(
        dimension="Security", severity="Minor",
        changes_behaviour=False, confidence=95,
    )
    assert needed is False


def test_behaviour_change_confirms_in_any_dimension():
    needed, reason = pv.fix_requires_user_confirmation(
        dimension="DRY", severity="Nit",
        changes_behaviour=True, confidence=100,
    )
    assert needed is True
    assert "behaviour" in reason.lower()


def test_low_confidence_still_confirms():
    needed, reason = pv.fix_requires_user_confirmation(
        dimension="CleanCode", severity="Minor",
        changes_behaviour=False, confidence=50,
    )
    assert needed is True
    assert "confidence" in reason.lower()


def test_confident_style_fix_needs_no_confirmation():
    needed, reason = pv.fix_requires_user_confirmation(
        dimension="CleanCode", severity="Minor",
        changes_behaviour=False, confidence=95,
    )
    assert needed is False
    assert reason == ""


def test_confidence_threshold_boundary_is_inclusive():
    """80 is the existing project threshold; at exactly 80 no confirmation."""
    assert pv.CONFIDENCE_CONFIRM_BELOW == 80
    needed, _ = pv.fix_requires_user_confirmation(
        dimension="DRY", severity="Nit", changes_behaviour=False, confidence=80,
    )
    assert needed is False
    needed, _ = pv.fix_requires_user_confirmation(
        dimension="DRY", severity="Nit", changes_behaviour=False, confidence=79,
    )
    assert needed is True


# --- Report vocabulary ----------------------------------------------------

def test_summarise_outcomes_counts_every_outcome():
    counts = pv.summarise_outcomes([
        "fixed", "fixed", "fixed-behaviour-changed", "not-fixed", "bogus",
    ])
    assert counts["fixed"] == 2
    assert counts["fixed-behaviour-changed"] == 1
    assert counts["not-fixed"] == 1
    assert counts["unclassified"] == 1
    assert all(k in counts for k in pv.PATCH_OUTCOMES)


# --- Behaviour-proof scope -------------------------------------------------

def test_hot_paths_require_behaviour_proof():
    assert pv.fix_requires_behaviour_proof(["src/moves/_base.py"]) is True
    assert pv.fix_requires_behaviour_proof(["src/combatant.py"]) is True
    assert pv.fix_requires_behaviour_proof(["src/secure_pickle.py"]) is True
    assert pv.fix_requires_behaviour_proof(["src/story/ch01.py"]) is True


def test_ordinary_paths_do_not():
    assert pv.fix_requires_behaviour_proof(["src/api/routes/shop.py"]) is False
    assert pv.fix_requires_behaviour_proof(["frontend/src/hooks/useApi.js"]) is False
    assert pv.fix_requires_behaviour_proof([]) is False


def test_one_hot_path_in_a_mixed_changeset_is_enough():
    assert pv.fix_requires_behaviour_proof(
        ["README.md", "tests/test_x.py", "src/moves/_base.py"]
    ) is True


def test_absolute_and_windows_paths_match():
    """The orchestrator may hand over absolute or Windows-style paths; a scope
    gate that silently misses them fails open on exactly the files it guards."""
    assert pv.fix_requires_behaviour_proof(
        ["/home/user/Heart-Of-Virtue/src/combatant.py"]
    ) is True
    assert pv.fix_requires_behaviour_proof(["src\\moves\\_base.py"]) is True


def test_scope_list_is_not_empty_and_stays_short():
    """Non-vacuity, plus a ceiling: this gate's value is that it is selective.
    If it grows past a handful of paths it has become 'everything', and a gate
    that fires on everything is one reviewers learn to skip."""
    assert len(pv.BEHAVIOUR_PROOF_PATHS) > 0
    assert len(pv.BEHAVIOUR_PROOF_PATHS) <= 8


def test_frontend_src_is_never_the_engine_tree():
    """`frontend/src/` shares the `src/` segment with the engine but is the SPA.

    No collision exists today, but the moment someone adds a `story/` or `moves/`
    component under frontend/src, a substring match would demand an *engine*
    behaviour proof for a React change. This gate's whole value is selectivity, so
    a false positive costs exactly what a false negative does: the next reader
    stops believing it.
    """
    assert pv.fix_requires_behaviour_proof(["frontend/src/story/StoryPanel.jsx"]) is False
    assert pv.fix_requires_behaviour_proof(["frontend/src/moves/MoveCard.jsx"]) is False
    assert pv.fix_requires_behaviour_proof(
        ["/home/user/Heart-Of-Virtue/frontend/src/story/StoryPanel.jsx"]
    ) is False


def test_engine_paths_still_match_when_absolute():
    """The absolute-path case the exclusion must not break."""
    assert pv.fix_requires_behaviour_proof(
        ["/home/user/Heart-Of-Virtue/src/story/ch01.py"]
    ) is True
    assert pv.fix_requires_behaviour_proof(
        ["/home/user/Heart-Of-Virtue/src/moves/_base.py"]
    ) is True


def test_a_frontend_and_an_engine_path_together_still_require_proof():
    """The exclusion must skip the frontend path, not abort the whole scan."""
    assert pv.fix_requires_behaviour_proof(
        ["frontend/src/story/StoryPanel.jsx", "src/combatant.py"]
    ) is True
