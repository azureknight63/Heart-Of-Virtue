# Heart of Virtue: Backend API Architecture (Phase 1 Sketch)

## Overview
This document outlines a Flask-based backend API that separates game logic from UI concerns. The API would be a **thin stateless layer** wrapping your existing game engine, allowing any frontend (terminal, web, mobile) to connect.

**Estimated Effort: 6-8 weeks** (including testing & debugging)

---

## Architecture Principles

1. **Minimal Refactoring**: Keep all existing game logic intact (Player, NPC, Universe, Items, Combat)
2. **Session Management**: API manages player sessions/saves via simple in-memory or database storage
3. **Stateless Endpoints**: Each request is independent; state is serialized in requests/responses
4. **JSON Serialization**: Game objects (Player, Items, NPCs) serialize to/from JSON
5. **Real-Time**: WebSockets for live combat updates; REST for turn-based world exploration

---

## Backend Structure

```
backend/
├── __init__.py
├── app.py                          # Flask app initialization, route registration
├── session_manager.py              # Player session lifecycle (create, load, save)
├── game_service.py                 # Wraps Player/Universe; returns serializable objects
├── serializers.py                  # Convert Player/Item/NPC to JSON and back
├── routes/
│   ├── __init__.py
│   ├── auth.py                     # GET /api/auth/session (create new game)
│   ├── world.py                    # GET /api/world/current, POST /api/world/move
│   ├── inventory.py                # GET /api/inventory, POST /api/inventory/equip, etc.
│   ├── combat.py                   # WebSocket: /ws/combat
│   ├── status.py                   # GET /api/status/player
│   └── save.py                     # POST /api/save, GET /api/saves
└── models/
    ├── __init__.py
    ├── session.py                  # Session object (player + metadata)
    └── serialized_objects.py       # Dataclasses for JSON responses
```

---

## Key API Endpoints

### Authentication & Session

```
POST /api/auth/new-game
  → Creates new Player, Universe, returns session_id
  ← { session_id, player: {...}, current_room: {...} }

POST /api/auth/load-game
  Body: { save_name }
  → Loads game from disk
  ← { session_id, player: {...}, current_room: {...} }

GET /api/auth/status
  → Checks if session_id is valid
  ← { valid, player_name, location }
```

### World Exploration

```
GET /api/world/current
  → Returns current room state
  ← { 
      name, description, items: [...], npcs: [...], 
      objects: [...], available_actions: [...]
    }

POST /api/world/move
  Body: { direction }  # "north", "south", "east", etc.
  → Moves player, evaluates events
  ← { success, current_room: {...}, combat_triggered?: true }

GET /api/world/map
  → Returns discovered map with player position
  ← { grid: [...], current_pos: (x, y) }
```

### Inventory & Equipment

```
GET /api/inventory
  → Lists player inventory
  ← { items: [...], weight: 5.2, weight_limit: 20 }

POST /api/inventory/take
  Body: { item_id }
  → Picks up item from room
  ← { success, inventory: [...] }

POST /api/inventory/drop
  Body: { item_id }
  → Drops item to room
  ← { success, inventory: [...], current_room: {...} }

POST /api/inventory/equip
  Body: { item_id }
  → Equips armor/weapon
  ← { success, equipped_items: [...], player_stats: {...} }

POST /api/inventory/use
  Body: { item_id }
  → Uses consumable
  ← { success, player: {...}, message: "..." }
```

### Player Status

```
GET /api/status/player
  → Returns full player state
  ← {
      name, hp, maxhp, fatigue, maxfatigue, level, exp,
      stats: { strength, finesse, speed, ... },
      inventory: [...], equipped: [...],
      resistances: {...}
    }

GET /api/status/skills
  → Returns learned skills & progression
  ← { skills: [...], skill_trees: {...} }

POST /api/status/learn-skill
  Body: { skill_id }
  → Learns a new skill
  ← { success, skills: [...] }
```

### Combat (WebSocket)

```
WS /ws/combat?session_id=XXX
  
  Client → Server:
    { action: "use_move", move_id, target_id? }
    { action: "check" }
    { action: "check_move_status" }
  
  Server → Client (push updates):
    { type: "combat_state", enemies: [...], allies: [...], battlefield: {...} }
    { type: "move_executed", actor, move_name, result }
    { type: "battlefield_update", combatant: {...} }
    { type: "combat_end", victory: true|false }
```

### Save/Load

```
GET /api/saves
  → Lists all save files
  ← { saves: [{ name, timestamp, character_name, level }] }

POST /api/save
  Body: { save_name }
  → Saves current player to disk
  ← { success, save_name, timestamp }

DELETE /api/saves/{save_name}
  → Deletes a save file
  ← { success }
```

