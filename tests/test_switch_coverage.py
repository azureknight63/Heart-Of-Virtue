"""Coverage for src/switch.py — a small case/switch helper (currently unused
elsewhere in the codebase, but exercised here to close out the 29% -> 100%
coverage gap).
"""

import pytest

from src.switch import switch


def test_match_with_no_args_after_fallthrough_is_true():
    s = switch("ten")
    s.fall = True
    assert s.match() is True


def test_match_with_matching_value_sets_fall_and_returns_true():
    s = switch("ten")
    assert s.match("one", "ten") is True
    assert s.fall is True


def test_match_with_non_matching_value_returns_false():
    s = switch("ten")
    assert s.match("one", "two") is False
    assert s.fall is False


def test_match_with_no_args_and_no_fall_is_default_true():
    """`case()` with no arguments and no prior match is the default branch."""
    s = switch("anything")
    assert s.match() is True


def test_iter_yields_match_once_then_stops():
    s = switch("z")
    it = iter(s)
    case = next(it)
    assert case == s.match
    # PEP 479: raising StopIteration inside a generator body is converted
    # to a RuntimeError once the generator resumes past that point.
    with pytest.raises(RuntimeError):
        next(it)


def test_full_case_statement_usage():
    results = []
    for case in switch("ten"):
        if case("one"):
            results.append(1)
            break
        if case("two"):
            results.append(2)
            break
        if case("ten"):
            results.append(10)
            break
        if case():
            results.append("default")
    assert results == [10]
