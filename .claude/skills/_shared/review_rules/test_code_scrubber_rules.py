"""
pytest suite for the Code Scrubber rules module.

Module: code_scrubber_rules.py (same directory)

Run:
  python -m pytest .claude/skills/_shared/review_rules/test_code_scrubber_rules.py -v

Not part of the default `python -m pytest -q` run — .claude/ is excluded via
pytest.ini's norecursedirs, matching the source design's intent that these
constants are pinned on demand (when the reference values change), not
wired into CI alongside src/ai coverage.
"""

import sys
import os

# Allow running from the repo root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import pytest
from code_scrubber_rules import (
    MODEL_CHUNK_SIZES,
    CHUNK_SIZE_FALLBACK,
    get_chunk_size,
    SOFT_CAP_PCT,
    HARD_CAP_PCT,
    MAX_CHUNK_COUNT,
    MAX_BUDGET_MULTIPLIER,
    CHUNK_WAVE_SIZE,
    chunk_requires_confirmation,
    chunk_is_oversized,
    MAX_ITERATIONS_PER_CHUNK,
    GRADING_DIMENSIONS,
    VALID_GRADES,
    validate_grades,
    all_a_grade,
    SEVERITY_LEVELS,
    SEVERITY_ORDER,
    sort_findings_by_severity,
    SPLIT_STRATEGIES,
    TEST_SUITE_COMMANDS,
    SECURITY_SUBAGENT_MODEL,
    ALIGNMENT_FALLBACK_BRIEF,
    DIMENSION_SUBAGENTS,
    get_unique_subagents,
    get_subagent_model_override,
    ADVERSARY_STYLE_MODEL,
    ADVERSARY_SECURITY_MODEL,
    ADVERSARY_STYLE_AGENT,
    ADVERSARY_SECURITY_AGENT,
    ADVERSARY_STYLE_DIMENSIONS,
    ADVERSARY_SECURITY_DIMENSIONS,
    get_adversary_for_dimension,
)


# ---------------------------------------------------------------------------
# Constants — value and format assertions
# ---------------------------------------------------------------------------

class TestConstants:
    def test_chunk_size_fallback_value(self):
        assert CHUNK_SIZE_FALLBACK == 400

    def test_soft_cap_pct(self):
        assert SOFT_CAP_PCT == pytest.approx(1.10)

    def test_hard_cap_pct(self):
        assert HARD_CAP_PCT == pytest.approx(2.00)

    def test_max_chunk_count(self):
        assert MAX_CHUNK_COUNT == 15

    def test_max_budget_multiplier(self):
        assert MAX_BUDGET_MULTIPLIER == pytest.approx(2.0)

    def test_chunk_wave_size_value(self):
        assert CHUNK_WAVE_SIZE == 5

    def test_chunk_wave_size_less_than_max_chunk_count(self):
        """Wave size must stay below MAX_CHUNK_COUNT to make sense as a batching unit."""
        assert CHUNK_WAVE_SIZE < MAX_CHUNK_COUNT

    def test_max_iterations(self):
        assert MAX_ITERATIONS_PER_CHUNK == 3

    def test_grading_dimensions_count(self):
        assert len(GRADING_DIMENSIONS) == 7

    def test_grading_dimensions_names(self):
        expected = {"DRY", "CleanCode", "Optimization", "Maintainability", "Security", "AIFriendliness", "Alignment"}
        assert set(GRADING_DIMENSIONS) == expected

    def test_severity_levels_count(self):
        assert len(SEVERITY_LEVELS) == 4

    def test_severity_levels_names(self):
        assert SEVERITY_LEVELS == ["Critical", "Major", "Minor", "Nit"]

    def test_split_strategies_count(self):
        assert len(SPLIT_STRATEGIES) == 3

    def test_model_chunk_sizes_has_entries(self):
        """haiku, sonnet, opus — the three Claude tiers this environment actually runs."""
        assert len(MODEL_CHUNK_SIZES) >= 3


# ---------------------------------------------------------------------------
# get_chunk_size — one test per model tier + fallback + case-insensitivity
# ---------------------------------------------------------------------------

class TestGetChunkSize:
    def test_haiku(self):
        assert get_chunk_size("haiku") == 300

    def test_haiku_full_model_id(self):
        assert get_chunk_size("claude-haiku-4-5-20251001") == 300

    def test_haiku_case_insensitive(self):
        assert get_chunk_size("HAIKU") == 300

    def test_sonnet(self):
        assert get_chunk_size("sonnet") == 600

    def test_sonnet_full_model_id(self):
        assert get_chunk_size("claude-sonnet-5") == 600

    def test_sonnet_case_insensitive(self):
        assert get_chunk_size("SONNET") == 600

    def test_opus(self):
        assert get_chunk_size("opus") == 1000

    def test_opus_full_model_id(self):
        assert get_chunk_size("claude-opus-4-8") == 1000

    def test_fable_has_no_dedicated_tier_yet(self):
        """fable falls through to the fallback until its profile is established."""
        assert get_chunk_size("fable") == CHUNK_SIZE_FALLBACK
        assert get_chunk_size("claude-fable-5") == CHUNK_SIZE_FALLBACK

    def test_unknown_model_returns_fallback(self):
        assert get_chunk_size("gpt-5") == CHUNK_SIZE_FALLBACK

    def test_empty_string_returns_fallback(self):
        assert get_chunk_size("") == CHUNK_SIZE_FALLBACK


