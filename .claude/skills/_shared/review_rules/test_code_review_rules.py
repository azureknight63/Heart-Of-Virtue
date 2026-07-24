"""
pytest suite for the Code Review Skill rules module.

Module: code_review_rules.py (same directory)

Run:
  python -m pytest .claude/skills/_shared/review_rules/test_code_review_rules.py -v

Not part of the default `python -m pytest -q` run — .claude/ is excluded via
pytest.ini's norecursedirs, matching the source design's intent that these
constants are pinned on demand (when the reference values change), not
wired into CI alongside src/ai coverage.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import pytest
from code_review_rules import (
    REVIEW_DIMENSIONS,
    DIMENSION_KEYS,
    DIMENSION_DISPLAY_NAMES,
    VALID_GRADES,
    GRADE_SEVERITY_FLOOR,
    SEVERITY_TIERS,
    DIFF_STANDARD_THRESHOLD,
    DIFF_FOCUSED_THRESHOLD,
    DIFF_REDIRECT_THRESHOLD,
    validate_grades,
    all_a_grade,
    grade_from_severity,
    review_depth_for_diff_size,
)


# ---------------------------------------------------------------------------
# Constants — value and format assertions
# ---------------------------------------------------------------------------

class TestDimensions:
    def test_dimension_count(self):
        assert len(REVIEW_DIMENSIONS) == 6

    def test_dimension_keys_match_expected(self):
        expected_keys = {"DRY", "CleanCode", "Optimization", "Maintainability", "Security", "AIFriendliness"}
        assert set(DIMENSION_KEYS) == expected_keys

    def test_dimension_display_names_match_expected(self):
        expected = {"DRY", "Clean Code", "Optimization", "Maintainability", "Security", "AI-Friendliness"}
        assert set(DIMENSION_DISPLAY_NAMES) == expected

    def test_dimension_keys_derivable_from_review_dimensions(self):
        assert DIMENSION_KEYS == [key for _, key in REVIEW_DIMENSIONS]

    def test_dimension_display_names_derivable_from_review_dimensions(self):
        assert DIMENSION_DISPLAY_NAMES == [name for name, _ in REVIEW_DIMENSIONS]

    def test_dimension_order(self):
        # Canonical order: DRY first, AIFriendliness last
        assert DIMENSION_KEYS[0] == "DRY"
        assert DIMENSION_KEYS[-1] == "AIFriendliness"


class TestGrades:
    def test_valid_grades_set(self):
        assert VALID_GRADES == {"A", "B", "C", "D", "F"}

    def test_valid_grades_includes_f(self):
        assert "F" in VALID_GRADES

    def test_grade_severity_floor_has_all_grades(self):
        for grade in VALID_GRADES:
            assert grade in GRADE_SEVERITY_FLOOR

    def test_grade_severity_floor_values_are_valid_tiers(self):
        for grade, floor in GRADE_SEVERITY_FLOOR.items():
            assert floor in SEVERITY_TIERS, f"Grade {grade!r} has invalid severity floor {floor!r}"


class TestSeverityTiers:
    def test_severity_count(self):
        assert len(SEVERITY_TIERS) == 4

    def test_severity_order(self):
        assert SEVERITY_TIERS == ["Critical", "Major", "Minor", "Nit"]

    def test_critical_is_highest(self):
        assert SEVERITY_TIERS[0] == "Critical"

    def test_nit_is_lowest(self):
        assert SEVERITY_TIERS[-1] == "Nit"


class TestDiffSizeThresholds:
    def test_standard_threshold_value(self):
        assert DIFF_STANDARD_THRESHOLD == 50

    def test_focused_threshold_value(self):
        assert DIFF_FOCUSED_THRESHOLD == 300

    def test_redirect_threshold_value(self):
        assert DIFF_REDIRECT_THRESHOLD == 1_000

    def test_thresholds_are_ordered(self):
        assert DIFF_STANDARD_THRESHOLD < DIFF_FOCUSED_THRESHOLD < DIFF_REDIRECT_THRESHOLD


# ---------------------------------------------------------------------------
# validate_grades
# ---------------------------------------------------------------------------

class TestValidateGrades:
    def test_valid_all_a(self):
        grades = {k: "A" for k in DIMENSION_KEYS}
        assert validate_grades(grades) == []

    def test_valid_mixed_grades(self):
        grades = {k: "B" for k in DIMENSION_KEYS}
        grades["Security"] = "F"
        assert validate_grades(grades) == []

    def test_missing_one_dimension(self):
        grades = {k: "A" for k in DIMENSION_KEYS if k != "Security"}
        errors = validate_grades(grades)
        assert len(errors) == 1
        assert "Security" in errors[0]

    def test_missing_all_dimensions(self):
        errors = validate_grades({})
        assert len(errors) == len(DIMENSION_KEYS)

    def test_invalid_grade_value(self):
        grades = {k: "A" for k in DIMENSION_KEYS}
        grades["DRY"] = "Z"
        errors = validate_grades(grades)
        assert len(errors) == 1
        assert "DRY" in errors[0]
        assert "Z" in errors[0]

    def test_unknown_dimension_key(self):
        grades = {k: "A" for k in DIMENSION_KEYS}
        grades["UnknownDim"] = "A"
        errors = validate_grades(grades)
        assert len(errors) == 1
        assert "UnknownDim" in errors[0]

    def test_grade_case_sensitive(self):
        grades = {k: "A" for k in DIMENSION_KEYS}
        grades["DRY"] = "a"  # lowercase a is invalid
        errors = validate_grades(grades)
        assert len(errors) == 1

    def test_f_grade_is_valid(self):
        grades = {k: "A" for k in DIMENSION_KEYS}
        grades["Security"] = "F"
        assert validate_grades(grades) == []


# ---------------------------------------------------------------------------
# all_a_grade
# ---------------------------------------------------------------------------

class TestAllAGrade:
    def test_all_a_returns_true(self):
        grades = {k: "A" for k in DIMENSION_KEYS}
        assert all_a_grade(grades) is True

    def test_one_b_returns_false(self):
        grades = {k: "A" for k in DIMENSION_KEYS}
        grades["CleanCode"] = "B"
        assert all_a_grade(grades) is False

    def test_empty_dict_returns_false(self):
        assert all_a_grade({}) is False

    def test_f_grade_returns_false(self):
        grades = {k: "A" for k in DIMENSION_KEYS}
        grades["Security"] = "F"
        assert all_a_grade(grades) is False


# ---------------------------------------------------------------------------
# grade_from_severity
# ---------------------------------------------------------------------------

class TestGradeFromSeverity:
    def test_critical_maps_to_f(self):
        assert grade_from_severity("Critical") == "F"

    def test_major_maps_to_c(self):
        assert grade_from_severity("Major") == "C"

    def test_minor_maps_to_b(self):
        assert grade_from_severity("Minor") == "B"

    def test_nit_maps_to_a(self):
        assert grade_from_severity("Nit") == "A"

    def test_unknown_severity_defaults_to_a(self):
        assert grade_from_severity("Unknown") == "A"

    def test_all_severity_tiers_covered(self):
        """Every defined severity tier must map to a valid grade."""
        for tier in SEVERITY_TIERS:
            result = grade_from_severity(tier)
            assert result in VALID_GRADES, f"Severity {tier!r} mapped to invalid grade {result!r}"

    def test_critical_produces_worst_grade(self):
        """Critical must map to F — the lowest grade."""
        assert grade_from_severity("Critical") == "F"

    def test_nit_produces_best_grade(self):
        """Nit must map to A — the best grade."""
        assert grade_from_severity("Nit") == "A"


# ---------------------------------------------------------------------------
# review_depth_for_diff_size
# ---------------------------------------------------------------------------

class TestReviewDepthForDiffSize:
    def test_zero_lines_is_full_depth(self):
        assert review_depth_for_diff_size(0) == "full-depth"

    def test_exactly_standard_threshold_is_full_depth(self):
        assert review_depth_for_diff_size(DIFF_STANDARD_THRESHOLD) == "full-depth"

    def test_one_above_standard_is_standard(self):
        assert review_depth_for_diff_size(DIFF_STANDARD_THRESHOLD + 1) == "standard"

    def test_exactly_focused_threshold_is_standard(self):
        assert review_depth_for_diff_size(DIFF_FOCUSED_THRESHOLD) == "standard"

    def test_one_above_focused_is_focused(self):
        assert review_depth_for_diff_size(DIFF_FOCUSED_THRESHOLD + 1) == "focused"

    def test_exactly_redirect_threshold_is_focused(self):
        assert review_depth_for_diff_size(DIFF_REDIRECT_THRESHOLD) == "focused"

    def test_one_above_redirect_is_redirect(self):
        assert review_depth_for_diff_size(DIFF_REDIRECT_THRESHOLD + 1) == "redirect-to-scrubber"

    def test_large_diff_is_redirect(self):
        assert review_depth_for_diff_size(50_000) == "redirect-to-scrubber"

    def test_all_labels_are_known(self):
        """Spot-check that each boundary returns a non-empty known label."""
        known_labels = {"full-depth", "standard", "focused", "redirect-to-scrubber"}
        for size in [0, 25, 50, 51, 150, 300, 301, 500, 1000, 1001, 5000]:
            result = review_depth_for_diff_size(size)
            assert result in known_labels, f"Unexpected label {result!r} for {size} lines"
