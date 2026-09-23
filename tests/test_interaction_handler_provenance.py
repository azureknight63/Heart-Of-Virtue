"""Issue #620: an interaction handler must come from the target's CLASS.

``resolve_interaction`` used to resolve the verb with a bare
``getattr(target, name)`` and accept whatever came back on ``callable()``
alone. The legacy map loader (``Universe._deserialize_saved_instance``)
``setattr``s every authored prop straight onto the instance, and a prop
written as the map editor's class marker --
``{"__class_type__": "module:Class"}`` -- deserializes to an engine CLASS,
which is callable. So a placement authored with a prop named after an
interaction verb nominated that class as the verb's handler, and
``GameService._dispatch_interaction`` then called it with the player as its
first argument.

Nothing shipped does this today, which is the only reason it was a hole rather
than a bug report -- the census in ``test_object_action_dispatch_contract.py``
finds every verb-named prop in the maps holding a dict, never a class. A guard
that only asserted "shipped content is fine" would therefore pass against the
unfixed code, so every test here builds the hostile placement through the
**real loader** and drives the **real dispatch**.

The rule is provenance, not shape: the class nominates handlers and the
instance never does. ``Passageway``'s name words (how the shipped city gates
and tent flaps are used) are DATA -- the class-declared
``instance_keyword_aliases`` maps each one to ``enter``, so an instance can
supply a word and never the method it reaches. ``HealingSpring.clean`` is a
``staticmethod`` and resolves through the ordinary class lookup.

This module pins the resolver. The loaders' refusal to let an instance
shadow class behaviour at all -- the root of the hops past it -- is pinned by
``tests/test_instance_shadowing_guard.py``.
"""

import inspect
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import src.objects as objects_module  # noqa: E402
import src.states as states_module  # noqa: E402
from src.api.services.game_service import GameService  # noqa: E402
from src.combatant import wire_handle  # noqa: E402
from src.narration import capture_narration  # noqa: E402
from src.objects import (  # noqa: E402
    Container,
    HealingSpring,
    Passageway,
    resolve_interaction,
)
from tests._gs_fixtures import live_world  # noqa: E402
from tests._map_scan import object_placements, resolve_class  # noqa: E402

#: The class a hostile placement nominates. Any allow-listed engine class would
#: do; this one takes exactly one positional argument, so an unfixed dispatch
#: constructs it cleanly instead of raising -- a raise would look like a
#: refusal and let the hole pass for the wrong reason.
_NOMINATED = ("states:Clean", states_module.Clean)

#: The verbs a hostile prop could be named after. Derived from the API's own
#: allow-list: those are the verbs a client may send at ANY target regardless
#: of what the placement advertises, so they are the reachable names.
_HOSTILE_VERBS = tuple(sorted(GameService._ALLOWED_INTERACTION_VERBS))


@pytest.fixture
def game_service():
    return GameService()


def _load_hostile(prop_name, *, class_spec=_NOMINATED[0]):
    """A shipped-shape placement whose ``prop_name`` prop is a class marker.

    Built through ``Universe._deserialize_saved_instance`` -- the real legacy
    loader, the one live path for all shipped placements. ``HealingSpring`` is
    the host because it declares no ``KEYWORD_METHOD_ALIASES``: an aliasing
    class would redirect the verb to a real method and hide the hole.

    Since #651 the loader applies only props the class declares, so it no
    longer stores the class at all -- asserted here, as the first of the two
    layers. The resolver is the second, and must hold on its own: the class is
    then planted on the instance directly, as any other writer of instance
    state (a restored save, a future loader) could, so every guard below keeps
    exercising the resolver rather than passing because nothing reached it.

    Returns ``(player, instance)`` with the instance standing on the player's
    tile and reachable by ``wire_handle``.
    """
    player, game_map = live_world()
    tile = game_map[(0, 0)]
    payload = {
        "__class__": "HealingSpring",
        "__module__": "objects",
        "props": {
            "name": "Suspicious Spring",
            prop_name: {"__class_type__": class_spec},
        },
    }
    with capture_narration():
        instance = player.universe._deserialize_saved_instance(payload, tile=tile)
    assert instance is not None, "the loader refused the payload outright"
    assert prop_name not in instance.__dict__, (
        f"the map loader applied the undeclared prop {prop_name!r} (#651)"
    )
    instance.__dict__[prop_name] = _NOMINATED[1]
    instance.tile = tile
    instance.player = player
    tile.objects_here = [instance]
    return player, instance


