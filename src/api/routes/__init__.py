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
from .reputation import reputation_bp
from .quest_chains import quest_chains_bp
from .npc_availability import npc_availability_bp
from .dialogue_context import dialogue_context_bp
from .logs import logs_bp
from .feedback import feedback_bp

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
    "reputation_bp",
    "quest_chains_bp",
    "npc_availability_bp",
    "dialogue_context_bp",
    "logs_bp",
    "feedback_bp",
]
