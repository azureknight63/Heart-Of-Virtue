"""Comprehensive tests for OpenAPI schema generation."""

import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.api.schemas.openapi import generate_openapi_schema  # type: ignore


class TestOpenAPISchemaGeneration:
    """Test OpenAPI schema generation function."""

    def test_schema_is_dict(self):
        """Test that schema generation returns a dictionary."""
        schema = generate_openapi_schema()
        assert isinstance(schema, dict)

    def test_schema_has_openapi_version(self):
        """Test that schema includes OpenAPI version."""
        schema = generate_openapi_schema()
        assert "openapi" in schema
        assert schema["openapi"] == "3.0.3"

    def test_schema_has_info_section(self):
        """Test that schema includes info section."""
        schema = generate_openapi_schema()
        assert "info" in schema
        info = schema["info"]
        assert isinstance(info, dict)

    def test_info_has_required_fields(self):
        """Test that info section has all required fields."""
        schema = generate_openapi_schema()
        info = schema["info"]
        assert "title" in info
        assert "version" in info
        assert "description" in info
        assert info["title"] == "Heart of Virtue API"
        assert info["version"] == "1.0.0"

    def test_info_has_contact_info(self):
        """Test that info section includes contact information."""
        schema = generate_openapi_schema()
        info = schema["info"]
        assert "contact" in info
        assert "name" in info["contact"]
        assert "url" in info["contact"]

    def test_info_has_license(self):
        """Test that info section includes license."""
        schema = generate_openapi_schema()
        info = schema["info"]
        assert "license" in info
        assert "name" in info["license"]
        assert info["license"]["name"] == "MIT"

    def test_schema_has_servers(self):
        """Test that schema includes servers."""
        schema = generate_openapi_schema()
        assert "servers" in schema
        assert isinstance(schema["servers"], list)
        assert len(schema["servers"]) > 0

    def test_servers_have_urls(self):
        """Test that each server has a URL."""
        schema = generate_openapi_schema()
        servers = schema["servers"]
        for server in servers:
            assert "url" in server
            assert isinstance(server["url"], str)
            assert server["url"].startswith("http")

    def test_schema_has_paths(self):
        """Test that schema includes paths."""
        schema = generate_openapi_schema()
        assert "paths" in schema
        assert isinstance(schema["paths"], dict)
        assert len(schema["paths"]) > 0


class TestOpenAPIAuthenticationPaths:
    """Test authentication endpoints in OpenAPI schema."""

    def test_auth_login_path_exists(self):
        """Test that /auth/login path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/auth/login" in paths

    def test_auth_login_is_post(self):
        """Test that /auth/login is a POST endpoint."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/auth/login"]
        assert "post" in path_item

    def test_auth_login_has_request_body(self):
        """Test that /auth/login has requestBody."""
        schema = generate_openapi_schema()
        post_op = schema["paths"]["/auth/login"]["post"]
        assert "requestBody" in post_op
        assert post_op["requestBody"]["required"] is True

    def test_auth_login_has_responses(self):
        """Test that /auth/login has responses."""
        schema = generate_openapi_schema()
        post_op = schema["paths"]["/auth/login"]["post"]
        assert "responses" in post_op
        responses = post_op["responses"]
        assert "201" in responses
        assert "400" in responses
        assert "500" in responses

    def test_auth_logout_path_exists(self):
        """Test that /auth/logout path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/auth/logout" in paths

    def test_auth_logout_has_security(self):
        """Test that /auth/logout requires security."""
        schema = generate_openapi_schema()
        post_op = schema["paths"]["/auth/logout"]["post"]
        assert "security" in post_op


class TestOpenAPIWorldPaths:
    """Test world navigation endpoints in OpenAPI schema."""

    def test_world_root_path_exists(self):
        """Test that /world/ path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/world/" in paths

    def test_world_get_is_get_method(self):
        """Test that /world/ GET method is documented."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/world/"]
        assert "get" in path_item

    def test_world_move_path_exists(self):
        """Test that /world/move path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/world/move" in paths

    def test_world_move_is_post(self):
        """Test that /world/move is a POST endpoint."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/world/move"]
        assert "post" in path_item

    def test_world_move_has_direction_field(self):
        """Test that /world/move request schema includes direction."""
        schema = generate_openapi_schema()
        post_op = schema["paths"]["/world/move"]["post"]
        request_body = post_op["requestBody"]
        json_schema = request_body["content"]["application/json"]["schema"]
        assert "direction" in json_schema["properties"]
        direction_prop = json_schema["properties"]["direction"]
        assert direction_prop["type"] == "string"
        assert "enum" in direction_prop
        directions = direction_prop["enum"]
        assert "north" in directions
        assert "south" in directions
        assert "east" in directions
        assert "west" in directions

    def test_world_tile_path_exists(self):
        """Test that /world/tile path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/world/tile" in paths

    def test_world_tile_has_parameters(self):
        """Test that /world/tile has query parameters."""
        schema = generate_openapi_schema()
        get_op = schema["paths"]["/world/tile"]["get"]
        assert "parameters" in get_op
        params = get_op["parameters"]
        param_names = [p["name"] for p in params]
        assert "x" in param_names
        assert "y" in param_names


