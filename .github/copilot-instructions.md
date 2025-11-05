# Heart of Virtue - AI Coding Agent Instructions

## Project Overview
A text-based RPG following Jean Claire through a tile-based world with turn-based combat, inventory management, and NPC interactions (some of which may involve LLM-based behavior). Built with Python 3.13, heavy use of `neotermcolor` for colored terminal output, and `asciimatics` for visual effects.

## Architecture & Core Systems

### Module Import Pattern (CRITICAL)
The codebase uses a **dual-namespace import pattern** to support both direct execution and test isolation:

- **Production imports**: `src.module_name` (canonical namespace for coverage tracking)
- **Test compatibility**: `conftest.py` shims `src.*` modules into bare names (`functions`, `items`, `npc`, etc.)
- **Type checking imports**: Use `if TYPE_CHECKING:` guards to avoid circular dependencies

**When adding/editing imports:**
```python
# ✅ Correct - uses src. prefix for coverage
import functions as functions
from items import Item
Prefer importing specific classes/functions over wildcard imports.

# ✅ Type hints only
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from player import Player

# ❌ Avoid in production code (causes problems)
import src.functions  # only acceptable in tests
from src import functions
from src.items import Item
```

### Game State Architecture
- **Universe**: Container for all maps, global story switches, player reference, and game tick counter
- **MapTile**: Base class for world tiles at (x, y) coordinates; contains `npcs_here`, `items_here`, `events_here`, `objects_here`
- **Player**: 1600+ line class managing inventory, stats, equipment, combat, skill trees, and save/load
- **NPC**: Creatures with combat stats, AI behavior, inventory, resistance profiles, and merchant capabilities

### Map System (JSON-First Workflow)
Maps are stored in `src/resources/maps/*.json` and edited via the **GUI map editor** at `utils/map_generator.py`:

```bash
python utils/map_generator.py
```

**Map JSON structure:**
- Tiles keyed by `"(x, y)"` coordinate strings
- Each tile contains: `description`, `exits`, `events`, `items`, `npcs`, `objects`
- Objects serialized with `__class__`, `__module__`, `props` for full reconstruction

**Adding new maps:**
1. Use the map_generator GUI (File → New Map)
2. Save to `src/resources/maps/yourmap.json`
3. Maps auto-load on game start via `Universe._load_all_json_maps()

As an agent, you may be asked to create or modify map files. You can do this directly in the JSON format, so long as you reference existing maps, the map editor code, and universe loading functions for structure and consistency.

**Module name rule**: When serializing, use `items`, `npc`, `events`, etc. - **NEVER** `src.items` or you'll get deserialization errors.

### Item & Object Hierarchy
**Items** (carried in inventory):
- Base class: `Item` (in `src/items.py`)
- Major types: `Weapon`, `Armor`, `Boots`, `Helm`, `Gloves`, `Accessory`, `Consumable`, `Special`, `Gold`
- All items support: `merchandise` flag (prevents use until purchased), `hidden`/`hide_factor`, `equip_states`, resistance modifiers

**Objects** (exist on tiles):
- Base class: `Object` (in `src/objects.py`)
- Examples: `Container`, `Chest`, `Door`, `Shrine`
- Support `events` list, `keywords` for custom interactions

Objects are (typically) non-movable, persistent world elements that players can interact with, often triggering events or containing items.

**Events** (trigger on tile entry or combat):
- Base class: `Event` (in `src/events.py`)
- Story events in `src/story/` (e.g., `ch01.py`, `effects.py`)
- Events have `repeat` flag, `params`, and custom `check_conditions()` + `process()` methods

### Combat System
- Turn-based with `combat_list` (enemies) and `combat_list_allies` (player party)
- **Moves**: Defined in `src/moves.py`, use `cast()` method and `advance()` for cooldowns
- **States**: Status effects (poison, stun, sleep, etc.) managed in `src/states.py`
- **Resistance**: Damage types (`fire`, `ice`, `piercing`, etc.) and status resistances (both 1.0 = normal, 0.5 = half damage, 2.0 = double)
- **Distance system**: `combat_proximity` lists track range between combatants

### AI Integration (Mynx LLM Adapter)
Optional LLM-driven behavior for the in-game "mynx" creature. This is expected to extend to other NPCs in the future.

**Configuration** (environment variables):
```bash
MYNX_LLM_ENABLED=1
MYNX_LLM_PROVIDER=ollama|openrouter
MYNX_LLM_MODEL=llama3.1:7b  # or x-ai/grok-4-fast:free
OPENROUTER_API_KEY=sk_or_...  # required for openrouter
```

**Adapter class**: `ai/llm_client.py` → `MynxLLMAdapter`
- Supports plain-text and structured JSON responses
- Graceful fallback to deterministic stubs if unavailable
- Behavior profile in `ai/npc/animal/mynx.json` (system prompt, allowed actions, examples)

## Flask REST API Layer (NEW - Phase 1)

### Architecture Overview
The codebase now includes a complete REST API layer (`src/api/`) that wraps the existing game engine:

```
Client (Web/Mobile) → Flask API (17 endpoints) → GameService Wrapper → Game Engine
```

### API Structure
- **Sessions**: 24-hour in-memory authentication via Bearer tokens
- **Routes**: 6 blueprints with 17 endpoints (auth, world, player, inventory, equipment, combat, saves)
- **Validation**: 10 reusable validator functions for input checking
- **Error Handling**: 8 global HTTP error handlers with consistent JSON responses
- **Documentation**: OpenAPI 3.0 schema with Swagger UI at `/api/docs`

### Key API Concepts

**GameService (Stateless Wrapper)**
- Located: `src/api/services/game_service.py`
- Each method receives `Player` object, returns JSON-safe dict
- 18 core methods for game operations
- Does NOT hold session state (SessionManager's responsibility)
- Easy to test with mocked universe

**SessionManager (Session Lifecycle)**
- Located: `src/api/services/session_manager.py`
- Creates sessions with 24-hour lifetime
- Associates players with session IDs
- Handles automatic expiration cleanup
- In-memory storage (Phase 1; database in Phase 2)

**Input Validators (Reusable Validation)**
- Located: `src/api/services/validators.py`
- 10 functions covering all validation needs
- Examples: `validate_direction()`, `validate_coordinates()`, `validate_item_slot()`
- Centralized, testable, reusable across routes

**Error Handlers (Consistent Responses)**
- Located: `src/api/handlers/error_handler.py`
- 8 HTTP status codes: 400, 401, 403, 404, 422, 429, 500, 503
- All errors return: `{success: false, error: "...", message: "..."}`
- Global handler prevents duplicate error logic in routes

### Running the API

```bash
# Install API dependencies
pip install -r requirements-api.txt

