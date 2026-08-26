"""Regression coverage for issue #16's testable pieces: the map editor's
Edit Properties dialog (utils/map_generator.py) got a search filter,
per-property tooltips, customized-value highlighting, thematic grouping,
and cross-tile bulk editing.

Only the pure-logic pieces are meaningfully unit-testable here:
_property_description(), _property_group(), _grouped_field_layout(), and
the existing/existing_list normalization open_property_dialog uses for bulk
edit. The widget-construction code (search box wiring, tooltip popups,
label styling, the actual dialog/canvas) can't be exercised without a
display -- this sandbox has no tkinter at all, and this module has no
existing test infrastructure or CI coverage to build on.
"""

import importlib
import sys
import types
from unittest.mock import MagicMock

import pytest

from conftest import restore_mapgen_modules, snapshot_and_clear_mapgen_modules


@pytest.fixture(scope="module")
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
    previous_mapgen = snapshot_and_clear_mapgen_modules()

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
        module = importlib.import_module("utils.map_generator")
        yield module
    finally:
        restore_mapgen_modules(previous_mapgen)
        for name, mod in previous.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


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


class TestPropertyGrouping:
    def test_known_names_map_to_their_bucket(self, map_generator_module):
        assert map_generator_module._property_group("name") == "Appearance"
        assert map_generator_module._property_group("locked") == "State"
        assert map_generator_module._property_group("teleport_map") == "Location"
        assert map_generator_module._property_group("inventory") == "Contents"

    def test_unknown_name_falls_back_to_other(self, map_generator_module):
        assert map_generator_module._property_group("some_made_up_field") == "Other"

    def test_layout_groups_container_params_with_headers_and_no_gaps(
        self, map_generator_module
    ):
        from src.objects import Container

        editable, _ = map_generator_module.get_editable_params(Container)
        layout = map_generator_module._grouped_field_layout(editable, col_count=2)

        headers = [e for e in layout if e["kind"] == "header"]
        fields = [e for e in layout if e["kind"] == "field"]

        # Every editable param is placed exactly once.
        assert sorted(e["param"].name for e in fields) == sorted(
            p.name for p in editable
        )
        # More than one group is present for Container, so headers should
        # actually appear (not a single pointless "Other" header).
        assert len(headers) >= 2
        # No two fields collide on the same (row, col) cell.
        cells = [(e["row"], e["col"]) for e in fields]
        assert len(cells) == len(set(cells))
        # Columns never exceed col_count - 1.
        assert all(e["col"] in (0, 1) for e in fields)

    def test_layout_omits_headers_when_everything_falls_in_one_group(
        self, map_generator_module
    ):
        import inspect

        class OnlyAppearanceFields:
            def __init__(self, name: str = "x", description: str = "y"):
                pass

        params = [
            p
            for p in inspect.signature(OnlyAppearanceFields.__init__).parameters.values()
            if p.name != "self"
        ]
        layout = map_generator_module._grouped_field_layout(params, col_count=1)
        assert all(e["kind"] == "field" for e in layout)


class TestClassDiscovery:
    def _allowed_classes(self, map_generator_module, base_class_name):
        paths = map_generator_module._get_module_paths_for_class(base_class_name)
        class_info = {}
        for path in paths:
            class_info.update(
                map_generator_module.parse_module_classes(
                    path, map_generator_module.project_root
                )
            )
        class_info = map_generator_module.build_class_hierarchy(class_info)
        return map_generator_module.filter_classes(class_info, base_class_name)

    def test_npc_discovery_includes_transitive_friend_descendants(
        self, map_generator_module
    ):
        allowed = self._allowed_classes(map_generator_module, "NPC")

        assert {"Friend", "Mynx", "Gorran", "Mara", "Devet", "Liss"}.issubset(
            allowed
        )

    def test_npc_discovery_keeps_direct_merchant_descendants(
        self, map_generator_module
    ):
        allowed = self._allowed_classes(map_generator_module, "NPC")

        assert {
            "Merchant",
            "MiloCurioDealer",
            "JamboHealsU",
        }.issubset(allowed)


# NOTE: the bulk-edit tests that used to live here have MOVED to
# ``tests/test_map_generator_open_property_dialog.py``
# (``TestBulkEdit`` / ``TestBulkEditCandidateGathering``).
#
# They were not tests of ``utils/mapgen`` at all: each one re-implemented
# open_property_dialog's ``existing``-normalization and auto_save() apply loop,
# or MapEditor.bulk_edit_selected_tiles's candidate-gathering loop, *inline in
# the test body*, then asserted on that copy. Their own docstrings said so
# ("Re-derive open_property_dialog's normalization inline", "Mirrors what
# ... does"). No change to the production code could fail them --
# ``test_single_object_is_not_treated_as_bulk`` computed a list in the test and
# asserted ``len(...) == 1``.
#
# The replacements drive the real ``open_property_dialog`` and the real
# ``MapEditor.bulk_edit_selected_tiles`` against the permissive fake-widget
# stub that file already maintains, including the untouched-field-flattening
# regression this class was written to guard.