# ---------------------------------------------------------------------------
# chunk_requires_confirmation
# ---------------------------------------------------------------------------

class TestChunkRequiresConfirmation:
    def test_normal_plan_does_not_require_confirmation(self):
        needs, reason = chunk_requires_confirmation(500, 600, 10)
        assert not needs
        assert reason == ""

    def test_too_many_chunks_requires_confirmation(self):
        needs, reason = chunk_requires_confirmation(500, 600, 16)
        assert needs
        assert "16" in reason
        assert str(MAX_CHUNK_COUNT) in reason

    def test_exact_max_chunk_count_does_not_require_confirmation(self):
        needs, _ = chunk_requires_confirmation(500, 600, MAX_CHUNK_COUNT)
        assert not needs

    def test_chunk_exceeds_budget_multiplier_requires_confirmation(self):
        target = 600
        oversized = int(target * MAX_BUDGET_MULTIPLIER) + 1
        needs, reason = chunk_requires_confirmation(oversized, target, 5)
        assert needs
        assert str(oversized) in reason

    def test_chunk_at_exact_budget_multiplier_does_not_require_confirmation(self):
        target = 600
        exactly = int(target * MAX_BUDGET_MULTIPLIER)
        needs, _ = chunk_requires_confirmation(exactly, target, 5)
        assert not needs


# ---------------------------------------------------------------------------
# chunk_is_oversized
# ---------------------------------------------------------------------------

class TestChunkIsOversized:
    def test_within_hard_cap_is_not_oversized(self):
        assert not chunk_is_oversized(600, 600)       # 100%
        assert not chunk_is_oversized(660, 600)       # 110%
        assert not chunk_is_oversized(1199, 600)      # ~200% - 1

    def test_at_hard_cap_is_not_oversized(self):
        assert not chunk_is_oversized(1200, 600)      # exactly 200%

    def test_above_hard_cap_is_oversized(self):
        assert chunk_is_oversized(1201, 600)
        assert chunk_is_oversized(2000, 600)


# ---------------------------------------------------------------------------
# validate_grades
# ---------------------------------------------------------------------------

class TestValidateGrades:
    def _all_a(self):
        return {dim: "A" for dim in GRADING_DIMENSIONS}

    def test_all_valid_returns_no_errors(self):
        grades = self._all_a()
        assert validate_grades(grades) == []

    def test_missing_dimension_is_reported(self):
        grades = self._all_a()
        del grades["Security"]
        errors = validate_grades(grades)
        assert any("Security" in e for e in errors)

    def test_invalid_grade_value_is_reported(self):
        grades = self._all_a()
        grades["DRY"] = "Z"
        errors = validate_grades(grades)
        assert any("DRY" in e and "Z" in e for e in errors)

    def test_unknown_dimension_is_reported(self):
        grades = self._all_a()
        grades["Nonsense"] = "A"
        errors = validate_grades(grades)
        assert any("Nonsense" in e for e in errors)

    def test_valid_grades_include_b_through_f(self):
        for grade in ["B", "C", "D", "F"]:
            grades = self._all_a()
            grades["DRY"] = grade
            assert validate_grades(grades) == []


# ---------------------------------------------------------------------------
# all_a_grade
# ---------------------------------------------------------------------------

class TestAllAGrade:
    def test_all_a_returns_true(self):
        assert all_a_grade({dim: "A" for dim in GRADING_DIMENSIONS})

    def test_one_b_returns_false(self):
        grades = {dim: "A" for dim in GRADING_DIMENSIONS}
        grades["Security"] = "B"
        assert not all_a_grade(grades)

    def test_missing_dimension_returns_false(self):
        grades = {dim: "A" for dim in GRADING_DIMENSIONS}
        del grades["DRY"]
        assert not all_a_grade(grades)


# ---------------------------------------------------------------------------
# sort_findings_by_severity
# ---------------------------------------------------------------------------

class TestSortFindingsBySeverity:
    def test_sorted_highest_first(self):
        findings = [
            {"severity": "Nit", "msg": "nit"},
            {"severity": "Critical", "msg": "critical"},
            {"severity": "Minor", "msg": "minor"},
            {"severity": "Major", "msg": "major"},
        ]
        result = sort_findings_by_severity(findings)
        assert [f["severity"] for f in result] == ["Critical", "Major", "Minor", "Nit"]

    def test_unknown_severity_goes_to_end(self):
        findings = [
            {"severity": "Unknown", "msg": "unknown"},
            {"severity": "Critical", "msg": "critical"},
        ]
        result = sort_findings_by_severity(findings)
        assert result[0]["severity"] == "Critical"
        assert result[-1]["severity"] == "Unknown"

    def test_empty_list_returns_empty(self):
        assert sort_findings_by_severity([]) == []

    def test_single_item_unchanged(self):
        findings = [{"severity": "Major", "msg": "only one"}]
        assert sort_findings_by_severity(findings) == findings


