"""BETA2-FIX-11 (fase C): la wiki se escribe A MANO, sin IA.

Antes el cuerpo de la página era `setReadOnly(True)` («lo escribe Regar»), `_save`
ni siquiera mandaba `cuerpo=`, no había forma de crear una página y la lista
identificaba cada una por `entity:<uuid>`. Resultado: quien trabaja con el
proveedor apagado no podía usar la función insignia del producto (SIA-19, deseo
nº1 de Marta, que acabó escribiendo sus tres páginas por código).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from dataclasses import dataclass, field  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.widgets.memory_viewer_panel import MemoryViewerPanel  # noqa: E402
from packages.application.narrative_memory_service import NarrativeMemoryService  # noqa: E402
from packages.domain.causal_milestone import CausalMilestone  # noqa: E402
from packages.domain.entity import NarrativeEntity  # noqa: E402
from packages.domain.narrative_memory import (  # noqa: E402
    MemoryFreshness,
    MemoryOrigin,
    MemoryTargetKind,
)
from packages.domain.project import Project  # noqa: E402
from packages.domain.relation import NarrativeRelation  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@dataclass
class _FakeProjectService:
    active_project: Project = None


@dataclass
class _FakeCtx:
    """Doble del AppContext: solo cuenta cuántas veces se pidió guardar a disco."""

    saves: list[str] = field(default_factory=list)

    def request_save_silent(self) -> None:
        self.saves.append("silent")


def _project() -> Project:
    p = Project(id="p", name="La escalera del olmo")
    p.entities.append(NarrativeEntity(id="e1", name="Marta Olmo"))
    p.entities.append(NarrativeEntity(id="e2", name="El olmo viejo"))
    p.relations.append(NarrativeRelation(id="r1", source_id="e1", target_id="e2"))
    p.causal_milestones.append(CausalMilestone(id="h1", title="La tala"))
    return p


def _panel(ctx=None, ai=None):
    ps = _FakeProjectService(active_project=_project())
    mem = NarrativeMemoryService(ps)
    return MemoryViewerPanel(mem, ai, ctx=ctx), mem, ps


# ── el cuerpo se escribe ────────────────────────────────────────────────


def test_beta_m2fix11_cuerpo_editable_y_guardado(qapp):
    panel, mem, _ = _panel(ctx=_FakeCtx())
    assert not panel.cuerpo.isReadOnly()  # la caja ya no está cerrada con llave

    assert panel.create_page(MemoryTargetKind.ENTITY.value, "e1")
    panel.cuerpo.setPlainText("Marta bajó la escalera.\n\nY el olmo la miraba.")
    panel.resumen.setPlainText("La protagonista.")
    panel._save()

    block = mem.get_memory(MemoryTargetKind.ENTITY, "e1").value
    assert block is not None
    assert "el olmo la miraba" in block.cuerpo  # lo escrito NO se tira
    assert block.resumen_editorial == "La protagonista."


def test_beta_m2fix11_guardar_pide_guardado_a_disco(qapp):
    ctx = _FakeCtx()
    panel, _, _ = _panel(ctx=ctx)
    panel.create_page(MemoryTargetKind.ENTITY.value, "e1")
    saves_tras_crear = len(ctx.saves)
    panel.cuerpo.setPlainText("Tres párrafos de wiki.")
    panel._save()
    assert saves_tras_crear >= 1  # crear ya programa guardado
    assert len(ctx.saves) > saves_tras_crear  # y guardar también


def test_beta_m2fix11_sin_ctx_no_revienta(qapp):
    """El panel se usa también sin ctx (tests, otras puertas): no puede explotar."""
    panel, mem, _ = _panel(ctx=None)
    panel.create_page(MemoryTargetKind.ENTITY.value, "e1")
    panel.cuerpo.setPlainText("texto")
    panel._save()
    assert mem.get_memory(MemoryTargetKind.ENTITY, "e1").value.cuerpo == "texto"


# ── nueva página ────────────────────────────────────────────────────────


def test_beta_m2fix11_nueva_pagina_elige_por_nombre(qapp):
    panel, mem, _ = _panel(ctx=_FakeCtx())
    etiquetas = [label for label, _kind, _tid in panel.available_targets()]
    assert any("Marta Olmo" == label for label in etiquetas)
    assert any("Marta Olmo → El olmo viejo" in label for label in etiquetas)
    assert any("La tala" in label for label in etiquetas)
    assert all("e1" != label for label in etiquetas)  # nunca el uuid pelado

    # El combo se rellena con esas mismas etiquetas y «Crear» crea el bloque.
    panel._toggle_new_page()
    assert not panel.new_page_row.isHidden()
    idx = next(
        i for i in range(panel.new_page_combo.count())
        if panel.new_page_combo.itemText(i) == "Marta Olmo"
    )
    panel.new_page_combo.setCurrentIndex(idx)
    panel._confirm_new_page()

    block = mem.get_memory(MemoryTargetKind.ENTITY, "e1").value
    assert block is not None
    assert block.origin == MemoryOrigin.USUARIO
    assert block.freshness == MemoryFreshness.REGADA  # nace vigente → Regar no la pisa
    assert panel.new_page_row.isHidden()


def test_beta_m2fix11_lista_y_cabecera_por_nombre_no_uuid(qapp):
    panel, mem, _ = _panel(ctx=_FakeCtx())
    mem.upsert_memory(MemoryTargetKind.ENTITY, "e1", resumen_editorial="x")
    mem.upsert_memory(MemoryTargetKind.RELATION, "r1", resumen_editorial="y")
    mem.upsert_memory(MemoryTargetKind.MILESTONE, "h1", resumen_editorial="z")
    panel.refresh()
    filas = [panel.list.item(i).text() for i in range(panel.list.count())]
    assert any(f.startswith("Marta Olmo ·") for f in filas)
    assert any("Marta Olmo → El olmo viejo" in f for f in filas)
    assert any("La tala" in f for f in filas)
    assert not any("e1" in f or "r1" in f or "h1" in f for f in filas)

    panel.list.setCurrentRow(0)
    assert "e1" not in panel.header.text()


def test_beta_m2fix11_pagina_de_elemento_borrado_no_ensena_uuid(qapp):
    panel, mem, _ = _panel(ctx=_FakeCtx())
    mem.upsert_memory(MemoryTargetKind.ENTITY, "fantasma-1234-5678", resumen_editorial="x")
    panel.refresh()
    filas = [panel.list.item(i).text() for i in range(panel.list.count())]
    assert any("elemento eliminado" in f for f in filas)
    assert not any("fantasma-1234-5678" in f for f in filas)


# ── todo lo anterior, con la IA apagada ─────────────────────────────────


def test_beta_m2fix11_sin_ia_solo_se_apaga_regenerar(qapp):
    panel, mem, _ = _panel(ctx=_FakeCtx(), ai=None)
    assert not panel.regen_btn.isEnabled()
    assert "proveedor" in panel.regen_btn.toolTip().lower()
    # ...y el resto de la wiki funciona igual
    assert panel.new_page_btn.isEnabled()
    assert panel.save_btn.isEnabled()
    assert panel.delete_btn.isEnabled()
    assert panel.create_page(MemoryTargetKind.ENTITY.value, "e2")
    panel.cuerpo.setPlainText("Escrito sin proveedor de IA.")
    panel._save()
    assert mem.get_memory(MemoryTargetKind.ENTITY, "e2").value.cuerpo.startswith("Escrito sin")


def test_beta_m2fix11_editar_a_mano_marca_autoria_y_vigencia(qapp):
    """Editar a mano una página que escribió la IA la hace tuya (y Regar no la pisa)."""
    panel, mem, _ = _panel(ctx=_FakeCtx())
    mem.upsert_memory(
        MemoryTargetKind.ENTITY,
        "e1",
        cuerpo="lo que escribió la IA",
        origin=MemoryOrigin.IA,
        freshness=MemoryFreshness.FALTA_REGAR,
    )
    panel.refresh()
    panel.select_page((MemoryTargetKind.ENTITY.value, "e1", ""))
    panel.cuerpo.setPlainText("lo que escribí yo")
    panel._save()
    block = mem.get_memory(MemoryTargetKind.ENTITY, "e1").value
    assert block.cuerpo == "lo que escribí yo"
    assert block.origin == MemoryOrigin.USUARIO
    assert block.freshness == MemoryFreshness.REGADA