---

## Core Implementation: `game_service.py`

This is the **heart** of Phase 1. It wraps your existing game logic:

```python
class GameService:
    """Wraps Player/Universe logic for API use."""
    
    def __init__(self, player: Player):
        self.player = player
        self.universe = player.universe  # Already initialized
    
    # World Navigation
    def get_current_room_data(self) -> dict:
        """Serialize current room to JSON."""
        room = self.player.current_room
        return {
            "name": room.name,
            "description": room.intro_text(),
            "items": [serialize_item(i) for i in room.items_here],
            "npcs": [serialize_npc(n) for n in room.npcs_here],
            "objects": [serialize_object(o) for o in room.objects_here],
            "available_actions": [a.name for a in room.available_actions()]
        }
    
    def move_player(self, direction: str) -> dict:
        """Execute movement and return new state."""
        direction_map = {
            "north": (0, -1), "south": (0, 1),
            "east": (1, 0), "west": (-1, 0),
            "northeast": (1, -1), "northwest": (-1, -1),
            "southeast": (1, 1), "southwest": (-1, 1)
        }
        if direction not in direction_map:
            return {"success": False, "error": "Invalid direction"}
        
        dx, dy = direction_map[direction]
        
        # Call existing player.move() method
        try:
            self.player.move(dx, dy)
            # Check for combat trigger
            combat_list = functions.check_for_combat(self.player)
            return {
                "success": True,
                "current_room": self.get_current_room_data(),
                "combat_triggered": len(combat_list) > 0
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Inventory Management
    def get_inventory(self) -> dict:
        """Serialize player inventory."""
        return {
            "items": [serialize_item(i) for i in self.player.inventory],
            "weight": self.player.weight_current,
            "weight_limit": self.player.weight_tolerance
        }
    
    def take_item(self, item_id: str) -> dict:
        """Player takes item from room."""
        # Find item in current room by ID
        item = next(
            (i for i in self.player.current_room.items_here if id(i) == int(item_id)),
            None
        )
        if not item:
            return {"success": False, "error": "Item not found"}
        
        try:
            self.player.take(item)  # Existing method
            return {
                "success": True,
                "inventory": self.get_inventory(),
                "current_room": self.get_current_room_data()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def equip_item(self, item_id: str) -> dict:
        """Equip armor/weapon."""
        item = next((i for i in self.player.inventory if id(i) == int(item_id)), None)
        if not item:
            return {"success": False, "error": "Item not in inventory"}
        
        try:
            # Call existing equip logic (encapsulate into a method if needed)
            item.isequipped = True
            functions.refresh_stat_bonuses(self.player)
            return {
                "success": True,
                "equipped_items": [serialize_item(i) for i in self.player.get_equipped_items()],
                "player_stats": serialize_player_stats(self.player)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Combat
    def start_combat(self) -> dict:
        """Initialize combat session, return initial state."""
        if not self.player.combat_list:
            return {"success": False, "error": "No enemies to combat"}
        
        return {
            "success": True,
            "enemies": [serialize_npc(e) for e in self.player.combat_list],
            "allies": [serialize_npc(a) for a in self.player.combat_list_allies],
            "battlefield": serialize_battlefield(self.player)
        }
    
    def execute_combat_move(self, move_id: str, target_id: str = None) -> dict:
        """Execute a move in combat."""
        move = next((m for m in self.player.known_moves if id(m) == int(move_id)), None)
        if not move:
            return {"success": False, "error": "Move not found"}
        
        try:
            # Call existing move execution
            if target_id:
                target = next(
                    (e for e in self.player.combat_list if id(e) == int(target_id)),
                    None
                )
                if target:
                    move.target = target
            
            move.execute(self.player)
            
            return {
                "success": True,
                "battlefield": serialize_battlefield(self.player),
                "player_hp": self.player.hp,
                "player_fatigue": self.player.fatigue
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Status
    def get_player_status(self) -> dict:
        """Full player serialization."""
        return serialize_player(self.player)
    
    # Save/Load
    def save_game(self, save_name: str) -> dict:
        """Save player to disk."""
        try:
            functions.save(self.player, save_name)
            return {"success": True, "save_name": save_name}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def load_game(self, save_name: str) -> dict:
        """Load player from disk."""
        try:
            player = functions.load(save_name)
            if not player:
                return {"success": False, "error": "Save not found"}
            self.player = player
            self.universe = player.universe
            return {"success": True, "player": serialize_player(player)}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

---

## Serialization: `serializers.py`

Convert game objects to/from JSON:

```python
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class SerializedItem:
    id: str
    name: str
    description: str
    weight: float
    equipped: bool
    value: int
    type: str  # "weapon", "armor", "consumable", etc.
    properties: Dict[str, Any]

