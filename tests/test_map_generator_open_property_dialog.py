"""Widget-level regression coverage for utils/map_generator.py's
open_property_dialog and the 5 field-builder helpers extracted from it
(_build_class_type_field, _build_map_name_field, _build_coordinate_field,
_build_class_chooser_field, _build_merchant_field).

Prior to this file, open_property_dialog's actual control flow had ZERO
coverage -- see the module docstring in test_map_generator_property_dialog_ux.py,
which only unit-tests the pure-logic pieces (_property_description,
_property_group, _grouped_field_layout, class discovery, and the bulk-edit
normalization re-derived inline). That was true because the only tkinter
stub previously used in this test suite replaces widget base classes (like
tk.Frame) with a bare MagicMock() *instance* -- and subclassing a MagicMock
instance (as TagListFrame(tk.Frame) does) silently turns the subclass itself
into a MagicMock rather than a real Python class, making it useless for
exercising real logic.

This file uses a different stub: real, lightweight Python classes standing
in for the tkinter widget/variable primitives (_FakeWidget, _FakeVar), so
`class TagListFrame(tk.Frame):` is genuine subclassing and open_property_dialog
actually runs its real field-dispatch logic under test -- only the drawing
primitives are faked, not the module's own code.
"""

import importlib
import sys
import types
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from conftest import restore_mapgen_modules, snapshot_and_clear_mapgen_modules


class _FakeVar:
    """Stand-in for tkinter.StringVar/BooleanVar with real get/set/trace_add
    semantics (unlike a bare MagicMock, whose .get() would return another
    Mock instead of the value actually .set() on it)."""

    def __init__(self, *args, value=None, **kwargs):
        self._value = value if value is not None else (args[0] if args else "")
        self._traces = []

    def get(self):
        return self._value

    def set(self, value):
        self._value = value

    def trace_add(self, mode, callback):
        self._traces.append((mode, callback))
        return f"trace-{len(self._traces)}"


class _FakeWidget:
    """Stand-in for tkinter widget base classes (Frame, Toplevel, Label,
    Button, Entry, Listbox, Scrollbar, Canvas, Menu, PhotoImage). A real
    Python class (not a MagicMock instance) so it can genuinely be
    subclassed -- see module docstring -- while any layout/config method
    not explicitly modeled here (pack, grid, bind, config, ...) is a no-op
    that returns a fresh MagicMock via __getattr__, matching how little the
    code under test cares about those calls' return values.
    """

    #: every instance created during the current test, so tests can find
    #: e.g. a specific Button by its text= and invoke its command= callback
    #: to simulate a click. Cleared per-test by the mg fixture below.
    registry: list = []

    def __init__(self, master=None, *args, **kwargs):
        self.master = master
        # Recorded so tests can retrieve e.g. a Button's command= callback
        # and invoke it directly to simulate a click.
        self.init_args = args
        self.init_kwargs = kwargs
        _FakeWidget.registry.append(self)

    def __getattr__(self, name):
        # Cache the generated mock as a real instance attribute so repeated
        # access (e.g. checking `.destroy.called` after the code under test
        # already called `.destroy()`) sees the same object, not a fresh
        # never-called mock each time.
        mock = MagicMock()
        object.__setattr__(self, name, mock)
        return mock

    def winfo_toplevel(self):
        node = self
        while getattr(node, "master", None) is not None:
            node = node.master
        return node


def find_button(text):
    """Locates a constructed Button-like _FakeWidget by its text= kwarg."""
    for widget in _FakeWidget.registry:
        if widget.init_kwargs.get("text") == text:
            return widget
    raise AssertionError(f"No widget constructed with text={text!r}")


def widget_texts():
    """Every non-empty ``text=`` the dialog constructed, in creation order.

    This is the dialog's observable output under the fake-widget stub, so it
    is what "the dialog rendered X" has to be asserted against -- several tests
    below used to call ``open_property_dialog`` and assert nothing at all.
    """
    return [w.init_kwargs.get("text") for w in _FakeWidget.registry
            if w.init_kwargs.get("text")]


