"""Tests for the authored-placeholder map serialization format (issue #463).

Covers src/map_placeholders.py directly, representative NPC/Item/Object/Event
classes from each family, the Universe game-boot loader's integration
(legacy/placeholder/mixed loading + the security gate), and the Map
Editor's Convert Elements report (utils/map_generator.py).
"""

import sys
import types
from unittest.mock import MagicMock

import pytest

import src.map_placeholders as map_placeholders
from src.map_placeholders import (
    PlaceholderError,
    PlaceholderSecurityError,
    authored_override_names,
    authored_param_names,
    class_ref_string,
    instantiate_placeholder,
    is_authorable,
    is_class_type_marker,
    is_placeholder_payload,
    resolve_class,
    to_placeholder,
)

from conftest import restore_mapgen_modules, snapshot_and_clear_mapgen_modules


# ---------------------------------------------------------------------------
# Core module: class reference resolution + security gate
# ---------------------------------------------------------------------------

class TestResolveClass:
    def test_dotted_form_resolves(self):
        from src.npc._enemies import Slime

        assert resolve_class("npc.Slime") is Slime

    def test_colon_form_resolves(self):
        from src.npc._enemies import Slime

        assert resolve_class("npc:Slime") is Slime

    def test_rejects_src_prefixed_module(self):
        with pytest.raises(PlaceholderError, match="must be bare"):
            resolve_class("src.npc.Slime")

    def test_rejects_non_engine_class(self):
        with pytest.raises(PlaceholderSecurityError, match="allow-list"):
            resolve_class("os.system")

    def test_rejects_malformed_reference(self):
        with pytest.raises(PlaceholderError):
            resolve_class("not-a-valid-ref")

    def test_rejects_non_string(self):
        with pytest.raises(PlaceholderError):
            resolve_class(1234)

    def test_nonexistent_class_in_valid_module_raises_placeholder_error(self):
        """A well-formed but typo'd class reference (valid, allow-listed
        module; class name that doesn't exist there) must raise
        PlaceholderError like every other malformed-input case -- not an
        unguarded AttributeError. Every caller (Universe, map_generator's
        load_map) only catches PlaceholderError, so an uncaught AttributeError
        here would abort the whole map's load instead of just this element."""
        with pytest.raises(PlaceholderError):
            resolve_class("npc.ThisClassDoesNotExist")


class TestShapeDetection:
    def test_is_placeholder_payload_requires_class_key(self):
        assert is_placeholder_payload({"class": "npc.Slime"})
        assert is_placeholder_payload({"class": "npc.Slime", "params": {}})
        assert not is_placeholder_payload({"__class__": "Slime", "__module__": "npc"})
        assert not is_placeholder_payload({"__class_type__": "npc:Slime"})
        assert not is_placeholder_payload("not a dict")

    def test_is_class_type_marker(self):
        assert is_class_type_marker({"__class_type__": "npc:Slime"})
        assert not is_class_type_marker({"__class_type__": "npc:Slime", "extra": 1})
        assert not is_class_type_marker({"class": "npc.Slime"})


# ---------------------------------------------------------------------------
# Core module: to_placeholder / instantiate_placeholder against a controlled
# dummy class (isolates the generic mechanism from any real engine class's
# specific quirks).
# ---------------------------------------------------------------------------

class _DummyBase:
    MAP_AUTHORED_PARAMS = {"foo"}
    MAP_AUTHORED_OVERRIDES = {"hidden"}

    def __init__(self, foo=1):
        self.foo = foo
        self.hidden = False
        self.secret = "never serialized"


class _DummyChild(_DummyBase):
    """Adds no metadata of its own; must inherit the parent's via MRO merge."""


class _DummyNoMetadata:
    def __init__(self):
        self.name = "plain"


class _DummyZeroArg:
    """Mirrors the hardcoded-stat-enemy shape: no constructor kwargs at all,
    so its whole authored surface can only reach the instance via overrides.
    """

    MAP_AUTHORED_OVERRIDES = {"power"}

    def __init__(self):
        self.power = 10


class _DummyAliased:
    """A property whose getter has a side effect (recorded in
    `read_count`), mirroring Book.text's lazy-load-from-disk problem."""

    MAP_AUTHORED_PARAMS = {"value"}
    MAP_AUTHORED_ATTR_ALIASES = {"value": "_value"}

    def __init__(self, value=None):
        self._value = value
        self.read_count = 0

    @property
    def value(self):
        self.read_count += 1
        return self._value


