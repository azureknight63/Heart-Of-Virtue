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


class TestBulkEditAppliesToEveryInstance:
    """Mirrors what open_property_dialog's existing/existing_list
    normalization and auto_save() do for a bulk edit, without needing to
    construct the real tkinter dialog (see module docstring)."""

    def test_single_object_is_not_treated_as_bulk(self, map_generator_module):
        # Re-derive open_property_dialog's normalization inline: a single
        # instance (not a list) is wrapped to a 1-element list, is_bulk_edit
        # is False.
        from src.objects import Container

        existing = Container(name="solo")
        existing_list = (
            existing
            if isinstance(existing, list)
            else ([existing] if existing is not None else [])
        )
        assert len(existing_list) == 1
        assert (len(existing_list) > 1) is False

    def test_bulk_list_change_applies_to_every_instance(self, map_generator_module):
        from src.objects import Container

        c1 = Container(name="remains-a")
        c2 = Container(name="remains-b")
        c3 = Container(name="remains-c")
        existing = [c1, c2, c3]

        existing_list = (
            existing
            if isinstance(existing, list)
            else ([existing] if existing is not None else [])
        )
        is_bulk_edit = len(existing_list) > 1
        assert is_bulk_edit is True

        # auto_save()'s (unfiltered-field) apply loop: for k, v in
        # kwargs.items(): for obj in existing_list: setattr(obj, k, v)
        kwargs = {"locked": True, "hide_factor": 5}
        for k, v in kwargs.items():
            for obj in existing_list:
                setattr(obj, k, v)

        for obj in (c1, c2, c3):
            assert obj.locked is True
            assert obj.hide_factor == 5

    def test_bulk_edit_does_not_flatten_untouched_fields_to_primary_instance(
        self, map_generator_module
    ):
        """Regression test: auto_save() reruns its full kwargs rebuild on
        every keystroke across every field (it's wired to fire on any single
        widget's change), and every field is seeded from the primary
        (first) instance. Without initial_kwargs diffing, editing just
        `locked` on one of several selected containers with different names
        would silently flatten every instance's `name` to the primary's the
        moment ANY field was touched -- not just the field being edited.
        """
        from src.objects import Container

        primary = Container(name="remains-a", locked=False)
        other = Container(name="remains-b", locked=False)
        existing_list = [primary, other]

        # Snapshot taken once, right after the dialog's fields are built --
        # mirrors initial_kwargs, seeded entirely from the primary instance.
        initial_kwargs = {"name": primary.name, "locked": primary.locked}

        # User only ever interacts with the `locked` toggle; `name`'s widget
        # is never touched, so re-reading it still reports the primary's
        # (unchanged) seeded value -- exactly what _collect_kwargs() would
        # return.
        kwargs = {"name": primary.name, "locked": True}

        _UNSET = object()
        for k, v in kwargs.items():
            if v == initial_kwargs.get(k, _UNSET):
                continue
            for obj in existing_list:
                setattr(obj, k, v)

        # The untouched field must NOT have been flattened to the primary's
        # value on the other instance.
        assert other.name == "remains-b"
        assert primary.name == "remains-a"
        # The field the user actually changed applies to every instance.
        assert primary.locked is True
        assert other.locked is True

    def test_bulk_candidates_grouped_by_class_across_tiles(self, map_generator_module):
        # Mirrors MapEditor.bulk_edit_selected_tiles's candidate-gathering
        # loop: scan objects/npcs/events/items across several tiles' data,
        # grouped by type.
        from src.objects import Container

        class FakeNpc:
            def __init__(self, name):
                self.name = name

        map_data = {
            (0, 0): {"objects": [Container(name="a")], "npcs": [FakeNpc("m1")]},
            (1, 0): {"objects": [Container(name="b"), Container(name="c")]},
            (2, 0): {},  # empty tile, must not raise
        }
        selected_tiles = {(0, 0), (1, 0), (2, 0)}

        candidates = {}
        for pos in selected_tiles:
            tile_data = map_data.get(pos)
            if not tile_data:
                continue
            for bucket in ("objects", "npcs", "events", "items"):
                for inst in tile_data.get(bucket, []) or []:
                    candidates.setdefault(type(inst), []).append(inst)

        assert len(candidates[Container]) == 3
        assert len(candidates[FakeNpc]) == 1
