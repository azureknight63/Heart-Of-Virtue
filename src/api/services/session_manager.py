"""Session management for player persistence."""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple


class MinimalPlayer:
    """Minimal player object for API testing/initialization."""
    
    def __init__(self, name):
        self.name = name
        self.x = 0  # Starting at origin
        self.y = 0
        self.inventory = []
        self.equipment = {}
        self.hp = 100
        self.max_hp = 100
        self.level = 1
        self.exp = 0


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
            # Try to import and create actual Player object
            # This will fail during testing/API initialization due to game engine dependencies
            # So we use MinimalPlayer as fallback
            player = MinimalPlayer(username)
            
            # If universe is available, position player at starting location
            if self.universe and hasattr(self.universe, 'maps') and self.universe.maps:
                first_map = self.universe.maps[0]
                tiles = [k for k in first_map if isinstance(k, tuple)]
                if tiles:
                    start_pos = tiles[0]
                    player.x, player.y = start_pos
            
            self.players[player_id] = player
        except Exception:
            # Fallback to minimal player
            player = MinimalPlayer(username)
            
            # If universe is available, position player at starting location
            if self.universe and hasattr(self.universe, 'maps') and self.universe.maps:
                first_map = self.universe.maps[0]
                tiles = [k for k in first_map if isinstance(k, tuple)]
                if tiles:
                    start_pos = tiles[0]
                    player.x, player.y = start_pos
            
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