def serialize_item(item) -> SerializedItem:
    """Convert Item to JSON-safe dict."""
    return {
        "id": str(id(item)),
        "name": item.name,
        "description": str(item),
        "weight": getattr(item, "weight", 0),
        "equipped": getattr(item, "isequipped", False),
        "value": getattr(item, "value", 0),
        "type": item.__class__.__name__.lower(),
        "properties": {
            "base_damage": getattr(item, "base_damage", None),
            "damage_type": getattr(item, "damage_type", None),
            "armor_rating": getattr(item, "armor_rating", None),
        }
    }

def serialize_npc(npc) -> dict:
    """Convert NPC to JSON."""
    return {
        "id": str(id(npc)),
        "name": npc.name,
        "hp": npc.hp,
        "maxhp": npc.maxhp,
        "level": getattr(npc, "level", 1),
        "position": {
            "x": npc.combat_position.x if npc.combat_position else None,
            "y": npc.combat_position.y if npc.combat_position else None,
            "facing": str(npc.combat_position.facing) if npc.combat_position else None
        } if hasattr(npc, "combat_position") else None
    }

def serialize_player(player) -> dict:
    """Full player serialization."""
    return {
        "id": str(id(player)),
        "name": player.name,
        "level": player.level,
        "exp": player.skill_exp.get("Basic", 0),
        "hp": player.hp,
        "maxhp": player.maxhp,
        "fatigue": player.fatigue,
        "maxfatigue": player.maxfatigue,
        "stats": {
            "strength": player.strength,
            "finesse": player.finesse,
            "speed": player.speed,
            "endurance": player.endurance,
            "charisma": player.charisma,
            "intelligence": player.intelligence,
            "faith": player.faith,
        },
        "inventory": [serialize_item(i) for i in player.inventory],
        "equipped": [serialize_item(i) for i in player.get_equipped_items()],
        "location": {
            "map": player.map.get("name", "unknown"),
            "x": player.location_x,
            "y": player.location_y
        },
        "resistances": player.resistance,
        "status_effects": [{"name": s.name, "duration": s.duration} for s in player.states]
    }

def serialize_battlefield(player) -> dict:
    """Combat battlefield state."""
    return {
        "player": {
            "position": {
                "x": player.combat_position.x,
                "y": player.combat_position.y,
                "facing": str(player.combat_position.facing)
            } if player.combat_position else None,
            "hp": player.hp,
            "fatigue": player.fatigue
        },
        "enemies": [serialize_npc(e) for e in player.combat_list],
        "allies": [serialize_npc(a) for a in player.combat_list_allies],
        "available_moves": [
            {
                "id": str(id(m)),
                "name": m.name,
                "viable": m.viable(),
                "fatigue_cost": getattr(m, "fatigue_cost", 0),
                "cooldown": getattr(m, "cooldown", 0)
            }
            for m in player.known_moves
        ]
    }
```

---

## Flask Routes: `routes/world.py` (Example)

```python
from flask import Blueprint, request, jsonify
from backend.game_service import GameService
from backend.session_manager import SessionManager

bp = Blueprint("world", __name__, url_prefix="/api/world")
session_mgr = SessionManager()

@bp.route("/current", methods=["GET"])
def get_current_room():
    session_id = request.args.get("session_id")
    game_service = session_mgr.get_game_service(session_id)
    if not game_service:
        return jsonify({"error": "Invalid session"}), 401
    
    return jsonify(game_service.get_current_room_data())

@bp.route("/move", methods=["POST"])
def move_player():
    session_id = request.args.get("session_id")
    data = request.json
    direction = data.get("direction")
    
    game_service = session_mgr.get_game_service(session_id)
    if not game_service:
        return jsonify({"error": "Invalid session"}), 401
    
    result = game_service.move_player(direction)
    return jsonify(result), 200 if result["success"] else 400

@bp.route("/map", methods=["GET"])
def get_map():
    session_id = request.args.get("session_id")
    game_service = session_mgr.get_game_service(session_id)
    if not game_service:
        return jsonify({"error": "Invalid session"}), 401
    
    # Serialize player's discovered map
    player = game_service.player
    grid = {}
    for (x, y), tile in player.map.items():
        if (x, y) == 'name':
            continue
        if tile.discovered:
            grid[(x, y)] = {
                "visited": tile.last_entered > 0,
                "symbol": getattr(tile, "symbol", "●")
            }
    
    return jsonify({
        "grid": grid,
        "current_pos": [player.location_x, player.location_y]
    })