# Start development server
python run_api.py

# Access Swagger UI (interactive docs)
open http://localhost:5000/api/docs

# Get OpenAPI schema
curl http://localhost:5000/api/openapi.json
```

### API Testing

```bash
# All API tests
pytest tests/api/ -v --cov=src/api

# Test specific file
pytest tests/api/test_validators.py -v

# Test specific function
pytest tests/api/test_validators.py::test_validate_direction_valid -v

# With coverage report
pytest tests/api/ --cov=src/api --cov-report=term-missing
```

### Extending the API

**Add a new endpoint:**
1. Create route function in appropriate blueprint (e.g., `src/api/routes/world.py`)
2. Use `get_session_and_player()` helper to extract auth context
3. Validate input with validators from `services/validators.py`
4. Call GameService method
5. Return JSON response with `{success: true, data: {...}}`
6. Write integration test in `tests/api/test_routes_integration.py`

**Add a new validator:**
1. Create function in `src/api/services/validators.py`
2. Return tuple: `(is_valid: bool, error_message: Optional[str])`
3. Add unit tests in `tests/api/test_validators.py`
4. Export from `src/api/services/__init__.py`

**Update OpenAPI schema:**
1. Edit `src/api/schemas/openapi.py`
2. Update endpoint definition in `paths` dict
3. Add request/response schemas
4. Schema auto-served at `/api/openapi.json`

## Development Workflows

### Running Tests
Activate the virtual environment before running tests:
```pwsh
.venv\Scripts\Activate.ps1
```

Then run tests with:

```bash
# All tests (game engine + API)
pytest -q

# With coverage report (both src and api)
pytest --cov=src --cov=ai --cov-report=term-missing

# Game engine tests only
pytest tests/test_*.py -v

# API tests only
pytest tests/api/ -v

# Specific test file
pytest tests/test_universe.py -v
```

**Test structure:**
- `tests/conftest.py` sets up module shims and coverage hooks
- `tests/api/conftest.py` sets up Flask test fixtures
- Fixtures in individual test files or conftest
- Use `monkeypatch` for path/file mocking

**API Test Pattern (for new API tests):**
```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
try:
    from flask import Flask
    from src.api.services.validators import validate_direction
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
def test_validator():
    is_valid, error = validate_direction("north")
    assert is_valid is True
    assert error is None
