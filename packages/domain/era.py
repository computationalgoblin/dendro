"""BETA1-G02 — Era: estrato temporal del mundo.

Contrato: docs/architecture/G01_time_contract.md. Las eras dividen la vista
cronológica en bandas horizontales; toda entidad pertenece (derivadamente)
a la era que contiene su año de nacimiento.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Era:
    """Estrato temporal: [start_year, end_year] — end_year None = era abierta."""

    id: str = field(default_factory=lambda: f"era_{uuid.uuid4().hex[:8]}")
    name: str = ""
    start_year: int = 0
    end_year: int | None = None
    order: int = 0
    description: str = ""

    def contains(self, year: int | None) -> bool:
        # BETA1-J04: un año None (entidad 'por datar') no pertenece a ninguna era.
        if year is None:
            return False
        if year < self.start_year:
            return False
        return self.end_year is None or year <= self.end_year

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "start_year": int(self.start_year),
            "end_year": int(self.end_year) if self.end_year is not None else None,
            "order": int(self.order),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Era":
        if not isinstance(data, dict):
            data = {}
        raw_end = data.get("end_year")
        try:
            end_year = int(raw_end) if raw_end is not None else None
        except (TypeError, ValueError):
            end_year = None
        try:
            start_year = int(data.get("start_year", 0))
        except (TypeError, ValueError):
            start_year = 0
        raw_id = data.get("id")
        return cls(
            id=raw_id if isinstance(raw_id, str) and raw_id.strip() else f"era_{uuid.uuid4().hex[:8]}",
            name=str(data.get("name", "")),
            start_year=start_year,
            end_year=end_year,
            order=int(data.get("order", 0) or 0),
            description=str(data.get("description", "")),
        )


__all__ = ["Era"]
