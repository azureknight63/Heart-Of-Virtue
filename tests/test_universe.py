"""Unit coverage for ``src.universe``: map-JSON deserialization and loading.

Map JSON is attacker-influenceable (map files are hand-editable and can be
shipped by third parties), so ``_deserialize_saved_instance`` runs every
``__module__``/``__class__`` reference through the same engine trust boundary
that guards save-file unpickling (``src.secure_pickle._is_allowed``). The
``TestDeserializeTrustGate`` class below is the guard for that; before it, the
gate had no test at all.
"""

import contextlib

import pytest

import src.functions as functions
from src.narration import capture_narration
from src.universe import Universe, tile_exists


@contextlib.contextmanager
def narration_text():
    """Collect the plain text of narration emitted inside the block.

    The loader reports every refusal through ``narrate`` rather than raising,
    so asserting on the message is the only way to tell "refused by the trust
    gate" apart from "silently produced nothing".
    """
    texts = []
    with capture_narration() as messages:
        yield texts
    texts.extend(m.get("text", "") for m in messages)


class DummyItem:
    def __init__(self, name, value):
        self.name = name
        self.value = value


class DummyMerchant:
    def __init__(self, inventory):
        self.inventory = inventory


@pytest.fixture(autouse=True)
def dummy_modules(monkeypatch):
    # Payloads store bare module names ('items', 'npc'); the deserializer maps
    # them to the canonical src.* modules, so attach the dummy classes there.
    import src.items
    import src.npc
    monkeypatch.setattr(src.items, 'DummyItem', DummyItem, raising=False)
    monkeypatch.setattr(src.npc, 'DummyMerchant', DummyMerchant, raising=False)
    yield


def test_recursive_deserialize_inventory():
    # Simulate a merchant with a nested inventory of items
    payload = {
        '__class__': 'DummyMerchant',
        '__module__': 'npc',
        'props': {
            'inventory': [
                {
                    '__class__': 'DummyItem',
                    '__module__': 'items',
                    'props': {'name': 'Sword', 'value': 100}
                },
                {
                    '__class__': 'DummyItem',
                    '__module__': 'items',
                    'props': {'name': 'Shield', 'value': 150}
                }
            ]
        }
    }
    universe = Universe()
    merchant = universe._deserialize_saved_instance(payload)
    assert isinstance(merchant, DummyMerchant)
    # Order and per-item props must survive the recursion, not merely the count:
    # a loader that rebuilt the list from the *first* payload would still give
    # two DummyItems.
    assert [(i.name, i.value) for i in merchant.inventory] == [
        ("Sword", 100), ("Shield", 150),
    ]


def test_tile_exists():
    test_map = {(1, 2): 'tileA', (3, 4): 'tileB'}
    assert tile_exists(test_map, 1, 2) == 'tileA'
    assert tile_exists(test_map, 3, 4) == 'tileB'
    assert tile_exists(test_map, 0, 0) is None


def test_universe_init():
    u = Universe()
    assert u.game_tick == 0
    assert u.maps == []
    assert u.starting_map_default is None
    assert isinstance(u.story, dict)
    assert u.locked_chests == []


def test_json_maps_root_candidates_returns_only_existing_directories(
        tmp_path, monkeypatch):
    """Exercise the real method.

    The previous version of this test replaced ``_json_maps_root_candidates``
    with a lambda returning two directories and then asserted that the lambda
    returned those two directories — it patched out the unit under test and
    proved only that Python closures work.
    """
    resources = tmp_path / 'resources'
    maps_dir = resources / 'maps'
    maps_dir.mkdir(parents=True)
    monkeypatch.setattr('src.universe.RESOURCES_DIR', resources)

    candidates = Universe()._json_maps_root_candidates()
    assert maps_dir in candidates
    assert all(c.exists() and c.is_dir() for c in candidates)


def test_json_maps_root_candidates_drops_a_missing_maps_directory(
        tmp_path, monkeypatch):
    resources = tmp_path / 'resources'
    resources.mkdir()  # exists, but has no 'maps' subdirectory
    monkeypatch.setattr('src.universe.RESOURCES_DIR', resources)

    assert (resources / 'maps') not in Universe()._json_maps_root_candidates()