class TestToPlaceholderGeneric:
    def test_returns_none_for_non_authorable_class(self):
        assert to_placeholder(_DummyNoMetadata()) is None

    def test_authored_param_and_override_routing(self):
        inst = _DummyBase(foo=5)
        inst.hidden = True
        payload = to_placeholder(inst)
        assert payload["class"].endswith("_DummyBase")
        assert payload["params"]["foo"] == 5
        assert payload["params"]["overrides"] == {"hidden": True}
        assert "secret" not in payload["params"]

    def test_untouched_zero_arg_class_prunes_to_empty_overrides(self):
        assert to_placeholder(_DummyZeroArg())["params"] == {}

    def test_zero_arg_class_delta_survives_pruning(self):
        inst = _DummyZeroArg()
        inst.power = 99
        payload = to_placeholder(inst)
        assert payload["params"]["overrides"] == {"power": 99}

    def test_attr_alias_reads_backing_attribute_not_the_property(self):
        """Confirms the general alias mechanism -- not just Book's specific
        use of it -- avoids invoking a property getter with side effects."""
        inst = _DummyAliased(value="hello")
        payload = to_placeholder(inst)
        assert payload["params"]["value"] == "hello"
        assert inst.read_count == 0  # the property getter was never invoked

    def test_metadata_inherited_via_mro(self):
        assert authored_param_names(_DummyChild) == {"foo"}
        assert authored_override_names(_DummyChild) == {"hidden"}
        assert is_authorable(_DummyChild)

    def test_nested_fallback_used_for_unregistered_nested_instance(self):
        inst = _DummyBase()
        inst.foo = _DummyNoMetadata()  # non-primitive, non-authorable nested value
        fallback_calls = []

        def fallback(value):
            fallback_calls.append(value)
            return {"legacy": True}

        payload = to_placeholder(inst, nested_fallback=fallback)
        assert payload["params"]["foo"] == {"legacy": True}
        assert len(fallback_calls) == 1

    def test_nested_without_fallback_raises(self):
        inst = _DummyBase()
        inst.foo = _DummyNoMetadata()
        with pytest.raises(PlaceholderError):
            to_placeholder(inst)

    def test_class_value_serializes_as_class_type_marker(self):
        inst = _DummyBase()
        inst.foo = _DummyBase  # a bare class reference, not an instance
        payload = to_placeholder(inst)
        ref = payload["params"]["foo"]["__class_type__"]
        assert ref.endswith(":_DummyBase")


class TestInstantiatePlaceholderGeneric:
    def test_round_trip(self):
        payload = {"class": "npc.Slime", "params": {}}
        # Slime takes no constructor args; sanity check it constructs.
        from src.npc._enemies import Slime

        inst = instantiate_placeholder(payload)
        assert isinstance(inst, Slime)

    def test_overrides_filtered_to_allow_list(self):
        """An override key not on the class's declared allow-list is dropped,
        never applied -- this is a security boundary (map JSON is
        attacker-influenceable), not just a data-modeling nicety.
        """
        from src.npc._enemies import Slime

        payload = {
            "class": "npc.Slime",
            "params": {"overrides": {"maxhp": 12345, "not_a_real_field": "x"}},
        }
        inst = instantiate_placeholder(payload)
        assert inst.maxhp == 12345
        assert not hasattr(inst, "not_a_real_field")

    def test_missing_params_key_defaults_empty(self):
        """A bare {"class": ...} placeholder (no params at all) is valid --
        requiring empty "params": {} boilerplate for zero-config placements
        would be needless authoring overhead."""
        from src.npc._enemies import Slime

        inst = instantiate_placeholder({"class": "npc.Slime"})
        assert isinstance(inst, Slime)

    def test_malformed_params_type_raises(self):
        with pytest.raises(PlaceholderError):
            instantiate_placeholder({"class": "npc.Slime", "params": "not-a-dict"})

    def test_not_a_placeholder_payload_raises(self):
        with pytest.raises(PlaceholderError):
            instantiate_placeholder({"__class__": "Slime", "__module__": "npc"})

    def test_depth_limit_enforced(self):
        payload = {"class": "npc.Slime", "params": {}}
        with pytest.raises(PlaceholderError, match="depth"):
            instantiate_placeholder(payload, _depth=map_placeholders.MAX_DEPTH + 1)

    def test_security_rejection_propagates(self):
        with pytest.raises(PlaceholderSecurityError):
            instantiate_placeholder({"class": "os.system", "params": {}})


# ---------------------------------------------------------------------------
# Representative NPC classes
# ---------------------------------------------------------------------------

