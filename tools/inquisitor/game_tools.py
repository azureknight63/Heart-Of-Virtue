"""ToolResult — returned by layer.execute()."""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ToolResult:
    """Wraps the outcome of a single layer tool call."""

    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    http_status: int = 200
    # If True the layer detected an implicit bug (e.g. 5xx response).
    implicit_bug: bool = False
    implicit_bug_title: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "http_status": self.http_status,
        }

    @classmethod
    def ok(cls, data: dict) -> "ToolResult":
        return cls(success=True, data=data)

    @classmethod
    def err(cls, error: str, http_status: int = 400) -> "ToolResult":
        return cls(success=False, error=error, http_status=http_status)

    @classmethod
    def server_error(cls, error: str, title: str = "") -> "ToolResult":
        return cls(
            success=False,
            error=error,
            http_status=500,
            implicit_bug=True,
            implicit_bug_title=title or f"Server error: {error[:80]}",
        )