def test_load_all_json_maps(monkeypatch, tmp_path):
    # Setup dummy map file
    maps_dir = tmp_path / 'resources' / 'maps'
    maps_dir.mkdir(parents=True)
    dummy_map = maps_dir / 'testmap.json'
    dummy_map.write_text('{"(0,0)": {"title": "DummyTile", "description": "desc"}}')
    monkeypatch.setattr('src.universe.RESOURCES_DIR', tmp_path / 'resources')
    u = Universe()
    # Patch _json_maps_root_candidates to only return our test dir
    u._json_maps_root_candidates = lambda: [maps_dir]
    # Patch _load_single_json_map to count calls
    called = []

    def fake_load_single_json_map(player, jf):
        called.append(jf)

    u._load_single_json_map = fake_load_single_json_map
    count = u._load_all_json_maps(player=None)
    assert count == 1
    assert called[0].name == 'testmap.json'


def test_load_all_json_maps_reports_and_survives_a_broken_map(
        monkeypatch, tmp_path):
    """One unloadable map must not abort the whole world build."""
    maps_dir = tmp_path / 'resources' / 'maps'
    maps_dir.mkdir(parents=True)
    (maps_dir / 'aaa_broken.json').write_text('{not json')
    (maps_dir / 'zzz_good.json').write_text(
        '{"(0,0)": {"title": "Room", "description": "desc"}}')
    monkeypatch.setattr('src.universe.RESOURCES_DIR', tmp_path / 'resources')

    u = Universe()
    with narration_text() as messages:
        loaded = u._load_all_json_maps(player=None)

    assert loaded == 1                       # the good map still loaded
    assert [m['name'] for m in u.maps] == ['zzz_good']
    assert any('aaa_broken.json' in m for m in messages)


def test_deserialize_saved_instance_edge_cases():
    u = Universe()
    # Empty dict
    assert u._deserialize_saved_instance({}) is None
    # Missing __class__
    assert u._deserialize_saved_instance({'__module__': 'items', 'props': {}}) is None
    # Non-engine builtins are now rejected by the shared allow-list gate (a bare
    # ``builtins.int`` is not an engine class), so the loader returns None.
    payload = {'__class__': 'int', '__module__': 'builtins', 'props': {'x': 5}}
    assert u._deserialize_saved_instance(payload) is None
    # An engine class (attached to src.items by the dummy_modules fixture) still
    # resolves through the gate.
    payload = {'__class__': 'DummyItem', '__module__': 'items',
               'props': {'name': 'Gate', 'value': 1}}
    assert isinstance(u._deserialize_saved_instance(payload), DummyItem)
    # Nested dicts/lists
    payload = {
        '__class__': 'DummyMerchant',
        '__module__': 'npc',
        'props': {
            'inventory': [
                {
                    '__class__': 'DummyItem',
                    '__module__': 'items',
                    'props': {'name': 'Sword', 'value': 100}
                },
                {'foo': 'bar'}
            ],
            'meta': {'subitem': {
                '__class__': 'DummyItem',
                '__module__': 'items',
                'props': {'name': 'Potion', 'value': 10}
            }}
        }
    }
    merchant = u._deserialize_saved_instance(payload)
    assert isinstance(merchant, DummyMerchant)
    assert isinstance(merchant.inventory[0], DummyItem)
    assert merchant.inventory[1] == {'foo': 'bar'}
    assert isinstance(merchant.meta['subitem'], DummyItem)


@pytest.mark.parametrize("props", ["notadict", 5, [1, 2], None])
def test_deserialize_rejects_non_dict_props(props):
    payload = {'__class__': 'DummyItem', '__module__': 'items', 'props': props}
    result = Universe()._deserialize_saved_instance(payload)
    # ``props: None`` is normalised to {} by the loader; anything else is a
    # malformed payload and must be refused outright.
    if props is None:
        assert isinstance(result, DummyItem)
    else:
        assert result is None


@pytest.mark.parametrize("module", [None, 5, [], ""])
def test_deserialize_rejects_non_string_module(module):
    payload = {'__class__': 'DummyItem', '__module__': module, 'props': {}}
    assert Universe()._deserialize_saved_instance(payload) is None


