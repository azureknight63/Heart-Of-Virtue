"""Regression coverage for issue #131: opening/closing a Container's property
dialog in the map editor (utils/map_generator.py) without editing anything
wiped its items.

Root cause: Container.__init__ accepts both 'inventory' (the real, canonical
attribute) and 'items' (a legacy/test-only alias normalized into 'inventory'
at construction time and never stored on the instance). The property dialog
built a separate, independently-tracked widget for each constructor param,
so 'items' and 'inventory' ended up as two divergent widgets for one
underlying field -- and since 'items' is declared after 'inventory' in
Container's signature, it was processed second in the save loop and
silently overwrote whatever 'inventory' held, even when the user made no
edit at all.

The fix (get_editable_params in utils/map_generator.py) excludes 'items'
from the editable param list whenever 'inventory' is also a constructor
param, so only the real attribute gets a widget.

This module isn't executable in this sandbox (no tkinter), so the test
stubs out tkinter's submodules before import -- get_editable_params() only
uses inspect.signature() and never touches a real widget, so this is safe.
"""

import importlib
import sys
import types
from unittest.mock import MagicMock

import pytest

from src.objects import Container


@pytest.fixture
def map_generator_module():
    """Import utils.map_generator with tkinter stubbed out.

    Restores the real modules (or removes the stubs) afterward so this
    doesn't leak into other tests that might rely on tkinter's absence/
    presence.
    """
    tk_module_names = [
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.simpledialog",
        "tkinter.font",
    ]
    previous = {name: sys.modules.get(name) for name in tk_module_names}
    previous_map_generator = sys.modules.get("utils.map_generator")

    tk_stub = types.ModuleType("tkinter")
    sys.modules["tkinter"] = tk_stub
    for name in tk_module_names[1:]:
        submodule_name = name.rsplit(".", 1)[-1]
        submodule_stub = MagicMock(spec=types.ModuleType(name))
        sys.modules[name] = submodule_stub
        setattr(tk_stub, submodule_name, submodule_stub)
    # Attributes map_generator.py references directly off `tk` (e.g. tk.Tk,
    # tk.Frame, tk.StringVar) -- MagicMock auto-creates them on access.
    for attr in ("Tk", "Frame", "Toplevel", "Label", "Button", "Entry", "StringVar",
                 "BooleanVar", "Listbox", "Scrollbar", "Canvas", "Menu", "PhotoImage"):
        setattr(tk_stub, attr, MagicMock())

    try:
        sys.modules.pop("utils.map_generator", None)
        module = importlib.import_module("utils.map_generator")
        yield module
    finally:
        sys.modules.pop("utils.map_generator", None)
        for name, mod in previous.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod
        if previous_map_generator is not None:
            sys.modules["utils.map_generator"] = previous_map_generator


class TestContainerItemsAliasExcluded:
    def test_items_alias_excluded_when_inventory_present(self, map_generator_module):
        editable, _excluded = map_generator_module.get_editable_params(Container)
        names = [p.name for p in editable]

        assert "items" not in names
        assert "inventory" in names

    def test_editable_params_unaffected_for_classes_without_the_alias(
        self, map_generator_module
    ):
        # A plain class with only 'items' (no 'inventory' alias) must still
        # get a real, editable 'items' field -- the exclusion is scoped to
        # the specific alias collision, not a blanket ban on the name.
        class OnlyItems:
            def __init__(self, name: str = "x", items: list = None):
                self.name = name
                self.items = items or []

        editable, _excluded = map_generator_module.get_editable_params(OnlyItems)
        names = [p.name for p in editable]

        assert "items" in names

    def test_container_inventory_survives_a_no_op_property_edit(
        self, map_generator_module
    ):
        """End-to-end reproduction of the reported bug: build the exact
        kwargs the property dialog's auto_save() would apply for a
        Container opened and closed with no edits, and confirm the real
        inventory contents survive.
        """
        from src.items import Restorative, Shortsword

        # Two distinct classes so Container.__init__'s stack_items() doesn't
        # merge them -- keeps the "before" count unambiguous.
        container = Container(name="remains", inventory=[Restorative(), Shortsword()])
        original_items = list(container.inventory)
        assert len(container.inventory) == 2

        editable, _ = map_generator_module.get_editable_params(Container)
        # Simulate auto_save()'s kwargs build: every editable field's current
        # value, unchanged (i.e. no dialog interaction happened).
        kwargs = {
            p.name: getattr(container, p.name, None)
            for p in editable
            if hasattr(container, p.name)
        }
        assert "items" not in kwargs

        for k, v in kwargs.items():
            setattr(container, k, v)

        assert len(container.inventory) == 2
        assert container.inventory == original_items
