"""BETA-MULTIAGENT2-FIX-02 (G2-02): la semilla de HITO se revisa legible.

Antes, `candidate_body_text` solo miraba claves de primer nivel de
`proposed_data`, y el payload del hito va ANIDADO en `proposed_data["milestone"]`:
el 100 % de las semillas de hito se revisaban en blanco («acepté un recuadro
gris»). Y la caja, además de no leer, escribía lo editado en
`extended_description`, clave que la aceptación de hitos nunca lee.

Estos tests fijan las dos direcciones: se LEE lo que se va a aceptar (texto, año,
tipo) y lo editado vuelve al MISMO sitio del que se leyó.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hosts.DesktopHostPySide.widgets.candidate_review_panel import (
    CandidateReviewPanel,
    candidate_body_text,
    is_milestone_candidate,
    milestone_facts_text,
)
from packages.domain.result import Ok

ROOT = Path(__file__).resolve().parents[2]
BETA = ROOT / "beta-testing" / "2026-08-04"


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


class _FakeController:
    """Mismo patrón que `tests/desktop/test_ux5_candidate_review.py`."""

    def __init__(self, entities=None):
        self.accepted: list[str] = []
        self.rejected: list[str] = []
        self.ps = SimpleNamespace(active_project=SimpleNamespace(entities=list(entities or [])))

    def accept(self, cid):
        self.accepted.append(cid)
        return Ok(SimpleNamespace(id=cid))

    def reject(self, cid):
        self.rejected.append(cid)
        return Ok(SimpleNamespace(id=cid))


def _candidate(proposed, *, cid="c1", title="Hito sugerido: X", kind="sugerencia_ia"):
    return SimpleNamespace(
        id=cid,
        title=title,
        candidate_type=SimpleNamespace(value=kind),
        proposed_data=proposed,
        metadata={},
    )


def _beta_milestone_candidate(world: str, *, state: str = "pendiente", title_contains: str = ""):
    """Carga del beta un candidato de hito real (o salta si el mundo no está)."""
    path = BETA / world
    if not path.exists():  # pragma: no cover — el repo del beta viaja con el ticket
        pytest.skip(f"mundo del beta no disponible: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    for raw in data.get("candidates", []):
        proposed = raw.get("proposed_data") or {}
        if proposed.get("kind") != "causal_milestone":
            continue
        if raw.get("state") != state:
            continue
        if title_contains and title_contains not in str(raw.get("title") or ""):
            continue
        return _candidate(proposed, cid=str(raw.get("id") or "beta"), title=str(raw.get("title")))
    pytest.skip(f"sin candidato de hito {state!r} en {world}")
    return None  # pragma: no cover


# ── Lectura: el helper desciende al payload anidado ──────────────────────────


def test_beta_m2fix02_body_text_desciende_al_hito_anidado():
    proposed = {
        "kind": "causal_milestone",
        "milestone": {
            "title": "El pacto de la sal",
            "description": "Las dos casas firman una tregua.",
            "rationale": "Explica por qué el puerto queda neutral tres generaciones.",
        },
    }
    body = candidate_body_text(proposed)
    assert body != ""
    assert "Las dos casas firman una tregua." in body
    assert "el puerto queda neutral" in body
    assert is_milestone_candidate(proposed) is True


def test_beta_m2fix02_body_text_ignora_la_clave_muerta_de_primer_nivel():
    # Los proyectos del beta traen `extended_description: ''` de primer nivel
    # (basura que escribía `_apply_edits`): el payload anidado MANDA.
    proposed = {
        "kind": "causal_milestone",
        "extended_description": "",
        "milestone": {"description": "Cae Alburquerque.", "rationale": ""},
    }
    assert candidate_body_text(proposed) == "Cae Alburquerque."


def test_beta_m2fix02_body_text_cae_al_cuerpo_duplicado_en_metadata():
    # `ai_jobs` duplica la razón en metadata["body"]; si falta `rationale`, se usa.
    proposed = {
        "kind": "causal_milestone",
        "milestone": {"description": "", "metadata": {"body": "Cuerpo largo del hito."}},
    }
    assert "Cuerpo largo del hito." in candidate_body_text(proposed)


def test_beta_m2fix02_semilla_de_hito_real_del_beta_se_lee():
    cand = _beta_milestone_candidate(
        "historiadora/mundo/castilla-s-xiv.json",
        title_contains="Juana de Castro",
    )
    body = candidate_body_text(cand.proposed_data)
    assert body.strip() != ""
    assert cand.proposed_data["milestone"]["description"] in body


# ── Panel: pinta cuerpo y hechos ─────────────────────────────────────────────


def test_beta_m2fix02_panel_pinta_el_cuerpo_del_hito(qapp):
    cand = _beta_milestone_candidate(
        "historiadora/mundo/castilla-s-xiv.json",
        title_contains="Juana de Castro",
    )
    panel = CandidateReviewPanel(cand, _FakeController())
    assert panel._mode == "milestone"
    assert panel._body_edit.toPlainText().strip() != ""  # antes: ""
    milestone = cand.proposed_data["milestone"]
    assert panel._body_edit.toPlainText().strip() == milestone["description"].strip()
    assert panel._rationale_edit is not None
    assert panel._rationale_edit.toPlainText().strip() == milestone["rationale"].strip()
    # UX5b aplicado al hito: el campo editable ES su título, sin el prefijo.
    assert panel._title_edit.text() == milestone["title"]
    assert "Hito sugerido" not in panel._title_edit.text()


def test_beta_m2fix02_panel_muestra_ano_y_tipo(qapp):
    from PySide6.QtWidgets import QLabel

    cand = _beta_milestone_candidate(
        "historiadora/mundo/castilla-s-xiv.json",
        title_contains="Juana de Castro",
    )
    panel = CandidateReviewPanel(cand, _FakeController())
    textos = " | ".join(w.text() for w in panel.findChildren(QLabel))
    assert "1354" in textos
    assert "Tipo:" in textos


def test_beta_m2fix02_panel_dice_cuando_el_hito_no_trae_ano(qapp):
    from PySide6.QtWidgets import QLabel

    cand = _beta_milestone_candidate(
        "ux-producto/mundo/la-traductora.json",
        title_contains="Sant Cugat",
    )
    assert cand.proposed_data["milestone"]["year"] is None
    panel = CandidateReviewPanel(cand, _FakeController())
    textos = " | ".join(w.text() for w in panel.findChildren(QLabel))
    assert "sin datar" in textos
    assert "Sin año" in textos


def test_beta_m2fix02_facts_resuelve_nombres_de_entidades_afectadas():
    milestone = {
        "year": 10,
        "milestone_type": "descubrimiento",
        "affected_entity_ids": ["e1", "e2"],
        "causal_parent_hito_ids": ["h1"],
    }
    texto = milestone_facts_text(milestone, {"e1": "Nadia", "e2": "Sena Ovid"})
    assert "Año: 10" in texto
    assert "descubrimiento" in texto
    assert "Padres causales: 1" in texto
    assert "Nadia" in texto and "Sena Ovid" in texto
    # Sin nombres resolubles cae al recuento, no a ids crudos.
    solo_cuenta = milestone_facts_text(milestone, {})
    assert "Entidades afectadas: 2" in solo_cuenta
    assert "e1" not in solo_cuenta


# ── Escritura: lo editado vuelve al payload anidado, no a una clave muerta ───


def test_beta_m2fix02_aceptar_no_ensucia_el_payload(qapp):
    cand = _beta_milestone_candidate(
        "guionista-serie/mundo/orbita-muerta.json",
        title_contains="El precio del aire",
    )
    original = dict(cand.proposed_data["milestone"])
    controller = _FakeController()
    panel = CandidateReviewPanel(cand, controller)
    panel._accept()

    assert controller.accepted == [cand.id]
    # La clave muerta ya no se escribe (hoy la ganaba vacía en los 3 mundos).
    assert "extended_description" not in cand.proposed_data
    assert set(cand.proposed_data) == {"kind", "milestone"}
    # Sin tocar nada, el payload anidado queda intacto.
    milestone = cand.proposed_data["milestone"]
    assert milestone["description"] == original["description"]
    assert milestone["rationale"] == original["rationale"]
    assert milestone["year"] == original["year"]


def test_beta_m2fix02_lo_editado_llega_al_hito(qapp):
    proposed = {
        "kind": "causal_milestone",
        "milestone": {
            "title": "Matrimonio en el Palacio de los Condes de Benavente",
            "description": "Boda con anacronismo.",
            "rationale": "Razón con el anacronismo de dos siglos.",
            "metadata": {"body": "Razón con el anacronismo de dos siglos."},
            "year": 1354,
        },
    }
    cand = _candidate(proposed, cid="h9", title="Hito sugerido: Matrimonio…")
    panel = CandidateReviewPanel(cand, _FakeController())
    panel._title_edit.setText("Matrimonio en Cuéllar")
    panel._body_edit.setPlainText("Boda corregida por el usuario.")
    panel._rationale_edit.setPlainText("Razón corregida: el palacio aún no existía.")
    panel._accept()

    milestone = cand.proposed_data["milestone"]
    assert milestone["title"] == "Matrimonio en Cuéllar"
    assert milestone["description"] == "Boda corregida por el usuario."
    assert milestone["rationale"] == "Razón corregida: el palacio aún no existía."
    # La copia duplicada de la razón no queda desincronizada.
    assert milestone["metadata"]["body"] == "Razón corregida: el palacio aún no existía."
    assert "extended_description" not in cand.proposed_data


def test_beta_m2fix02_ruta_b41_del_servicio_tambien_se_lee_y_se_escribe(qapp):
    """La OTRA ruta que anida igual: `create_causal_milestone_candidate`.

    Ningún tester la citó (sus semillas venían del pipeline de IA), pero monta
    `{"kind": "causal_milestone", "milestone": milestone.to_dict()}` exactamente
    igual. Se cierra el círculo hasta el objeto de dominio que construye la
    aceptación (`CausalMilestone.from_dict(proposed_data["milestone"])`,
    candidate_service.py:517-520): lo que el usuario corrige es lo que se canoniza.
    """
    from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneType

    hito = CausalMilestone(
        title="Caída de Alburquerque",
        description="El valido pierde el favor real.",
        rationale="Explica el vacío de poder que ocupa Juan Alfonso.",
        milestone_type=CausalMilestoneType.CAIDA,
        year=1353,
        affected_entity_ids=["e1"],
    )
    proposed = {"kind": "causal_milestone", "milestone": hito.to_dict()}
    cand = _candidate(proposed, cid="b41", title=f"Hito: {hito.title}")

    panel = CandidateReviewPanel(cand, _FakeController())
    assert panel._mode == "milestone"
    assert panel._body_edit.toPlainText().strip() == hito.description
    assert panel._rationale_edit.toPlainText().strip() == hito.rationale
    assert panel._title_edit.text() == hito.title

    panel._body_edit.setPlainText("El valido cae en desgracia ante Pedro I.")
    panel._accept()

    assert "extended_description" not in cand.proposed_data
    # El hito que crearía la aceptación lleva la corrección y conserva lo demás.
    aceptado = CausalMilestone.from_dict(cand.proposed_data["milestone"])
    assert aceptado.description == "El valido cae en desgracia ante Pedro I."
    assert aceptado.rationale == hito.rationale
    assert aceptado.year == 1353
    assert aceptado.milestone_type is CausalMilestoneType.CAIDA
    assert aceptado.affected_entity_ids == ["e1"]
    assert aceptado.id == hito.id


def test_beta_m2fix02_payload_sin_milestone_no_revienta(qapp):
    # `kind` de hito sin sub-diccionario: cae al modo clásico y no explota.
    cand = _candidate({"kind": "causal_milestone", "description": "suelta"})
    panel = CandidateReviewPanel(cand, _FakeController())
    assert panel._mode == "default"
    panel._accept()


# ── Los demás tipos de semilla no cambian de modo ni de cuerpo ───────────────


@pytest.mark.parametrize(
    ("nombre", "proposed", "modo", "trozo"),
    [
        (
            "entidad",
            {
                "name": "Eldrin",
                "brief_description": "breve",
                "extended_description": "Un mago anciano.",
            },
            "default",
            "Un mago anciano.",
        ),
        (
            "relacion",
            {"description": "Juan Alfonso ejerció como valido."},
            "default",
            "Juan Alfonso ejerció como valido.",
        ),
        (
            "informe",
            {"report": "Hay una contradicción central."},
            "analysis",
            "contradicción central",
        ),
        (
            "ring_template",
            {"kind": "ring_template", "report": "Anillos propuestos: 3."},
            "analysis",
            "Anillos propuestos: 3.",
        ),
        (
            "edicion",
            {"edit_proposed_value": "texto nuevo", "edit_target_name": "Eldrin"},
            "edit",
            "texto nuevo",
        ),
        (
            "cronologia",
            {"kind": "project_chronology_suggestion", "summary": "Tres eras encadenadas."},
            "default",
            "Tres eras encadenadas.",
        ),
    ],
)
def test_beta_m2fix02_otros_kinds_conservan_su_modo(qapp, nombre, proposed, modo, trozo):
    panel = CandidateReviewPanel(_candidate(dict(proposed)), _FakeController())
    assert panel._mode == modo, nombre
    assert trozo in panel._body_edit.toPlainText(), nombre


@pytest.mark.parametrize("kind", ["ring_move", "ring_merge", "branch_move", "ascending_exception"])
def test_beta_m2fix02_estructurales_siguen_en_solo_lectura(qapp, kind):
    from PySide6.QtWidgets import QTextEdit

    proposed = {
        "kind": kind,
        "current_ring_id": "r1",
        "target_ring_id": "r2",
        "reasons": ["potencia alta"],
    }
    cand = _candidate(dict(proposed), cid="s1")
    panel = CandidateReviewPanel(cand, _FakeController())
    assert panel._mode == "structural"
    assert all(box.isReadOnly() for box in panel.findChildren(QTextEdit))
    panel._accept()
    assert cand.proposed_data == proposed  # payload §17 intacto