# ---------------------------------------------------------------------------
# Enumerations — value presence tests
# ---------------------------------------------------------------------------

class TestEnumerations:
    def test_valid_grades_contains_a_through_f_minus_e(self):
        assert VALID_GRADES == {"A", "B", "C", "D", "F"}

    def test_severity_order_is_dense(self):
        assert set(SEVERITY_ORDER.values()) == {0, 1, 2, 3}

    def test_pytest_command_in_test_suite_commands(self):
        assert "python -m pytest -q" in TEST_SUITE_COMMANDS

    def test_frontend_npm_command_in_test_suite_commands(self):
        assert "cd frontend && npm test -- --run" in TEST_SUITE_COMMANDS


# ---------------------------------------------------------------------------
# Dimension Subagents
# ---------------------------------------------------------------------------

class TestDimensionSubagents:
    def test_dimension_subagents_has_eight_keys(self):
        """DIMENSION_SUBAGENTS maps all 7 grading dimensions + Correctness."""
        assert len(DIMENSION_SUBAGENTS) == 8

    def test_security_dimension_maps_to_security_agent(self):
        assert DIMENSION_SUBAGENTS["Security"] == "code-scrubber-security"

    def test_alignment_dimension_maps_to_alignment_agent(self):
        assert DIMENSION_SUBAGENTS["Alignment"] == "code-scrubber-alignment-correctness"

    def test_correctness_dimension_maps_to_alignment_agent(self):
        assert DIMENSION_SUBAGENTS["Correctness"] == "code-scrubber-alignment-correctness"

    def test_unique_subagents_returns_five(self):
        unique = get_unique_subagents()
        assert len(unique) == 5

    def test_unique_subagents_order_is_stable(self):
        """Calling twice must return the same order."""
        assert get_unique_subagents() == get_unique_subagents()

    def test_security_has_model_override(self):
        override = get_subagent_model_override("code-scrubber-security")
        assert override == SECURITY_SUBAGENT_MODEL

    def test_non_security_has_no_override(self):
        for name in get_unique_subagents():
            if name != "code-scrubber-security":
                assert get_subagent_model_override(name) is None

    def test_security_model_constant_value(self):
        assert SECURITY_SUBAGENT_MODEL == "opus"

    def test_alignment_fallback_brief_is_not_empty(self):
        assert ALIGNMENT_FALLBACK_BRIEF.strip() != ""


# ---------------------------------------------------------------------------
# Adversary Agents
# ---------------------------------------------------------------------------

class TestAdversaryAgents:
    def test_style_model_is_haiku(self):
        assert ADVERSARY_STYLE_MODEL == "haiku"

    def test_security_model_is_opus(self):
        assert ADVERSARY_SECURITY_MODEL == "opus"

    def test_style_agent_name_contains_style(self):
        assert "style" in ADVERSARY_STYLE_AGENT

    def test_security_agent_name_contains_security(self):
        assert "security" in ADVERSARY_SECURITY_AGENT

    def test_adversary_dimensions_are_disjoint(self):
        assert ADVERSARY_STYLE_DIMENSIONS.isdisjoint(ADVERSARY_SECURITY_DIMENSIONS)

    def test_adversary_dimensions_cover_all_grading_dimensions(self):
        all_covered = ADVERSARY_STYLE_DIMENSIONS | ADVERSARY_SECURITY_DIMENSIONS
        for dim in GRADING_DIMENSIONS:
            assert dim in all_covered, f"Dimension '{dim}' not covered by any adversary"

    def test_correctness_covered_by_security_adversary(self):
        """Correctness is a sub-dimension of the security adversary, not in GRADING_DIMENSIONS."""
        assert "Correctness" in ADVERSARY_SECURITY_DIMENSIONS

    def test_get_adversary_style_dimension(self):
        for dim in ADVERSARY_STYLE_DIMENSIONS:
            result = get_adversary_for_dimension(dim)
            assert result is not None
            agent, model = result
            assert agent == ADVERSARY_STYLE_AGENT
            assert model == ADVERSARY_STYLE_MODEL

    def test_get_adversary_security_dimension(self):
        for dim in ADVERSARY_SECURITY_DIMENSIONS:
            result = get_adversary_for_dimension(dim)
            assert result is not None
            agent, model = result
            assert agent == ADVERSARY_SECURITY_AGENT
            assert model == ADVERSARY_SECURITY_MODEL

    def test_get_adversary_unknown_dimension_returns_none(self):
        assert get_adversary_for_dimension("Nonsense") is None

    def test_get_adversary_empty_string_returns_none(self):
        assert get_adversary_for_dimension("") is None

    def test_style_adversary_model_is_cheaper_than_security_adversary_model(self):
        """Haiku is cheaper/faster than Opus — used for style; Opus for high-stakes security."""
        assert ADVERSARY_STYLE_MODEL == "haiku"
        assert ADVERSARY_SECURITY_MODEL == "opus"