```

---

## Session Management: `session_manager.py`

```python
import uuid
import pickle
from typing import Optional
from backend.game_service import GameService

class SessionManager:
    """In-memory session storage (can be replaced with Redis/database later)."""
    
    def __init__(self):
        self.sessions = {}  # session_id -> GameService
    
    def create_new_game(self) -> tuple[str, GameService]:
        """Create new player and game session."""
        from src.player import Player
        from src.universe import Universe
        
        player = Player()
        player.universe = Universe(player)
        player.universe.build(player)
        
        session_id = str(uuid.uuid4())
        game_service = GameService(player)
        self.sessions[session_id] = game_service
        
        return session_id, game_service
    
    def load_game(self, save_name: str) -> tuple[str, GameService]:
        """Load saved game into session."""
        import src.functions as functions
        
        player = functions.load(save_name)
        if not player:
            raise ValueError(f"Save '{save_name}' not found")
        
        session_id = str(uuid.uuid4())
        game_service = GameService(player)
        self.sessions[session_id] = game_service
        
        return session_id, game_service
    
    def get_game_service(self, session_id: str) -> Optional[GameService]:
        """Get active game service."""
        return self.sessions.get(session_id)
    
    def save_and_close(self, session_id: str, save_name: str) -> bool:
        """Save game and close session."""
        game_service = self.sessions.get(session_id)
        if not game_service:
            return False
        
        import src.functions as functions
        functions.save(game_service.player, save_name)
        del self.sessions[session_id]
        return True
```

---

## Flask App: `app.py`

```python
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from backend.routes import auth, world, inventory, combat, status, save

def create_app():
    app = Flask(__name__)
    CORS(app)
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    # Register route blueprints
    app.register_blueprint(auth.bp)
    app.register_blueprint(world.bp)
    app.register_blueprint(inventory.bp)
    app.register_blueprint(status.bp)
    app.register_blueprint(save.bp)
    
    # WebSocket for combat
    combat.init_socketio(socketio)
    
    return app, socketio

if __name__ == "__main__":
    app, socketio = create_app()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
```

---

## Refactoring Requirements (Minimal)

To make this work smoothly, only these small changes to existing code:

1. **Wrap `player.move()` in exception handling** (already mostly there)
2. **Extract equip logic into a method** (currently scattered in player.py)
3. **Add getters for combat state** (battlefield data)
4. **Make serialization functions** (modest effort, ~200 lines)

**No core game logic changes needed.** All existing Player/Combat/NPC code works as-is.

---

## Testing Phase 1

1. **Unit tests** for `GameService` methods
2. **Integration tests** for API endpoints (Flask test client)
3. **Manual test**: Launch API, call `/api/auth/new-game`, verify Player is created
4. **Serialization tests**: Ensure Items/NPCs serialize/deserialize correctly

---

## Migration Path to Web Frontend

Once Phase 1 is solid:

1. **JavaScript/React client** makes HTTP requests to these endpoints
2. **WebSocket connection** for real-time combat
3. **Responsive UI** built separately
4. **Terminal version** can keep existing code OR switch to HTTP client

---

## Estimated Breakdown

| Task | Duration |
|------|----------|
| Set up Flask + structure | 1 week |
| Implement GameService | 2 weeks |
| Serializers | 1 week |
| API Routes (all endpoints) | 2 weeks |
| Session management | 3-4 days |
| WebSocket combat layer | 1 week |
| Testing + debugging | 1-2 weeks |
| **Total** | **6-8 weeks** |

---

## Questions to Answer Before Starting

1. **Database?** In-memory sessions for MVP, or Redis/PostgreSQL?
2. **Authentication?** Simple session IDs for now, or user accounts later?
3. **Persistence?** Keep existing pickle format, or migrate to JSON?
4. **Rate limiting?** Needed if public API?
5. **CORS?** Allow all origins (dev), or restrict to specific frontend domains?

---

## Next Steps

1. Review this architecture with your codebase in mind
2. Identify any missing pieces or conflicts
3. Prototype `GameService` with one endpoint (e.g., `get_current_room()`)
4. Test serialization with your actual Player/Item objects
5. Build out routes incrementally

This is a **low-risk, high-reward** first step toward web support. Even if you don't complete Phase 2 (React frontend) for 6 months, the API is ready whenever you are.