class TestNPCBucket:
    def test_untouched_hardcoded_enemy_prunes_to_empty_overrides(self):
        """An unmodified KingSlime's stat block matches what a fresh
        KingSlime() already produces -- overrides should prune to empty
        rather than dumping the whole block on every untouched placement."""
        from src.npc._enemies import KingSlime

        king = KingSlime()
        payload = to_placeholder(king)
        assert payload["params"] == {}

        king2 = instantiate_placeholder({"class": "npc.KingSlime", "params": {}})
        assert king2.maxhp == king.maxhp
        assert king2.is_boss is True

    def test_hardcoded_enemy_stat_delta_survives_pruning(self):
        """KingSlime's constructor takes no args -- a genuine authored stat
        tweak must route through overrides and survive the default-pruning
        pass (only the touched field, not the whole block)."""
        from src.npc._enemies import KingSlime

        king = KingSlime()
        king.maxhp = 9999  # a genuine, non-default authored tweak
        payload = to_placeholder(king)
        assert set(payload["params"].keys()) == {"overrides"}
        assert payload["params"]["overrides"] == {"maxhp": 9999}

        king2 = instantiate_placeholder(
            {"class": "npc.KingSlime", "params": {"overrides": {"maxhp": 9999}}}
        )
        assert king2.maxhp == 9999
        assert king2.is_boss is True  # class-hardcoded default preserved

    def test_merchant_shop_config_delta_survives_pruning(self):
        """MiloCurioDealer's own __init__ takes no args -- like the hardcoded
        enemy classes, its whole shop config can only reach the instance via
        the override bucket. An untouched instance prunes clean of every
        *deterministic* field; a genuine tweak survives. (MiloCurioDealer's
        starting inventory includes a procedurally-enchanted item, so
        "inventory" itself never prunes away for this one class -- a
        documented non-determinism, not a bug; see the issue #463 audit.)"""
        from src.npc._merchants import MiloCurioDealer

        milo = MiloCurioDealer()
        untouched_overrides = to_placeholder(milo)["params"].get("overrides", {})
        assert set(untouched_overrides.keys()) <= {"inventory"}

        milo.stock_count = 99
        milo.shop_name = "New Name"
        payload = to_placeholder(milo)
        assert payload["params"]["overrides"]["stock_count"] == 99
        assert payload["params"]["overrides"]["shop_name"] == "New Name"

        restored = instantiate_placeholder(
            {"class": "npc.MiloCurioDealer",
             "params": {"overrides": {"stock_count": 99, "shop_name": "New Name"}}}
        )
        assert restored.stock_count == 99
        assert restored.shop_name == "New Name"

    def test_nomad_boy_deterministic_override_params(self):
        from src.npc._eastern_descent import NomadBoy

        boy = NomadBoy(description="A specific test boy.", personality="curious")
        payload = to_placeholder(boy)
        assert payload["params"]["description"] == "A specific test boy."
        assert payload["params"]["personality"] == "curious"

        boy2 = instantiate_placeholder(
            {
                "class": "npc._eastern_descent.NomadBoy",
                "params": {"description": "round trip", "personality": "shy"},
            }
        )
        assert boy2.description == "round trip"
        assert boy2.personality == "shy"
        assert boy2._chat_personality == "shy"

    def test_debug_npcs_still_authorable_even_though_hidden_from_palette(self):
        """TheAdjutant/StatusDummy/Testexp are excluded from the Map Editor's
        placeable-NPC palette (see filter_classes in utils/map_generator.py)
        but the placeholder format itself must keep working for them, since
        combat-testing-arena.json already places StatusDummy this way."""
        from src.npc._enemies import StatusDummy

        pell = StatusDummy()
        payload = to_placeholder(pell)
        assert payload is not None
        restored = instantiate_placeholder(payload)
        assert restored.name == "Pell"


# ---------------------------------------------------------------------------
# Representative Item classes
# ---------------------------------------------------------------------------

