import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import inspect
from typing import get_origin, get_type_hints

from src.objects import Container


def test_allowed_subtypes_annotation_origin_is_list():
    """The allowed_subtypes parameter in Container.__init__ is annotated as
    list[type[Item]] (with from __future__ import annotations active). We expect
    typing.get_origin on the effective annotation to be list. This test
    currently highlights the issue that open_property_dialog (and any code
    relying directly on Parameter.annotation) sees a raw string whose origin is
    None instead of list. The test intentionally asserts the desired (fixed)
    behavior so it will FAIL until the annotation is properly resolved before
    calling get_origin.
    """
    sig = inspect.signature(Container.__init__)
    param = sig.parameters['allowed_subtypes']

    # Raw annotation as stored (likely a string due to postponed evaluation)
    raw_ann = param.annotation

    # Document current (buggy) state for clarity (not asserting to avoid locking in bug)
    # If raw_ann is a str, get_origin will return None.
    if isinstance(raw_ann, str):
        # This prints helpful debug info when test fails
        print(f"DEBUG: raw annotation type is str: {raw_ann}")

    # Properly resolved annotation using get_type_hints (what production code SHOULD use)
    hints = get_type_hints(Container.__init__)
    resolved_ann = hints['allowed_subtypes']

    # Sanity: resolved origin should be list already (passive check)
    assert get_origin(resolved_ann) is list, (
        "Sanity check failed: resolved annotation origin is not list; got "
        f"{get_origin(resolved_ann)} for {resolved_ann!r}"
    )

    # The expectation for the production path: origin should be list. We assert this
    # directly on the raw annotation to drive a fix (will fail until code resolves it).
    assert get_origin(raw_ann) is list, (
        "Expected get_origin on raw Parameter.annotation for 'allowed_subtypes' to be 'list' "
        f"but got {get_origin(raw_ann)!r}. Raw annotation repr: {raw_ann!r}. "
        "This indicates the annotation is still a string and should be resolved with get_type_hints."
    )

