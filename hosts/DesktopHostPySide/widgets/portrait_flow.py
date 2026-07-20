"""Flujo compartido de retrato de entidad (BETA2-IMG-02).

Un solo lugar para el menú «Imagen…» del panel de detalle
(``NodeDetailPanel``, también como pestaña Ficha del Foco): elegir origen (archivo local o
búsqueda en Openverse), pasar SIEMPRE por el editor de encuadre y persistir a
través de ``ImageAssetService`` + ``entity_controller.update`` — la UI nunca
escribe persistencia ni assets por su cuenta.

Contrato de claves (docs/contracts/evolucion-esquema.md):
``custom_metadata["_image_path"]`` = ruta relativa al asset store (las
absolutas son legacy BETA1-F04 y se re-importan al volver a editar);
``custom_metadata["_image_crop"]`` = ``{"cx", "cy", "zoom"}``.

El panel llamador solo necesita: ``ctx`` (con ``project_controller``),
``entity_controller``, ``entity_id``, ``image_btn`` y ``refresh()``.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFileDialog, QMenu

from packages.application.image_asset_service import ImageAssetService
from packages.application.portrait_crop import (
    IMAGE_CROP_KEY,
    IMAGE_PATH_KEY,
    PortraitCrop,
    parse_crop,
)
from packages.domain.result import Error, Ok

_service = ImageAssetService()


# ---------------------------------------------------------------------------
# Helpers puros de estado (testeables sin diálogos)
# ---------------------------------------------------------------------------

def project_path_of(ctx) -> Path | None:
    """Ruta del JSON del proyecto, o None si aún no se guardó."""
    controller = getattr(ctx, "project_controller", None)
    current = getattr(controller, "current_path", None) if controller else None
    return Path(current) if current else None


def ensure_project_path(ctx) -> Path | None:
    """Como ``project_path_of`` pero avisa al usuario si falta."""
    path = project_path_of(ctx)
    if path is None:
        ctx.notify(
            "Guarda el proyecto antes de añadir imágenes — los retratos viven junto al archivo.",
            "info",
        )
    return path


def collect_referenced_image_paths(ctx) -> set[str]:
    """Rutas ``_image_path`` vivas de TODO el proyecto (para limpiar huérfanos)."""
    controller = getattr(ctx, "project_controller", None)
    project = getattr(getattr(controller, "ps", None), "active_project", None)
    referenced: set[str] = set()
    for entity in getattr(project, "entities", []) or []:
        meta = getattr(entity, "custom_metadata", {}) or {}
        stored = str(meta.get(IMAGE_PATH_KEY, "") or "")
        if stored:
            referenced.add(stored)
    return referenced


def resolve_portrait_path(ctx, stored: str) -> Path | None:
    """Ruta absoluta de la imagen guardada, o None si no es localizable.

    Relativa ⇒ asset store del proyecto; absoluta ⇒ legacy BETA1-F04 (se
    respeta mientras exista el archivo original).
    """
    stored = str(stored or "")
    if not stored:
        return None
    if os.path.isabs(stored):
        candidate = Path(stored)
        return candidate if candidate.exists() else None
    project_path = project_path_of(ctx)
    if project_path is None:
        return None
    candidate = _service.resolve(project_path, stored)
    return candidate if candidate.exists() else None


def apply_portrait(
    ctx,
    entity_controller,
    entity_id: str,
    crop: PortraitCrop,
    *,
    data: bytes | None = None,
    ext: str = "",
    source_file: Path | None = None,
    keep_rel: str | None = None,
) -> bool:
    """Importa (si procede) y persiste retrato + encuadre de la entidad.

    Exactamente uno de ``data``/``source_file``/``keep_rel`` decide el origen:
    bytes descargados, archivo local, o conservar el asset actual (solo cambia
    el encuadre). Devuelve True si quedó persistido.
    """
    project_path = project_path_of(ctx)
    if project_path is None:
        return False
    if keep_rel is not None:
        imported = Ok(keep_rel)
    elif source_file is not None:
        imported = _service.import_image_file(project_path, Path(source_file))
    elif data is not None:
        imported = _service.import_image_bytes(project_path, data, ext)
    else:
        return False
    if isinstance(imported, Error):
        ctx.notify(imported.error, "error")
        return False
    rel_path = imported.value

    result = entity_controller.get(entity_id)
    entity = getattr(result, "value", None)
    metadata = dict(getattr(entity, "custom_metadata", {}) or {}) if entity is not None else {}
    previous = str(metadata.get(IMAGE_PATH_KEY, "") or "")
    metadata[IMAGE_PATH_KEY] = rel_path
    metadata[IMAGE_CROP_KEY] = crop.normalize().to_dict()
    update = entity_controller.update(entity_id, {"custom_metadata": metadata})
    if isinstance(update, Error):
        ctx.notify(f"No se pudo asociar la imagen: {update.error}", "error")
        return False
    _cleanup_orphan(ctx, project_path, previous, rel_path)
    ctx.notify("Retrato guardado", "success")
    return True


def remove_portrait(ctx, entity_controller, entity_id: str) -> bool:
    """Quita el retrato de la entidad y limpia el asset si quedó huérfano."""
    result = entity_controller.get(entity_id)
    entity = getattr(result, "value", None)
    metadata = dict(getattr(entity, "custom_metadata", {}) or {}) if entity is not None else {}
    previous = str(metadata.pop(IMAGE_PATH_KEY, "") or "")
    metadata.pop(IMAGE_CROP_KEY, None)
    update = entity_controller.update(entity_id, {"custom_metadata": metadata})
    if isinstance(update, Error):
        ctx.notify(f"No se pudo quitar la imagen: {update.error}", "error")
        return False
    project_path = project_path_of(ctx)
    if project_path is not None:
        _cleanup_orphan(ctx, project_path, previous, "")
    ctx.notify("Imagen quitada", "info")
    return True


def _cleanup_orphan(ctx, project_path: Path, previous: str, current: str) -> None:
    """Borra el asset anterior si ya nadie lo referencia (solo rutas relativas)."""
    if not previous or previous == current or os.path.isabs(previous):
        return
    referenced = collect_referenced_image_paths(ctx)
    outcome = _service.delete_if_unreferenced(project_path, previous, referenced)
    if isinstance(outcome, Error):
        ctx.log("error", outcome.error)


# ---------------------------------------------------------------------------
# Flujo de UI (menú + diálogos)
# ---------------------------------------------------------------------------

def open_image_menu(panel) -> None:
    """Menú del botón de imagen: subir / buscar / editar encuadre / quitar."""
    result = panel.entity_controller.get(panel.entity_id)
    entity = getattr(result, "value", None)
    metadata = dict(getattr(entity, "custom_metadata", {}) or {}) if entity is not None else {}
    stored = str(metadata.get(IMAGE_PATH_KEY, "") or "")

    menu = QMenu(panel)
    act_upload = menu.addAction("Subir imagen…")
    act_search = menu.addAction("Buscar en internet…")
    act_edit = act_remove = None
    if stored:
        menu.addSeparator()
        act_edit = menu.addAction("Editar encuadre…")
        act_remove = menu.addAction("Quitar imagen")
    anchor = panel.image_btn
    chosen = menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))
    if chosen is None:
        return
    if chosen is act_upload:
        _upload_flow(panel)
    elif chosen is act_search:
        _search_flow(panel)
    elif act_edit is not None and chosen is act_edit:
        _edit_crop_flow(panel, stored, metadata)
    elif act_remove is not None and chosen is act_remove:
        if remove_portrait(panel.ctx, panel.entity_controller, panel.entity_id):
            panel.refresh()


def _upload_flow(panel) -> None:
    """Origen archivo local: QFileDialog → editor de encuadre → persistir."""
    if ensure_project_path(panel.ctx) is None:
        return
    path, _ = QFileDialog.getOpenFileName(
        panel, "Importar imagen", "", "Imágenes (*.png *.jpg *.jpeg *.webp)"
    )
    if not path:
        return
    pixmap = QPixmap(path)
    if pixmap.isNull():
        panel.ctx.notify("No se pudo leer esa imagen", "error")
        return
    crop = _run_editor(panel, pixmap)
    if crop is None:
        return
    if apply_portrait(
        panel.ctx, panel.entity_controller, panel.entity_id, crop, source_file=Path(path)
    ):
        panel.refresh()


def _search_flow(panel) -> None:
    """Origen internet: búsqueda Openverse → editor de encuadre → persistir."""
    if ensure_project_path(panel.ctx) is None:
        return
    # Import perezoso: el diálogo arrastra el cliente HTTP de infrastructure.
    from hosts.DesktopHostPySide.widgets.image_search_dialog import ImageSearchDialog

    dialog = ImageSearchDialog(parent=panel)
    if not dialog.exec():
        return
    picked = dialog.selected_image()
    if picked is None:
        return
    data, ext = picked
    pixmap = QPixmap()
    if not pixmap.loadFromData(data):
        panel.ctx.notify("La imagen descargada no se pudo leer", "error")
        return
    crop = _run_editor(panel, pixmap)
    if crop is None:
        return
    if apply_portrait(
        panel.ctx, panel.entity_controller, panel.entity_id, crop, data=data, ext=ext
    ):
        panel.refresh()


def _edit_crop_flow(panel, stored: str, metadata: dict) -> None:
    """Reencuadrar la imagen actual (las legacy absolutas se normalizan)."""
    resolved = resolve_portrait_path(panel.ctx, stored)
    if resolved is None:
        panel.ctx.notify("La imagen original ya no está disponible", "error")
        return
    pixmap = QPixmap(str(resolved))
    if pixmap.isNull():
        panel.ctx.notify("La imagen original no se pudo leer", "error")
        return
    current = parse_crop(metadata.get(IMAGE_CROP_KEY))
    crop = _run_editor(panel, pixmap, current)
    if crop is None:
        return
    if os.path.isabs(stored):
        # Legacy BETA1-F04: al reencuadrar se importa al asset store.
        applied = apply_portrait(
            panel.ctx, panel.entity_controller, panel.entity_id, crop, source_file=resolved
        )
    else:
        applied = apply_portrait(
            panel.ctx, panel.entity_controller, panel.entity_id, crop, keep_rel=stored
        )
    if applied:
        panel.refresh()


def _run_editor(panel, pixmap: QPixmap, crop: PortraitCrop | None = None) -> PortraitCrop | None:
    from hosts.DesktopHostPySide.widgets.portrait_editor_dialog import PortraitEditorDialog

    editor = PortraitEditorDialog(pixmap, crop, parent=panel)
    if not editor.exec():
        return None
    return editor.selected_crop()