```

**Game Engine Test Pattern (unchanged):**
```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.npc import NPC  # type: ignore
from src.universe import Universe  # type: ignore
```


### Running the Game
```bash
python src/game.py
```

**Save files**: Pickle format (`.sav`) stored in project root. Use `functions.saves_list()` to enumerate.

### Color Output Conventions
All terminal output uses `neotermcolor`:
```python
from neotermcolor import colored, cprint

cprint("Error message", "red")
cprint("Success message", "green")
colored("Inline text", "cyan")  # for f-strings or print()
```

**Color palette:**
- Red: errors, damage
- Green: healing, success
- Cyan: narrative text, locations
- Yellow: warnings, item discovery
- Magenta: borders, decorative elements

### Common Patterns

**Spawning items on tiles:**
```python
# In map editor or code
tile.items_here.append(items.Restorative())
# Or use spawn_item with class name
tile.spawn_item(item_type="Shortsword")
```

**Adding events to tiles:**
```python
event = functions.instantiate_event(
    Ch01_Start_Open_Wall,  # Event class
    player,
    tile,
    params=None,
    repeat=True
)
tile.events_here.append(event)
```

**Serialization for map editor:**
Objects must be JSON-serializable. The map editor handles:
- `__class__` and `__module__` metadata
- `props` dict with all instance attributes
- Recursive deserialization in `Universe._deserialize_saved_instance()`

**When creating new item/NPC classes**, ensure all `__init__` params have defaults or the editor will fail to instantiate them.

### File Organization
- `src/` - Core game engine (actions, combat, player, universe, tiles, items, npc, functions)
- `src/api/` - **NEW** Flask REST API layer with services, routes, handlers, schemas
  - `src/api/app.py` - Flask app factory
  - `src/api/config.py` - Environment-based configuration
  - `src/api/services/` - SessionManager, GameService, validators
  - `src/api/routes/` - Route blueprints (auth, world, player, inventory, equipment, combat, saves)
  - `src/api/handlers/` - Error handlers
  - `src/api/schemas/` - OpenAPI schema generator
- `src/story/` - Story-specific events and dialogues
- `src/resources/` - Assets (maps, images, books, animations)
- `tests/` - Pytest test suite
  - `tests/api/` - **NEW** Flask API tests
  - `tests/conftest.py` - Main test configuration
  - `tests/test_*.py` - Game engine tests
- `utils/map_generator.py` - GUI map editor (tkinter)
- `ai/` - LLM adapter and behavior definitions; useful when generating descriptions or dialogue
- `docs/` - Design docs and architecture notes
- `docs/lore/` - In-game lore and story background; useful when generating descriptions or dialogue
- `run_api.py` - **NEW** Flask API entry point
- `requirements-api.txt` - **NEW** API dependencies

### Project Conventions
- **No `src.` prefix in module names during serialization** (map JSON, pickle saves)
- **Use `functions.refresh_stat_bonuses(player)` after equipment changes** to recalculate stats
- **Merchandise items**: Set `item.merchandise = True` and block equip/use until purchased
- **Hidden items/NPCs**: Use `hidden=True` and `hide_factor` (0-10 difficulty to find)
- **PowerShell compatibility**: Avoid `&`, `&&`, `||` in scripts; use `;` for command chaining

### API Development Patterns (NEW)

**Common Session Extraction Pattern:**
```python
from flask import request, current_app, jsonify