@pytest.fixture
def mg():
    """Imports utils.map_generator with a tkinter stub permissive enough to
    actually execute open_property_dialog's widget-construction code, not
    just import the module."""
    tk_module_names = [
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.simpledialog",
        "tkinter.font",
    ]
    previous = {name: sys.modules.get(name) for name in tk_module_names}
    previous_mapgen = snapshot_and_clear_mapgen_modules()

    tk_stub = types.ModuleType("tkinter")
    sys.modules["tkinter"] = tk_stub

    # NOTE: MagicMock()-as-a-class returns the SAME shared `.return_value`
    # instance for every call, unlike a real ttk.Combobox() which
    # constructs a distinct widget each time. Fine for the tests in this
    # file (each fake holder class has exactly one Combobox-triggering
    # field), but a test class with two such fields would need per-call
    # instances (e.g. `side_effect=lambda *a, **k: MagicMock()`) to avoid
    # one field's .config() calls clobbering the other's.
    ttk_stub = types.ModuleType("tkinter.ttk")
    ttk_stub.Combobox = MagicMock(name="Combobox")
    sys.modules["tkinter.ttk"] = ttk_stub
    tk_stub.ttk = ttk_stub

    for name in ("filedialog", "messagebox", "simpledialog", "font"):
        submodule_stub = MagicMock(name=name)
        sys.modules[f"tkinter.{name}"] = submodule_stub
        setattr(tk_stub, name, submodule_stub)

    for attr in (
        "Tk",
        "Frame",
        "Toplevel",
        "Label",
        "Button",
        "Entry",
        "Listbox",
        "Scrollbar",
        "Canvas",
        "Menu",
        "PhotoImage",
    ):
        setattr(tk_stub, attr, _FakeWidget)
    tk_stub.StringVar = _FakeVar
    tk_stub.BooleanVar = _FakeVar
    tk_stub.END = "end"
    tk_stub.BOTH = "both"
    tk_stub.LAST = "last"

    _FakeWidget.registry.clear()

    try:
        module = importlib.import_module("utils.map_generator")
        yield module
    finally:
        restore_mapgen_modules(previous_mapgen)
        for name, mod in previous.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


class TestMapNameField:
    """_build_map_name_field: the teleport_map/target_map_name combobox."""

    def test_lists_real_map_files_and_preselects_existing_value(self, mg):
        class MapNameHolder:
            def __init__(self, teleport_map: str = ""):
                pass

        existing = MapNameHolder()
        existing.teleport_map = "dark-grotto"

        mg.open_property_dialog(_FakeWidget(), MapNameHolder, existing=existing)

        assert ttk_calls_for(mg, "Combobox")
        combo_kwargs = ttk_calls_for(mg, "Combobox")[-1].kwargs
        assert "dark-grotto" in combo_kwargs["values"]
        assert combo_kwargs["textvariable"].get() == "dark-grotto"

    def test_no_map_files_does_not_crash(self, mg, monkeypatch):
        class MapNameHolder:
            def __init__(self, teleport_map: str = ""):
                pass

        # Force the "no map files found" branch. _build_map_name_field builds
        # candidate_dirs from the shared `project_root` constant (imported
        # from utils.mapgen.constants), so patching Path.exists to always
        # report False -- rather than the project_root global itself -- is
        # what forces both candidate_dirs to be skipped regardless of which
        # directory they resolve to.
        monkeypatch.setattr("pathlib.Path.exists", lambda self: False)
        mg.open_property_dialog(_FakeWidget(), MapNameHolder, existing=None)

        label_texts = [
            w.init_kwargs.get("text") for w in _FakeWidget.registry
        ]
        assert "No map files (*.json) found." in label_texts
        assert ttk_calls_for(mg, "Combobox")[-1].kwargs["values"] == []


class TestCoordinateField:
    """_build_coordinate_field: the teleport_tile/target_coordinates combobox."""

    def test_lists_tiles_from_fallback_map_data(self, mg):
        class CoordHolder:
            def __init__(self, teleport_tile=None):
                pass

        map_data = {
            (0, 0): {"title": "Origin"},
            (1, 0): {"title": "Next Door"},
        }

        mg.open_property_dialog(
            _FakeWidget(), CoordHolder, existing=None, map_data=map_data
        )

        # The combobox starts empty at construction time and is populated by
        # refresh_tiles() calling .config(values=...) afterward, not via the
        # constructor kwargs -- assert on the widget instance's last .config
        # call rather than the constructor call.
        combo_instance = mg.ttk.Combobox.return_value
        config_kwargs = combo_instance.config.call_args.kwargs
        assert config_kwargs["values"] == ["Origin (0,0)", "Next Door (1,0)"]

    def test_preselects_existing_coordinate(self, mg):
        class CoordHolder:
            def __init__(self, teleport_tile=None):
                pass

        existing = CoordHolder()
        existing.teleport_tile = (1, 0)
        map_data = {
            (0, 0): {"title": "Origin"},
            (1, 0): {"title": "Next Door"},
        }

        mg.open_property_dialog(
            _FakeWidget(), CoordHolder, existing=existing, map_data=map_data
        )

        combo_kwargs = ttk_calls_for(mg, "Combobox")[-1].kwargs
        assert combo_kwargs["textvariable"].get() == "Next Door (1,0)"


