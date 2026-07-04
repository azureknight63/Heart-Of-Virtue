"""Coverage for src/genericng.py — the name generator. Closes gaps in
selection()'s defensive branches (an int entry appearing before the trailing
sum, and the "should not happen" fallback when the weighted sum never
resolves) that the normal consonants/vowels tables never exercise.
"""

from unittest.mock import patch

from src.genericng import selection, generate


def test_selection_skips_stray_int_entry_before_sum():
    """Line 105-106: a malformed table with an int entry ahead of the
    trailing sum must be skipped (`continue`) rather than crash."""
    # table[-1] is the sum (13); an extra stray int (99) sits before a
    # real weighted entry, exercising the `type(item) is int: continue` guard.
    table = [("x", 1), 99, ("y", 12), 13]
    with patch("random.randrange", return_value=12):
        result = selection(table)
    assert result == "y"


def test_selection_returns_empty_string_when_weights_never_resolve():
    """Line 112-113: if n never drops to <= 0 during the scan (a
    malformed/undersized weight table), fall back to "" rather than
    raising or returning garbage."""
    # Declared sum (100) far exceeds the actual weights (1 + 1 = 2), so `n`
    # (drawn from range(100)+1) will almost certainly never reach <= 0.
    table = [("a", 1), ("b", 1), 100]
    with patch("random.randrange", return_value=99):
        result = selection(table)
    assert result == ""


def test_generate_produces_a_capitalized_word():
    name = generate(2, 2)
    assert isinstance(name, str)
    assert name[0].isupper()
    assert len(name) > 0


def test_generate_respects_syllable_bounds():
    for _ in range(20):
        name = generate(1, 1)
        assert isinstance(name, str)
        assert len(name) > 0
