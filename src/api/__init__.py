"""Heart of Virtue API package."""

# Avoid eager top-level imports here — importing src.api.app at package init
# time creates a circular import chain (src.api -> src.api.app -> src.api.config
# -> back through src.api before it is fully initialized).  Callers import
# directly from the submodules (e.g. ``from src.api.app import create_app``).

__all__ = ["create_app", "SessionManager", "GameService"]
