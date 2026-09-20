"""Generated prose must not say "A iron lockbox".

Issue #629 part B (paired with #616). ``Container.refresh_description`` built
``f"A {self.nickname}..."`` unconditionally at three sites, so six of the 47
shipped placements read "A equipment rack", "A archive coffer", "A open
crate", "A iron lockbox", "A inset shelf" and "A open stall" the moment their
description was regenerated.

The article rule now lives once, in ``functions.indefinite_article``, and the
only other article logic in the tree — ``_weapon_noun_phrase`` in the combat
adapter, a naive ``noun[:1] in "aeiou"`` with no exceptions — calls it. The API
layer importing an engine helper is the allowed direction; the engine importing
from ``src/api/`` is what is forbidden.

The map-derived guard below deliberately does NOT call the helper: a guard that
computes its expectation with the code under test asserts only that the code
agrees with itself. It applies the plain vowel-letter rule instead, which is
correct for the whole shipped population — and a derivation guard asserts that
no shipped nickname falls in the helper's exception set, so authoring an
"hourglass" surfaces as a failing control rather than a silent hole.
"""

import pytest

from src import functions
from src.api.combat_adapter import _weapon_noun_phrase
from src.objects import Container
from tests._map_scan import MIN_CONTAINER_PLACEMENTS, container_placements


def _letter_article(word):
    """The plain written rule -- ``"an"`` before a vowel LETTER -- and nothing else.

    Deliberately independent of ``functions.indefinite_article``: a guard that
    computes its expectation with the code under test asserts only that the
    code agrees with itself. It is spelled here once rather than at each of the
    two sites that need it, because two copies of the "independent" rule can
    drift apart and then only one of them is the control anybody reads.
    """
    return "an" if str(word)[:1].lower() in "aeiou" else "a"


def _shipped_container_nicknames():
    """Every authored nickname on a shipped ``Container``-family placement."""
    return [
        (placement.map_name, placement.coord, placement.props["nickname"])
        for placement, _cls in container_placements()
        if placement.props.get("nickname")
    ]


def _generated_descriptions(nickname):
    """The three templates ``refresh_description`` can produce, as a dict.

    Every container here is freshly constructed and left carrying the
    constructor's default description, which is exactly the state in which
    regeneration is allowed to happen. Nothing is reset by hand, so this helper
    stays readable against both the fixed and the unfixed engine.
    """
    from src.items import Restorative

    closed = Container(nickname=nickname)
    closed.refresh_description()

    stocked = Container(nickname=nickname, start_open=True,
                        inventory=[Restorative()])
    stocked.refresh_description()

    empty = Container(nickname=nickname, start_open=True)
    empty.refresh_description()

    return {
        "closed": closed.description,
        "stocked": stocked.description,
        "empty": empty.description,
    }


# ---------------------------------------------------------------------------
# The helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "word,expected",
    [
        ("crate", "a"), ("lockbox", "a"), ("stone plate", "a"),
        ("archive coffer", "an"), ("equipment rack", "an"),
        ("iron lockbox", "an"), ("inset shelf", "an"),
        ("open crate", "an"), ("open stall", "an"),
        ("Iron Lockbox", "an"),
        ("handcart", "a"),
    ],
)
def test_plain_words_follow_the_vowel_letter_rule(word, expected):
    assert functions.indefinite_article(word) == expected


@pytest.mark.parametrize(
    "word,expected",
    [
        # Consonant sound behind a vowel letter.
        ("unicorn", "a"), ("university", "a"), ("useful pouch", "a"),
        ("one crate", "a"), ("euro", "a"), ("ewe", "a"),
        # Vowel sound behind a consonant letter.
        ("hour", "an"), ("hourglass", "an"), ("honest merchant", "an"),
        ("honor guard", "an"), ("heir", "an"),
    ],
)
def test_the_exception_table_overrides_the_letter_rule(word, expected):
    assert functions.indefinite_article(word) == expected


@pytest.mark.parametrize(
    "word,expected",
    [
        # "uni" as a bare prefix would claim the whole un- negation family.
        ("uninhabited niche", "an"), ("unimportant ledger", "an"),
        ("uninscribed slab", "an"), ("unopened crate", "an"),
        # ...while these really are /juː/ and must stay "a".
        ("unicorn skull", "a"), ("uniform rack", "a"), ("unit crate", "a"),
        ("union banner", "a"),
        # "one" as a bare prefix would claim "onerous".
        ("onerous ledger", "an"),
    ],
)
def test_the_exception_tables_do_not_overreach(word, expected):
    """Every entry is a prefix of some word — it must not be a prefix of one
    that takes the OTHER article. These are the collisions that shape them."""
    assert functions.indefinite_article(word) == expected