class TestMerchantField:
    """_build_merchant_field: the merchant-picker combobox.

    Dispatch note: this branch is only reached when the "merchant"-named
    parameter's annotation does NOT resolve to a real class via
    parse_type_hint (see _build_class_chooser_field's elif, which is
    checked first and wins whenever base_class is a class -- e.g. the real
    Container.merchant param is annotated `merchant: object = ""`, which
    *does* resolve to a class (object) and so is actually routed through
    _build_class_chooser_field in production, not this helper. That's a
    pre-existing dispatch-order behavior predating this test file, not
    something introduced here -- these tests use a non-class annotation so
    they can exercise _build_merchant_field's own logic directly.
    """

    def test_no_merchants_shows_placeholder_and_no_combobox(self, mg):
        class MerchantHolder:
            def __init__(self, merchant: Dict[str, Any] = None):
                pass

        mg.open_property_dialog(_FakeWidget(), MerchantHolder, existing=None)

        assert ttk_calls_for(mg, "Combobox") == []

    def test_preselects_matching_merchant_by_instance(self, mg):
        class MerchantHolder:
            def __init__(self, merchant: Dict[str, Any] = None):
                pass

        merchant_inst = mg.Merchant(
            name="Milo",
            description="A merchant.",
            damage=0,
            aggro=False,
            exp_award=0,
            stock_count=1,
        )
        map_data = {(0, 0): {"npcs": [merchant_inst]}}
        existing = MerchantHolder()
        existing.merchant = merchant_inst

        mg.open_property_dialog(
            _FakeWidget(), MerchantHolder, existing=existing, map_data=map_data
        )

        combo_kwargs = ttk_calls_for(mg, "Combobox")[-1].kwargs
        assert combo_kwargs["values"] == ["Milo"]
        assert combo_kwargs["textvariable"].get() == "Milo"


class TestClassChooserField:
    """_build_class_chooser_field: the generic Item/NPC/Object/Event
    instance tag-list chooser (as opposed to the Type[Base]-picks-a-class
    field tested below)."""

    def test_builds_an_empty_tag_list_with_a_choose_button(self, mg):
        """An instance-typed field with no existing value renders its label and
        a "Choose" button, and no tags.

        This exercises create_element_frame -> TagListFrame -> refresh_tags.
        Clicking "Choose" is deliberately out of scope here (it would pull in
        open_chooser/show_hierarchy_chooser), but the widgets it builds are
        observable, so "did not raise" is not the strongest claim available.
        """
        class FakeItem:
            pass

        class LootHolder:
            def __init__(self, loot: FakeItem = None):
                pass

        result = {}

        def fake_callback(inst):
            result["inst"] = inst

        mg.open_property_dialog(
            _FakeWidget(), LootHolder, existing=None, callback=fake_callback
        )

        texts = widget_texts()
        assert texts == ["loot:", "Choose", "Add"]
        assert "FakeItem" not in texts          # nothing selected yet
        # The callback only fires when the dialog is committed.
        assert result == {}

    def test_list_variant_reads_existing_collection(self, mg):
        """Each element of the existing collection must render its own tag.

        The old body called the dialog and asserted nothing, so a builder that
        rendered an empty tag list (losing the player's existing loot on every
        edit) passed.
        """
        from typing import List as TList

        class FakeItem:
            pass

        class InventoryHolder:
            def __init__(self, loot: TList[FakeItem] = None):
                pass

        existing = InventoryHolder()
        existing.loot = [FakeItem(), FakeItem()]

        mg.open_property_dialog(_FakeWidget(), InventoryHolder, existing=existing)

        texts = widget_texts()
        assert texts.count("FakeItem") == 2      # one tag per existing element
        assert texts.count("\u00d7") == 2       # a remove button per tag
        assert "Choose" in texts                 # and the add-another chooser


class TestClassTypeField:
    """_build_class_type_field: Type[Base]/list[Type[Base]] class pickers."""

    def test_single_type_base_field_offers_a_singular_chooser(self, mg):
        from typing import Type as TType

        class FakeBase:
            pass

        class SingleTypeHolder:
            def __init__(self, kind: TType[FakeBase] = None):
                pass

        mg.open_property_dialog(_FakeWidget(), SingleTypeHolder, existing=None)

        texts = widget_texts()
        assert "kind:" in texts
        assert "Choose Type" in texts
        assert "Choose Types" not in texts

    def test_list_type_base_field_offers_a_plural_chooser(self, mg):
        """``list[Type[Base]]`` must route to the multi-select chooser.

        Both of these tests previously asserted nothing, so the singular/plural
        dispatch -- the entire point of having two builders -- was unverified.
        """
        from typing import List as TList, Type as TType

        class FakeBase:
            pass

        class ListTypeHolder:
            def __init__(self, kinds: TList[TType[FakeBase]] = None):
                pass

        mg.open_property_dialog(_FakeWidget(), ListTypeHolder, existing=None)

        texts = widget_texts()
        assert "kinds:" in texts
        assert "Choose Types" in texts
        assert "Choose Type" not in texts


