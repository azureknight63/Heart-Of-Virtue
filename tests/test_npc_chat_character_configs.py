"""Issue #685: every named conversational NPC on the beta route has an authored
chat character file, and every such file satisfies what the loader reads.

The live defect: ``JamboHealsU`` had no ``_chat_config_path``, so in his
Grondia tent the mixin gave him a generated personality whose prompt says
"You speak in first person", and the only setting he was shown was the shared
``world_facts.json`` -- whose place list opens on the east-bank camp and the
river. He gave river-crossing advice, in the first person, inside a cavern city.

Both populations here are DERIVED rather than listed:

* the NPCs come from the beta-route map files themselves (every class
  reference a ``grondia*``, ``grondelith*`` or ``eastern-descent*`` map can
  place, resolved through the loader's own ``map_placeholders.resolve_class``),
  filtered to ``ConversationalNPCMixin`` hosts. A host is *named* -- and so owes
  an authored config -- when it has a canon character profile in
  ``docs/lore/character-profiles/`` or opts into ``_chat_keep_name``. The
  generic nomads have neither, and a generated personality is their design.
* the config keys come from ``src/npc/_chat_llm.py``'s own source: every
  ``.get("<key>")`` it makes on a character config. A key the mixin starts
  reading fails ``test_the_schema_covers_every_key_the_mixin_reads`` until it
  is given a shape here, so the schema cannot silently fall behind the reader.
"""

import ast
import json
import re
from pathlib import Path

import pytest

from src import map_placeholders
from src.npc._chat_llm import _HUMAN_NPC_DIR, ConversationalNPCMixin
from tests._source_scan import MAP_DIR

_ROOT = Path(__file__).resolve().parent.parent
_PROFILES_DIR = _ROOT / "docs" / "lore" / "character-profiles"
_MIXIN_SOURCE = _ROOT / "src" / "npc" / "_chat_llm.py"

#: The beta route, by map-file prefix (issue #685's scope).
_BETA_ROUTE_PREFIXES = ("grondia", "grondelith", "eastern-descent")


# ---------------------------------------------------------------------------
# Population 1: named conversational NPCs placed on the beta route
# ---------------------------------------------------------------------------


def _class_refs(node):
    """Every class reference in a map payload, in the three shapes the loader
    accepts: legacy ``__class__``/``__module__``, the ``__class_type__`` marker
    (NPCSpawnerEvent's ``npc_cls``), and the authored-placeholder ``class``."""
    if isinstance(node, dict):
        if isinstance(node.get("__class__"), str) and isinstance(node.get("__module__"), str):
            yield f"{node['__module__']}:{node['__class__']}"
        if isinstance(node.get("__class_type__"), str):
            yield node["__class_type__"]
        if isinstance(node.get("class"), str):
            yield node["class"]
        for value in node.values():
            yield from _class_refs(value)
    elif isinstance(node, list):
        for value in node:
            yield from _class_refs(value)


def _beta_route_conversational_placements():
    """``{class: sorted map names}`` for every conversational host the beta
    route can place."""
    placements = {}
    for path in sorted(MAP_DIR.glob("*.json")):
        if not path.name.startswith(_BETA_ROUTE_PREFIXES):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for ref in _class_refs(payload):
            try:
                cls = map_placeholders.resolve_class(ref)
            except map_placeholders.PlaceholderError:
                continue  # objects/items the allow-list does not cover
            if isinstance(cls, type) and issubclass(cls, ConversationalNPCMixin):
                placements.setdefault(cls, set()).add(path.stem)
    return {cls: sorted(maps) for cls, maps in placements.items()}


def _has_canon_profile(name):
    return (_PROFILES_DIR / (name.lower().replace(" ", "_") + ".md")).is_file()


def _named_placements():
    """``[(class, instance, maps)]`` for hosts with a canon identity."""
    named = []
    for cls, maps in _beta_route_conversational_placements().items():
        npc = cls()
        if cls._chat_keep_name or _has_canon_profile(npc.name):
            named.append((cls, npc, maps))
    return sorted(named, key=lambda entry: entry[0].__name__)


_NAMED = _named_placements()


