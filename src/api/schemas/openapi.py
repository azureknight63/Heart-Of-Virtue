"""OpenAPI schema generation for Heart of Virtue API."""

from typing import Any, Dict, List


def generate_openapi_schema() -> Dict[str, Any]:
    """Generate OpenAPI 3.0 schema for the Heart of Virtue API.

    Returns:
        Dictionary containing the full OpenAPI schema
    """
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Heart of Virtue API",
            "description": "REST API for the Heart of Virtue text-based RPG",
            "version": "1.0.0",
            "contact": {
                "name": "Heart of Virtue Team",
                "url": "https://github.com/yourusername/heart-of-virtue",
            },
            "license": {"name": "MIT"},
        },
        "servers": [
            {"url": "http://localhost:5000", "description": "Development server"},
            {"url": "http://localhost:8000", "description": "Production server"},
        ],
        "paths": {
            "/auth/login": {
                "post": {
                    "summary": "Login and create a new session",
                    "tags": ["Authentication"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "character_name": {"type": "string"},
                                        "slot": {
                                            "type": "integer",
                                            "minimum": 0,
                                            "maximum": 2,
                                        },
                                    },
                                    "required": ["character_name", "slot"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Session created successfully",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "session_id": {"type": "string"},
                                                    "expires_at": {"type": "string"},
                                                    "player": {
                                                        "type": "object",
                                                        "properties": {
                                                            "name": {"type": "string"},
                                                            "level": {"type": "integer"},
                                                            "experience": {
                                                                "type": "integer"
                                                            },
                                                            "health": {"type": "integer"},
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Invalid request parameters",
                        },
                        "500": {
                            "description": "Server error",
                        },
                    },
                }
            },
            "/auth/logout": {
                "post": {
                    "summary": "Logout and end session",
                    "tags": ["Authentication"],
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "Logged out successfully",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "message": {"type": "string"}
                                                },
                                            },
                                        },
                                    }
                                }
                            },
                        },
                        "401": {
                            "description": "Unauthorized - invalid or missing session",
                        },
                    },
                }
            },
            "/auth/validate": {
                "get": {
                    "summary": "Validate current session",
                    "tags": ["Authentication"],
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "Session is valid",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "is_valid": {"type": "boolean"},
                                                    "player_name": {"type": "string"},
                                                    "expires_at": {"type": "string"},
                                                },
                                            },
                                        },
                                    }
                                }
                            },
                        },
                        "401": {
                            "description": "Unauthorized - invalid or missing session",
                        },
                    },
                }
            },
            "/world/": {
                "get": {
                    "summary": "Get current room information",
                    "tags": ["World"],
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "Current room data",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "x": {"type": "integer"},
                                                    "y": {"type": "integer"},
                                                    "description": {"type": "string"},
                                                    "exits": {
                                                        "type": "array",
                                                        "items": {"type": "string"},
                                                    },
                                                    "items": {
                                                        "type": "array",
                                                        "items": {"type": "object"},
                                                    },
                                                    "npcs": {
                                                        "type": "array",
                                                        "items": {"type": "object"},
                                                    },
                                                },
                                            },
                                        },
                                    }
                                }
                            },
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                    },
                }
            },
            "/world/move": {
                "post": {
                    "summary": "Move player in specified direction",
                    "tags": ["World"],
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "direction": {
                                            "type": "string",
                                            "enum": ["north", "south", "east", "west"],
                                        }
                                    },
                                    "required": ["direction"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Moved successfully",
                        },
                        "400": {
                            "description": "Invalid direction",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                    },
                }
            },
            "/world/tile": {
                "get": {
                    "summary": "Get tile information at specific coordinates",
                    "tags": ["World"],
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "x",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "y",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Tile data",
                        },
                        "400": {
                            "description": "Invalid coordinates",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                    },
                }
            },
            "/player/status": {
                "get": {
                    "summary": "Get player health and status",
                    "tags": ["Player"],
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "Player status",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                    },
                }
            },
            "/player/stats": {
                "get": {
                    "summary": "Get player character stats",
                    "tags": ["Player"],
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "Player stats",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                    },
                }
            },
            "/inventory/": {
                "get": {
                    "summary": "Get current inventory",
                    "tags": ["Inventory"],
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "Inventory contents",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                    },
                }
            },
            "/inventory/take": {
                "post": {
                    "summary": "Pick up item from ground",
                    "tags": ["Inventory"],
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"item_id": {"type": "string"}},
                                    "required": ["item_id"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Item taken successfully",
                        },
                        "400": {
                            "description": "Invalid item or not on ground",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                    },
                }
            },
            "/inventory/drop": {
                "post": {
                    "summary": "Drop item to ground",
                    "tags": ["Inventory"],
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"item_index": {"type": "integer"}},
                                    "required": ["item_index"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Item dropped successfully",
                        },
                        "400": {
                            "description": "Invalid item index",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                    },
                }
            },
            "/equipment/": {
                "get": {
                    "summary": "Get current equipment",
                    "tags": ["Equipment"],
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "Current equipment by slot",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                    },
                }
            },
            "/equipment/equip": {
                "post": {
                    "summary": "Equip an item",
                    "tags": ["Equipment"],
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"item_index": {"type": "integer"}},
                                    "required": ["item_index"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Item equipped successfully",
                        },
                        "400": {
                            "description": "Invalid item or cannot equip",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                    },
                }
            },
            "/equipment/unequip": {
                "post": {
                    "summary": "Remove equipped item",
                    "tags": ["Equipment"],
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"slot": {"type": "string"}},
                                    "required": ["slot"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Item unequipped successfully",
                        },
                        "400": {
                            "description": "Invalid slot or nothing equipped",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                    },
                }
            },
            "/combat/start": {
                "post": {
                    "summary": "Start a combat encounter",
                    "tags": ["Combat"],
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"enemy_id": {"type": "string"}},
                                    "required": ["enemy_id"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Combat started",
                        },
                        "400": {
                            "description": "Invalid enemy or cannot start combat",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                    },
                }
            },
            "/combat/move": {
                "post": {
                    "summary": "Execute a combat action",
                    "tags": ["Combat"],
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "action": {
                                            "type": "string",
                                            "enum": [
                                                "attack",
                                                "defend",
                                                "cast",
                                                "item",
                                                "flee",
                                            ],
                                        },
                                        "target_id": {"type": "string"},
                                        "move_id": {"type": "string"},
                                    },
                                    "required": ["action"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Action executed",
                        },
                        "400": {
                            "description": "Invalid action",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                    },
                }
            },
            "/combat/status": {
                "get": {
                    "summary": "Get current combat status",
                    "tags": ["Combat"],
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "Combat status",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                    },
                }
            },
            "/saves/": {
                "get": {
                    "summary": "List all saved games",
                    "tags": ["Saves"],
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "List of saves",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                    },
                },
                "post": {
                    "summary": "Create a new save",
                    "tags": ["Saves"],
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"save_name": {"type": "string"}},
                                    "required": ["save_name"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Save created",
                        },
                        "400": {
                            "description": "Invalid save name",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                    },
                },
            },
            "/saves/{save_id}/load": {
                "post": {
                    "summary": "Load a saved game",
                    "tags": ["Saves"],
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "save_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Save loaded",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                        "404": {
                            "description": "Save not found",
                        },
                    },
                }
            },
            "/saves/{save_id}": {
                "delete": {
                    "summary": "Delete a save",
                    "tags": ["Saves"],
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "save_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Save deleted",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                        "404": {
                            "description": "Save not found",
                        },
                    },
                }
            },
        },
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "Bearer token obtained from /auth/login endpoint",
                }
            },
            "schemas": {
                "Player": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "level": {"type": "integer"},
                        "experience": {"type": "integer"},
                        "health": {"type": "integer"},
                        "max_health": {"type": "integer"},
                        "mana": {"type": "integer"},
                        "max_mana": {"type": "integer"},
                    },
                },
                "Item": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "description": {"type": "string"},
                        "value": {"type": "integer"},
                    },
                },
                "Error": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": False},
                        "error": {"type": "string"},
                        "message": {"type": "string"},
                    },
                },
            },
        },
        "tags": [
            {
                "name": "Authentication",
                "description": "Session and authentication management",
            },
            {
                "name": "World",
                "description": "World navigation and exploration",
            },
            {
                "name": "Player",
                "description": "Player status and statistics",
            },
            {
                "name": "Inventory",
                "description": "Inventory and item management",
            },
            {
                "name": "Equipment",
                "description": "Equipment and armor management",
            },
            {
                "name": "Combat",
                "description": "Combat encounters and actions",
            },
            {
                "name": "Saves",
                "description": "Game save and load functionality",
            },
        ],
    }


def generate_swagger_ui_html() -> str:
    """Generate HTML for Swagger UI.

    Returns:
        HTML string for Swagger UI
    """
    return """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Heart of Virtue API - Swagger UI</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@3/swagger-ui.css">
      </head>
      <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@3/swagger-ui.js"></script>
        <script src="https://unpkg.com/swagger-ui-dist@3/swagger-ui-bundle.js"></script>
        <script>
        const ui = SwaggerUIBundle({
            url: "/api/openapi.json",
            dom_id: '#swagger-ui',
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIBundle.SwaggerUIStandalonePreset
            ],
            layout: "StandaloneLayout"
        });
        </script>
      </body>
    </html>
    """
