"""Debug / combat-testing endpoints (test mode only).

Replaces TheAdjutant's legacy terminal input() menu. These routes drive the
parametrized operations on TheAdjutant (src/npc/_adjutant.py) so the combat
testing arena can be configured over the web API: set Jean's stats, restore,
learn skills, and manage the NPC roster on each arena tile.

The blueprint is registered ONLY when app.config["TESTING"] is true (see
create_app), so it is never reachable in production.
"""

from flask import Blueprint, jsonify, request
from src.api.middleware.auth import get_session_and_player

debug_bp = Blueprint("debug", __name__)


_adjutant_instance = None


def _adjutant():
    """Lazily create a shared TheAdjutant; operations take the player explicitly."""
    global _adjutant_instance
    if _adjutant_instance is None:
        from src.npc._adjutant import TheAdjutant

        _adjutant_instance = TheAdjutant()
    return _adjutant_instance


def _run(operation):
    """Resolve the session player and run `operation(adjutant, player, body)`."""
    _sm, _session, player, error = get_session_and_player()
    if error:
        return error
    # Coerce a non-object body (list/string/number/bool) to {}. ``or {}`` only
    # catches falsy values, so a truthy non-dict body would reach ``body.get``
    # / ``body[...]`` and surface as a 500 instead of a structured 400.
    raw_body = request.get_json(silent=True)
    body = raw_body if isinstance(raw_body, dict) else {}
    try:
        result = operation(_adjutant(), player, body)
        return jsonify(result), 200
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify({"success": False, "error": str(exc)}), 500


# --- Player stat operations -------------------------------------------------

@debug_bp.route("/player", methods=["GET"])
def player_state():
    return _run(lambda adj, player, body: adj.player_state(player))


@debug_bp.route("/player/hp", methods=["POST"])
def set_hp():
    return _run(lambda adj, player, body: adj.set_hp(player, body["hp"], body["maxhp"]))


@debug_bp.route("/player/level", methods=["POST"])
def set_level():
    return _run(
        lambda adj, player, body: adj.set_level(player, body["level"], body["exp"])
    )


@debug_bp.route("/player/attributes", methods=["POST"])
def set_attributes():
    return _run(
        lambda adj, player, body: adj.set_attributes(player, body.get("attributes", {}))
    )


@debug_bp.route("/player/heat", methods=["POST"])
def set_heat():
    return _run(lambda adj, player, body: adj.set_heat(player, body["heat"]))


@debug_bp.route("/player/restore", methods=["POST"])
def restore():
    return _run(lambda adj, player, body: adj.restore(player))


@debug_bp.route("/player/learn-skills", methods=["POST"])
def learn_skills():
    return _run(lambda adj, player, body: adj.learn_all_skills(player))


@debug_bp.route("/player/skills", methods=["GET"])
def list_skills():
    return _run(lambda adj, player, body: {"skills": adj.list_skills(player)})


# --- Party ally progression ---------------------------------------------------

@debug_bp.route("/allies", methods=["GET"])
def ally_state():
    return _run(lambda adj, player, body: adj.ally_state(player))


@debug_bp.route("/allies/progression", methods=["POST"])
def set_ally_progression():
    return _run(
        lambda adj, player, body: adj.set_ally_progression(
            player, body["name"], body.get("level"), body.get("exp")
        )
    )


# --- Arena combatant management ---------------------------------------------

@debug_bp.route("/arena", methods=["GET"])
def arena_rosters():
    return _run(lambda adj, player, body: {"rosters": adj.arena_rosters(player)})


@debug_bp.route("/arena/add", methods=["POST"])
def arena_add():
    return _run(
        lambda adj, player, body: adj.add_combatant(
            player, body["arena"], body["cls_name"]
        )
    )


@debug_bp.route("/arena/remove", methods=["POST"])
def arena_remove():
    return _run(
        lambda adj, player, body: adj.remove_combatant(
            player, body["arena"], body["index"]
        )
    )


@debug_bp.route("/arena/clear", methods=["POST"])
def arena_clear():
    return _run(lambda adj, player, body: adj.clear_room(player, body["arena"]))


@debug_bp.route("/arena/stats", methods=["POST"])
def arena_stats():
    return _run(
        lambda adj, player, body: adj.set_combatant_stats(
            player, body["arena"], body["index"], body.get("stats", {})
        )
    )