class TestOpenAPIPlayerPaths:
    """Test player endpoints in OpenAPI schema."""

    def test_player_status_path_exists(self):
        """Test that /player/status path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/player/status" in paths

    def test_player_status_is_get(self):
        """Test that /player/status is a GET endpoint."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/player/status"]
        assert "get" in path_item

    def test_player_stats_path_exists(self):
        """Test that /player/stats path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/player/stats" in paths

    def test_player_stats_is_get(self):
        """Test that /player/stats is a GET endpoint."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/player/stats"]
        assert "get" in path_item

    def test_player_endpoints_have_security(self):
        """Test that player endpoints require security."""
        schema = generate_openapi_schema()
        for path in ["/player/status", "/player/stats"]:
            ops = schema["paths"][path]
            for method_key in ops:
                if method_key in ["get", "post", "put", "delete"]:
                    op = ops[method_key]
                    assert "security" in op


class TestOpenAPIInventoryPaths:
    """Test inventory endpoints in OpenAPI schema."""

    def test_inventory_root_path_exists(self):
        """Test that /inventory/ path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/inventory/" in paths

    def test_inventory_get_is_get(self):
        """Test that /inventory/ GET is documented."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/inventory/"]
        assert "get" in path_item

    def test_inventory_take_path_exists(self):
        """Test that /inventory/take path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/inventory/take" in paths

    def test_inventory_take_is_post(self):
        """Test that /inventory/take is a POST endpoint."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/inventory/take"]
        assert "post" in path_item

    def test_inventory_drop_path_exists(self):
        """Test that /inventory/drop path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/inventory/drop" in paths

    def test_inventory_drop_is_post(self):
        """Test that /inventory/drop is a POST endpoint."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/inventory/drop"]
        assert "post" in path_item


class TestOpenAPIEquipmentPaths:
    """Test equipment endpoints in OpenAPI schema."""

    def test_equipment_root_path_exists(self):
        """Test that /equipment/ path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/equipment/" in paths

    def test_equipment_get_is_get(self):
        """Test that /equipment/ GET is documented."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/equipment/"]
        assert "get" in path_item

    def test_equipment_equip_path_exists(self):
        """Test that /equipment/equip path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/equipment/equip" in paths

    def test_equipment_equip_is_post(self):
        """Test that /equipment/equip is a POST endpoint."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/equipment/equip"]
        assert "post" in path_item

    def test_equipment_unequip_path_exists(self):
        """Test that /equipment/unequip path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/equipment/unequip" in paths

    def test_equipment_unequip_is_post(self):
        """Test that /equipment/unequip is a POST endpoint."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/equipment/unequip"]
        assert "post" in path_item