@pytest.mark.parametrize(
    "word,expected",
    [("one-eyed skull", "a"), ("hour-glass", "an")],
)
def test_a_hyphenated_first_word_is_decided_by_its_first_element(word, expected):
    """Separate from the collision cases above: this is about WHERE the rule
    looks, not about a table entry claiming too much."""
    assert functions.indefinite_article(word) == expected


def test_the_aggregate_lists_exactly_the_words_the_letter_rule_gets_wrong():
    """``ARTICLE_EXCEPTION_STEMS`` is what the map control below consults.

    It is derived from the tables rather than re-listed, so a new table cannot
    be missed — but a stem that is NOT actually an exception would make that
    control flag innocent nicknames, and a table wired into the helper without
    going through ``_ARTICLE_PREFIX_TABLES`` would leave the control fail-open.
    Both show up here: every listed stem must disagree with the plain letter
    rule, which is the only reason for a stem to be listed at all.
    """
    stems = functions.ARTICLE_EXCEPTION_STEMS
    assert stems, "the aggregate is empty — the map control below is vacuous"
    not_exceptions = [
        stem for stem in stems
        if functions.indefinite_article(stem) == _letter_article(stem)
    ]
    assert not not_exceptions, (
        f"these stems agree with the plain letter rule and do not belong in "
        f"the exception aggregate: {not_exceptions}"
    )


@pytest.mark.parametrize("word", ["", None, "   "])
def test_an_absent_word_falls_back_to_a(word):
    """Never raise in the middle of building a description."""
    assert functions.indefinite_article(word) == "a"


# ---------------------------------------------------------------------------
# Derivation guards
# ---------------------------------------------------------------------------


def test_the_shipped_nickname_population_is_not_empty():
    nicknames = _shipped_container_nicknames()
    assert len(nicknames) >= MIN_CONTAINER_PLACEMENTS, (
        "map scan found almost no authored container nicknames — the scan "
        f"broke and every assertion below is vacuous. Found: {nicknames}"
    )


def test_some_shipped_nickname_actually_starts_with_a_vowel():
    """Positive control: no vowel-initial nickname means no bug to catch."""
    vowel_initial = [
        n for _m, _c, n in _shipped_container_nicknames()
        if _letter_article(n) == "an"
    ]
    assert vowel_initial, (
        "no shipped container nickname starts with a vowel — the guard below "
        "would pass against the unfixed code"
    )


def test_no_shipped_nickname_needs_the_exception_table():
    """The map guard uses the plain letter rule; this says that is safe.

    If this fails, a nickname like "hourglass" has been authored and the guard
    below must start consulting the helper rather than the letter.
    """
    tricky = [
        (m, c, n) for m, c, n in _shipped_container_nicknames()
        if n.lower().startswith(functions.ARTICLE_EXCEPTION_STEMS)
    ]
    assert not tricky, (
        f"these shipped nicknames need the article exception table: {tricky}"
    )


# ---------------------------------------------------------------------------
# The regression itself
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "map_name,coord,nickname",
    [
        pytest.param(*p, id=f"{p[0]}:{p[1]}:{p[2]}")
        for p in _shipped_container_nicknames()
    ],
)
def test_no_generated_description_uses_the_wrong_article(
    map_name, coord, nickname
):
    expected = _letter_article(nickname).capitalize()
    wrong = "An" if expected == "A" else "A"
    for which, text in _generated_descriptions(nickname).items():
        assert f"{wrong} {nickname}" not in text, (
            f"{map_name} {coord} {which} description reads "
            f"{wrong!r} before {nickname!r}: {text[:80]!r}"
        )
        assert f"{expected} {nickname}" in text, (
            f"{map_name} {coord} {which} description does not name the "
            f"container at all: {text[:80]!r}"
        )


# ---------------------------------------------------------------------------
# The other article site in the tree
# ---------------------------------------------------------------------------


def test_weapon_noun_phrase_keeps_its_ordinary_behaviour():
    assert _weapon_noun_phrase("Crossbow") == "a crossbow"
    assert _weapon_noun_phrase("Axe") == "an axe"
    assert _weapon_noun_phrase("Crossbow", with_article=False) == "crossbow"
    # The two subtypes that take no article at all.
    assert _weapon_noun_phrase("Unarmed") == "bare hands"
    assert _weapon_noun_phrase("Stars") == "throwing stars"


def test_weapon_noun_phrase_shares_the_engine_article_rule():
    """Its own ``noun[:1] in "aeiou"`` had no exceptions; the helper does.

    Asserted against literals, not against ``indefinite_article``'s own
    output: comparing the adapter to the helper would pass even if both were
    wrong, which is the only way this assertion could fail to earn its place.
    """
    assert _weapon_noun_phrase("Unicorn Horn") == "a unicorn horn"
    assert _weapon_noun_phrase("Hourblade") == "an hourblade"
