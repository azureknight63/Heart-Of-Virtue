import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import get_origin, get_type_hints

from src.objects import Container


def test_allowed_subtypes_annotation_origin_is_list():
    """The allowed_subtypes parameter in Container.__init__ is annotated as
    list[type[Item]] (with ``from __future__ import annotations`` active).

    Because postponed evaluation stores the raw ``Parameter.annotation`` as a
    string, the correct way to obtain the effective annotation is
    ``typing.get_type_hints()`` — any code performing reflection on this
    parameter (e.g. property dialogs) must resolve hints the same way rather
    than reading the raw string. This test verifies that resolved path yields
    ``list`` as the origin.
    """
    # Properly resolved annotation using get_type_hints (what production code SHOULD use)
    hints = get_type_hints(Container.__init__)
    resolved_ann = hints['allowed_subtypes']

    assert get_origin(resolved_ann) is list, (
        "Resolved annotation origin is not list; got "
        f"{get_origin(resolved_ann)} for {resolved_ann!r}"
    )
