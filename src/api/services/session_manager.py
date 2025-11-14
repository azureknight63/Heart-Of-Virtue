"""Session management for player persistence."""

import os
import uuid
import configparser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Tuple


class MinimalPlayer:
    """Minimal player object for API testing/initialization."""
    
    def __init__(self, name):
        self.name = name
        self.x = 0  # Starting at origin
        self.y = 0
        self.inventory = self._create_starting_inventory()
        self.equipment = {}
        self.hp = 100
        self.max_hp = 100
        self.level = 1
        self.exp = 0
        self.story = {}  # Empty story dict for API operations
        self.reputation = {}  # Empty reputation dict for API operations
        self.completed_dialogues = []  # Track completed dialogues
        self.dialogue_contexts = {}  # Store active dialogue contexts
    
    def _create_starting_items(self):
        """Create starting items for new players."""
        return [
            {
                "name": "Wooden Sword",
                "__class__": "Weapon",
                "weight": 2.0,
                "description": "A basic wooden practice sword.",
                "base_damage": 5,
                "damage_type": "piercing",
            },
            {
                "name": "Leather Armor",
                "__class__": "Armor",
                "weight": 5.0,
                "description": "Simple leather protection.",
                "defense": 2,
            },
            {
                "name": "Health Potion",
                "__class__": "Consumable",
                "weight": 0.5,
                "description": "Restores 50 HP when used.",
                "restoration": 50,
                "type": "health",
            },
            {
                "name": "Gold Coins",
                "__class__": "Gold",
                "weight": 0.1,
                "amount": 50,
                "description": "50 gold coins.",
            },
        ]


class Session:
    """Represents a player session."""

    def __init__(self, session_id: str, player_id: str, username: str, created_at: datetime):
        """Initialize a session.

        Args:
            session_id: Unique session identifier
            player_id: ID of the player in this session
            username: Username for this session
            created_at: When the session was created
        """
        self.session_id = session_id
        self.player_id = player_id
        self.username = username
        self.created_at = created_at
        self.last_accessed = created_at
        self.expires_at = created_at + timedelta(hours=24)

    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.now() > self.expires_at

    def update_access_time(self) -> None:
        """Update last accessed time to keep session alive."""
        self.last_accessed = datetime.now()
        # Extend expiration if still active
        if not self.is_expired():
            self.expires_at = datetime.now() + timedelta(hours=24)

    def to_dict(self) -> dict:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "player_id": self.player_id,
            "username": self.username,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }


