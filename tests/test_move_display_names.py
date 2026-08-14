"""Contracts for player-facing combat move display names."""

import inspect
import pytest

import src.moves as moves
from src.api.serializers.combat import CombatantSerializer
from src.moves._base import display_name_of


_CONCRETE_MOVE_CLASSES = [
    cls
    for _, cls in inspect.getmembers(moves, inspect.isclass)
    if issubclass(cls, moves.Move)
    and cls not in {moves.Move, moves.PassiveMove}
    and cls.__module__.startswith("src.moves")
]


_CONCRETE_MOVE_NAMES = [cls.__name__ for cls in _CONCRETE_MOVE_CLASSES]


def test_every_exported_move_declares_a_display_name():
    missing = []
    for cls in _CONCRETE_MOVE_CLASSES:
        display_name = cls.__dict__.get("display_name")
        if not isinstance(display_name, str) or not display_name.strip():
            missing.append(cls.__name__)
    assert missing == [], f"Moves missing required display_name: {missing}"


def test_npc_attack_uses_player_facing_display_name():
    assert moves.NpcAttack.display_name == "Attack"
    assert moves.GorranClub.display_name == "Club Strike"


def test_active_move_serialization_keeps_internal_name_and_adds_display_name():
    class MoveProbe:
        name = "NPC_Attack"
        display_name = "Attack"
        category = "Offensive"
        description = ""
        current_stage = 0
        beats_left = 1
        stage_beat = [2, 1, 0, 4]

        # Every real Move defines these (src/moves/_base.py); the serializer
        # calls them unguarded, so a probe standing in for a Move has to
        # provide them or it is testing a shape production never sees.
        def get_effective_range_max(self, user):
            return None

        def get_accuracy_falloff(self, user):
            return None

    class CombatantProbe:
        current_move = MoveProbe()
        known_moves = []

    result = CombatantSerializer._serialize_active_move(CombatantProbe())

    assert result["name"] == "NPC_Attack"
    assert result["display_name"] == "Attack"


def test_move_base_rejects_subclasses_without_display_name():
    class MissingDisplayName(moves.Move):
        pass

    with pytest.raises(TypeError, match="display_name"):
        MissingDisplayName(
            name="internal",
            description="",
            xp_gain=0,
            current_stage=0,
            beats_left=0,
            stage_announce=["", "", "", ""],
            target=None,
            user=None,
            stage_beat=[0, 0, 0, 0],
            targeted=False,
        )


def test_display_name_helper_falls_back_to_internal_name():
    probe = type("Probe", (), {"name": "Legacy"})()
    assert display_name_of(probe) == "Legacy"
