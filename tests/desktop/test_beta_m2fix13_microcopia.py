"""BETA2-FIX-13 · TANDA E — hablar el idioma del usuario (G2-20).

    «"(contrato §16)". La aplicación está citando su propia especificación
    interna, por número de sección, a una novelista. No existe ningún §16 que yo
    pueda abrir.» — Nerea, diseñadora de producto.

La metáfora del jardín NO se toca: gusta. Lo que se arregla es que no se enseñaba
(el glosario sólo salía por tooltip) y que los nombres internos se filtraban por
encima de ella.
"""
from __future__ import annotations

import os
import re
import unicodedata

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.widgets.design_system import enum_human  # noqa: E402
from packages.domain.causal_milestone import CausalMilestoneType  # noqa: E402
from packages.domain.entity import EntityType  # noqa: E402
from packages.domain.relation import RelationType  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ── criterio 14 · las tildes ───────────────────────────────────────────────

# Las once palabras que cazó la maestra, tal y como las enseñaba la app.
_SIN_TILDE_CAZADAS = (
    "Localizacion",
    "Faccion",
    "Tecnologia",
    "Sistema magico",
    "Institucion",
    "Fundacion",
    "Traicion",
    "Catastrofe",
    "Migracion",
    "Caida",
    "Revelacion",
)


def _etiquetas() -> list[str]:
    return [
        enum_human(v)
        for enum in (EntityType, RelationType, CausalMilestoneType)
        for v in enum
    ]


def test_beta_m2fix13_enum_human_pone_las_tildes():
    mostradas = _etiquetas()
    culpables = [p for p in _SIN_TILDE_CAZADAS if p in mostradas]
    assert not culpables, f"todavía se enseñan sin tilde: {culpables}"

    # Y las once, escritas como toca.
    esperadas = {
        EntityType.LOCALIZACION: "Localización",
        EntityType.FACCION: "Facción",
        EntityType.TECNOLOGIA: "Tecnología",
        EntityType.SISTEMA_MAGICO: "Sistema mágico",
        EntityType.INSTITUCION: "Institución",
        CausalMilestoneType.FUNDACION: "Fundación",
        CausalMilestoneType.TRAICION: "Traición",
        CausalMilestoneType.CATASTROFE: "Catástrofe",
        CausalMilestoneType.MIGRACION: "Migración",
        CausalMilestoneType.CAIDA: "Caída",
        CausalMilestoneType.REVELACION: "Revelación",
    }
    for valor, etiqueta in esperadas.items():
        assert enum_human(valor) == etiqueta, valor


def test_beta_m2fix13_ninguna_etiqueta_termina_en_cion_sin_tilde():
    """Guarda general: cualquier enum nuevo que acabe en -cion/-sion se cazaría
    aquí antes de llegar a un combo."""
    patron = re.compile(r"\b\w*(cion|sion)\b", re.IGNORECASE)
    culpables = [e for e in _etiquetas() if patron.search(e)]
    assert not culpables, f"etiquetas sin tilde: {culpables}"


def test_beta_m2fix13_ningun_valor_de_enum_cambio_en_disco():
    """Las tildes son SOLO la cara visible: la forma en disco no se toca (si
    cambiara, ningún proyecto existente cargaría)."""
    for enum in (EntityType, RelationType, CausalMilestoneType):
        for valor in enum:
            crudo = valor.value
            assert crudo == crudo.lower()
            assert crudo == unicodedata.normalize("NFKD", crudo).encode("ascii", "ignore").decode()


def test_beta_m2fix13_los_combos_siguen_reseleccionando(qapp):
    """TRAMPA del ticket: `node_detail_panel` y `relation_detail_panel` reseleccionan
    su combo con `combo.findText(enum_human(value))`. Si el mapa de etiquetas se
    hubiera puesto en los `addItem` y no dentro de `enum_human`, la ficha dejaría
    de reseleccionar su propio tipo al abrirse, EN SILENCIO. Prueba de ida y vuelta."""
    from PySide6.QtWidgets import QComboBox

    combo = QComboBox()
    try:
        for tipo in EntityType:
            combo.addItem(enum_human(tipo), tipo.value)
        for tipo in EntityType:
            indice = combo.findText(enum_human(tipo))
            assert indice >= 0, f"«{tipo.value}» no se encuentra por su texto mostrado"
            assert combo.itemData(indice) == tipo.value
    finally:
        combo.deleteLater()
        qapp.processEvents()


def test_beta_m2fix13_la_ficha_reselecciona_su_tipo_con_tilde(qapp):
    """El caso real end-to-end: una entidad de tipo `localizacion` abre su ficha y
    el combo tiene que quedar en «Localización»."""
    from hosts.DesktopHostPySide.app_context import AppContext
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel
    from packages.application.project_service import ProjectService

    servicio = ProjectService()
    servicio.create("Tildes")
    ctx = AppContext()
    ctx.project_controller = type("Stub", (), {"ps": servicio})()
    controlador = EntityController(servicio)
    hoja = controlador.create({"name": "Cádiz", "entity_type": "localizacion"}).value

    panel = NodeDetailPanel(ctx, controlador, hoja.id, variant="foco")
    try:
        assert panel.type_combo.currentText() == "Localización"
    finally:
        panel.deleteLater()
        qapp.processEvents()


# ── criterio 15 · nombres internos en pantalla ─────────────────────────────