class TestItemBucket:
    def test_enchantment_level_stored_and_round_trips(self):
        from src.items import Rock

        r = Rock(merchandise=True, enchantment_level=0)
        assert r.enchantment_level == 0  # previously never stored at all
        payload = to_placeholder(r)
        assert payload["params"]["enchantment_level"] == 0
        assert payload["params"]["merchandise"] is True

    def test_consumable_count_round_trips(self):
        from src.items import Restorative

        item = Restorative(count=5)
        payload = to_placeholder(item)
        assert payload["params"]["count"] == 5
        restored = instantiate_placeholder(payload)
        assert restored.count == 5

    def test_gold_amount_round_trips(self):
        from src.items import Gold

        g = Gold(amt=42)
        payload = to_placeholder(g)
        assert payload["params"]["amt"] == 42
        restored = instantiate_placeholder(payload)
        assert restored.amt == 42

    def test_key_lock_nickname_is_the_authored_destination(self):
        from src.items import Key

        k = Key(lock_nickname="archive coffer")
        payload = to_placeholder(k)
        assert payload["params"]["lock_nickname"] == "archive coffer"
        assert "lock" not in payload["params"]  # live object ref, never authored

    def test_unique_zero_param_item_is_a_bare_class_reference(self):
        """Untouched, this collapses to essentially {"class": ..., "params":
        {"merchandise": False}} -- default-pruning removes the rest since a
        fresh JeanWeddingBand() already matches it."""
        from src.items import JeanWeddingBand

        item = JeanWeddingBand()
        payload = to_placeholder(item)
        assert "overrides" not in payload["params"]
        restored = instantiate_placeholder(payload)
        assert restored.name == "Wedding Band"
        assert restored.isequipped is True  # hardcoded class default preserved

    def test_unique_item_name_override_survives_pruning(self):
        from src.items import JeanWeddingBand

        item = JeanWeddingBand()
        item.name = "Amelia's Ring"  # a genuine authored override
        payload = to_placeholder(item)
        assert payload["params"]["overrides"] == {"name": "Amelia's Ring"}

    def test_book_event_nested_placeholder(self):
        from src.events import Event
        from src.items import Book

        book = Book(text="hello")
        book.event = Event(name="TestEvent", repeat=True)
        payload = to_placeholder(book)
        assert payload["params"]["text"] == "hello"
        assert payload["params"]["event"]["class"] == "events.Event"

    def test_book_file_backed_text_does_not_read_disk(self, tmp_path):
        """Regression test: `Book.text` is a lazily-loading property that
        reads text_file_path from disk on first access. Serializing it via
        the property (instead of the private _text cache) would bake the
        entire file's contents into the placeholder redundantly alongside
        text_file_path -- this is exactly what made
        eastern-descent-jambos-tent.json balloon during the real-map size
        measurement (a 693-byte legacy entry became 4328 bytes)."""
        from src.items import Book

        book_file = tmp_path / "lore.txt"
        book_file.write_text("A" * 5000)  # much larger than a reasonable placeholder
        book = Book(text_file_path=str(book_file))
        assert book._text is None  # never read yet

        payload = to_placeholder(book)
        assert payload["params"]["text"] is None
        assert payload["params"]["text_file_path"] == str(book_file)
        assert book._text is None  # still never read -- to_placeholder didn't trigger the load
        assert len(str(payload)) < 1000


# ---------------------------------------------------------------------------
# Representative Object classes
# ---------------------------------------------------------------------------

class TestObjectBucket:
    def test_container_nested_inventory_round_trips(self):
        from src.items import Restorative
        from src.objects import Container

        c = Container(name="Chest", nickname="archive coffer", locked=True,
                      inventory=[Restorative(count=2)])
        payload = to_placeholder(c)
        nested = payload["params"]["inventory"][0]
        assert nested["class"] == "items.Restorative"
        assert nested["params"]["count"] == 2

        restored = instantiate_placeholder(payload)
        assert restored.locked is True
        assert restored.nickname == "archive coffer"
        assert len(restored.inventory) == 1
        assert restored.inventory[0].count == 2

    def test_crate_requires_player_and_tile_injected_by_loader(self):
        from src.objects import Crate

        class DummyPlayer:
            pass

        class DummyTile:
            objects_here = []
            events_here = []

        payload = {
            "class": "objects.Crate",
            "params": {"stock_count": 5, "overrides": {"inventory": [{"class": "items.Gold"}]}},
        }
        crate = instantiate_placeholder(payload, player=DummyPlayer(), tile=DummyTile())
        assert isinstance(crate, Crate)
        assert crate.stock_count == 5
        assert len(crate.inventory) == 1

    def test_wallswitch_clears_fired_event_like_its_siblings(self):
        """Regression test for the bug surfaced by the issue #463 audit:
        WallSwitch previously never cleared event_on/event_off after firing,
        unlike every sibling one-shot-attached-event object in objects.py."""
        from src.objects import WallSwitch
        from src.events import Event

        switch = WallSwitch(player=None, tile=None)
        switch.event_on = Event(name="OnFire", repeat=False)
        switch.press()
        assert switch.position is True
        assert switch.event_on is None  # fired non-repeat event is cleared

    def test_wallswitch_keeps_repeating_event(self):
        from src.objects import WallSwitch
        from src.events import Event

        switch = WallSwitch(player=None, tile=None)
        switch.event_on = Event(name="OnFire", repeat=True)
        switch.press()
        assert switch.event_on is not None  # repeat events are never cleared

    def test_shrine_event_is_an_override(self):
        from src.objects import Shrine
        from src.events import Event

        shrine = Shrine()
        shrine.event = Event(name="TestEvent")
        payload = to_placeholder(shrine)
        assert payload["params"]["overrides"]["event"]["class"] == "events.Event"


