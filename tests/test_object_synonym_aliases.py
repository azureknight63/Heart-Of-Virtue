"""Issue #626: synonym verbs are class-level aliases, not one-line delegators.

#615 collapses an object's button row by grouping keywords on the handler
``resolve_interaction`` returns. A synonym written as its own method::

    def hit(self):
        self.strike()

is a distinct function, so the grouping could not see it and Market Gong kept
rendering STRIKE / HIT / BANG / USE. Maintainer decision: write synonyms as
class-level aliases (``hit = bang = use = strike``) so a synonym IS its target
and the existing grouping folds it.

Three guards:

* an AST scan of every class in ``src/objects.py`` for a method whose whole body
  forwards its own arguments to another ``self`` method -- none may remain
  outside ``_KEEP``;
* the population the scan found before the change is pinned as identities, so
  the scan passing cannot mean "the detector went blind";
* an alias bound in a base class keeps pointing at the BASE function, so a
  subclass overriding the target must re-alias. Checked across every loaded
  ``Object`` subclass, tests' included.
"""

import ast
import inspect
from pathlib import Path

import pytest

import src.objects as objects
from src.api.serializers.object_serializer import ObjectSerializer
from src.objects import MarketGong, Object, resolve_interaction

_OBJECTS_PY = Path(objects.__file__)

#: ``(class, method)`` delegators that must stay methods, each with its reason.
#: Empty: every forwarder in the module was a pure synonym.
_KEEP = {}

#: Every pure forwarder ``src/objects.py`` carried before #626:
#: ``class -> {synonym: target}``.
_CONVERTED = {
    "WallSwitch": {"push": "press", "touch": "press"},
    "WallInscription": {"examine": "read"},
    "HealingSpring": {"wash": "clean"},
    "Passageway": {"go": "enter", "leave": "enter", "exit": "enter"},
    "MarketBell": {"use": "ring"},
    "Fountain": {"use": "drink"},
    "StreetLantern": {"extinguish": "douse"},
    "NoticeBoard": {"use": "read"},
    "PrayerCandleRack": {"use": "pray"},
    "MarketGong": {"hit": "strike", "bang": "strike", "use": "strike"},
    "GeminateGeode": {"insert": "place", "solve": "place", "use": "place"},
    "WaterBarrel": {"use": "drink"},
    "WashingBasin": {"clean": "wash", "use": "wash"},
    "DryingRack": {"loot": "take", "use": "take", "examine": "check"},
    "RiverCrossingMarker": {"examine": "read", "use": "read"},
    "CampBanner": {"read": "examine", "look": "examine", "use": "examine"},
    "TravelersLogbook": {"examine": "read", "use": "read"},
}


def _forwarders(source):
    """``[(class, method, target)]`` for each method whose body, docstring
    aside, is one ``self.<target>(...)`` call -- returned or not -- passing
    exactly its own parameters through, in order."""
    found = []
    for cls in ast.parse(source).body:
        if not isinstance(cls, ast.ClassDef):
            continue
        for fn in cls.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            body = [
                s for s in fn.body
                if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
            ]
            if len(body) != 1 or not isinstance(body[0], (ast.Return, ast.Expr)):
                continue
            call = body[0].value
            if not (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "self"
                and not call.keywords
            ):
                continue
            params = [a.arg for a in fn.args.args[1:]]
            passed = [a.id if isinstance(a, ast.Name) else None for a in call.args]
            if passed == params:
                found.append((cls.name, fn.name, call.func.attr))
    return found


def test_the_detector_sees_both_delegator_shapes():
    """Non-vacuity: the scan recognises the returned and the bare forms, and
    leaves alone a body that is not a pure pass-through."""
    source = (
        "class A:\n"
        "    def hit(self):\n"
        "        '''Doc.'''\n"
        "        self.strike()\n"
        "    def go(self, player):\n"
        "        return self.enter(player)\n"
        "    def other(self, player):\n"
        "        return self.enter(player, quietly=True)\n"
        "    def swapped(self, player):\n"
        "        return self.enter(self.player)\n"
    )
    assert _forwarders(source) == [("A", "hit", "strike"), ("A", "go", "enter")]


def test_no_one_line_delegator_remains_in_objects_py():
    remaining = [
        f"{c}.{m} -> {t}"
        for c, m, t in _forwarders(_OBJECTS_PY.read_text(encoding="utf-8"))
        if (c, m) not in _KEEP
    ]
    assert not remaining, (
        "Synonym verbs must be class-level aliases (`hit = strike`) so #615's "
        "handler grouping collapses them into one button; a delegator that "
        f"really does something else belongs on _KEEP with its reason: {remaining}"
    )


@pytest.mark.parametrize(
    "cls_name, synonym, target",
    [(c, s, t) for c, pairs in _CONVERTED.items() for s, t in pairs.items()],
)
def test_each_former_delegator_is_its_target(cls_name, synonym, target):
    cls = getattr(objects, cls_name)
    assert cls.__dict__[synonym] is cls.__dict__[target]


def _all_subclasses(cls):
    for sub in cls.__subclasses__():
        yield sub
        yield from _all_subclasses(sub)


def _aliases_of(cls):
    """``{alias name: target name}`` for each class-level alias ``cls`` sees."""
    out = {}
    for name, value in inspect.getmembers(cls):
        raw = inspect.getattr_static(cls, name)
        fn = raw.__func__ if isinstance(raw, (staticmethod, classmethod)) else raw
        target = getattr(fn, "__name__", None)
        if (
            inspect.isfunction(fn)
            and target != name
            and not name.startswith("__")
            and target in dir(cls)
        ):
            out[name] = target
    return out


def test_an_alias_follows_its_target_in_every_subclass():
    """``hit = strike`` binds the function object. A subclass that overrides
    ``strike`` without re-aliasing ``hit`` leaves HIT calling the base
    behaviour -- two buttons, two different calls. Re-alias in the subclass."""
    stale = []
    for cls in [Object, *_all_subclasses(Object)]:
        if cls.__module__ == __name__:
            continue  # the deliberately-broken probe class below
        for alias, target in _aliases_of(cls).items():
            if inspect.getattr_static(cls, alias) is not inspect.getattr_static(cls, target):
                stale.append(f"{cls.__module__}.{cls.__qualname__}.{alias} -> {target}")
    assert not stale, stale


def test_the_subclass_guard_catches_an_unrealiased_override():
    class _Gong(MarketGong):
        def strike(self):
            return "overridden"

    # _Gong stays in MarketGong.__subclasses__() until collected; the
    # repo-wide guard above skips classes defined in this module for that reason.
    assert inspect.getattr_static(_Gong, "hit") is not inspect.getattr_static(_Gong, "strike")
    assert _aliases_of(_Gong)["hit"] == "strike"


def _gong():
    tile = type("T", (), {"items_here": [], "objects_here": [], "events_here": []})()
    return MarketGong(player=None, tile=tile)


def test_market_gong_renders_one_button():
    gong = _gong()
    assert gong.keywords == ["strike", "hit", "bang", "use"]  # authored shape
    assert ObjectSerializer.serialize(gong)["keywords"] == ["strike"]


def test_every_gong_verb_still_resolves_to_strike():
    gong = _gong()
    strike = resolve_interaction(gong, "strike")
    for verb in ("hit", "bang", "use"):
        assert resolve_interaction(gong, verb) == strike
