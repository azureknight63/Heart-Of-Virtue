"""The combat move picker the harness scenarios and ``tests/api`` share.

Dependency-free on purpose: ``tests/api`` fight drivers import it without
running ``tools/harness/scenarios/__init__.py`` (and with it every scenario
module and the harness client).
"""

from typing import Optional

#: Wait duration sent when a ``number_input`` prompt carries no ``default``.
FALLBACK_NUMBER_INPUT = 5
#: Direction sent when a ``direction_selection`` prompt lists none.
FALLBACK_DIRECTION = "north"


def _pick_number(options) -> Optional[dict]:
    """``number_input``: options is a dict with ``min``/``max``/``default``."""
    default = (
        options.get("default", FALLBACK_NUMBER_INPUT)
        if isinstance(options, dict) else FALLBACK_NUMBER_INPUT
    )
    return {"move_type": "number", "move_id": str(default)}


def _pick_direction(options) -> Optional[dict]:
    """``direction_selection``: options is a list[str] (e.g. ``["north", ...]``)."""
    direction = (
        options[0] if isinstance(options, list) and options else FALLBACK_DIRECTION
    )
    return {"move_type": "direction", "direction": direction}


def _pick_target(options) -> Optional[dict]:
    """``target_selection``: options is a list[dict] of viable targets."""
    targets = [o for o in options if isinstance(o, dict) and o.get("id")]
    if not targets:
        return None
    return {"move_type": "target", "target_id": targets[0]["id"]}


# The multi-step prompts: a move already chosen is awaiting a direction, a
# number (Wait duration) or a target before it executes. Anything else is the
# ordinary move menu.
_SUB_STAGE_PICKERS = {
    "direction_selection": _pick_direction,
    "number_input": _pick_number,
    "target_selection": _pick_target,
}

#: The ``input_type`` values of a multi-step prompt. Derived from the dispatch
#: above, so a sub-stage the picker handles is always one the callers skip.
SUB_STAGE_INPUT_TYPES = tuple(_SUB_STAGE_PICKERS)


def pick_move_body(battle: dict) -> Optional[dict]:
    """The ``/api/combat/move`` request body for Jean's current prompt, or None
    when nothing is usable.

    ``available_options`` changes shape with ``input_type`` (see
    ``combat_adapter.py``'s ``_handle_*_selection``):

    - ``"move_selection"``      -> list[dict] (the normal move menu)
    - ``"target_selection"``    -> list[dict] (viable targets)
    - ``"direction_selection"`` -> list[str]  (e.g. ``["north", ...]``)
    - ``"number_input"``        -> dict with ``"min"``/``"max"``/``"default"``

    The move menu is ``_pick_menu_move``. Non-dict menu entries are skipped
    here; a caller that treats them as a contract violation checks for them
    itself.

    The one move picker the harness scenarios and the ``tests/api`` fight
    drivers share (issue #706).
    """
    options = battle.get("available_options", [])
    input_type = battle.get("input_type", "move_selection")

    sub_stage = _SUB_STAGE_PICKERS.get(input_type)
    if sub_stage is not None:
        return sub_stage(options)
    return _pick_menu_move(options)


def _pick_menu_move(options: list) -> Optional[dict]:
    """The body for the ordinary move menu: the first available Offensive move
    with a viable target, else Advance, else Wait (each with its first viable
    target, if any). None when none of those is available."""
    move_index = None
    target_id = None
    advance_opt = None
    wait_opt = None
    for opt in options:
        if not isinstance(opt, dict) or not opt.get("available"):
            continue
        if opt.get("category") == "Offensive" and opt.get("viable_targets"):
            move_index = opt.get("index")
            target_id = opt["viable_targets"][0]["id"]
            break
        if opt.get("name") == "Advance" and advance_opt is None:
            advance_opt = opt
        if opt.get("name") == "Wait" and wait_opt is None:
            wait_opt = opt

    if move_index is None:
        chosen = advance_opt or wait_opt
        if chosen is None:
            return None
        move_index = chosen.get("index")
        targets = chosen.get("viable_targets", [])
        if targets:
            target_id = targets[0]["id"]

    body: dict = {"move_type": "move", "move_id": str(move_index)}
    if target_id:
        body["target_id"] = target_id
    return body
