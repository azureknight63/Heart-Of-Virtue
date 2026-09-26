"""The combat move picker the harness scenarios and ``tests/api`` share.

Dependency-free on purpose: ``tests/api`` fight drivers import it without
running ``tools/harness/scenarios/__init__.py`` (and with it every scenario
module and the harness client).
"""

from typing import Optional

#: The ``input_type`` values of a multi-step prompt: a move already chosen is
#: awaiting a direction, a number (Wait duration) or a target before it
#: executes. Anything else is the ordinary move menu.
SUB_STAGE_INPUT_TYPES = ("direction_selection", "number_input", "target_selection")


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

    if input_type == "number_input":
        default = options.get("default", 5) if isinstance(options, dict) else 5
        return {"move_type": "number", "move_id": str(default)}
    if input_type == "direction_selection":
        direction = options[0] if isinstance(options, list) and options else "north"
        return {"move_type": "direction", "direction": direction}
    if input_type == "target_selection":
        targets = [o for o in options if isinstance(o, dict) and o.get("id")]
        if not targets:
            return None
        return {"move_type": "target", "target_id": targets[0]["id"]}
    return _pick_menu_move(options)


def _pick_menu_move(options) -> Optional[dict]:
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