class TestOpenPropertyDialogEndToEnd:
    def test_no_editable_properties_shows_placeholder_label(self, mg):
        class Empty:
            def __init__(self):
                pass

        mg.open_property_dialog(_FakeWidget(), Empty, existing=None)

        texts = widget_texts()
        assert "No editable properties." in texts
        # New object (existing=None): only "Add", never Close/Delete.
        assert "Add" in texts
        assert "Delete" not in texts and "Close" not in texts

    def test_bool_and_text_fields_render_grouped_and_marked_as_customized(self, mg):
        """str and bool fields get grouped headers, and a value that differs
        from the constructor default is flagged with a trailing ``*``.

        That asterisk is the "customized value" highlight from issue #16; the
        old test called the dialog and asserted nothing, so losing the grouping
        *and* the highlight would both have gone unnoticed.
        """
        class Simple:
            def __init__(self, name: str = "x", locked: bool = False):
                pass

        customized = Simple()
        customized.name = "a torch"
        customized.locked = True
        mg.open_property_dialog(_FakeWidget(), Simple, existing=customized)
        texts = widget_texts()

        assert "Appearance" in texts and "State" in texts    # group headers
        assert "name*:" in texts and "locked*:" in texts     # customized marks
        assert "False" in texts and "True" in texts          # bool radio pair
        assert "Close" in texts and "Delete" in texts        # editing an object

        # Same class, values left at their defaults -> no asterisk.
        _FakeWidget.registry.clear()
        defaults = Simple()
        defaults.name = "x"
        defaults.locked = False
        mg.open_property_dialog(_FakeWidget(), Simple, existing=defaults)
        plain = widget_texts()

        assert "name:" in plain and "locked:" in plain
        assert "name*:" not in plain and "locked*:" not in plain

    def test_close_button_saves_existing_object_and_invokes_callback(self, mg):
        """Exercises on_add_save's existing-object branch (auto_save() +
        dlg.destroy()), previously entirely uncovered."""

        class Simple:
            def __init__(self, name: str = "x"):
                pass

        existing = Simple()
        existing.name = "a torch"

        result = {}
        mg.open_property_dialog(
            _FakeWidget(),
            Simple,
            existing=existing,
            callback=lambda inst: result.setdefault("saved", inst),
        )

        close_btn = find_button("Close")
        close_btn.init_kwargs["command"]()

        assert result["saved"] is existing

    def test_add_button_constructs_new_object_from_field_values(self, mg):
        """Exercises on_add_save's new-object branch: reads every entries[]
        getter, builds kwargs via ast.literal_eval, and constructs cls(**kwargs)."""

        class Simple:
            def __init__(self, name: str = "x"):
                self.name = name

        result = {}
        mg.open_property_dialog(
            _FakeWidget(),
            Simple,
            existing=None,
            callback=lambda inst: result.setdefault("created", inst),
        )

        add_btn = find_button("Add")
        add_btn.init_kwargs["command"]()

        assert isinstance(result["created"], Simple)

    def test_delete_button_invokes_callback_with_none_on_confirm(self, mg, monkeypatch):
        class Simple:
            def __init__(self, name: str = "x"):
                pass

        existing = Simple()
        monkeypatch.setattr(mg.messagebox, "askyesno", lambda *a, **k: True)

        result = {}
        mg.open_property_dialog(
            _FakeWidget(),
            Simple,
            existing=existing,
            callback=lambda inst: result.setdefault("deleted", inst),
        )

        delete_btn = find_button("Delete")
        delete_btn.init_kwargs["command"]()

        assert "deleted" in result
        assert result["deleted"] is None

    def test_delete_button_does_nothing_when_not_confirmed(self, mg, monkeypatch):
        class Simple:
            def __init__(self, name: str = "x"):
                pass

        existing = Simple()
        monkeypatch.setattr(mg.messagebox, "askyesno", lambda *a, **k: False)

        result = {}
        mg.open_property_dialog(
            _FakeWidget(),
            Simple,
            existing=existing,
            callback=lambda inst: result.setdefault("deleted", inst),
        )

        delete_btn = find_button("Delete")
        delete_btn.init_kwargs["command"]()

        assert "deleted" not in result


def ttk_calls_for(mg_module, widget_name):
    """Every call made to tkinter.ttk.<widget_name> during the test, in
    call order."""
    widget_mock = getattr(mg_module.ttk, widget_name)
    return list(widget_mock.call_args_list)