# ---------------------------------------------------------------------------
# Representative Event classes
# ---------------------------------------------------------------------------

class TestEventBucket:
    def test_base_event_excludes_session_bookkeeping(self):
        from src.events import Event

        ev = Event(name="TestEvent", repeat=True)
        ev.has_run = True
        ev.completed = True
        ev.api_event_id = "abc123"
        payload = to_placeholder(ev)
        for leaked in ("has_run", "completed", "api_event_id", "thread",
                       "referenceobj", "needs_input"):
            assert leaked not in payload["params"]
        assert payload["params"]["repeat"] is True

    def test_npc_spawner_event_round_trips(self):
        from src.story.effects import NPCSpawnerEvent

        spawner = NPCSpawnerEvent(npc_cls="GronditeElder", count=3)
        payload = to_placeholder(spawner)
        assert payload["params"]["npc_cls"] == "GronditeElder"
        assert payload["params"]["count"] == 3

        restored = instantiate_placeholder(payload)
        assert restored.npc_cls == "GronditeElder"
        assert restored.count == 3

    def test_combat_event_config_is_a_nested_placeholder(self):
        from src.combat_event_config import CombatEventConfig
        from src.events import CombatEvent

        cfg = CombatEventConfig(enemy_list=[("Slime", 2)], narrative_text="hi")
        ev = CombatEvent(name="TestCombat", config=cfg)
        payload = to_placeholder(ev)
        nested = payload["params"]["config"]
        assert nested["class"] == "combat_event_config.CombatEventConfig"
        assert nested["params"]["enemy_list"] == [["Slime", 2]]

    def test_story_chapter_event_reduces_to_near_bare_reference(self):
        """Story events (ch01/ch02/ch03) declare no extra metadata of their
        own -- inheriting Event's base set alone should reduce them to just
        name/repeat/params, confirming the "near-zero payload" conclusion
        from the issue #463 audit."""
        from src.story.ch02 import AfterDefeatingKingSlime

        class DummyPlayer:
            pass

        class DummyTile:
            events_here = []
            map = {}

        ev = AfterDefeatingKingSlime(player=DummyPlayer(), tile=DummyTile())
        payload = to_placeholder(ev)
        assert set(payload["params"].keys()) <= {"name", "repeat", "params"}


# ---------------------------------------------------------------------------
# Universe (game boot loader) integration: legacy / placeholder / mixed
# ---------------------------------------------------------------------------

class TestUniverseIntegration:
    def test_deserialize_saved_instance_placeholder_shape(self):
        from src.universe import Universe

        u = Universe()
        u.player = MagicMock()
        payload = {"class": "npc.Slime", "params": {"overrides": {"maxhp": 999}}}
        inst = u._deserialize_saved_instance(payload)
        assert inst.maxhp == 999

    def test_deserialize_saved_instance_legacy_shape_still_works(self):
        from src.universe import Universe

        u = Universe()
        u.player = MagicMock()
        payload = {"__class__": "Gold", "__module__": "items", "props": {"amt": 10}}
        inst = u._deserialize_saved_instance(payload)
        assert type(inst).__name__ == "Gold"

    def test_placeholder_security_rejection_returns_none(self):
        from src.universe import Universe

        u = Universe()
        u.player = MagicMock()
        payload = {"class": "os.system", "params": {}}
        assert u._deserialize_saved_instance(payload) is None

    def test_full_map_load_mixed_legacy_and_placeholder(self, tmp_path):
        import json

        from src.universe import Universe

        map_data = {
            "meta": {"schema_version": 2},
            "(0,0)": {
                "title": "Test Room",
                "npcs": [
                    {"__class__": "Slime", "__module__": "npc", "props": {"name": "Slime", "maxhp": 55}},
                    {"class": "npc.CaveBat", "params": {}},
                ],
                "items": [{"class": "items.Restorative", "params": {"count": 3}}],
                "objects": [{"class": "objects.Crate", "params": {"stock_count": 7}}],
                "events": [
                    {"class": "story.effects.NPCSpawnerEvent",
                     "params": {"npc_cls": "GronditeElder", "count": 2}}
                ],
            },
        }
        mapfile = tmp_path / "mixed.json"
        mapfile.write_text(json.dumps(map_data))

        class DummyPlayer:
            def __init__(self):
                self.map = None
                self.saveuniv = None
                self.savestat = None

        u = Universe()
        player = DummyPlayer()
        u.player = player
        u._load_single_json_map(player, mapfile)

        tile = u.maps[0][(0, 0)]
        npc_names = sorted(type(n).__name__ for n in tile.npcs_here)
        assert npc_names == ["CaveBat", "Slime"]
        slime = next(n for n in tile.npcs_here if type(n).__name__ == "Slime")
        assert slime.maxhp == 55

        assert len(tile.items_here) == 1
        assert tile.items_here[0].count == 3

        assert len(tile.objects_here) == 1
        assert tile.objects_here[0].stock_count == 7
        assert tile.objects_here[0].tile is tile  # injected at construction, mandatory arg

        assert len(tile.events_here) == 1
        assert tile.events_here[0].npc_cls == "GronditeElder"