class TestBetaRouteNamedNpcsHaveCharacterConfigs:
    def test_the_population_is_non_empty_and_reaches_grondia(self):
        """Non-vacuity: a moved maps directory or a broken resolver must fail
        here, not parametrize the real check below to zero cases."""
        assert _NAMED, "no named conversational NPC found on the beta route"
        assert any(
            m.startswith("grondia") for _cls, _npc, maps in _NAMED for m in maps
        ), "the population never reaches a Grondia map"

    def test_the_generic_nomads_are_the_control(self):
        """The filter must actually filter: the camp's generic hosts are
        conversational, placed on the route, and deliberately config-less."""
        placed = _beta_route_conversational_placements()
        named = {cls for cls, _npc, _maps in _NAMED}
        generic = set(placed) - named
        assert generic, "every placed host counted as named; the filter is inert"
        for cls in generic:
            assert cls().__dict__.get("_chat_char_config") is None, cls.__name__

    @pytest.mark.parametrize(
        "cls,npc,maps", _NAMED, ids=[entry[0].__name__ for entry in _NAMED]
    )
    def test_every_named_npc_resolves_its_own_config(self, cls, npc, maps):
        config = npc._chat_char_config
        assert isinstance(config, dict), (
            f"{cls.__name__} (placed on {maps}) has no character config, so it "
            "chats on a generated personality and the global world facts (#685)"
        )
        assert config.get("character_name") == npc.name


class TestJambo:
    """The NPC the live defect was observed on, pinned by name as well."""

    @pytest.fixture(scope="class")
    def jambo(self):
        from src.npc._merchants import JamboHealsU

        return JamboHealsU()

    def test_jambo_is_placed_in_both_his_tents(self):
        from src.npc._merchants import JamboHealsU

        maps = _beta_route_conversational_placements().get(JamboHealsU, [])
        assert "grondia-jambos_shop" in maps
        assert "eastern-descent-jambos-tent" in maps

    def test_jambo_resolves_his_character_config(self, jambo):
        assert jambo._chat_char_config is not None
        assert jambo._chat_char_config["character_name"] == "Jambo"

    def test_his_prompt_does_not_tell_him_to_speak_in_first_person(self, jambo):
        """The generated-personality prompt said "You speak in first person";
        his authored voice is third person ("Jambo does not have a potion for
        stone", ch02.py)."""
        block = jambo._build_character_block()
        assert "first person" not in block.lower()
        assert "third person" in block.lower()

    def _verbatim_lines(self, jambo):
        """Lines the fallback path renders as-is, in whichever tent he is in."""
        config = jambo._chat_char_config
        lines = list(config["fallback_replies"]) + list(config["closing_lines_when_exhausted"])
        for starters in config["conversation_starters_by_chapter"].values():
            lines.extend(starters)
        assert lines
        return lines

    def test_his_verbatim_lines_name_neither_tent(self, jambo):
        """One class stands in two places. The prompt is told which (#717's
        WHERE YOU ARE line), but these lines are rendered verbatim in either
        tent, so they must not claim a location (#685 observed river talk in
        Grondia)."""
        placeish = re.compile(
            r"\b(?:river|crossing|ferry|camp|grondia|ecumerium|citadel|market)\b",
            re.IGNORECASE,
        )
        for line in self._verbatim_lines(jambo):
            assert not placeish.search(line), line

    def test_his_quoted_speech_is_third_person(self, jambo):
        """Speech is double-quoted in his file, as in his scripted ``talk``
        (single quotes would collide with every "Jambo's")."""
        first_person = re.compile(r"\b(?:I|I'm|I've|I'll|me|my|mine|myself)\b")
        speeches = [
            speech
            for line in self._verbatim_lines(jambo)
            for speech in re.findall(r'"([^"]*)"', line)
        ]
        assert speeches, "no quoted speech found; the check below is vacuous"
        for speech in speeches:
            assert not first_person.search(speech), speech


# ---------------------------------------------------------------------------
# Population 2: every key the mixin reads off a character config
# ---------------------------------------------------------------------------


def _config_keys_the_mixin_reads():
    """``{key: first line}`` for every ``<config>.get("<key>")`` in the mixin,
    where the receiver is the character config (``self._chat_char_config``
    or one of the two local names the mixin binds it to)."""
    source = _MIXIN_SOURCE.read_text(encoding="utf-8")
    keys = {}
    for node in ast.walk(ast.parse(source)):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            continue
        receiver = node.func.value
        is_config = any(
            (isinstance(sub, ast.Attribute) and sub.attr == "_chat_char_config")
            or (isinstance(sub, ast.Name) and sub.id in ("cfg", "config"))
            for sub in ast.walk(receiver)
        )
        if is_config:
            keys.setdefault(node.args[0].value, node.lineno)
    return keys


