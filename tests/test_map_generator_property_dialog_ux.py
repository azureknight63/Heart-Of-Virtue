"""Regression coverage for issue #16's testable pieces: property tooltips in
the map editor's Edit Properties dialog (utils/map_generator.py).

Scope note: issue #16 asked for five UX improvements to the property dialog
(searchable filter, grouped properties, tooltips, bulk multi-tile editing,
highlighting customized properties). The filter, tooltip-description, and
highlight-customized-properties pieces are implemented directly in
open_property_dialog. Grouping and bulk multi-tile editing are left for a
follow-up -- they require a product decision (what grouping taxonomy; what
"apply to multiple tiles" should mean/how tiles get selected for it) rather
than a mechanical implementation, per CLAUDE.md's guidance not to invent
resolutions for ambiguous requirements.

Only _property_description() is meaningfully unit-testable here: it's a
pure function. The filter/highlight logic lives inline inside
open_property_dialog, which constructs real tkinter widgets and can't be
exercised without a display (this sandbox has no tkinter at all, and this
module has no existing test infrastructure or CI coverage to build on).
"""

import importlib
import sys
import types
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def map_generator_module():
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


class TestPropertyDescriptions:
    def test_known_property_has_a_real_description(self, map_generator_module):
        text = map_generator_module._property_description("locked")
        assert text
        assert text != map_generator_module._PROPERTY_DESCRIPTION_FALLBACK

    def test_unknown_property_gets_the_fallback_message(self, map_generator_module):
        text = map_generator_module._property_description("some_made_up_field_xyz")
        assert text == map_generator_module._PROPERTY_DESCRIPTION_FALLBACK

    def test_every_description_is_non_empty(self, map_generator_module):
        for name, text in map_generator_module._PROPERTY_DESCRIPTIONS.items():
            assert isinstance(text, str) and text.strip(), name
