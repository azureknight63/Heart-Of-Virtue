"""Scenario registry."""

from .health import HealthScenario
from .auth import AuthScenario
from .world import WorldScenario
from .combat import CombatScenario
from .inventory import InventoryScenario
from .player import PlayerScenario
from .saves import SavesScenario
from .phase3 import Phase3Scenario
from .no_auth import NoAuthScenario
from .combat_edge import CombatEdgeScenario
from .inventory_actions import InventoryActionsScenario

_ALL_SCENARIOS = [
    HealthScenario(),
    AuthScenario(),
    WorldScenario(),
    CombatScenario(),
    InventoryScenario(),
    PlayerScenario(),
    SavesScenario(),
    Phase3Scenario(),
    NoAuthScenario(),
    CombatEdgeScenario(),
    InventoryActionsScenario(),
]


def get_scenarios(name: str = None):
    """Return all scenarios, or a filtered list if name is given."""
    if name:
        matches = [s for s in _ALL_SCENARIOS if s.name == name]
        return matches
    return list(_ALL_SCENARIOS)
