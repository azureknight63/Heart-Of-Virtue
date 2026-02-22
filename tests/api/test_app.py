"""Tests for Flask application factory and initialization."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.api.app import create_app
from src.api.config import DevelopmentConfig, TestingConfig, ProductionConfig


class TestCreateApp:
    """Test the create_app function and app initialization."""

    def test_create_app_default_config(self):
        """Test create_app with default configuration."""
        app, socketio = create_app()
        assert app is not None
        assert socketio is not None
        assert hasattr(app, 'session_manager')
        assert hasattr(app, 'game_service')
        assert hasattr(app, 'socketio')

    def test_create_app_development_config(self):
        """Test create_app with DevelopmentConfig."""
        app, socketio = create_app(DevelopmentConfig)
        assert app.config['DEBUG'] is True
        assert 'CORS_ORIGINS' in app.config

    def test_create_app_testing_config(self):
        """Test create_app with TestingConfig."""
        app, socketio = create_app(TestingConfig)
        assert app.config['TESTING'] is True

    def test_create_app_production_config(self):
        """Test create_app with ProductionConfig."""
        app, socketio = create_app(ProductionConfig)
        assert app.config['DEBUG'] is False

    @patch('src.api.app.universe_module.Universe')
    @patch('src.player.Player')
    def test_create_app_universe_initialization_dev(self, mock_player, mock_universe):
        """Test universe initialization in development mode."""
        # Mock the player and universe
        mock_player_instance = MagicMock()
        mock_player.return_value = mock_player_instance
        mock_universe_instance = MagicMock()
        mock_universe.return_value = mock_universe_instance

        # Mock universe.build and other methods
        mock_universe_instance.build.return_value = None
        mock_universe_instance.maps = [{'name': 'default'}]
        mock_universe_instance.starting_map_default = {'name': 'default'}

        app, socketio = create_app(DevelopmentConfig)

        # Verify universe was created and configured
        mock_player.assert_called_once()
        mock_universe.assert_called_once_with(mock_player_instance)
        mock_universe_instance.build.assert_called_once_with(mock_player_instance)

        # Verify get_tile method was added
        assert hasattr(mock_universe_instance, 'get_tile')

    def test_create_app_config_file_loading(self):
        """Test loading configuration from config file."""
        # Create a temporary config file
        config_content = """[game]
startposition = (5, 10)
starting_exp = 100
startmap = test_map
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            # Set environment variable
            with patch.dict(os.environ, {'CONFIG_FILE': config_path}):
                with patch('src.api.app.universe_module.Universe') as mock_universe:
                    with patch('src.player.Player') as mock_player:
                        mock_player_instance = MagicMock()
                        mock_player.return_value = mock_player_instance
                        mock_universe_instance = MagicMock()
                        mock_universe.return_value = mock_universe_instance
                        mock_universe_instance.build.return_value = None
                        mock_universe_instance.maps = [{'name': 'test_map'}]

                        app, socketio = create_app(DevelopmentConfig)

                        # Verify player position was set from config
                        assert mock_player_instance.location_x == 5
                        assert mock_player_instance.location_y == 10
                        # Verify starting exp was applied
                        assert mock_player_instance.skill_exp is not None
        finally:
            # Clean up
            os.unlink(config_path)

    def test_create_app_config_file_not_found(self):
        """Test handling of missing config file."""
        with patch.dict(os.environ, {'CONFIG_FILE': '/nonexistent/path.ini'}):
            with patch('src.api.app.universe_module.Universe') as mock_universe:
                with patch('src.player.Player') as mock_player:
                    mock_player_instance = MagicMock()
                    mock_player.return_value = mock_player_instance
                    mock_universe_instance = MagicMock()
                    mock_universe.return_value = mock_universe_instance
                    mock_universe_instance.build.return_value = None
                    mock_universe_instance.maps = [{'name': 'default'}]

                    # Should not raise exception
                    app, socketio = create_app(DevelopmentConfig)
                    assert app is not None

    def test_create_app_universe_initialization_failure(self):
        """Test fallback when universe initialization fails."""
        with patch('src.api.app.universe_module.Universe', side_effect=Exception("Test error")):
            app, socketio = create_app(DevelopmentConfig)
            # Should still create app despite universe failure
            assert app is not None
            assert app.game_service is not None

    def test_create_app_blueprints_registered(self):
        """Test that all blueprints are registered."""
        app, socketio = create_app(TestingConfig)

        # Check that expected blueprints are registered
        rules = [str(rule) for rule in app.url_map.iter_rules()]
        assert any('/api/auth' in rule for rule in rules)
        assert any('/api/world' in rule for rule in rules)
        assert any('/api/inventory' in rule for rule in rules)
        assert any('/api/equipment' in rule for rule in rules)
        assert any('/api/combat' in rule for rule in rules)
        assert any('/api/player' in rule for rule in rules)
        assert any('/api/saves' in rule for rule in rules)


class TestAppEndpoints:
    """Test application endpoints."""

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get('/health')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'healthy'
        assert 'sessions' in data

    def test_api_info_endpoint(self, client):
        """Test API info endpoint."""
        response = client.get('/api/info')
        assert response.status_code == 200
        data = response.get_json()
        assert data['name'] == 'Heart of Virtue API'
        assert data['version'] == '1.0.0'
        assert data['phase'] == 'Phase 1'

    def test_openapi_schema_endpoint(self, client):
        """Test OpenAPI schema endpoint."""
        response = client.get('/api/openapi.json')
        assert response.status_code == 200
        data = response.get_json()
        assert 'openapi' in data
        assert 'paths' in data

    def test_swagger_ui_endpoint(self, client):
        """Test Swagger UI endpoint."""
        response = client.get('/api/docs')
        assert response.status_code == 200
        assert 'swagger' in response.get_data(as_text=True).lower()

    def test_debug_routes_endpoint(self, client):
        """Test debug routes endpoint."""
        response = client.get('/api/debug/routes')
        assert response.status_code == 200
        data = response.get_json()
        assert 'routes' in data
        assert isinstance(data['routes'], list)
        assert len(data['routes']) > 0

    def test_cors_preflight_handling(self, client):
        """Test CORS preflight OPTIONS request handling."""
        response = client.options('/api/info',
                                headers={'Origin': 'http://localhost:3000',
                                        'Access-Control-Request-Method': 'POST'})
        assert response.status_code == 200
        assert 'Access-Control-Allow-Origin' in response.headers
        assert 'Access-Control-Allow-Methods' in response.headers
        assert 'Access-Control-Allow-Headers' in response.headers

    def test_404_handling(self, client):
        """Test 404 error handling."""
        response = client.get('/nonexistent')
        assert response.status_code == 404
        data = response.get_json()
        assert 'success' in data
        assert data['success'] is False
        assert 'error' in data