@pytest.mark.parametrize("cls_name", [None, 5, [], ""])
def test_deserialize_rejects_non_string_class(cls_name):
    payload = {'__class__': cls_name, '__module__': 'items', 'props': {}}
    assert Universe()._deserialize_saved_instance(payload) is None


# ---------------------------------------------------------------------------
# The engine trust boundary for map JSON.
#
# Each gadget is asserted individually and by name: a single spot-check of
# ``os.system`` is exactly what let the dotted-attribute-path bypass survive in
# the pickle loader (``src.secure_pickle``), so the same shortcut is not taken
# here.
# ---------------------------------------------------------------------------

_GADGETS = [
    ("os", "system"),
    ("os", "popen"),
    ("os", "remove"),
    ("subprocess", "Popen"),
    ("subprocess", "run"),
    ("subprocess", "check_output"),
    ("builtins", "eval"),
    ("builtins", "exec"),
    ("builtins", "getattr"),
    ("builtins", "__import__"),
    ("builtins", "open"),
    ("posix", "system"),
    ("nt", "system"),
    ("shutil", "rmtree"),
    ("pickle", "loads"),
    ("importlib", "import_module"),
    ("webbrowser", "open"),
]


class TestDeserializeTrustGate:
    """``_deserialize_class_allowed`` must refuse every non-engine global."""

    @pytest.mark.parametrize("module, name", _GADGETS,
                             ids=[f"{m}.{n}" for m, n in _GADGETS])
    def test_gadget_payload_is_refused(self, module, name):
        payload = {"__class__": name, "__module__": module, "props": {}}
        with narration_text() as messages:
            result = Universe()._deserialize_saved_instance(payload)
        assert result is None
        assert any("refusing to deserialize non-engine class" in m
                   for m in messages), messages

    @pytest.mark.parametrize("module, name", _GADGETS,
                             ids=[f"{m}:{n}" for m, n in _GADGETS])
    def test_gadget_class_type_marker_is_refused(self, module, name):
        payload = {"__class_type__": f"{module}:{name}"}
        assert Universe()._deserialize_saved_instance(payload) is None

    def test_the_gate_delegates_to_the_shared_secure_pickle_boundary(self):
        """Both loaders must share one trust boundary, not two drifting copies."""
        import src.secure_pickle as secure_pickle

        assert Universe._deserialize_class_allowed("src.items", "Gold") is True
        assert Universe._deserialize_class_allowed("os", "system") is False
        assert (Universe._deserialize_class_allowed("src.items", "Gold")
                is secure_pickle._is_allowed("src.items", "Gold"))

    @pytest.mark.parametrize("module, name", [(5, "Gold"), ("items", 5),
                                              (None, None), (["items"], "Gold")])
    def test_the_gate_refuses_non_string_references(self, module, name):
        assert Universe._deserialize_class_allowed(module, name) is False

    def test_dotted_attribute_path_cannot_escape_a_trusted_module(self):
        """Regression mirroring the pickle STACK_GLOBAL bypass.

        ``src.secure_pickle`` really is an engine module, so the ``(module,
        name)`` pair passes the gate — the protection is that this loader
        resolves ``name`` with a single ``getattr`` and never walks dots.
        """
        payload = {"__class__": "os.system", "__module__": "secure_pickle",
                   "props": {}}
        assert Universe()._deserialize_saved_instance(payload) is None
        assert Universe()._deserialize_saved_instance(
            {"__class_type__": "secure_pickle:os.system"}) is None

    def test_engine_classes_still_load_through_the_gate(self):
        """The accept side: a real shipped payload must not be collateral."""
        from src.items import Gold
        from src.objects import WallSwitch

        universe = Universe()
        gold = universe._deserialize_saved_instance(
            {"__class__": "Gold", "__module__": "items", "props": {"amt": 12}})
        assert isinstance(gold, Gold) and gold.amt == 12
        assert universe._deserialize_saved_instance(
            {"__class_type__": "objects:WallSwitch"}) is WallSwitch

    def test_src_prefixed_module_is_rejected_loudly(self):
        """Map data stores *bare* module names; an 'src.'-prefixed one is a
        corrupt/hand-tampered payload and must raise rather than be guessed at."""
        with pytest.raises(ValueError, match="Invalid module name format"):
            Universe()._deserialize_saved_instance(
                {"__class__": "Gold", "__module__": "src.items", "props": {}})

    def test_recursion_bomb_is_depth_capped(self):
        """A hostile map must not be able to blow the Python stack."""
        from src.universe import MAX_DESERIALIZE_DEPTH

        payload = {"__class__": "DummyItem", "__module__": "items",
                   "props": {"name": "deep", "value": 1}}
        with narration_text() as messages:
            result = Universe()._deserialize_saved_instance(
                payload, _depth=MAX_DESERIALIZE_DEPTH + 1)
        assert result is None
        assert any("maximum nesting depth" in m for m in messages), messages

    def test_deeply_nested_props_collapse_to_none_instead_of_recursing(self):
        """Nested props past the cap are dropped, not followed."""
        from src.universe import MAX_DESERIALIZE_DEPTH

        payload = {"__class__": "DummyItem", "__module__": "items",
                   "props": {"name": "x", "value": 1}}
        nested = {"leaf": 1}
        for _ in range(MAX_DESERIALIZE_DEPTH + 5):
            nested = {"deeper": nested}
        payload["props"]["value"] = nested

        item = Universe()._deserialize_saved_instance(payload)
        assert isinstance(item, DummyItem)
        # Walk down until the loader stopped following the chain.
        node = item.value
        for _ in range(MAX_DESERIALIZE_DEPTH + 5):
            if node is None:
                break
            node = node.get("deeper") if isinstance(node, dict) else None
        assert node is None


