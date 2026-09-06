"""Regression coverage for Jambo's tent action list and the eastern-descent ->
nomad-camp -> Jambo's tent -> exit navigation route.

Issue: Jambo's Tent passageway exposed an "Enter", "Jambo" and "Tent" action; it
should expose only "Enter". The "Jambo"/"Tent" verbs come from the name-word
aliases ``Passageway.__init__`` synthesizes from the name "Jambo's Tent" and
which were persisted into the map's serialized ``keywords`` array. The frontend
(``actionKeywords``) hides anything in ``action_aliases`` but NOT these, so they
rendered as extra buttons that misled navigation.

This test loads the REAL map JSON through the engine loader (the same path the
game boots) and:
  * proves the serialized ``keywords`` for the Jambo's Tent passage no longer
    carry the name-word aliases ``jambo``/``tent``,
  * proves the *displayed* actions (keywords minus action_aliases) are exactly
    ``["enter"]``,
  * proves the complete enter/exit route lands on the expected map name and
    (x, y) after every passageway traversal (east-descent -> nomad-camp ->
    jambos-tent -> back to nomad-camp -> back to eastern-descent).

The route-coordinate assertions encode the diagnosis: the teleport coordinates
are correct; there is no backend coordinate/source regression. Only the
serialized keyword data needed fixing.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.api.serializers.object_serializer import ObjectSerializer
from src.universe import Universe
from src.player._movement import PlayerMovementMixin
from src.narration import capture_narration

from tests._cite import Read, verify

MAP_DIR = ROOT / "src" / "resources" / "maps"
MAP_FILES = [
    "eastern-descent.json",
    "eastern-descent-nomad-camp.json",
    "eastern-descent-jambos-tent.json",
]


class _MinPlayer(PlayerMovementMixin):
    """Minimal Player stand-in sufficient for Passageway._commit_teleport /
    PlayerMovementMixin.teleport (drop_merchandise_items, map, location, room)."""

    def __init__(self, universe):
        self.universe = universe
        self.map = None
        self.location_x = None
        self.location_y = None
        self.current_room = None

    def drop_merchandise_items(self):
        return None


def _build_universe():
    universe = Universe()
    player = _MinPlayer(universe)
    universe.player = player
    for m in MAP_FILES:
        universe._load_single_json_map(player, MAP_DIR / m)
    return universe, player


def _find_passage(map_dict, name):
    for coord, tile in map_dict.items():
        if not isinstance(coord, tuple):
            continue
        for obj in getattr(tile, "objects_here", []) or []:
            if (
                getattr(obj, "name", None) == name
                and getattr(obj, "__class__", None).__name__ == "Passageway"
            ):
                return coord, tile, obj
    return None


#: The frontend function this module mirrors. Cited by anchor rather than by
#: line: the previous version of this helper named ``InteractPanel.jsx`` in
#: prose with nothing checking that the name still resolved to anything, which
#: is the defect class ``tests/_cite.py`` exists to close.
_ACTION_KEYWORDS_JS = Read(
    "frontend/src/components/InteractPanel.jsx",
    "export function actionKeywords(",
)

#: The aliases ``actionKeywords`` collapses to a single button. Parsed out of
#: the JSX by :func:`_javascript_chat_keywords` and compared against this, so
#: the two halves cannot disagree silently.
_CHAT_KEYWORDS = frozenset({"talk", "chat"})

#: The drop rules :func:`_displayed_actions` implements, by the ids
#: :func:`_javascript_drop_rules` assigns, IN THE ORDER ``actionKeywords``
#: applies them. Asserted equal to what the JSX actually contains, so a rule
#: added there and not here fails a test rather than quietly rendering a button
#: set no Python check predicts.
#:
#: A sequence rather than a set, because the prose beside the mirror claims the
#: frontend's rules in the frontend's order and a set comparison checked
#: neither -- not how many rules there are, not what order they run in. That is
#: the same shape as the transposed-bullet claim
#: :meth:`TestTheMirrorTracksTheFrontend
#: .test_the_docstring_names_every_rule_the_function_applies` was written to
#: close; a claim nothing counts is a claim that goes wrong quietly.
_MIRRORED_RULES = (
    "container-loot",
    "action-aliases",
    "chat-collapse",
    "case-folded-dedupe",
)


def _displayed_actions(obj):
    """The buttons the frontend renders for the world object ``obj``.

    Split in two on purpose, because the helper it replaces conflated them and
    got the first half wrong. The frontend renders
    ``ObjectSerializer.serialize(obj)``, not the engine object: ``_serialize_base``
    rewrites ``keywords`` -- adding or removing ``open``/``unlock`` -- for
    anything carrying ``locked``, ``state`` or ``opened``, and
    ``serialize_container`` is what sets the ``is_container`` flag
    :func:`_render_buttons`' first rule reads. A ``Passageway`` declares none of
    those today, which is exactly why reading ``obj.keywords`` off the engine
    looked correct while modelling a different pipeline: give one a ``locked``
    attribute and the engine-side version stays green against a UI rendering a
    different button set. Pinned by
    :meth:`TestTheMirrorTracksTheFrontend.test_the_mirror_reads_the_wire_not_the_engine`.
    """
    return _render_buttons(ObjectSerializer.serialize(obj))


def _render_buttons(target):
    """``actionKeywords(target)``, in Python, over a *serialized* object.

    The drop rules below are the frontend's, in the frontend's order.
    :meth:`TestTheMirrorTracksTheFrontend
    .test_the_python_mirror_implements_every_javascript_rule` parses that
    sequence out of the JSX and compares it with :data:`_MIRRORED_RULES` as a
    sequence, so a rule added, removed or reordered there fails here instead of
    silently going unmirrored. Neither the count nor the order is written down
    in this prose: the tuple carries both, and the tuple is checked.
    """
    keywords = target.get("keywords") or []
    aliases = target.get("action_aliases") or []
    is_container = bool(target.get("is_container"))

    # `chatKw.find(k => k === 'talk') || chatKw[0]` -- prefer the canonical
    # spelling, fall back to whichever alias came first, nothing if neither.
    chat = [k for k in keywords if str(k).lower() in _CHAT_KEYWORDS]
    chat_kept = next(
        (k for k in chat if str(k).lower() == "talk"),
        chat[0] if chat else None,
    )

    seen = set()
    out = []
    for keyword in keywords:
        # Case-folded, matching the JS `String(keyword).toLowerCase()`: the
        # rendered list collapses 'Enter' and 'enter' into one button, so a
        # case-sensitive check here would claim two where the player sees one.
        action = str(keyword).lower()
        if is_container and action in ("loot", "take_all"):  # container-loot
            continue
        if keyword in aliases:  # action-aliases
            continue
        if action in _CHAT_KEYWORDS and keyword != chat_kept:  # chat-collapse
            continue
        if action in seen:  # case-folded-dedupe
            continue
        seen.add(action)
        out.append(keyword)
    return out


def _interact_panel_source():
    return Path(_ACTION_KEYWORDS_JS.path()).read_text(encoding="utf-8")


def _action_keywords_body():
    """The body of ``actionKeywords``, brace-matched from its declaration."""
    text = _interact_panel_source()
    start = text.index(_ACTION_KEYWORDS_JS.anchor)
    open_brace = text.index("{", start)
    depth = 0
    for index in range(open_brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace : index + 1]
    raise AssertionError("actionKeywords' body is not brace-balanced")


#: ``rule id -> the tokens that identify that clause``. Keyed on the
#: discriminating identifier rather than the whole expression, so reformatting
#: or an added optional-chain does not fail the test while a *new rule* does.
_RULE_SIGNATURES = {
    "container-loot": ("is_container",),
    "action-aliases": ("action_aliases",),
    "chat-collapse": ("CHAT_KEYWORDS", "chatKept"),
    "case-folded-dedupe": ("seen.has",),
}


#: An ``if (...) return false`` guard, in either spelling Prettier may leave
#: behind. ``DOTALL`` and the optional brace are load-bearing: without them a
#: condition wrapped across lines, or a braced ``{ return false }`` body,
#: matched NOTHING, and the parse quietly returned only the rules it could
#: still see -- a green mirror test beside a frontend applying one more.
_DROP_RULE_RE = re.compile(r"if\s*\((.*?)\)\s*\{?\s*return false", re.DOTALL)


def _javascript_drop_rules():
    """Every ``if (...) return false`` in ``actionKeywords``, as a rule id.

    Returns ``(ids, unrecognised, raw clauses, body)``, where ``ids`` is a LIST
    in source order -- ``findall`` yields the clauses in the order the function
    applies them, and a set threw that away along with the count. A clause
    matching no signature -- or more than one -- is reported rather than
    dropped: a parse that silently skipped the rule it could not classify would
    pass on exactly the change this test exists to catch.
    """
    body = _action_keywords_body()
    clauses = _DROP_RULE_RE.findall(body)
    rules = []
    unrecognised = []
    for clause in clauses:
        matched = [
            name
            for name, tokens in _RULE_SIGNATURES.items()
            if all(token in clause for token in tokens)
        ]
        if len(matched) == 1:
            rules.append(matched[0])
        else:
            unrecognised.append((clause.strip(), matched))
    return rules, unrecognised, clauses, body


def _action_keywords_docstring():
    """The JSDoc block immediately above ``actionKeywords``."""
    text = _interact_panel_source()
    end = text.index(_ACTION_KEYWORDS_JS.anchor)
    start = text.rfind("/**", 0, end)
    assert start != -1, "actionKeywords has no JSDoc block above it"
    return text[start:end]


def _javascript_chat_keywords():
    """The ``CHAT_KEYWORDS`` set literal, read out of the JSX."""
    match = re.search(
        r"CHAT_KEYWORDS\s*=\s*new Set\(\[([^\]]*)\]\)", _interact_panel_source()
    )
    assert match, "could not find the CHAT_KEYWORDS set in InteractPanel.jsx"
    tokens = {t.strip().strip("'\"") for t in match.group(1).split(",")}
    return tokens - {""}


class TestTheMirrorTracksTheFrontend:
    """``_displayed_actions`` is a second implementation of JS that ships.

    A Python copy of frontend logic is worth only its agreement with the
    original, and nothing was checking that agreement: the helper named the
    four rules and claimed to implement two of them, entirely in prose. These
    tests derive both halves. The model is
    ``frontend/src/hooks/useNpcChat.test.js``, which parses ``JEAN_TONES`` out
    of the Python source and set-compares -- this is the same test pointing the
    other way.
    """

    def test_the_cited_function_still_exists(self):
        broken = verify([_ACTION_KEYWORDS_JS])
        assert not broken, (
            "the frontend function this module mirrors has moved or been "
            "renamed:\n  " + "\n  ".join(broken) + "\n\nRepoint "
            "_ACTION_KEYWORDS_JS, or delete the mirror if the frontend no "
            "longer computes the button list here."
        )

    def test_the_python_mirror_implements_every_javascript_rule(self):
        rules, unrecognised, clauses, body = _javascript_drop_rules()
        # Guard-the-guard, on the INCREMENT rather than the base. A floor
        # ("more than one clause") is satisfied by the rules already parsed,
        # so a fifth rule the regex cannot see costs nothing and the set
        # comparison below still passes. `return false` is what a drop rule
        # IS, whatever shape it is written in: parse one per occurrence, or
        # fail loudly instead of predicting a button set the player never sees.
        returns = body.count("return false")
        assert len(clauses) == returns, (
            f"parsed {len(clauses)} drop rule(s) out of actionKeywords but its "
            f"body contains {returns} `return false` -- the parse is broken, "
            "not the frontend, and every comparison below is vacuous until it "
            f"is fixed. Body was:\n{body}"
        )
        assert not unrecognised, (
            "actionKeywords contains a drop rule this module cannot classify: "
            f"{unrecognised}\n\n_displayed_actions is a mirror of that "
            "function, so a rule only the frontend applies means the Python "
            "here predicts a button set the player never sees. Implement it "
            "and add its signature to _RULE_SIGNATURES."
        )
        assert rules == list(_MIRRORED_RULES), (
            f"the frontend applies {rules}; this module mirrors "
            f"{list(_MIRRORED_RULES)}. Compared as a SEQUENCE, not a set: "
            "_render_buttons' docstring claims the frontend's rules in the "
            "frontend's order, and a set comparison checked neither how many "
            "there are nor what order they run in."
        )

    def test_the_docstring_names_every_rule_the_function_applies(self):
        """The prose beside the filter, held to the filter.

        That docstring used to promise "one bullet per ``return false``, in the
        same order" and had two of them transposed -- a claim about ORDER is
        checkable only by counting, and nobody counts. Each bullet now leads
        with the identifier its clause turns on, which is a claim about NAMES,
        and names are matchable. A rule with no bullet fails here.
        """
        rules, _, _, _ = _javascript_drop_rules()
        assert rules, "no drop rules were classified -- the parse is broken"
        doc = _action_keywords_docstring()
        missing = {
            rule: [t for t in _RULE_SIGNATURES[rule] if t not in doc]
            for rule in sorted(rules)
            if any(t not in doc for t in _RULE_SIGNATURES[rule])
        }
        assert not missing, (
            "actionKeywords applies drop rules its own docstring does not "
            f"name: {missing}\n\nAdd a bullet led by the identifier the clause "
            "turns on. Prose that describes a subset of the rules is how the "
            "button list and its explanation drift apart."
        )

    def test_the_chat_alias_set_is_the_frontends(self):
        derived = _javascript_chat_keywords()
        assert derived == set(_CHAT_KEYWORDS), (
            "the frontend's CHAT_KEYWORDS and this mirror's copy have "
            "diverged: frontend has %s, mirror has %s"
            % (sorted(derived), sorted(_CHAT_KEYWORDS))
        )

    @pytest.mark.parametrize(
        "target, expected, rule",
        [
            (
                {"keywords": ["loot", "take_all", "search"], "is_container": True},
                ["search"],
                "container-loot",
            ),
            (
                {"keywords": ["enter", "go"], "action_aliases": ["go"]},
                ["enter"],
                "action-aliases",
            ),
            (
                {"keywords": ["chat", "Talk", "look"]},
                ["Talk", "look"],
                "chat-collapse",
            ),
            (
                {"keywords": ["Enter", "enter", "look"]},
                ["Enter", "look"],
                "case-folded-dedupe",
            ),
        ],
    )
    def test_each_mirrored_rule_actually_fires(self, target, expected, rule):
        """One case per id in :data:`_MIRRORED_RULES`, on a wire-shaped dict.

        The test above compares that set against the JSX; this one stops the
        set being a bare claim. Deleting a branch from :func:`_render_buttons`
        while leaving its id in place would otherwise satisfy both.
        """
        assert _render_buttons(target) == expected, rule

    def test_the_mirror_reads_the_wire_not_the_engine(self):
        """The half the old helper got wrong, made falsifiable.

        ``_serialize_base`` rewrites ``keywords`` for any object carrying
        ``locked``: it strips ``open``/``unlock`` and re-adds the one the state
        warrants. An object whose engine ``keywords`` disagree with its
        serialized ones therefore renders differently from what
        ``obj.keywords`` predicts, and only a mirror that goes through the
        serializer says so.
        """

        class _LockedThing:
            name = "Strongbox"
            keywords = ["examine", "open"]
            action_aliases = []
            locked = True

        obj = _LockedThing()
        assert obj.keywords == ["examine", "open"]
        assert ObjectSerializer.serialize(obj)["keywords"] == [
            "examine",
            "unlock",
        ]
        assert _displayed_actions(obj) == ["examine", "unlock"]


@pytest.fixture(scope="module")
def universe_player():
    return _build_universe()


def test_jambos_tent_serialized_keywords_have_no_name_word_aliases():
    """The serialized Jambo's Tent passage must not carry the 'jambo'/'tent'
    name-word aliases that rendered as extra frontend buttons."""
    raw = json.loads((MAP_DIR / "eastern-descent-nomad-camp.json").read_text(encoding="utf-8"))
    for coord, tile in raw.items():
        if not isinstance(tile, dict):
            continue
        for obj in tile.get("objects", []):
            if obj.get("props", {}).get("name") == "Jambo's Tent":
                keywords = obj["props"].get("keywords", [])
                assert "jambo" not in keywords, keywords
                assert "tent" not in keywords, keywords
                return
    pytest.fail("Jambo's Tent passage not found in serialized nomad-camp map")


def test_jambos_tent_displayed_actions_are_only_enter(universe_player):
    """After loading through the real engine, the only displayed action for
    Jambo's Tent is 'enter' (the frontend hides action_aliases + dups)."""
    universe, _ = universe_player
    nomad = next(a for a in universe.maps if a.get("name") == "eastern-descent-nomad-camp")
    res = _find_passage(nomad, "Jambo's Tent")
    assert res, "Jambo's Tent passage not loaded"
    pw = res[2]
    assert _displayed_actions(pw) == ["enter"], _displayed_actions(pw)


