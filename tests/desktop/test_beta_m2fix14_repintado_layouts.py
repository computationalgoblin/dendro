"""BETA2-FIX-14 (G2-21 + «texto fantasma» de G2-26): layouts que no se vacían.

El idioma repetido por el host —`while layout.count(): layout.takeAt(0)` +
`widget.deleteLater()`— NO basta: `deleteLater` solo ENCUELA el borrado, así que
hasta que el bucle de eventos lo procese el widget sigue siendo hijo del contenedor
y **sigue pintándose**.

Dos testers, dos síntomas, un mismo bug en tres ficheros: el panel de Estructura
pintando el mensaje nuevo encima del anterior (dos párrafos entrelazados e
ilegibles) y los chips de la Ficha del Foco leyéndose «MedioMedio» / «Medio» sobre
«(edio». El síntoma depende de si el bucle de eventos corre entre el `_build()` y el
repintado — por eso un guion que no cede el control no lo ve y una captura sí.

Estos tests NO procesan eventos a propósito: es exactamente la ventana en la que el
usuario ve el fantasma.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget  # noqa: E402

from hosts.DesktopHostPySide.widgets.design_system import clear_layout  # noqa: E402
from hosts.DesktopHostPySide.widgets.structure_review_panel import (  # noqa: E402
    StructureReviewPanel,
)
from packages.application.causal_potency import build_ring_move_proposal  # noqa: E402
from packages.application.project_service import ProjectService  # noqa: E402
from packages.application.structural_analysis_service import StructuralFinding  # noqa: E402
from packages.domain.entity import NarrativeEntity, NarrativeImportance  # noqa: E402
from packages.domain.result import Ok  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


# ── el helper compartido ─────────────────────────────────────────────────────


def test_beta_m2fix14_clear_layout_desparenta_de_verdad():
    contenedor = QWidget()
    layout = QVBoxLayout(contenedor)
    etiquetas = [QLabel(f"viejo {n}", contenedor) for n in range(3)]
    for etiqueta in etiquetas:
        layout.addWidget(etiqueta)
    assert all(e.parent() is contenedor for e in etiquetas)

    retirados = clear_layout(layout)

    assert retirados == 3
    assert layout.count() == 0
    assert all(e.parent() is None for e in etiquetas), (
        "sin setParent(None) el widget sigue siendo hijo y SIGUE pintándose"
    )


def test_beta_m2fix14_clear_layout_recurre_sobre_sublayouts():
    """Varios `_build` mezclan `addWidget` y `addLayout`."""
    contenedor = QWidget()
    layout = QVBoxLayout(contenedor)
    fila = QVBoxLayout()
    dentro = QLabel("dentro", contenedor)
    fila.addWidget(dentro)
    layout.addLayout(fila)

    clear_layout(layout)

    assert layout.count() == 0
    assert dentro.parent() is None


def test_beta_m2fix14_clear_layout_conserva_el_stretch_final():
    """La estantería de contenidos conserva su `addStretch` final."""
    contenedor = QWidget()
    layout = QVBoxLayout(contenedor)
    etiqueta = QLabel("chip", contenedor)
    layout.addWidget(etiqueta)
    layout.addStretch(1)

    retirados = clear_layout(layout, conservar_al_final=1)

    assert retirados == 1
    assert layout.count() == 1, "el espaciador final debe sobrevivir"
    assert etiqueta.parent() is None


# ── el panel de Estructura ───────────────────────────────────────────────────


@dataclass
class _FakeService:
    findings: list = field(default_factory=list)
    structures: list = field(default_factory=list)

    def analyze(self):
        return Ok(list(self.findings))

    def baseline_justification(self, finding):
        return "razón base"

    def enrich_justification(self, finding):
        return Ok("prosa")

    def dismiss(self, fingerprint):
        return Ok(True)

    def postpone(self, fingerprint):
        return Ok(True)

    def structure_proposals(self):
        return list(self.structures)

    def propose_ring_structure(self):
        return Ok(list(self.structures))

    def discard_structure_proposal(self, fingerprint):
        self.structures = [f for f in self.structures if f.fingerprint != fingerprint]


def _finding(fp: str) -> StructuralFinding:
    propuesta = build_ring_move_proposal(
        "Hoja",
        current_ring_id="a",
        target_ring_id="b",
        reasons=["motivo"],
        expected_consequences=["consecuencia"],
        supporting_relation_ids=["rel"],
    )
    return StructuralFinding(
        kind="ring_move",
        target_id="Hoja",
        proposed_data=propuesta,
        confidence=0.9,
        fingerprint=fp,
        title=f"Reubicar «Hoja» ({fp})",
    )


def test_beta_m2fix14_structure_panel_no_deja_widgets_huerfanos():
    servicio = _FakeService(findings=[_finding("uno")])
    panel = StructureReviewPanel(servicio, on_accept=lambda f: None)
    primeros = panel.findChildren(QWidget)
    assert primeros, "el primer build debe haber creado algo"

    servicio.findings = [_finding("dos")]
    panel._build()  # segundo build SIN ceder el control al bucle de eventos

    # La invariante REAL del repintado: Qt pinta el árbol de hijos del panel. Un
    # widget del build anterior que siga siendo descendiente se sigue pintando,
    # aunque tenga un `deleteLater` encolado.
    vivos = [w for w in primeros if panel.isAncestorOf(w)]
    assert vivos == [], (
        "los widgets del primer build siguen colgando del panel y se pintan encima"
    )
    # Y el mensaje nuevo está, entero y solo.
    assert panel.findChildren(QWidget), "el segundo build debe haber pintado algo"


def test_beta_m2fix14_el_mensaje_de_estado_no_se_entrelaza():
    """Reproduce lo que fotografió la tester: «Proponer estructura» sin proveedor."""
    servicio = _FakeService()
    panel = StructureReviewPanel(servicio, on_accept=lambda f: None)
    panel._status_text = "No hay proveedor de IA configurado."
    panel._build()
    viejos = [w for w in panel.findChildren(QLabel) if "proveedor" in w.text()]
    assert viejos

    panel._status_text = "Se proponen 2 anillos nuevos."
    panel._build()

    textos = [w.text() for w in panel.findChildren(QLabel)]
    assert not any("proveedor" in t for t in textos), (
        "el mensaje anterior seguía vivo bajo el nuevo (dos párrafos entrelazados)"
    )
    assert any("2 anillos nuevos" in t for t in textos)
    assert all(not panel.isAncestorOf(w) for w in viejos)


# ── la Ficha del Foco ────────────────────────────────────────────────────────


def _foco_view():
    servicio = ProjectService()
    servicio.create("Fantasmas")
    proyecto = servicio.active_project

    from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

    view = FocoView(project_provider=lambda: proyecto)
    return servicio, proyecto, view


def _entidad(proyecto, nombre, importancia):
    entidad = NarrativeEntity(name=nombre, narrative_importance=importancia)
    proyecto.entities.append(entidad)
    proyecto.touch()
    return entidad


def test_beta_m2fix14_tira_de_chips_del_foco_no_duplica():
    _, proyecto, view = _foco_view()
    uno = _entidad(proyecto, "Rosa", NarrativeImportance.MEDIO)
    dos = _entidad(proyecto, "Nasr", NarrativeImportance.CRITICO)

    view._refresh_meta_summary(uno)
    primeros = [w for w in view._meta_summary_box.findChildren(QLabel) if w.text()]
    textos_uno = {w.text() for w in primeros}
    assert textos_uno, "la tira de chips debe pintar algo"

    view._refresh_meta_summary(dos)

    caja = view._meta_summary_box
    huerfanos = [w for w in primeros if caja.isAncestorOf(w)]
    assert huerfanos == [], (
        "los chips de la entidad anterior seguían colgando del cuadro: eso es el "
        "«MedioMedio» y la «s» suelta que fotografió dirección de arte"
    )
    vivos = {w.text() for w in caja.findChildren(QLabel) if w.text()}
    assert vivos, "la tira nueva debe existir"
    assert "Crítico" in vivos or "Critico" in vivos, vivos
    assert "Medio" not in vivos, "el chip de la entidad anterior no puede sobrevivir"


def test_beta_m2fix14_estanteria_de_contenidos_no_duplica():
    _, proyecto, view = _foco_view()
    rama = _entidad(proyecto, "La Casa", NarrativeImportance.ALTO)
    hoja_a = _entidad(proyecto, "Sótano", NarrativeImportance.MEDIO)
    hoja_b = _entidad(proyecto, "Desván", NarrativeImportance.MEDIO)

    view._refresh_contents_shelf(rama)
    antes = [w for w in view._contents_shelf.findChildren(QWidget) if w.parent() is not None]

    view._refresh_contents_shelf(hoja_a)  # una hoja: la estantería se vacía y se oculta
    view._refresh_contents_shelf(hoja_b)

    layout = view._contents_layout
    assert layout.count() == 1, "solo debe quedar el espaciador final"
    # Ninguna miniatura del primer llenado conserva el padre.
    from hosts.DesktopHostPySide.widgets.foco.foco_view import _ContentThumb

    miniaturas = [w for w in antes if isinstance(w, _ContentThumb)]
    assert all(w.parent() is None for w in miniaturas)


def test_beta_m2fix14_las_tres_copias_usan_el_helper():
    """Guarda de fuente: si alguien vuelve al idioma roto, este test cae."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    foco = (raiz / "hosts/DesktopHostPySide/widgets/foco/foco_view.py").read_text(
        encoding="utf-8"
    )
    panel = (raiz / "hosts/DesktopHostPySide/widgets/structure_review_panel.py").read_text(
        encoding="utf-8"
    )
    assert foco.count("clear_layout(") >= 2
    assert "clear_layout(self._outer)" in panel
    for fuente in (foco, panel):
        assert "takeAt(0)\n" not in fuente or "clear_layout" in fuente


def test_beta_m2fix14_el_contexto_falso_no_hace_falta():
    """El helper es puro Qt: no necesita ctx ni servicios (evita acoplarlo)."""
    assert clear_layout(None) == 0
    assert isinstance(SimpleNamespace(), SimpleNamespace)