def test_load_single_json_map(monkeypatch, tmp_path):
    # Setup dummy tile class
    class DummyTile:
        def __init__(self, universe, this_map, x, y, description=None):
            self.x = x
            self.y = y
            self.description = description
            self.block_exit = []
            self.symbol = None
            self.events_here = []
            self.items_here = []
            self.npcs_here = []
            self.objects_here = []

    monkeypatch.setattr(functions, 'seek_class', lambda title, mod, **kw: DummyTile)
    # Create dummy map JSON. The optional "class" field is what selects a real
    # tileset subclass; "title" is display-only and is never used for class
    # resolution.
    map_json = tmp_path / 'testmap.json'
    map_json.write_text(
        '{"(1,2)": {"title": "Dummy Tile Display Name", "class": "DummyTile", '
        '"description": "desc", "block_exit": ["N"], "symbol": "#", '
        '"events": [], "items": [], "npcs": [], "objects": []}}')
    u = Universe()
    u._load_single_json_map(player=None, json_path=map_json)
    assert u.maps[-1]['name'] == 'testmap'
    tile = u.maps[-1][(1, 2)]
    assert isinstance(tile, DummyTile)
    assert tile.x == 1 and tile.y == 2
    assert tile.description == 'desc'
    assert tile.block_exit == ['N']
    assert tile.symbol == '#'
    assert tile.events_here == []
    assert tile.items_here == []
    assert tile.npcs_here == []
    assert tile.objects_here == []


def test_load_single_json_map_refuses_gadget_payloads_in_map_content(tmp_path):
    """End-to-end: a tampered map file cannot land a gadget on a tile."""
    map_json = tmp_path / 'hostile.json'
    map_json.write_text(
        '{"(0,0)": {"title": "Room", "description": "d",'
        ' "items": [{"__class__": "system", "__module__": "os", "props": {}}],'
        ' "npcs": [{"__class__": "Popen", "__module__": "subprocess",'
        ' "props": {}}],'
        ' "objects": [{"__class__": "eval", "__module__": "builtins",'
        ' "props": {}}],'
        ' "events": [{"__class__": "rmtree", "__module__": "shutil",'
        ' "props": {}}]}}')

    u = Universe()
    u._load_single_json_map(player=None, json_path=map_json)
    tile = u.maps[-1][(0, 0)]
    assert tile.items_here == []
    assert tile.npcs_here == []
    assert tile.objects_here == []
    assert tile.events_here == []
    # The tile itself still loads — a hostile entry is dropped, not fatal.
    assert tile.description == 'd'
