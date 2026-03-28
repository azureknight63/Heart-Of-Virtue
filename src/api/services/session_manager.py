"""Session management for player persistence."""

import os
import uuid
import configparser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Tuple, Any
from src.config_manager import ConfigManager


class MinimalPlayer:
    """Minimal player object for API testing/initialization."""

    def __init__(self, username):
        self.username = username
        self.name = "Jean"
        self.location_x = 0  # Starting at origin
        self.location_y = 0
        self.universe = None
        self.inventory = self._create_starting_inventory()
        self.equipment = {}
        self.hp = 100
        self.maxhp = 100
        self.maxhp_base = 100
        self.fatigue = 150
        self.maxfatigue = 150
        self.maxfatigue_base = 150

        # Core stats to avoid crashes in events/interactions
        self.strength = 10
        self.strength_base = 10
        self.finesse = 10
        self.finesse_base = 10
        self.faith = 10
        self.faith_base = 10
        self.intelligence = 10
        self.intelligence_base = 10
        self.charisma = 10
        self.charisma_base = 10
        self.endurance = 10
        self.endurance_base = 10
        self.speed = 10
        self.speed_base = 10
        self.awareness = 10

        # Resistances (required by refresh_stat_bonuses and game_service)
        self.resistance = {
            "fire": 1.0,
            "ice": 1.0,
            "shock": 1.0,
            "earth": 1.0,
            "light": 1.0,
            "dark": 1.0,
            "piercing": 1.0,
            "slashing": 1.0,
            "crushing": 1.0,
            "spiritual": 1.0,
            "pure": 1.0,
        }
        self.resistance_base = {
            "fire": 1.0,
            "ice": 1.0,
            "shock": 1.0,
            "earth": 1.0,
            "light": 1.0,
            "dark": 1.0,
            "piercing": 1.0,
            "slashing": 1.0,
            "crushing": 1.0,
            "spiritual": 1.0,
            "pure": 1.0,
        }
        self.status_resistance = {
            "generic": 1.0,
            "stun": 1.0,
            "poison": 1.0,
            "inflamed": 1.0,
            "sloth": 1.0,
            "apathy": 1.0,
            "blind": 1.0,
            "incoherence": 1.0,
            "mute": 1.0,
            "enraged": 1.0,
            "enchanted": 1.0,
            "ethereal": 1.0,
            "berserk": 1.0,
            "slow": 1.0,
            "sleep": 1.0,
            "confusion": 1.0,
            "cursed": 1.0,
            "stop": 1.0,
            "stone": 1.0,
            "frozen": 1.0,
            "doom": 1.0,
            "death": 1.0,
        }
        self.status_resistance_base = {
            "generic": 1.0,
            "stun": 1.0,
            "poison": 1.0,
            "inflamed": 1.0,
            "sloth": 1.0,
            "apathy": 1.0,
            "blind": 1.0,
            "incoherence": 1.0,
            "mute": 1.0,
            "enraged": 1.0,
            "enchanted": 1.0,
            "ethereal": 1.0,
            "berserk": 1.0,
            "slow": 1.0,
            "sleep": 1.0,
            "confusion": 1.0,
            "cursed": 1.0,
            "stop": 1.0,
            "stone": 1.0,
            "frozen": 1.0,
            "doom": 1.0,
            "death": 1.0,
        }

        self.level = 1
        self.exp = 0
        self.story = {}  # Empty story dict for API operations
        self.reputation = {}  # Empty reputation dict for API operations
        self.completed_dialogues = []  # Track completed dialogues
        self.dialogue_contexts = {}  # Store active dialogue contexts
        self.combat_log = []  # List of combat messages

        # Default prayer messages (subset of Player messages)
        self.prayer_msg = [
            "A warm sense of peace fills Jean's heart.",
            "Jean frowns impatiently.",
            "Jean shudders slightly.",
            "Jean makes the sign of the cross.",
            "Jean becomes conscious of his own heart beating loudly.",
            "Jean feels the silence around him to be very heavy.",
        ]

    def _create_starting_inventory(self):
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

    def __init__(
        self,
        session_id: str,
        player_id: str,
        username: str,
        created_at: datetime,
    ):
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
        self.data: Dict[str, Any] = {}

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
            "data": self.data,
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
        self.starting_map_name = "dark-grotto"
        self.starting_item_types = []  # List of item class names to spawn
        self.game_config = None  # Full GameConfig object
        self._load_starting_position_from_config()
        self._load_game_config()
        self._load_starting_items_from_config()

    def _load_starting_position_from_config(self):
        """Load starting position from config file specified in .env."""
        config_file = os.environ.get("CONFIG_FILE")

        print(f"[SessionManager] CONFIG_FILE env var: {config_file}", flush=True)

        if config_file:
            try:
                # Remove quotes if present (from .env file)
                config_file = config_file.strip("'\"")
                config_path = Path(config_file)

                print(
                    f"[SessionManager] Initial config path: {config_path}",
                    flush=True,
                )

                # If relative path, make it relative to project root
                if not config_path.is_absolute():
                    # Get project root (4 levels up from this file: src/api/services/session_manager.py)
                    project_root = Path(__file__).resolve().parent.parent.parent.parent
                    config_path = project_root / config_file
                    print(
                        f"[SessionManager] Project root: {project_root}",
                        flush=True,
                    )
                    print(
                        f"[SessionManager] Resolved to: {config_path}",
                        flush=True,
                    )

                print(
                    f"[SessionManager] Config path exists: {config_path.exists()}",
                    flush=True,
                )

                if config_path.exists():
                    parser = configparser.ConfigParser()
                    parser.read(config_path)

                    print(
                        f"[SessionManager] Config sections: {parser.sections()}",
                        flush=True,
                    )

                    if parser.has_option("game", "startposition"):
                        pos_str = parser.get("game", "startposition")
                        print(
                            f"[SessionManager] Raw position string: '{pos_str}'",
                            flush=True,
                        )
                        # Strip parentheses and whitespace
                        pos_str = pos_str.strip("() ")
                        coords = [int(x.strip()) for x in pos_str.split(",")]
                        if len(coords) == 2:
                            self.start_x, self.start_y = coords
                            print(
                                f"[SessionManager] [OK] Loaded starting position from config: ({self.start_x}, {self.start_y})",
                                flush=True,
                            )
                    else:
                        print(
                            "[SessionManager] No startposition option in [game] section",
                            flush=True,
                        )

                    if parser.has_option("game", "startmap"):
                        self.starting_map_name = parser.get("game", "startmap")
                        print(
                            f"[SessionManager] [OK] Loaded starting map from config: {self.starting_map_name}",
                            flush=True,
                        )
                    else:
                        print(
                            "[SessionManager] No startmap option in [game] section, using default",
                            flush=True,
                        )
            except Exception as e:
                import traceback

                print(
                    f"[SessionManager] [ERROR] Error loading config: {e}",
                    flush=True,
                )
                traceback.print_exc()
        else:
            print(
                "[SessionManager] CONFIG_FILE environment variable not set",
                flush=True,
            )

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
                        self.starting_item_types = [
                            item.strip() for item in items_str.split(",")
                        ]
                        print(
                            f"[SessionManager] [OK] Loaded starting items from config: {self.starting_item_types}",
                            flush=True,
                        )
                    else:
                        print(
                            "[SessionManager] No starting_items option in [game] section",
                            flush=True,
                        )
            except Exception as e:
                import traceback

                print(
                    f"[SessionManager] [ERROR] Error loading starting_items config: {e}",
                    flush=True,
                )
                traceback.print_exc()

    def _load_game_config(self):
        """Load full game configuration using ConfigManager."""
        config_file = os.environ.get("CONFIG_FILE", "config_dev.ini")

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
                    config_mgr = ConfigManager(str(config_path))
                    self.game_config = config_mgr.load()
                    print(
                        f"[SessionManager] [OK] Loaded full game config from: {config_path}",
                        flush=True,
                    )
                else:
                    print(
                        f"[SessionManager] Config file not found: {config_path}",
                        flush=True,
                    )
            except Exception as e:
                import traceback

                print(
                    f"[SessionManager] [ERROR] Error loading game config: {e}",
                    flush=True,
                )
                traceback.print_exc()

    def _create_items_from_config(self):
        """Create item instances from config item types.

        Returns:
            List of item instances
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
                        items.append(item_instance)
                        print(
                            f"[SessionManager] [OK] Created starting item: {item_type}",
                            flush=True,
                        )
                    else:
                        print(
                            f"[SessionManager] [ERROR] Item class not found: {item_type}",
                            flush=True,
                        )
                except Exception as e:
                    print(
                        f"[SessionManager] [ERROR] Error creating item {item_type}: {e}",
                        flush=True,
                    )
        except Exception as e:
            print(
                f"[SessionManager] [ERROR] Error importing items module: {e}",
                flush=True,
            )

        return items

    def _create_player_for_session(self, username: str) -> object:
        """Create a fresh player instance for a session.

        Args:
            username: Username for the player

        Returns:
            Player or MinimalPlayer instance
        """
        try:
            # Create fresh player and universe for every session to ensure isolation
            try:
                from src.player import Player
                from src.universe import Universe

                # Create new player
                player = Player()
                player.username = username
                # player.name is already "Jean" by default in Player.__init__

                # Create isolated universe for this player
                player.universe = Universe(player)
                player.universe.build(player)

                # Set starting map — prefer configured name, then universe default, then first available map
                starting_map = next(
                    (
                        map_item
                        for map_item in player.universe.maps
                        if map_item.get("name") == self.starting_map_name
                    ),
                    player.universe.starting_map_default,
                )
                if starting_map is None and player.universe.maps:
                    # No named or default map found — fall back to first map that contains tiles
                    starting_map = next(
                        (
                            m
                            for m in player.universe.maps
                            if any(isinstance(k, tuple) for k in m)
                        ),
                        player.universe.maps[0],
                    )
                    print(
                        f"[SessionManager] Warning: startmap '{self.starting_map_name}' not found; falling back to '{starting_map.get('name')}'",
                        flush=True,
                    )
                player.map = starting_map
                print(
                    f"[SessionManager] [OK] Set player starting map to: {starting_map.get('name') if starting_map else 'None'}",
                    flush=True,
                )
            except (ImportError, Exception) as e:
                print(
                    f"[SessionManager] Warning: Could not create full game state ({e}), falling back to MinimalPlayer",
                    flush=True,
                )
                player = MinimalPlayer(username)

            # Apply game config if available
            if self.game_config and hasattr(player, "game_config"):
                player.game_config = self.game_config
                if self.game_config.starting_exp > 0:
                    player.apply_starting_experience(self.game_config.starting_exp)
                    print(
                        f"[SessionManager] [OK] Applied starting_exp {self.game_config.starting_exp} to all skill categories",
                        flush=True,
                    )

            # Set starting position — validate it exists in the chosen map; fall back to first valid tile
            eff_x, eff_y = self.start_x, self.start_y
            if getattr(player, "map", None) and not player.map.get((eff_x, eff_y)):
                valid_coord = next(
                    (k for k in player.map if isinstance(k, tuple)),
                    (eff_x, eff_y),
                )
                eff_x, eff_y = valid_coord
                print(
                    f"[SessionManager] Warning: start position ({self.start_x},{self.start_y}) not in map; using {valid_coord}",
                    flush=True,
                )
            player.location_x, player.location_y = eff_x, eff_y

            # Add starting items from config if available
            config_items = self._create_items_from_config()
            if config_items:
                # If player already has inventory, extend it
                if hasattr(player, "inventory") and isinstance(player.inventory, list):
                    player.inventory.extend(config_items)
                    print(
                        f"[SessionManager] [OK] Added {len(config_items)} starting items to player inventory",
                        flush=True,
                    )

            return player
        except Exception as e:
            print(f"[SessionManager] Error creating player: {e}", flush=True)
            # Fallback to minimal player
            player = MinimalPlayer(username)

            # Set starting position from config
            player.location_x, player.location_y = self.start_x, self.start_y

            # Add starting items from config if available
            config_items = self._create_items_from_config()
            if config_items:
                if hasattr(player, "inventory") and isinstance(player.inventory, list):
                    player.inventory.extend(config_items)
                    print(
                        f"[SessionManager] [OK] Added {len(config_items)} starting items to player inventory",
                        flush=True,
                    )

            return player

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
        player = self._create_player_for_session(username)
        self.players[player_id] = player

        return session_id, player_id

    def start_new_game(self, session_id: str) -> bool:
        """Reset player state for an existing session to start a new game.

        Args:
            session_id: The session ID to reset

        Returns:
            True if successful, False if session not found
        """
        session = self.get_session(session_id)
        if not session:
            return False

        player_id = session.player_id

        # Create fresh player instance
        player = self._create_player_for_session(session.username)

        # Replace existing player
        self.players[player_id] = player

        # Explicitly clear any combat state if game_service exists (though we don't have ref here easily)
        # Actually replacing the player object should be enough as combat is usually linked to player

        return True

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
        expired_ids = [sid for sid, sess in self.sessions.items() if sess.is_expired()]

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