def test_beta_m2fix13_no_hay_nombres_internos_en_pantalla(qapp):
    """«Campo: extended_description» era lo ÚNICO que le decía a Carmen QUÉ iba a
    cambiar la IA en su novela."""
    from PySide6.QtWidgets import QLabel

    from hosts.DesktopHostPySide.widgets.candidate_review_panel import CandidateReviewPanel
    from packages.domain.candidate_issue import Candidate, CandidateType

    candidato = Candidate(
        title="Editar Marta Iriarte",
        candidate_type=CandidateType.ENTIDAD,
        proposed_data={
            "edit_kind": "entity_edits",
            "edit_target_name": "Marta Iriarte",
            "edit_fields": {
                "birth_year": 1931,
                "extended_description": "Nació en un cortijo de Medina Sidonia.",
            },
        },
        source="ai",
    )
    panel = CandidateReviewPanel(candidato, controller=None)
    try:
        textos = " ".join(w.text() for w in panel.findChildren(QLabel))
        assert "extended_description" not in textos
        assert "birth_year" not in textos
        assert "descripción larga" in textos
        assert "año de nacimiento" in textos
    finally:
        panel.deleteLater()
        qapp.processEvents()


# ── criterio 17 · el glosario ──────────────────────────────────────────────

# Los 27 términos del «Diccionario de Carmen»: los 19 que ya existían + los 8
# que faltaban (entidad, germinar/florecer/marchitarse, cultivar, foco,
# raíces/entorno/brotes, estructura, play, token).
_DICCIONARIO_DE_CARMEN = (
    "anillo", "arraigo", "canon", "capa", "cultivar", "entidad", "era",
    "estructura", "falta_regar", "fantasma", "foco", "germinar", "hito", "hoja",
    "iluminada", "lapso_vida", "memoria", "nutrida", "play", "potencia_causal",
    "raices", "rama", "regar", "relevancia", "secada", "semilla", "token",
)


def test_beta_m2fix13_glosario_cubre_el_diccionario_de_carmen():
    from hosts.DesktopHostPySide.widgets.field_help import glossary

    assert len(_DICCIONARIO_DE_CARMEN) == 27
    faltan = [t for t in _DICCIONARIO_DE_CARMEN if not glossary(t).strip()]
    assert not faltan, f"sin definición: {faltan}"
    # Regla heredada de BETA-AUDIT-06: una definición no puede ser la palabra.
    for termino in _DICCIONARIO_DE_CARMEN:
        definicion = glossary(termino).strip().lower()
        assert definicion != termino.replace("_", " ")
        assert len(definicion) > 40, f"«{termino}» se explica en cuatro palabras"


def test_beta_m2fix13_el_glosario_se_lee_sin_hover(qapp):
    """Criterio 13/17: el catálogo llega a una superficie visible, no a un tooltip."""
    from PySide6.QtWidgets import QLabel

    from hosts.DesktopHostPySide.widgets.field_help import GlossaryPanel, glossary

    panel = GlossaryPanel()
    try:
        en_pantalla = set(panel.terms_on_screen())
        faltan = [t for t in _DICCIONARIO_DE_CARMEN if t not in en_pantalla]
        assert not faltan, f"términos que el panel no pinta: {faltan}"
        textos = " ".join(w.text() for w in panel.findChildren(QLabel))
        assert glossary("anillo") in textos
        assert glossary("germinar") in textos
        # …y se lee del texto, no de un tooltip.
        assert "Germinar, florecer, marchitarse" in textos
    finally:
        panel.deleteLater()
        qapp.processEvents()


# ── criterio 18 · la salida del proveedor ──────────────────────────────────


def test_beta_m2fix13_el_markdown_no_llega_al_canon():
    """Decisión tomada: se LIMPIA, y se limpia al estadiar (antes de que el usuario
    lo lea), no al aceptar — así lo que lee y lo que acepta son el mismo texto."""
    from packages.application.ai_jobs import sanitize_model_text

    sucio = "El **rey** de *Cádiz* guarda un `secreto`.\n## Notas\n* uno\n* dos"
    limpio = sanitize_model_text(sucio)
    assert "**" not in limpio and "`" not in limpio and "##" not in limpio
    assert "rey" in limpio and "Cádiz" in limpio and "secreto" in limpio
    assert "uno" in limpio and "dos" in limpio
    # La prosa normal no se toca (guiones de diálogo, puntuación, asteriscos sueltos).
    assert sanitize_model_text("—¿Y ahora qué? —dijo.") == "—¿Y ahora qué? —dijo."


def test_beta_m2fix13_se_avisa_del_alfabeto_extranjero(qapp):
    """No se borra (quien escribe en chino tiene derecho a su canon): se AVISA."""
    from hosts.DesktopHostPySide.widgets.candidate_review_panel import foreign_script_warning
    from packages.domain.candidate_issue import Candidate, CandidateType

    limpio = Candidate(
        title="x",
        candidate_type=CandidateType.ENTIDAD,
        proposed_data={"report": "Falta de años en entidades clave"},
    )
    sucio = Candidate(
        title="x",
        candidate_type=CandidateType.ENTIDAD,
        proposed_data={"report": "Falta de年份 en entidades clave"},
    )
    assert foreign_script_warning(limpio) == ""
    assert "otro alfabeto" in foreign_script_warning(sucio)
    # El prompt del PROPIO usuario no dispara el aviso (es suyo, no del modelo).
    suyo = Candidate(
        title="x", candidate_type=CandidateType.ENTIDAD, proposed_data={"prompt": "年份"}
    )
    assert foreign_script_warning(suyo) == ""


def test_beta_m2fix13_el_prompt_base_prohibe_markdown_y_fija_el_idioma():
    from packages.application.command_prompts import _BASE_ES

    assert "Markdown" in _BASE_ES
    assert "idioma del proyecto" in _BASE_ES