class SessionManager:
    """Manages player sessions (in-memory for Phase 1)."""

    def __init__(self, universe=None):
        """Initialize session manager.
        
        Args:
            universe: Optional Universe instance for player positioning
        """
        self.sessions: Dict[str, Session] = {}
        self.players: Dict[str, object] = {}  # Stores Player or MinimalPlayer objects
        self.session_to_player: Dict[str, str] = {}
        self.universe = universe  # Reference to universe for getting starting positions
        
        # Load starting position from config file
        self.start_x, self.start_y = 1, 1  # defaults
        self.starting_item_types = []  # List of item class names to spawn
        self._load_starting_position_from_config()
        self._load_starting_items_from_config()
    
    def _load_starting_position_from_config(self):
        """Load starting position from config file specified in .env."""
        import sys
        config_file = os.environ.get("CONFIG_FILE")
        
        print(f"[SessionManager] CONFIG_FILE env var: {config_file}", flush=True)
        
        if config_file:
            try:
                # Remove quotes if present (from .env file)
                config_file = config_file.strip("'\"")
                config_path = Path(config_file)
                
                print(f"[SessionManager] Initial config path: {config_path}", flush=True)
                
                # If relative path, make it relative to project root
                if not config_path.is_absolute():
                    # Get project root (4 levels up from this file: src/api/services/session_manager.py)
                    project_root = Path(__file__).resolve().parent.parent.parent.parent
                    config_path = project_root / config_file
                    print(f"[SessionManager] Project root: {project_root}", flush=True)
                    print(f"[SessionManager] Resolved to: {config_path}", flush=True)
                
                print(f"[SessionManager] Config path exists: {config_path.exists()}", flush=True)
                
                if config_path.exists():
                    parser = configparser.ConfigParser()
                    parser.read(config_path)
                    
                    print(f"[SessionManager] Config sections: {parser.sections()}", flush=True)
                    
                    if parser.has_option("game", "startposition"):
                        pos_str = parser.get("game", "startposition")
                        print(f"[SessionManager] Raw position string: '{pos_str}'", flush=True)
                        coords = [int(x.strip()) for x in pos_str.split(",")]
                        if len(coords) == 2:
                            self.start_x, self.start_y = coords
                            print(f"[SessionManager] ✓ Loaded starting position from config: ({self.start_x}, {self.start_y})", flush=True)
                    else:
                        print(f"[SessionManager] No startposition option in [game] section", flush=True)
            except Exception as e:
                import traceback
                print(f"[SessionManager] ✗ Error loading config: {e}", flush=True)
                traceback.print_exc()
        else:
            print(f"[SessionManager] CONFIG_FILE environment variable not set", flush=True)

    def _load_starting_items_from_config(self):
        """Load starting item types from config file specified in .env."""
        config_file = os.environ.get("CONFIG_FILE")
        
        if config_file:
            try:
                # Remove quotes if present (from .env file)
                config_file = config_file.strip("'\"")
                config_path = Path(config_file)
                
                # If relative path, make it relative to project root
                if not config_path.is_absolute():
                    # Get project root (4 levels up from this file)
                    project_root = Path(__file__).resolve().parent.parent.parent.parent
                    config_path = project_root / config_file
                
                if config_path.exists():
                    parser = configparser.ConfigParser()
                    parser.read(config_path)
                    
                    if parser.has_option("game", "starting_items"):
                        items_str = parser.get("game", "starting_items")
                        # Parse comma-separated list of item types
                        self.starting_item_types = [item.strip() for item in items_str.split(",")]
                        print(f"[SessionManager] ✓ Loaded starting items from config: {self.starting_item_types}", flush=True)
                    else:
                        print(f"[SessionManager] No starting_items option in [game] section", flush=True)
            except Exception as e:
                import traceback
                print(f"[SessionManager] ✗ Error loading starting_items config: {e}", flush=True)
                traceback.print_exc()

    def _create_items_from_config(self):
        """Create item instances from config item types.
        
        Returns:
            List of item dictionaries
        """
        items = []
        
        if not self.starting_item_types:
            return items
        
        try:
            # Try to import items module
            try:
                import items as items_module
            except ImportError:
                # Try alternate import path
                from src import items as items_module
            
            for item_type in self.starting_item_types:
                try:
                    # Get the class from items module
                    if hasattr(items_module, item_type):
                        item_class = getattr(items_module, item_type)
                        # Create instance of the item
                        item_instance = item_class()
                        
                        # Convert to dict for MinimalPlayer compatibility
                        item_dict = {
                            "name": item_instance.name if hasattr(item_instance, 'name') else item_type,
                            "__class__": item_type,
                            "weight": item_instance.weight if hasattr(item_instance, 'weight') else 1.0,
                            "description": item_instance.description if hasattr(item_instance, 'description') else "",
                        }
                        
                        # Add type-specific attributes
                        if hasattr(item_instance, 'maintype'):
                            item_dict["maintype"] = item_instance.maintype
                        if hasattr(item_instance, 'subtype'):
                            item_dict["subtype"] = item_instance.subtype
                        if hasattr(item_instance, 'value'):
                            item_dict["value"] = item_instance.value
                        if hasattr(item_instance, 'rarity'):
                            item_dict["rarity"] = item_instance.rarity
                        if hasattr(item_instance, 'quantity'):
                            item_dict["quantity"] = item_instance.quantity
                        
                        items.append(item_dict)
                        print(f"[SessionManager] ✓ Created starting item: {item_type}", flush=True)
                    else:
                        print(f"[SessionManager] ✗ Item class not found: {item_type}", flush=True)
                except Exception as e:
                    print(f"[SessionManager] ✗ Error creating item {item_type}: {e}", flush=True)
        except Exception as e:
            print(f"[SessionManager] ✗ Error importing items module: {e}", flush=True)
        
        return items

    def create_session(self, username: str) -> Tuple[str, str]:
        """Create a new player session.

        Args:
            username: Username for the new player

        Returns:
            Tuple of (session_id, player_id)
        """
        player_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        # Create session
        session = Session(session_id, player_id, username, datetime.now())
        self.sessions[session_id] = session
        self.session_to_player[session_id] = player_id

        # Create new player
        try:
            # Try to get player from universe if available
            if self.universe and hasattr(self.universe, 'player'):
                player = self.universe.player
                # Update player name to match username
                if hasattr(player, 'name'):
                    player.name = username
            else:
                # Try to import and create actual Player object
                # This will fail during testing/API initialization due to game engine dependencies
                # So we use MinimalPlayer as fallback
                player = MinimalPlayer(username)
            
            # Set starting position from config
            player.x, player.y = self.start_x, self.start_y
            
            # Add starting items from config if available
            config_items = self._create_items_from_config()
            if config_items:
                # If player already has inventory, extend it
                if hasattr(player, 'inventory') and isinstance(player.inventory, list):
                    player.inventory.extend(config_items)
                    print(f"[SessionManager] ✓ Added {len(config_items)} starting items to player inventory", flush=True)
            
            self.players[player_id] = player
        except Exception as e:
            print(f"[SessionManager] Error creating player: {e}", flush=True)
            # Fallback to minimal player
            player = MinimalPlayer(username)
            
            # Set starting position from config
            player.x, player.y = self.start_x, self.start_y
            
            # Add starting items from config if available
            config_items = self._create_items_from_config()
            if config_items:
                if hasattr(player, 'inventory') and isinstance(player.inventory, list):
                    player.inventory.extend(config_items)
                    print(f"[SessionManager] ✓ Added {len(config_items)} starting items to player inventory", flush=True)
            
            self.players[player_id] = player

        return session_id, player_id

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID.

        Args:
            session_id: The session ID to retrieve

        Returns:
            Session object or None if not found or expired
        """
        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]

        # Check expiration
        if session.is_expired():
            self.expire_session(session_id)
            return None

        # Update access time
        session.update_access_time()
        return session

    def get_player(self, session_id: str) -> Optional[object]:
        """Get the player associated with a session.

        Args:
            session_id: The session ID

        Returns:
            Player object or None if session not found
        """
        session = self.get_session(session_id)
        if not session:
            return None

        player_id = session.player_id
        return self.players.get(player_id)

    def set_player(self, session_id: str, player: object) -> bool:
        """Associate a player with a session.

        Args:
            session_id: The session ID
            player: The Player object to associate

        Returns:
            True if successful, False if session not found
        """
        session = self.get_session(session_id)
        if not session:
            return False

        player_id = session.player_id
        self.players[player_id] = player
        return True

    def save_session(self, session_id: str) -> bool:
        """Save session data (placeholder for Phase 1).

        Args:
            session_id: The session ID to save

        Returns:
            True if successful
        """
        session = self.get_session(session_id)
        if not session:
            return False

        # TODO: Persist to database in Phase 2
        return True

    def expire_session(self, session_id: str) -> bool:
        """Expire a session.

        Args:
            session_id: The session ID to expire

        Returns:
            True if session was expired, False if not found
        """
        if session_id not in self.sessions:
            return False

        player_id = self.session_to_player.get(session_id)

        # Clean up
        del self.sessions[session_id]
        if session_id in self.session_to_player:
            del self.session_to_player[session_id]
        if player_id and player_id in self.players:
            del self.players[player_id]

        return True

    def cleanup_expired(self) -> int:
        """Remove all expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        expired_ids = [
            sid for sid, sess in self.sessions.items() if sess.is_expired()
        ]

        for session_id in expired_ids:
            self.expire_session(session_id)

        return len(expired_ids)

    def get_active_session_count(self) -> int:
        """Get count of active (non-expired) sessions."""
        return len([s for s in self.sessions.values() if not s.is_expired()])

    def get_all_sessions(self) -> list:
        """Get all active sessions (for debugging/admin)."""
        self.cleanup_expired()
        return [s.to_dict() for s in self.sessions.values()]