def get_session_and_player(request):
    """Extract and validate session from request header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, None, None, jsonify({"success": False, "error": "Missing auth"}), 401
    
    session_id = auth_header[7:]
    session_manager = current_app.session_manager
    session = session_manager.get_session(session_id)
    
    if not session:
        return None, None, None, jsonify({"success": False, "error": "Invalid session"}), 401
    
    player = session_manager.get_player(session_id)
    if not player:
        return None, None, None, jsonify({"success": False, "error": "Player not found"}), 404
    
    return session_manager, session, player, None

# In route:
@blueprint.route("/endpoint", methods=["POST"])
def endpoint():
    session_manager, session, player, error = get_session_and_player(request)
    if error:
        return error
    # ... rest of implementation
```

**Common Validation Pattern:**
```python
from src.api.services.validators import validate_direction, validate_required_fields

# Check required fields
is_valid, error = validate_required_fields(request.get_json(), ["direction"])
if not is_valid:
    return jsonify({"success": False, "error": error}), 400

# Validate specific field
direction = request.json["direction"]
is_valid, error = validate_direction(direction)
if not is_valid:
    return jsonify({"success": False, "error": error}), 400
```

**Common GameService Call Pattern:**
```python
# GameService method receives player, returns JSON-safe dict
result = current_app.game_service.get_player_status(player)

# Always save session after modifications
session_manager.save_session(session.session_id)

# Return response
return jsonify({"success": True, "data": result}), 200
```

### Common Issues & Solutions

**"Module 'src.X' has no attribute 'Y'"** during deserialization:
- Check that the class exists in the target module
- Verify no `src.` prefix in `__module__` field in JSON

**Coverage tracking missing modules:**
- Ensure production code uses `import src.module_name`
- Check `conftest.py` shims are loading in correct order

**LLM adapter always returns None:**
- Verify environment variables are set (especially `MYNX_LLM_ENABLED=1`)
- For OpenRouter, confirm `OPENROUTER_API_KEY` is present
- Set `MYNX_LLM_DEBUG=1` to see availability diagnostics

**Map editor crashes on save:**
- Check that all tile objects have serializable attributes
- Look for lambda functions or non-pickleable objects in events/items
- Review `MapSerializationError` traceback for specific tile/object

### Key Files to Reference
- **Game Engine Core:**
  - `src/functions.py` - Utility functions (saves, item stacking, input validation, serialization helpers)
  - `src/universe.py` - Map loading, JSON deserialization, tile management
  - `src/player.py` - Player class with inventory, combat, stats, skill trees
  - `src/items.py` - Item hierarchy and equipment system
  - `src/npc.py` - NPC/enemy classes and AI
- **API Layer (NEW):**
  - `src/api/app.py` - Flask app factory (entry point)
  - `src/api/services/game_service.py` - Game logic wrapper (18 core methods)
  - `src/api/services/session_manager.py` - Session lifecycle management
  - `src/api/services/validators.py` - Input validation functions (10 total)
  - `src/api/handlers/error_handler.py` - Global error handlers (8 HTTP codes)
  - `src/api/schemas/openapi.py` - OpenAPI 3.0 schema generator
  - `src/api/routes/` - 6 blueprint modules (17 total endpoints)
  - `run_api.py` - Flask development server entry point
- **Testing:**
  - `tests/conftest.py` - Test environment setup and module shimming
  - `tests/api/conftest.py` - Flask test configuration
  - `tests/api/test_session_manager.py` - SessionManager tests (12)
  - `tests/api/test_game_service.py` - GameService tests (15)
  - `tests/api/test_validators.py` - Validator tests (28)
  - `tests/api/test_routes_integration.py` - Integration tests (27)
  - `tests/api/test_error_handlers.py` - Error handler tests (9)
- **Other:**
  - `ai/llm_client.py` - LLM adapter implementation
  - `utils/map_generator.py` - Map editor GUI
  - `src/story/` - Story-specific events and dialogues
  - `docs/` - Design docs and architecture notes
  - `docs/lore/` - In-game lore and story background
  - `docs/MILESTONE1_COMPLETE.md` - API Phase 1 progress report
  - `ARCHITECTURE_DIAGRAM.md` - Visual architecture guide

## Quick Reference

**Add a new weapon:**
1. Subclass `Weapon` in `src/items.py`
2. Set `subtype` (Sword, Axe, etc.) for damage type calculation
3. Define `base_damage_type` if overriding archetype defaults

**Add a new map:**
1. Run `python utils/map_generator.py`
2. File → New Map, set dimensions and name
3. Add tiles, items, NPCs, events via GUI
4. Save to `src/resources/maps/yourmap.json`

**Add a story event:**
1. Create class in `src/story/` inheriting from `Event`
2. Implement `check_conditions()` and `process()`
3. Attach to tiles via map editor or code

**Add a new API endpoint (NEW):**
1. Create route function in appropriate blueprint (e.g., `src/api/routes/world.py`)
2. Validate request data with validators from `services/validators.py`
3. Extract session/player using `get_session_and_player()` helper
4. Call GameService method to perform action
5. Return JSON: `{success: true, data: {...}}`
6. Add integration test in `tests/api/test_routes_integration.py`
7. Update OpenAPI schema in `src/api/schemas/openapi.py` (paths section)

**Add a new validator (NEW):**
1. Create function in `src/api/services/validators.py`
2. Return `(is_valid: bool, error_message: Optional[str])`
3. Add unit tests in `tests/api/test_validators.py`
4. Export from `src/api/services/__init__.py`

**Test a specific function:**
```bash
pytest tests/test_functions.py::test_function_name -v
```

**Test a specific API validator:**
```bash
pytest tests/api/test_validators.py::test_validate_direction_valid -v
```

## Repository Reference
### Pull Requests
- When adding comments to PRs or when commenting on lines within PRs, prefix your comments with the [Agent] tag.