# ---------------------------------------------------------------------------
# Map Editor: save/load round trip + Convert Elements report
# ---------------------------------------------------------------------------

@pytest.fixture
def map_generator_module():
    """Import utils.map_generator with tkinter stubbed out (no tkinter in
    this sandbox). Mirrors the fixture in test_map_generator_container_fix.py."""
    tk_module_names = [
        "tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox",
        "tkinter.simpledialog", "tkinter.font",
    ]
    previous = {name: sys.modules.get(name) for name in tk_module_names}
    previous_mapgen = snapshot_and_clear_mapgen_modules()

    tk_stub = types.ModuleType("tkinter")
    sys.modules["tkinter"] = tk_stub
    for name in tk_module_names[1:]:
        submodule_name = name.rsplit(".", 1)[-1]
        submodule_stub = MagicMock()
        sys.modules[name] = submodule_stub
        setattr(tk_stub, submodule_name, submodule_stub)
    for attr in ("Tk", "Frame", "Toplevel", "Label", "Button", "Entry", "StringVar",
                 "BooleanVar", "Listbox", "Scrollbar", "Canvas", "Menu", "PhotoImage",
                 "Text"):
        setattr(tk_stub, attr, MagicMock())

    try:
        import importlib
        module = importlib.import_module("utils.map_generator")
        yield module
    finally:
        restore_mapgen_modules(previous_mapgen)
        for name, mod in previous.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


