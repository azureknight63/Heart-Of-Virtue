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


def test_generate_produces_a_capitalized_alphabetic_word():
    name = generate(2, 2)

    assert name.isalpha()
    assert name[0].isupper()
    assert name[1:] == name[1:].lower()  # capitalize(), not title-case


def test_generate_draws_the_syllable_count_from_the_requested_range():
    """`generate` asks randint(minsyl, maxsyl) once and builds that many
    syllables. The old version of this test looped 20 times asserting only
    `len(name) > 0`, which says nothing about the bounds its name promises."""
    def syllable_selections(count):
        """How many table draws `generate` makes for `count` syllables."""
        draws = []
        with (
            patch("src.genericng.random.randint", return_value=count) as randint,
            patch(
                "src.genericng.selection",
                side_effect=lambda table: draws.append(table) or "x",
            ),
        ):
            generate(1, 4)
        randint.assert_called_once_with(1, 4)
        return draws

    one = syllable_selections(1)
    four = syllable_selections(4)

    # Each syllable is a vowel plus one or two consonant draws: 2-3 per
    # syllable, so the count scales with the requested syllable count.
    assert 2 <= len(one) <= 3
    assert 8 <= len(four) <= 12


def test_generate_with_zero_syllables_yields_an_empty_name():
    """The loop body never runs, so "".join([]).capitalize() is "" — pinned so
    a caller passing 0 gets a documented result rather than an IndexError."""
    assert generate(0, 0) == ""
