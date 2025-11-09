"""API routes blueprints."""

from .auth import auth_bp
from .world import world_bp
from .inventory import inventory_bp
from .equipment import equipment_bp
from .combat import combat_bp
from .player import player_bp
from .saves import saves_bp
from .npc import npc_bp
from .quest_rewards import quest_rewards_bp

__all__ = [
    "auth_bp",
    "world_bp",
    "inventory_bp",
    "equipment_bp",
    "combat_bp",
    "player_bp",
    "saves_bp",
    "npc_bp",
    "quest_rewards_bp",
]