class TestMapEditorIntegration:
    def test_save_map_writes_placeholder_shape_for_new_placement(self, map_generator_module, tmp_path):
        from src.npc import Slime

        editor = map_generator_module.MapEditor.__new__(map_generator_module.MapEditor)
        editor.map_data = {(0, 0): {"events": [], "items": [], "npcs": [Slime()], "objects": []}}
        editor.current_map_filepath = None
        editor.set_status = lambda msg: None
        editor.update_map_label = lambda: None

        outpath = tmp_path / "out.json"
        map_generator_module.filedialog.asksaveasfilename = lambda **kw: str(outpath)
        editor.save_map()

        import json
        data = json.loads(outpath.read_text())
        assert data["meta"]["schema_version"] == map_placeholders.SCHEMA_VERSION
        npc_payload = data["(0, 0)"]["npcs"][0]
        assert npc_payload["class"] == "npc._enemies.Slime"

    def test_load_map_no_forced_migration_on_resave(self, map_generator_module, tmp_path):
        import json

        map_json = {
            "(0, 0)": {
                "events": [], "items": [], "npcs": [],
                "objects": [{"__class__": "WallInscription", "__module__": "objects",
                             "props": {"name": "Old Sign", "text": "hi"}}],
            }
        }
        mapfile = tmp_path / "legacy.json"
        mapfile.write_text(json.dumps(map_json))

        editor = map_generator_module.MapEditor.__new__(map_generator_module.MapEditor)
        editor.set_status = lambda msg: None
        editor.update_map_label = lambda: None
        editor.draw_map = lambda: None
        editor.selected_tile = None
        editor.load_map(str(mapfile))

        obj = editor.map_data[(0, 0)]["objects"][0]
        assert obj._hov_placeholder_format is False

        outpath = tmp_path / "resaved.json"
        map_generator_module.filedialog.asksaveasfilename = lambda **kw: str(outpath)
        editor.current_map_filepath = None
        editor.save_map()

        resaved = json.loads(outpath.read_text())
        resaved_obj = resaved["(0, 0)"]["objects"][0]
        assert "__class__" in resaved_obj  # still legacy shape, not force-migrated
        assert resaved_obj["__module__"] == "objects"  # bare, not "src.objects"

    def test_load_map_rejects_malicious_legacy_class(self, map_generator_module, tmp_path):
        import json

        bad_map = {"(0,0)": {"events": [], "items": [], "npcs": [],
                              "objects": [{"__class__": "system", "__module__": "os", "props": {}}]}}
        mapfile = tmp_path / "bad.json"
        mapfile.write_text(json.dumps(bad_map))

        editor = map_generator_module.MapEditor.__new__(map_generator_module.MapEditor)
        statuses = []
        editor.set_status = lambda msg: statuses.append(msg)
        editor.update_map_label = lambda: None
        editor.draw_map = lambda: None
        editor.selected_tile = None
        editor.load_map(str(mapfile))

        # Refused to resolve -> raw dict kept, not the dangerous os.system callable
        obj = editor.map_data[(0, 0)]["objects"][0]
        assert isinstance(obj, dict)
        assert any("allow-list" in s for s in statuses)

    def test_convert_elements_report_categorizes_correctly(self, map_generator_module):
        from src.npc import Slime
        from src.items import Gold

        map_data = {
            (0, 0): {"events": [], "items": [Gold()], "npcs": [Slime()], "objects": []},
        }
        report = map_generator_module.compute_convert_elements_report(map_data)
        assert report["skipped"] == []
        # Both Gold and Slime are authorable (inherit base metadata) but have
        # at least one non-standard attribute the generic denylist doesn't
        # recognize -- both land in "ambiguous", not silently "converted".
        labels = [label for label, _ in report["ambiguous"]]
        assert any("Slime" in label for label in labels)
        assert any("Gold" in label for label in labels)
        # Tagged for compact re-save even though flagged for review.
        assert map_data[(0, 0)]["npcs"][0]._hov_placeholder_format is True

    def test_convert_elements_is_idempotent(self, map_generator_module):
        from src.npc import Slime

        map_data = {(0, 0): {"events": [], "items": [], "npcs": [Slime()], "objects": []}}
        map_generator_module.compute_convert_elements_report(map_data)
        second_report = map_generator_module.compute_convert_elements_report(map_data)
        assert second_report == {"converted": [], "ambiguous": [], "skipped": []}

    def test_debug_npcs_excluded_from_add_npc_palette(self, map_generator_module):
        class_info = {
            "NPC": {"bases": []},
            "Slime": {"bases": ["NPC"]},
            "TheAdjutant": {"bases": ["Friend", "NPC"]},
            "Friend": {"bases": ["NPC"]},
            "StatusDummy": {"bases": ["NPC"]},
            "Testexp": {"bases": ["NPC"]},
        }
        allowed = map_generator_module.filter_classes(class_info, "NPC")
        assert "Slime" in allowed
        assert "TheAdjutant" not in allowed
        assert "StatusDummy" not in allowed
        assert "Testexp" not in allowed

    def test_merchant_isinstance_check_survives_canonical_resolution(self, map_generator_module):
        """Regression guard: load_map()/instantiate_placeholder now always
        resolve classes through the canonical src.* path, so this module's
        own bare `Merchant` import would silently stop matching
        placeholder-loaded merchants without _is_merchant_like.
        """
        from src.npc._merchants import MiloCurioDealer  # canonical, as the loader now resolves it

        canonical_milo = MiloCurioDealer()
        assert map_generator_module._is_merchant_like(canonical_milo)

        # Fetch the *duplicate* class map_generator.py's own bare `from npc
        # import Merchant` creates -- via sys.modules, not a second bare
        # import statement of our own (the project's static bare-import
        # guard forbids that in tests/; this reads the module object that
        # already exists as a side effect of the fixture importing
        # utils.map_generator).
        bare_npc_module = sys.modules["npc"]
        bare_milo = bare_npc_module.MiloCurioDealer()
        assert bare_milo.__class__ is not canonical_milo.__class__
        assert map_generator_module._is_merchant_like(bare_milo)
        # A plain isinstance check against the module's bare `Merchant` would
        # already have worked for the bare instance but silently fail for
        # the canonical one -- confirming _is_merchant_like, not isinstance,
        # is what's actually in use at the two call sites.
        assert not isinstance(canonical_milo, map_generator_module.Merchant)


# ---------------------------------------------------------------------------
# Shipped map content: tile descriptions are PERMANENT
# ---------------------------------------------------------------------------
#
# CLAUDE.md (Map Design Skill, "Design Principles") states the rule outright:
# "Tile descriptions are permanent. Descriptions persist after NPCs are killed
# and items are picked up. Never write present-tense NPC behaviour or item
# references into a description."
#
# That rule was documented but unenforced, so a violation could only be caught
# by a human replaying the room after clearing it -- exactly the state QA
# reaches last. These tests read the shipped map JSON directly (no Universe
# build, no registry mutation) and are cheap enough to run every time.