def _is_str_list(value):
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(v, str) and v.strip() for v in value)
    )


#: The shape each read key must have. Keyed exactly by the derived set.
_SHAPES = {
    "role": lambda v: isinstance(v, str) and bool(v.strip()),
    "system_prompt_snippet": lambda v: isinstance(v, str) and bool(v.strip()),
    "voice_summary": lambda v: isinstance(v, str) and bool(v.strip()),
    "loquacity_base": lambda v: isinstance(v, int) and not isinstance(v, bool) and v > 0,
    "knowledge_scope": _is_str_list,
    "personality_notes": _is_str_list,
    "prohibited_phrases": _is_str_list,
    "closing_lines_when_exhausted": _is_str_list,
    "fallback_replies": _is_str_list,
    "conversation_starters_by_chapter": lambda v: isinstance(v, dict)
    and bool(v)
    and all(isinstance(k, str) and k.isdigit() and _is_str_list(lines) for k, lines in v.items()),
}


def _persona(name):
    """``<name>.json`` from the chat character directory, parsed."""
    return json.loads((_HUMAN_NPC_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _persona_paths():
    """Every character file the loader could be pointed at (``world_facts.json``
    shares the directory and is not one)."""
    return [
        path
        for path in sorted(_HUMAN_NPC_DIR.glob("*.json"))
        if "character_name" in json.loads(path.read_text(encoding="utf-8"))
    ]


_PERSONAS = _persona_paths()


class TestCharacterConfigsSatisfyTheLoader:
    def test_the_scan_finds_the_reads(self):
        assert len(_config_keys_the_mixin_reads()) >= 8

    def test_the_schema_covers_every_key_the_mixin_reads(self):
        read = _config_keys_the_mixin_reads()
        assert set(read) == set(_SHAPES), {
            "read but unshaped": sorted(set(read) - set(_SHAPES)),
            "shaped but no longer read": sorted(set(_SHAPES) - set(read)),
        }

    def test_every_persona_name_is_an_allowed_proper_noun(self):
        """The invented-name scrubber keeps only ``allowed_proper_nouns`` (plus
        the speaker's own name), so a persona missing from the list is scrubbed
        out of every OTHER NPC's line -- Votha Krr's "find Jambo, the trader"
        would lose its subject."""
        facts = _persona("world_facts")
        allowed = set(facts["allowed_proper_nouns"])
        names = {
            _persona(path.stem)["character_name"]
            for path in _PERSONAS
        }
        assert names - allowed == set()

    def test_the_new_personas_are_present(self):
        stems = {path.stem for path in _PERSONAS}
        assert {"jambo", "votha_krr", "gorran"} <= stems, stems

    @pytest.mark.parametrize("path", _PERSONAS, ids=[p.stem for p in _PERSONAS])
    def test_the_loader_reads_it_and_every_read_key_has_its_shape(self, path):
        # The loader's own read: None on any failure, which it then caches.
        config = ConversationalNPCMixin._read_json_config(path, "chat config")
        assert isinstance(config, dict), path.name
        assert isinstance(config.get("character_name"), str) and config["character_name"]
        bad = {
            key: config.get(key)
            for key, shape in _SHAPES.items()
            if not shape(config.get(key))
        }
        assert bad == {}, f"{path.name}: {bad}"
        # _init_chat_attrs compiles these; an escaped literal always compiles,
        # so the real check is that none is blank (a blank pattern matches
        # everywhere and would strip every reply).
        for phrase in config["prohibited_phrases"]:
            assert re.compile(re.escape(phrase), re.IGNORECASE).pattern.strip()


# ---------------------------------------------------------------------------
# Scrub review of #685: the invented-noun filter must not eat the names the
# world facts themselves hand the model. `_allowed_noun_tokens` splits
# `allowed_proper_nouns` into single words, so a place added to `geography`
# ("the Grondelith Mineral Pools") needs every capitalised word allowed, or
# `_find_invented_nouns` rewrites the model's correct answer to "the Grondelith
# someone someone". The population is read from the facts file and from Jambo's
# own role line -- not restated here -- so a new place is covered on arrival.
# ---------------------------------------------------------------------------


def _names_the_model_is_given():
    facts = _persona("world_facts")
    names = []
    for place in facts.get("geography", []):
        names.append(place.split(" (")[0])  # drop the parenthetical gloss
    for npc in facts.get("known_npcs", []):
        names.append(npc.split(" (")[0])
    jambo = _persona("jambo")
    names.append(jambo["role"])
    return names


def test_the_given_names_population_is_nonempty():
    names = _names_the_model_is_given()
    assert len(names) >= 3, names
    assert any("Grondelith" in n for n in names), names


@pytest.mark.parametrize("given", _names_the_model_is_given())
def test_the_noun_filter_keeps_every_name_the_facts_give(given):
    from src.npc._merchants import JamboHealsU

    jambo = JamboHealsU()
    # Mid-sentence, so no word is excused as a sentence opener.
    sentence = f"He said that {given} was worth the trip."
    invented = jambo._find_invented_nouns(sentence)
    assert invented == {}, (
        f"the noun filter would rewrite {sorted(invented)} in {given!r}; "
        "add the word(s) to allowed_proper_nouns in world_facts.json"
    )


# ---------------------------------------------------------------------------
# Issue #717: the chat prompt's WHERE YOU ARE line, and the character-file
# clauses the 2026-09-25 live run showed were missing. Populations derived from
# the map files and the character files, as above.
# ---------------------------------------------------------------------------


def _maps_hosting_conversation():
    return sorted(
        {m for maps in _beta_route_conversational_placements().values() for m in maps}
    )


_CHAT_MAPS = _maps_hosting_conversation()


def test_the_chat_map_population_includes_both_tents():
    assert "grondia-jambos_shop" in _CHAT_MAPS
    assert "eastern-descent-jambos-tent" in _CHAT_MAPS


@pytest.mark.parametrize("map_name", _CHAT_MAPS)
def test_every_map_with_a_conversation_names_its_place(map_name):
    """``_build_location_block`` reads ``metadata.place``; a map without one
    gives its NPCs no WHERE YOU ARE line, and Jambo guessed his tent (#717)."""
    from src.npc._merchants import JamboHealsU

    raw = json.loads((MAP_DIR / f"{map_name}.json").read_text(encoding="utf-8"))
    place = (raw.get("metadata") or {}).get("place")
    assert isinstance(place, str) and place.strip(), map_name
    # The place is handed to the model, which will say it back: every name in
    # it must survive the invented-noun filter, or the NPC's correct answer is
    # rewritten to "someone".
    invented = JamboHealsU()._find_invented_nouns(f"He said that {place} was near.")
    assert invented == {}, (map_name, sorted(invented))


_CHILD_AGE = re.compile(r"\byears old\b", re.IGNORECASE)


def _child_personas():
    return [
        p.stem for p in _PERSONAS
        if _CHILD_AGE.search(_persona(p.stem).get("system_prompt_snippet", ""))
    ]


def test_liss_is_in_the_child_population():
    assert "liss" in _child_personas()


@pytest.mark.parametrize("name", _child_personas())
def test_a_child_knows_jean_is_a_grown_man_and_never_calls_anyone_child(name):
    """A5: Liss, about nine, answered "They can be both, child." (#717)."""
    snippet = _persona(name)["system_prompt_snippet"]
    assert "Jean is a grown man" in snippet
    assert re.search(r"never call anyone ['\"]child['\"]", snippet, re.IGNORECASE)


_GUIDE_ROLE = re.compile(r"\b(?:ferry|guide)\b", re.IGNORECASE)


def _guide_personas():
    return [p.stem for p in _PERSONAS if _GUIDE_ROLE.search(_persona(p.stem).get("role", ""))]


def test_mara_is_in_the_guide_population():
    assert "mara" in _guide_personas()


@pytest.mark.parametrize("name", _guide_personas())
def test_a_guide_gives_no_routes_distances_or_travel_times(name):
    """O1: Mara gave "two days' drift downstream, about three leagues" --
    a route, a distance and a time, none of them canon (#717)."""
    snippet = _persona(name)["system_prompt_snippet"]
    assert re.search(r"no routes, distances or travel times", snippet, re.IGNORECASE)


def test_jambo_is_told_to_trust_the_where_line_not_to_guess():
    snippet = _persona("jambo")["system_prompt_snippet"]
    assert "not told which tent" not in snippet
    from ai.llm_client import NPC_LOCATION_BLOCK_NAME

    # The label the prompt actually prints, not a second spelling of it.
    assert NPC_LOCATION_BLOCK_NAME in snippet