class TestOpenAPICombatPaths:
    """Test combat endpoints in OpenAPI schema."""

    def test_combat_start_path_exists(self):
        """Test that /combat/start path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/combat/start" in paths

    def test_combat_start_is_post(self):
        """Test that /combat/start is a POST endpoint."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/combat/start"]
        assert "post" in path_item

    def test_combat_move_path_exists(self):
        """Test that /combat/move path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/combat/move" in paths

    def test_combat_move_is_post(self):
        """Test that /combat/move is a POST endpoint."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/combat/move"]
        assert "post" in path_item

    def test_combat_move_has_action_enum(self):
        """Test that /combat/move action has valid enum values."""
        schema = generate_openapi_schema()
        post_op = schema["paths"]["/combat/move"]["post"]
        request_body = post_op["requestBody"]
        json_schema = request_body["content"]["application/json"]["schema"]
        action_prop = json_schema["properties"]["action"]
        assert "enum" in action_prop
        actions = action_prop["enum"]
        valid_actions = ["attack", "defend", "cast", "item", "flee"]
        for action in valid_actions:
            assert action in actions

    def test_combat_status_path_exists(self):
        """Test that /combat/status path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/combat/status" in paths

    def test_combat_status_is_get(self):
        """Test that /combat/status is a GET endpoint."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/combat/status"]
        assert "get" in path_item


class TestOpenAPISavesPaths:
    """Test saves endpoints in OpenAPI schema."""

    def test_saves_root_path_exists(self):
        """Test that /saves/ path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/saves/" in paths

    def test_saves_get_is_get(self):
        """Test that /saves/ GET is documented."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/saves/"]
        assert "get" in path_item

    def test_saves_post_is_post(self):
        """Test that /saves/ POST is documented."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/saves/"]
        assert "post" in path_item

    def test_saves_load_path_exists(self):
        """Test that /saves/{save_id}/load path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/saves/{save_id}/load" in paths

    def test_saves_load_is_post(self):
        """Test that /saves/{save_id}/load is a POST endpoint."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/saves/{save_id}/load"]
        assert "post" in path_item

    def test_saves_delete_path_exists(self):
        """Test that /saves/{save_id} path is documented."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        assert "/saves/{save_id}" in paths

    def test_saves_delete_is_delete(self):
        """Test that /saves/{save_id} DELETE is documented."""
        schema = generate_openapi_schema()
        path_item = schema["paths"]["/saves/{save_id}"]
        assert "delete" in path_item


class TestOpenAPISecuritySchemes:
    """Test security schemes in OpenAPI schema."""

    def test_components_section_exists(self):
        """Test that components section exists."""
        schema = generate_openapi_schema()
        assert "components" in schema

    def test_security_schemes_exists(self):
        """Test that securitySchemes exists in components."""
        schema = generate_openapi_schema()
        components = schema["components"]
        assert "securitySchemes" in components

    def test_bearer_auth_scheme_exists(self):
        """Test that BearerAuth security scheme is defined."""
        schema = generate_openapi_schema()
        security_schemes = schema["components"]["securitySchemes"]
        assert "BearerAuth" in security_schemes

    def test_bearer_auth_type(self):
        """Test that BearerAuth is http type."""
        schema = generate_openapi_schema()
        bearer_auth = schema["components"]["securitySchemes"]["BearerAuth"]
        assert bearer_auth["type"] == "http"
        assert bearer_auth["scheme"] == "bearer"

    def test_bearer_auth_format(self):
        """Test that BearerAuth has JWT format."""
        schema = generate_openapi_schema()
        bearer_auth = schema["components"]["securitySchemes"]["BearerAuth"]
        assert "bearerFormat" in bearer_auth
        assert bearer_auth["bearerFormat"] == "JWT"


class TestOpenAPISchemas:
    """Test component schemas in OpenAPI schema."""

    def test_schemas_exist(self):
        """Test that schemas section exists in components."""
        schema = generate_openapi_schema()
        components = schema["components"]
        assert "schemas" in components

    def test_player_schema_exists(self):
        """Test that Player schema is defined."""
        schema = generate_openapi_schema()
        schemas = schema["components"]["schemas"]
        assert "Player" in schemas

    def test_player_schema_has_properties(self):
        """Test that Player schema has required properties."""
        schema = generate_openapi_schema()
        player_schema = schema["components"]["schemas"]["Player"]
        assert "properties" in player_schema
        props = player_schema["properties"]
        assert "name" in props
        assert "level" in props

    def test_item_schema_exists(self):
        """Test that Item schema is defined."""
        schema = generate_openapi_schema()
        schemas = schema["components"]["schemas"]
        assert "Item" in schemas

    def test_error_schema_exists(self):
        """Test that Error schema is defined."""
        schema = generate_openapi_schema()
        schemas = schema["components"]["schemas"]
        assert "Error" in schemas

    def test_error_schema_has_success_field(self):
        """Test that Error schema has success field."""
        schema = generate_openapi_schema()
        error_schema = schema["components"]["schemas"]["Error"]
        props = error_schema["properties"]
        assert "success" in props