import json as _json
import re as _re
from pathlib import Path as _Path

_MAPS_DIR = _Path(__file__).resolve().parents[1] / "src" / "resources" / "maps"

#: Dev-only map. CLAUDE.md documents combat-testing-arena as an agent-facing
#: testing arena whose descriptions deliberately address the *tester* ("Use
#: this arena for testing states.py interactions") and name the roster on
#: purpose. It is unreachable from the game world, so the permanence rule --
#: which exists to protect the player's experience -- does not apply.
_DEV_ONLY_MAPS = {"combat-testing-arena.json"}


def _shipped_map_tiles():
    """Yield ``(map_file, coord, tile_dict)`` for every shipped map tile."""
    map_files = sorted(_MAPS_DIR.glob("*.json"))
    assert map_files, "no shipped maps found — the glob is wrong"
    for path in map_files:
        if path.name in _DEV_ONLY_MAPS:
            continue
        with path.open() as handle:
            data = _json.load(handle)
        for coord, tile in data.items():
            if isinstance(tile, dict) and "description" in tile:
                yield path.name, coord, tile


def _entry_names(tile, key):
    """Names of the placeholder entries under ``tile[key]`` (npcs / items)."""
    names = set()
    for entry in tile.get(key) or []:
        if not isinstance(entry, dict):
            continue
        props = entry.get("props") or {}
        for candidate in (props.get("name"), entry.get("__class__")):
            if isinstance(candidate, str) and len(candidate) > 2:
                names.add(candidate)
    return names


def _mentions(description, name):
    return bool(_re.search(rf"\b{_re.escape(name)}\b", description or "", _re.I))


def test_tile_descriptions_never_name_an_item_lying_on_the_tile():
    """An item's name in the room text outlives the item itself.

    Once the player takes the Restorative, a description that says "a vial of
    Restorative sits on the ledge" is a lie the room repeats forever.
    """
    offenders = [
        f"{map_name} {coord}: description names item {name!r}"
        for map_name, coord, tile in _shipped_map_tiles()
        for name in _entry_names(tile, "items")
        if _mentions(tile["description"], name)
    ]
    assert not offenders, "\n".join(offenders)


def test_tile_descriptions_never_name_a_killable_npc_on_the_tile():
    """Same rule for NPCs: the description survives the NPC's death.

    Merchants are exempt -- a shop's proprietor is a permanent fixture of the
    room rather than a clearable encounter, and the room text is written
    around them ("a battered counter ... where Jambo greets customers").
    """
    from src.npc._merchants import Merchant
    import src.npc as npc_module

    def _is_merchant(class_name):
        cls = getattr(npc_module, class_name, None)
        return isinstance(cls, type) and issubclass(cls, Merchant)

    offenders = []
    for map_name, coord, tile in _shipped_map_tiles():
        for entry in tile.get("npcs") or []:
            if not isinstance(entry, dict):
                continue
            class_name = entry.get("__class__")
            if isinstance(class_name, str) and _is_merchant(class_name):
                continue
            props = entry.get("props") or {}
            for name in {props.get("name"), class_name}:
                if isinstance(name, str) and len(name) > 2 and _mentions(
                        tile["description"], name):
                    offenders.append(
                        f"{map_name} {coord}: description names NPC {name!r}")
    assert not offenders, "\n".join(offenders)


def test_the_permanence_lint_actually_detects_a_violation():
    """Non-vacuity guard for the two tests above.

    Both pass today by finding nothing, which is indistinguishable from a
    broken matcher that can never find anything. This feeds the matcher a
    known-bad tile and asserts it fires.
    """
    bad_tile = {
        "description": "A Restorative sits on the ledge, and a Slime blocks the way.",
        "items": [{"__class__": "Restorative", "props": {"name": "Restorative"}}],
        "npcs": [{"__class__": "Slime", "props": {"name": "Slime"}}],
    }

    assert any(_mentions(bad_tile["description"], n)
               for n in _entry_names(bad_tile, "items"))
    assert any(_mentions(bad_tile["description"], n)
               for n in _entry_names(bad_tile, "npcs"))
    # And a clean tile must not trip it.
    clean = {"description": "Wet stone, streaked where something heavy was dragged.",
             "items": [{"__class__": "Restorative", "props": {"name": "Restorative"}}],
             "npcs": []}
    assert not any(_mentions(clean["description"], n)
                   for n in _entry_names(clean, "items"))