def test_the_loader_still_turns_a_class_marker_into_a_class():
    """Positive control for every test below.

    If the hostile instance ever stops carrying the class, the guards here
    become inert and each passes because there is nothing left to refuse. The
    marker itself must still resolve to that class through the loader -- the
    #651 filter drops the undeclared prop, not the marker's meaning.
    """
    _player, instance = _load_hostile("look")
    assert inspect.isclass(instance.__dict__["look"])
    player, _game_map = live_world()
    with capture_narration():
        resolved = player.universe._deserialize_saved_instance(
            {"__class_type__": _NOMINATED[0]}
        )
    assert resolved is _NOMINATED[1]


@pytest.mark.parametrize("verb", _HOSTILE_VERBS)
def test_a_map_authored_class_is_never_a_handler(verb):
    """The hole itself, over every verb a client may send."""
    _player, instance = _load_hostile(verb)

    assert resolve_interaction(instance, verb) is None


@pytest.mark.parametrize("verb", _HOSTILE_VERBS)
def test_the_dispatch_never_constructs_a_map_authored_class(
    game_service, verb, monkeypatch
):
    """The consequence: ``_call_interaction_handler`` invoked the stored class
    with the player as its first argument.

    Asserting on the refusal alone would not catch a resolution that still
    returns the class but happens to fail on call, so this watches the
    constructor.
    """
    player, instance = _load_hostile(verb)
    constructed = []
    real_init = states_module.Clean.__init__

    def spy(self, *args, **kwargs):
        constructed.append(args)
        return real_init(self, *args, **kwargs)

    monkeypatch.setattr(states_module.Clean, "__init__", spy)

    with capture_narration():
        result = game_service.interact_with_target(
            player, wire_handle(instance), verb, session_data={}
        )

    assert constructed == [], result
    assert result["success"] is False, result
    assert "no way for Jean" in result["message"], result


def test_a_bound_method_of_some_other_object_is_not_a_handler():
    """``__self__`` alone is not the rule -- it must be ``__self__ is target``.

    A save or a loader that copied one instance's attributes onto another
    would otherwise let object A's method run with object B as ``self``.
    """
    player, game_map = live_world()
    tile = game_map[(0, 0)]
    stranger = HealingSpring(player=player, tile=tile)
    victim = HealingSpring(player=player, tile=tile)
    victim.__dict__["take"] = stranger.drink

    assert resolve_interaction(victim, "take") is None


def test_an_instance_bound_method_of_the_target_is_NOT_a_handler():
    """The carve-out this test used to pin is gone (#620 follow-up).

    It asserted that ``spring.__dict__["take"] = spring.drink`` made ``take``
    dispatch ``drink``, on the reasoning that only ``Passageway``'s name-word
    aliases reach that shape. A restored save reaches it too, and then an
    allow-listed verb can be pointed at any method of the object it is used
    on. Aliases are data now; nothing instance-stored nominates a handler.
    """
    player, game_map = live_world()
    tile = game_map[(0, 0)]
    spring = HealingSpring(player=player, tile=tile)
    spring.__dict__["take"] = spring.drink

    assert resolve_interaction(spring, "take") is None
    # The legitimate neighbour must not have been taken with it: `clean` is a
    # staticmethod the class declares and the placement advertises.
    assert callable(resolve_interaction(spring, "clean"))


def _staticmethod_keywords():
    """``(class, name)`` for every ``staticmethod`` a class in ``src.objects``
    both declares and ADVERTISES as an interaction keyword.

    Derived from the real classes rather than named: ``HealingSpring.clean`` is
    the only member today, and the reason the #620 guard cannot be
    ``__self__``-based, but a second one added later must be caught by this
    test rather than by a player.
    """
    found = []
    for cls in vars(objects_module).values():
        if not inspect.isclass(cls) or cls.__module__ != objects_module.__name__:
            continue
        statics = [
            name for name, raw in cls.__dict__.items()
            if isinstance(raw, staticmethod)
        ]
        if not statics:
            continue
        try:
            instance = cls(player=None, tile=None)
        except Exception:
            continue
        advertised = getattr(instance, "keywords", None) or []
        for name in statics:
            if name in advertised:
                found.append((cls, name, instance))
    return found


_STATIC_KEYWORDS = _staticmethod_keywords()


