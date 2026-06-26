"""API routes blueprints."""

from .auth import auth_bp
from .world import world_bp
from .inventory import inventory_bp
from .combat import combat_bp
from .player import player_bp
from .saves import saves_bp
from .npc import npc_bp
from .reputation import reputation_bp
from .logs import logs_bp
from .feedback import feedback_bp
from .shop import shop_bp

__all__ = [
    "auth_bp",
    "world_bp",
    "inventory_bp",
    "combat_bp",
    "player_bp",
    "saves_bp",
    "npc_bp",
    "reputation_bp",
    "logs_bp",
    "feedback_bp",
    "shop_bp",
]
