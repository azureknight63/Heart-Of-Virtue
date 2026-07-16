"""Serializers for API responses.

Every serializer class is hardened via ``harden_serializer`` (issue #295) so it
never raises on a degraded/partial engine object and always emits
JSON-serializable output — see ``_safe.py``. The hardening runs here, on import
of the package, so it applies regardless of whether a serializer is imported
from the package or from its submodule.
"""

from src.api.serializers._safe import harden_serializer, json_safe

from src.api.serializers.item_serializer import ItemSerializer
from src.api.serializers.npc_serializer import NPCSerializer
from src.api.serializers.object_serializer import ObjectSerializer
from src.api.serializers.event_serializer import EventSerializer
from src.api.serializers.shop_serializer import ShopSerializer
from src.api.serializers.combat import (
    CombatStateSerializer,
    CombatantSerializer,
    MoveSerializer,
    StateEffectSerializer,
)
from src.api.serializers.npc_ai import (
    NPCAIStateSerializer,
    DialogueStateSerializer,
    NPCBehaviorProfileSerializer,
)
from src.api.serializers.reputation import NPCRelationshipSerializer
from src.api.serializers.inventory import (
    InventoryItemSerializer,
    InventorySerializer,
    EquipmentSlotSerializer,
    EquipmentSerializer,
    ItemDetailSerializer,
    ItemComparisonSerializer,
)

# Harden every serializer class in place. setattr mutates the shared class
# object, so callers that imported a serializer directly from its submodule get
# the hardened methods too.
for _serializer in (
    ItemSerializer, NPCSerializer, ObjectSerializer, EventSerializer,
    ShopSerializer, CombatStateSerializer, CombatantSerializer, MoveSerializer,
    StateEffectSerializer, NPCAIStateSerializer, DialogueStateSerializer,
    NPCBehaviorProfileSerializer, NPCRelationshipSerializer,
    InventoryItemSerializer, InventorySerializer, EquipmentSlotSerializer,
    EquipmentSerializer, ItemDetailSerializer, ItemComparisonSerializer,
):
    harden_serializer(_serializer)

__all__ = [
    "harden_serializer",
    "json_safe",
    "ItemSerializer",
    "NPCSerializer",
    "ObjectSerializer",
    "EventSerializer",
    "ShopSerializer",
    "CombatStateSerializer",
    "CombatantSerializer",
    "MoveSerializer",
    "StateEffectSerializer",
    "NPCAIStateSerializer",
    "DialogueStateSerializer",
    "NPCBehaviorProfileSerializer",
    "NPCRelationshipSerializer",
    "InventoryItemSerializer",
    "InventorySerializer",
    "EquipmentSlotSerializer",
    "EquipmentSerializer",
    "ItemDetailSerializer",
    "ItemComparisonSerializer",
]