def test_the_static_keyword_population_is_real():
    """A guard over an empty population approves of everything."""
    assert _STATIC_KEYWORDS, (
        "no class in src.objects advertises a staticmethod as a keyword; "
        "the derivation below has stopped matching"
    )
    assert any(
        cls is HealingSpring and name == "clean"
        for cls, name, _instance in _STATIC_KEYWORDS
    ), _STATIC_KEYWORDS


@pytest.mark.parametrize(
    "cls,name,instance",
    _STATIC_KEYWORDS,
    ids=[f"{cls.__name__}.{name}" for cls, name, _ in _STATIC_KEYWORDS],
)
def test_an_advertised_static_method_still_resolves(cls, name, instance):
    """The blocking case: a ``staticmethod`` has no ``__self__``, so an
    instance-only rule would take the CLEAN button off four shipped springs."""
    handler = resolve_interaction(instance, name)

    assert handler is not None
    assert handler is cls.__dict__[name].__get__(None, cls)


def test_an_inherited_bound_method_still_resolves():
    """``Container.take_all`` is reached from every container subclass."""
    player, game_map = live_world()
    container = Container(
        name="Chest",
        description="A chest.",
        player=player,
        tile=game_map[(0, 0)],
    )

    assert resolve_interaction(container, "take_all") == container.take_all


def _shipped_passageway_instance_aliases():
    """``(map, coord, name, alias)`` for every instance-bound alias the shipped
    ``Passageway`` placements install.

    ``Passageway`` advertises each word of the placement's own name (over three
    letters, alphabetic) as a way to cross. Those words used to be bound onto
    the instance with ``setattr``; since #620's follow-up they are DATA, mapped
    to ``enter`` by the class-declared ``instance_keyword_aliases``. Reading
    them from that table rather than from ``instance.__dict__`` is the point:
    the scan follows where the aliases actually live, instead of quietly
    matching nothing once they moved. Derived from the shipped maps, never
    listed.
    """
    rows = []
    for placement in object_placements():
        cls = resolve_class(placement)
        if not issubclass(cls, Passageway):
            continue
        name = placement.props.get("name")
        instance = cls(player=None, tile=None, **({"name": name} if name else {}))
        for alias in sorted(instance.instance_keyword_aliases()):
            rows.append((
                placement.map_name, placement.coord,
                name or cls.__name__, alias, instance,
            ))
    return rows


_PASSAGEWAY_ALIASES = _shipped_passageway_instance_aliases()


def test_the_passageway_alias_population_is_real():
    """Aliases like ferry, landing, camp, boundary, tent, jambo and flap exist
    across the shipped maps. No count is asserted -- passageways are authored
    routinely, and a count a test does not derive goes stale -- but an empty
    scan is a broken scan, not a clean bill of health."""
    assert _PASSAGEWAY_ALIASES, (
        "no shipped Passageway installs an instance-bound name alias; the "
        "derivation has stopped matching the maps"
    )


@pytest.mark.parametrize(
    "map_name,coord,name,alias,instance",
    _PASSAGEWAY_ALIASES,
    ids=[f"{r[0]}:{r[2]}:{r[3]}" for r in _PASSAGEWAY_ALIASES],
)
def test_every_shipped_passageway_name_alias_still_resolves(
    map_name, coord, name, alias, instance
):
    """These are bound methods of the passageway itself, so the instance rule
    readmits them -- and they must still read as CROSSINGS, which is what the
    demo-end gate and (after #620) the step-through arm both key off."""
    handler = resolve_interaction(instance, alias)

    assert handler is not None, (map_name, coord, name, alias)
    assert instance.is_crossing_handler(handler), (map_name, coord, name, alias)


