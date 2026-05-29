"""
Project domain model (minimal).

Provides the base Project dataclass that represents a narrative project.
This is a minimal version — full entity model comes in Bloque 2.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now_utc() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


def _new_id() -> str:
    """Generate a new project ID."""
    return uuid.uuid4().hex[:12]


@dataclass
class Project:
    """A narrative project.

    This is the root entity of the application. Contains only the
    essential identification and metadata. Full entity, relation,
    source, and history models are added in Bloque 2.

    Attributes:
        id: Unique project identifier (hex string, 12 chars).
        name: Human-readable project name.
        created_at: Timestamp of project creation (UTC).
        updated_at: Timestamp of last modification (UTC).
        metadata: Extensible key-value metadata store.
    """
    id: str = field(default_factory=_new_id)
    name: str = ""
    created_at: datetime = field(default_factory=_now_utc)
    updated_at: datetime = field(default_factory=_now_utc)
    metadata: dict[str, str] = field(default_factory=dict)

    def touch(self) -> None:
        """Mark the project as updated (bump updated_at)."""
        self.updated_at = _now_utc()

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary.

        Returns:
            dict with string timestamps in ISO format.
        """
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Project:
        """Deserialize from a dictionary.

        Args:
            data: Dictionary with project data.

        Returns:
            New Project instance.

        Raises:
            KeyError: If required fields are missing.
            ValueError: If date fields are invalid.
        """
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", "")),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=dict(data.get("metadata", {})),
        )