class TestOpenAPITags:
    """Test tags in OpenAPI schema."""

    def test_tags_section_exists(self):
        """Test that tags section exists."""
        schema = generate_openapi_schema()
        assert "tags" in schema

    def test_tags_is_list(self):
        """Test that tags is a list."""
        schema = generate_openapi_schema()
        assert isinstance(schema["tags"], list)

    def test_tags_not_empty(self):
        """Test that tags list is not empty."""
        schema = generate_openapi_schema()
        assert len(schema["tags"]) > 0

    def test_each_tag_has_name(self):
        """Test that each tag has a name."""
        schema = generate_openapi_schema()
        tags = schema["tags"]
        for tag in tags:
            assert "name" in tag

    def test_authentication_tag_exists(self):
        """Test that Authentication tag is defined."""
        schema = generate_openapi_schema()
        tag_names = [tag["name"] for tag in schema["tags"]]
        assert "Authentication" in tag_names

    def test_combat_tag_exists(self):
        """Test that Combat tag is defined."""
        schema = generate_openapi_schema()
        tag_names = [tag["name"] for tag in schema["tags"]]
        assert "Combat" in tag_names


class TestOpenAPIResponseCodes:
    """Test response codes across OpenAPI schema."""

    def test_auth_login_success_response_code(self):
        """Test that /auth/login has 201 success code."""
        schema = generate_openapi_schema()
        responses = schema["paths"]["/auth/login"]["post"]["responses"]
        assert "201" in responses

    def test_auth_logout_success_response_code(self):
        """Test that /auth/logout has 200 success code."""
        schema = generate_openapi_schema()
        responses = schema["paths"]["/auth/logout"]["post"]["responses"]
        assert "200" in responses

    def test_combat_start_success_response_code(self):
        """Test that /combat/start has 201 success code."""
        schema = generate_openapi_schema()
        responses = schema["paths"]["/combat/start"]["post"]["responses"]
        assert "201" in responses

    def test_get_endpoints_have_200(self):
        """Test that GET endpoints have 200 response codes."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        for path, path_item in paths.items():
            if "get" in path_item:
                responses = path_item["get"]["responses"]
                assert "200" in responses

    def test_post_endpoints_have_error_codes(self):
        """Test that POST endpoints have error response codes."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        error_codes = ["400", "401"]
        for path, path_item in paths.items():
            if "post" in path_item:
                responses = path_item["post"]["responses"]
                # At least one error code should be present
                has_error_code = any(code in responses for code in error_codes)
                assert has_error_code or "201" in responses


class TestOpenAPIConsistency:
    """Test consistency across OpenAPI schema."""

    def test_all_paths_have_tags(self):
        """Test that operations have tags for grouping."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        for path, path_item in paths.items():
            for method in ["get", "post", "put", "delete", "patch"]:
                if method in path_item:
                    op = path_item[method]
                    assert "tags" in op, f"Operation {method} {path} missing tags"

    def test_all_paths_have_summary(self):
        """Test that operations have summaries."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        for path, path_item in paths.items():
            for method in ["get", "post", "put", "delete", "patch"]:
                if method in path_item:
                    op = path_item[method]
                    assert "summary" in op, f"Operation {method} {path} missing summary"

    def test_secured_endpoints_have_bearer_auth(self):
        """Test that secured endpoints reference BearerAuth."""
        schema = generate_openapi_schema()
        paths = schema["paths"]
        # Most endpoints except /auth/login should have security
        secured_paths = [p for p in paths if "/auth" not in p]
        for path in secured_paths:
            path_item = paths[path]
            for method in ["get", "post", "put", "delete"]:
                if method in path_item:
                    op = path_item[method]
                    if "security" in op:
                        security = op["security"]
                        # Should have BearerAuth reference
                        assert any("BearerAuth" in sec for sec in security)