class TestAGraftedBoundMethodIsNotAHandler:
    """A bound method of the target, stored on the target, is still not a
    nomination (#620 follow-up, found by the code-scrubber security pass).

    The first #620 fix admitted any instance attribute whose ``__self__`` was
    the target, on the reasoning that only ``Passageway``'s own name-word
    aliases could be in that shape. They are not the only thing that can be:
    ``inst.__dict__[verb] = inst.some_other_method`` satisfies it exactly, and
    a restored save carries an instance ``__dict__`` verbatim
    (``.claude/rules/saves-persistence.md`` treats save contents as untrusted).
    ``SafeUnpickler``'s allow-list bounds which CLASSES may appear, not which
    of their bound methods a dict points at.

    So an allow-listed verb could be pointed at any method of the object it is
    used on -- the surface ``_ALLOWED_INTERACTION_VERBS`` exists to close
    (#334).
    """

    def test_a_verb_grafted_onto_another_method_is_refused(self):
        """The reproduction: `look` grafted onto the target's own `take_all`.

        A genuine BOUND method of this very target, so ``__self__ is target``
        holds -- the exact shape the first fix readmitted. It must still be
        refused, because the class did not nominate it.
        """
        from src.objects import Container, resolve_interaction

        crate = Container(name="Crate", description="A crate.")
        grafted = crate.take_all
        assert getattr(grafted, "__self__", None) is crate, (
            "fixture must be a real bound method of the target, or this test "
            "passes for the wrong reason"
        )
        crate.__dict__["look"] = grafted

        assert resolve_interaction(crate, "look") is None, (
            "an instance-stored callable is a nomination by the map loader or "
            "a restored save, not by the class -- never dispatch it"
        )

    def test_every_shipped_passageway_name_alias_still_crosses(self):
        """The reason the instance carve-out existed must keep working."""
        from src.objects import Passageway, resolve_interaction

        way = Passageway(player=None, tile=None, name="Ferry Landing")
        for word in ("ferry", "landing"):
            assert word in way.keywords, f"{word} should be advertised"
            assert way.is_crossing_handler(resolve_interaction(way, word)), (
                f"{word} must still resolve to a crossing handler"
            )

    def test_is_crossing_handler_ignores_a_grafted_lookalike(self):
        """`is_crossing_handler` must read the class too, or the two halves of
        the dispatch disagree and #552's demo-end symptom comes back."""
        from src.objects import Passageway

        way = Passageway(player=None, tile=None, name="Ferry Landing")
        way.__dict__["enter"] = way.is_demo_edge
        assert not way.is_crossing_handler(way.__dict__["enter"])


def _passageway_with_shadowed_alias_words():
    """A ``Passageway`` whose instance ``__dict__`` shadows the class's
    ``_name_alias_words`` staticmethod with the nominated engine class.

    Written straight into ``__dict__``: neither loader can put it there any
    more (``tests/test_instance_shadowing_guard.py`` pins both refusals), so
    this is the state a future writer would have to create -- and the
    per-site read off the class must still hold against it.
    """
    player, game_map = live_world()
    tile = game_map[(0, 0)]
    way = Passageway(player=player, tile=tile, name="Ferry Landing")
    way.__dict__["_name_alias_words"] = _NOMINATED[1]
    way.tile, way.player = tile, player
    tile.objects_here = [way]
    return player, way


def test_the_map_loader_refuses_to_shadow_the_alias_word_helper():
    """The map vector C1 was found through: an authored class-marker prop
    named ``_name_alias_words``. The loader now refuses it outright."""
    player, game_map = live_world()
    payload = {
        "__class__": "Passageway",
        "__module__": "objects",
        "props": {
            "name": "Ferry Landing",
            "_name_alias_words": {"__class_type__": _NOMINATED[0]},
        },
    }
    with capture_narration():
        way = player.universe._deserialize_saved_instance(
            payload, tile=game_map[(0, 0)]
        )
    assert way is not None, "the loader refused the whole payload"
    assert "_name_alias_words" not in way.__dict__


@pytest.mark.parametrize("verb", _HOSTILE_VERBS)
def test_the_alias_word_helper_is_never_read_off_the_instance(
    game_service, verb, monkeypatch
):
    """``instance_keyword_aliases`` is class-declared so that what an alias
    word MEANS cannot come from the instance -- but it derived the words by
    calling ``self._name_alias_words``, and a ``staticmethod`` is a non-data
    descriptor, so an instance entry of that name wins the lookup. Every verb
    no class declares then CALLED the instance-supplied object, with the
    instance-supplied name as its argument: #620's primitive, one hop inside
    the resolver that closed it."""
    player, way = _passageway_with_shadowed_alias_words()
    constructed = []
    real_init = states_module.Clean.__init__

    def spy(self, *args, **kwargs):
        constructed.append(args)
        return real_init(self, *args, **kwargs)

    monkeypatch.setattr(states_module.Clean, "__init__", spy)

    with capture_narration():
        game_service.interact_with_target(
            player, wire_handle(way), verb, session_data={}
        )

    assert constructed == [], (
        f"{verb!r} on a Passageway called an instance-stored "
        f"_name_alias_words: {constructed}"
    )


def test_the_alias_words_still_cross_when_the_helper_is_shadowed():
    """The class-declared helper keeps working for the words themselves."""
    _player, way = _passageway_with_shadowed_alias_words()
    for word in ("ferry", "landing"):
        assert way.is_crossing_handler(resolve_interaction(way, word)), word