def test_full_enter_exit_route_coordinates(universe_player):
    """Reproduce the user's sequence and verify map name + (x, y) after every
    passageway traversal. Coordinates are correct; this encodes the diagnosis
    that there is no backend teleport regression."""
    universe, player = universe_player

    ed = next(a for a in universe.maps if a.get("name") == "eastern-descent")
    # Presence-only checks: StopIteration here means the map failed to load.
    next(a for a in universe.maps if a.get("name") == "eastern-descent-nomad-camp")
    next(a for a in universe.maps if a.get("name") == "eastern-descent-jambos-tent")

    # Start on the eastern-descent tile that holds the Camp Entrance passage.
    start = _find_passage(ed, "Camp Entrance")
    assert start, "Camp Entrance passage not found in eastern-descent"
    coord, tile, _ = start
    player.map = ed
    player.location_x, player.location_y = coord
    player.current_room = tile

    def step(target_name, expected_map, expected_coords):
        res = _find_passage(player.map, target_name)
        assert res, f"{target_name} not found in {player.map['name']}"
        pw = res[2]
        with capture_narration():
            pw._commit_teleport(player)
        got = (player.map["name"], (player.location_x, player.location_y))
        assert got == (expected_map, expected_coords), (target_name, got)

    # eastern-descent -> nomad-camp
    step("Camp Entrance", "eastern-descent-nomad-camp", (3, 0))
    # nomad-camp -> Jambo's tent
    step("Jambo's Tent", "eastern-descent-jambos-tent", (2, 2))
    # Jambo's tent -> back to nomad-camp (exit)
    step("Tent Flap", "eastern-descent-nomad-camp", (3, 0))
    # nomad-camp -> back to eastern-descent (exit the camp)
    step("Camp Boundary", "eastern-descent", (3, 6))
