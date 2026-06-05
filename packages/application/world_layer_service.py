"""
World layer service — application-layer management of project world layers.

Provides ``WorldLayerService``, a stateful service that orchestrates CRUD
and ordering operations on ``WorldLayer`` objects within the active project.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from packages.domain.result import Error, Ok, Result
from packages.domain.world_layer import WorldLayer


@dataclass
class WorldLayerService:
    """Manage world layers on a project.

    All methods derive the active project from ``project_service``.
    No auto-persistence — the caller invokes ``project_service.save()``
    after mutations.
    """

    project_service: Any  # ProjectService

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _active_project(self):
        ps = self.project_service
        if ps.active_project is None:
            return Error("No active project")
        return Ok(ps.active_project)

    def _is_default_layer(self, layer_id: str) -> bool:
        proj = self._active_project()
        if isinstance(proj, Error):
            return False
        for wl in proj.value.world_layers:
            if wl.id == layer_id:
                return wl.is_default
        return False

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def list_layers(self, include_hidden: bool = False) -> list[WorldLayer]:
        """Return all visible layers, or all if *include_hidden*."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return []
        layers = list(proj.value.world_layers)
        # Sort by order, then name
        layers.sort(key=lambda wl: (wl.order, wl.name.lower()))
        if not include_hidden:
            layers = [wl for wl in layers if wl.is_visible]
        return layers

    def get_layer(self, layer_id: str) -> Result[WorldLayer, str]:
        """Return a layer by ID, including hidden ones."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        for wl in proj.value.world_layers:
            if wl.id == layer_id:
                return Ok(wl)
        return Error(f"World layer '{layer_id}' not found")

    # ------------------------------------------------------------------
    # Create / Update
    # ------------------------------------------------------------------

    def create_layer(
        self,
        name: str,
        description: str = "",
        order: int | None = None,
    ) -> Result[WorldLayer, str]:
        """Create a new user-defined layer.

        New layers have ``is_default=False`` and ``is_visible=True``.
        """
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        name = name.strip()
        if not name:
            return Error("Layer name cannot be empty")

        new_id = f"layer_user_{uuid.uuid4().hex[:8]}"
        if order is None:
            # Place after the last layer
            order = max((wl.order for wl in proj.value.world_layers), default=0) + 1

        layer = WorldLayer(
            id=new_id,
            name=name,
            description=description,
            order=order,
            is_visible=True,
            is_default=False,
        )
        proj.value.world_layers.append(layer)
        proj.value.touch()
        return Ok(layer)

    def update_layer(
        self, layer_id: str, **kwargs: Any,
    ) -> Result[WorldLayer, str]:
        """Update mutable fields of a layer."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for wl in proj.value.world_layers:
            if wl.id == layer_id:
                for key in ("name", "description", "order"):
                    if key in kwargs:
                        setattr(wl, key, kwargs[key])
                if "metadata" in kwargs and isinstance(kwargs["metadata"], dict):
                    wl.metadata.update(kwargs["metadata"])
                proj.value.touch()
                return Ok(wl)
        return Error(f"World layer '{layer_id}' not found")

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------

    def hide_layer(self, layer_id: str) -> Result[None, str]:
        """Set is_visible=False. Default layers can be hidden."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for wl in proj.value.world_layers:
            if wl.id == layer_id:
                wl.is_visible = False
                proj.value.touch()
                return Ok(None)
        return Error(f"World layer '{layer_id}' not found")

    def show_layer(self, layer_id: str) -> Result[None, str]:
        """Set is_visible=True."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for wl in proj.value.world_layers:
            if wl.id == layer_id:
                wl.is_visible = True
                proj.value.touch()
                return Ok(None)
        return Error(f"World layer '{layer_id}' not found")

    # ------------------------------------------------------------------
    # Ordering
    # ------------------------------------------------------------------

    def reorder_layer(self, layer_id: str, new_order: int) -> Result[None, str]:
        """Change the display order of a layer."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for wl in proj.value.world_layers:
            if wl.id == layer_id:
                wl.order = new_order
                proj.value.touch()
                return Ok(None)
        return Error(f"World layer '{layer_id}' not found")

    # ── B39: Create ring (anillo) from branch ─────────────────────

    def create_ring_from_branch(
        self,
        name: str,
        description: str = "",
        order: int | None = None,
    ) -> Result[WorldLayer, str]:
        """Create a new ring (anillo/WorldLayer) based on a branch.

        This is non-destructive: the branch entity is preserved.
        The caller may optionally create a 'deriva de' relation
        between the branch and the new ring.
        """
        return self.create_layer(name=name, description=description, order=order)
