"""Panel de revisión por-candidato (Fase A): sustituye la tabla «Semillas».

Se abre al pulsar una notificación de semilla. Muestra el encabezado y el texto
del candidato de forma legible y editable, y permite Aceptar/Rechazar. Aceptar
escribe las ediciones en el candidato y lo canoniza vía el servicio; Rechazar lo
descarta.

El panel es consciente del tipo de candidato (UX5):
- **Edición** (`edit_proposed_value`): muestra el texto propuesto en la caja grande
  editable y un campo «Objetivo» editable; al aceptar, lo escrito se aplica a canon.
- **Análisis** (`report` + `issues/proposals/open_questions`): muestra el informe
  completo de forma legible (solo lectura) y ofrece «Reparar canon», que (UX8) lanza
  un job IA de reparación y abre un panel de cambios CONCRETOS (antes→después) sobre
  el canon — ya no sugerencias literales.
- **Normal** (entidad/relación/…): comportamiento clásico (cuerpo editable).

No escribe en persistencia directamente: usa CandidateController (que envuelve el
CandidateService). El candidato es el modelo de dominio; al aceptar, el servicio
crea/edita el elemento correspondiente.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from packages.domain.result import Error

# Campos de texto del candidato por orden de preferencia para el cuerpo legible.
_BODY_FIELDS = ("extended_description", "body", "brief_description", "description", "summary")


def is_edit_candidate(proposed_data: Any) -> bool:
    """True si el candidato propone una EDICIÓN aplicable a canon."""
    if not isinstance(proposed_data, dict):
        return False
    if str(proposed_data.get("edit_proposed_value") or "").strip():
        return True
    # UX5e: una edición de relación puede cambiar SOLO el tipo (sin contenido nuevo)
    # y sigue siendo una edición.
    return proposed_data.get("edit_kind") == "relation_edits" and bool(
        str(proposed_data.get("edit_relation_type") or "").strip()
    )


def is_analysis_candidate(proposed_data: Any) -> bool:
    """True si el candidato es un informe analítico (coherencia/revisión)."""
    if not isinstance(proposed_data, dict) or is_edit_candidate(proposed_data):
        return False
    if str(proposed_data.get("report") or "").strip():
        return True
    return any(proposed_data.get(k) for k in ("issues", "proposals", "open_questions"))


def candidate_body_text(proposed_data: dict[str, Any]) -> str:
    """Extrae el texto editable principal del candidato.

    Para ediciones devuelve el texto propuesto (`edit_proposed_value`); si no,
    el primer campo de texto rico disponible.
    """
    if not isinstance(proposed_data, dict):
        return ""
    edit_value = proposed_data.get("edit_proposed_value")
    if isinstance(edit_value, str) and edit_value.strip():
        return edit_value.strip()
    for key in _BODY_FIELDS:
        value = proposed_data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def analysis_report_text(proposed_data: dict[str, Any]) -> str:
    """Compone el informe analítico legible: report + problemas/sugerencias/preguntas."""
    if not isinstance(proposed_data, dict):
        return ""
    parts: list[str] = []
    report = str(proposed_data.get("report") or "").strip()
    if report:
        parts.append(report)

    issues = [x for x in (proposed_data.get("issues") or []) if isinstance(x, dict)]
    if issues:
        parts.append("\nProblemas detectados:")
        for it in issues:
            sev = str(it.get("severity") or "").strip()
            title = str(it.get("title") or "").strip()
            desc = str(it.get("description") or "").strip()
            head = f"• {title}" + (f"  [{sev}]" if sev else "")
            parts.append(head + (f"\n  {desc}" if desc else ""))

    proposals = [x for x in (proposed_data.get("proposals") or []) if isinstance(x, dict)]
    if proposals:
        parts.append("\nSugerencias:")
        for pr in proposals:
            title = str(pr.get("title") or "").strip()
            desc = str(pr.get("description") or "").strip()
            parts.append(f"• {title}" + (f"\n  {desc}" if desc else ""))

    questions = [
        str(x).strip() for x in (proposed_data.get("open_questions") or []) if str(x).strip()
    ]
    if questions:
        parts.append("\nPreguntas abiertas:")
        parts.extend(f"• {q}" for q in questions)

    return "\n".join(parts).strip()


def temporal_warnings_text(candidate: Any) -> str:
    """BETA1-J06: avisos de coherencia temporal asociados al candidato (J04),
    como texto legible. Cadena vacía si no hay avisos."""
    meta = getattr(candidate, "metadata", None) or {}
    warns = meta.get("temporal_warnings") if isinstance(meta, dict) else None
    lines = [
        f"• {str(w.get('message') or '').strip()}"
        for w in (warns or [])
        if isinstance(w, dict) and str(w.get("message") or "").strip()
    ]
    if not lines:
        return ""
    return "Avisos de coherencia temporal:\n" + "\n".join(lines)


def dating_badge_label(entity: Any) -> str:
    """BETA1-J06: etiqueta corta del estado de datación de una hoja/rama.

    'Por datar' (sin datación), 'Sin fundamentar' (incierto/migración), o el
    grado de precisión ('Datado'/'Aproximado'/'Mítico')."""
    from packages.application.temporal_dating import is_uncertain_dating
    from packages.domain.temporal_models import TemporalNature

    span = getattr(entity, "life_span", None)
    # BETA1-J07: la naturaleza manda sobre el grado de precisión.
    nature = getattr(span, "nature", None)
    if nature is TemporalNature.ETERNO:
        return "Eterno"
    if nature is TemporalNature.ATEMPORAL:
        return "Atemporal"
    if nature is TemporalNature.INMORTAL:
        return "Inmortal"
    if span is None or not span.is_dated():
        return "Por datar"
    if is_uncertain_dating(entity):
        return "Sin fundamentar"
    start = getattr(span, "start", None)
    precision = getattr(getattr(start, "precision", None), "value", "exact")
    return {
        "exact": "Datado",
        "approximate": "Aproximado",
        "mythical": "Mítico",
        "unknown": "Sin fundamentar",
    }.get(precision, "Datado")


class CandidateReviewPanel(QWidget):
    """Revisión ligera de un candidato: encabezado + texto editable + decisión."""

    def __init__(
        self,
        candidate: Any,
        controller: Any,
        *,
        on_decision: Callable[[str, str], None] | None = None,
        on_close: Callable[[], None] | None = None,
        on_repair: Callable[[str], None] | None = None,
        log: Callable[[str, str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._candidate = candidate
        self._controller = controller
        self._on_decision = on_decision
        self._on_close = on_close
        self._on_repair = on_repair
        self._log = log
        self._target_edit: QLineEdit | None = None
        self._rel_type_edit: QLineEdit | None = None  # UX5e: tipo en ediciones de relación
        proposed = dict(getattr(candidate, "proposed_data", {}) or {})
        if is_edit_candidate(proposed):
            self._mode = "edit"
        elif is_analysis_candidate(proposed):
            self._mode = "analysis"
        else:
            self._mode = "default"
        self._build(proposed)

    # ── construcción ──────────────────────────────────────────────────────

    def _build(self, proposed: dict[str, Any]) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        kind = getattr(getattr(self._candidate, "candidate_type", None), "value", "")
        tag = QLabel(str(kind).replace("_", " ").upper() or "CANDIDATO")
        tag.setObjectName("badge")
        layout.addWidget(tag)

        # UX5b: para candidatos de entidad el campo editable ES el nombre real
        # (`proposed_data["name"]`), no la etiqueta "Hoja candidata: …" — así el
        # nombre se puede editar y nunca se canoniza con ese prefijo.
        default_name = str(proposed.get("name") or "").strip()
        if self._mode == "default" and default_name:
            title_initial = default_name
            placeholder = "Nombre de la entidad"
        else:
            title_initial = str(getattr(self._candidate, "title", "") or "")
            placeholder = "Encabezado del candidato"
        self._title_edit = QLineEdit(title_initial)
        self._title_edit.setPlaceholderText(placeholder)
        layout.addWidget(self._title_edit)

        if self._mode == "edit":
            self._build_edit(layout, proposed)
        elif self._mode == "analysis":
            self._build_analysis(layout, proposed)
        else:
            self._build_default(layout, proposed)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        row = QHBoxLayout()
        # SEM04: cerrar SIN decidir — revisar sin compromiso; la semilla sigue
        # pendiente y se puede volver a abrir más tarde.
        close = QPushButton("Cerrar")
        close.setToolTip("Cerrar sin decidir (la semilla sigue pendiente)")
        close.clicked.connect(self._close)
        accept = QPushButton("Aceptar")
        accept.setObjectName("primaryButton")
        accept.clicked.connect(self._accept)
        reject = QPushButton("Rechazar")
        reject.clicked.connect(self._reject)
        row.addWidget(close)
        row.addStretch(1)
        row.addWidget(reject)
        row.addWidget(accept)
        layout.addLayout(row)

    def _build_edit(self, layout: QVBoxLayout, proposed: dict[str, Any]) -> None:
        """Candidato de EDICIÓN: objetivo editable + texto propuesto editable."""
        layout.addWidget(QLabel("Objetivo de la edición:"))
        self._target_edit = QLineEdit(str(proposed.get("edit_target_name") or ""))
        self._target_edit.setPlaceholderText("Nombre de la entidad/elemento a editar")
        layout.addWidget(self._target_edit)

        # UX5e: una edición de relación lleva DOS campos en UNA sola semilla — el
        # tipo (campo corto) y el contenido/descripción (caja grande). Antes salían
        # dos semillas separadas.
        if proposed.get("edit_kind") == "relation_edits":
            layout.addWidget(QLabel("Tipo de relación (vacío = sin cambio):"))
            self._rel_type_edit = QLineEdit(str(proposed.get("edit_relation_type") or ""))
            self._rel_type_edit.setPlaceholderText("p. ej. aliado_de, enemigo_de…")
            layout.addWidget(self._rel_type_edit)
            layout.addWidget(QLabel("Descripción propuesta (vacío = sin cambio):"))
        else:
            field = str(proposed.get("edit_field") or "body")
            field_label = QLabel(f"Campo: {field}")
            field_label.setObjectName("muted")
            layout.addWidget(field_label)
            layout.addWidget(QLabel("Texto propuesto (editable antes de aplicar):"))

        self._body_edit = QTextEdit()
        self._body_edit.setPlaceholderText("Texto que se aplicará a canon al aceptar")
        self._body_edit.setPlainText(candidate_body_text(proposed))
        self._body_edit.setMinimumHeight(220)
        layout.addWidget(self._body_edit, 1)

    def _build_analysis(self, layout: QVBoxLayout, proposed: dict[str, Any]) -> None:
        """Candidato de ANÁLISIS: informe legible (solo lectura) + reparar canon."""
        self._body_edit = QTextEdit()
        self._body_edit.setReadOnly(True)
        self._body_edit.setPlainText(analysis_report_text(proposed) or "Informe sin contenido.")
        self._body_edit.setMinimumHeight(280)
        layout.addWidget(self._body_edit, 1)

        proposals = [p for p in (proposed.get("proposals") or []) if isinstance(p, dict)]
        if proposals and self._on_repair is not None:
            repair = QPushButton("Reparar canon con estas sugerencias")
            repair.setObjectName("primaryButton")
            repair.setToolTip(
                "Convierte cada sugerencia en una edición revisable por entidad "
                "(podrás ajustar el texto y el objetivo antes de aceptar)"
            )
            repair.clicked.connect(self._repair)
            layout.addWidget(repair)

    def _build_default(self, layout: QVBoxLayout, proposed: dict[str, Any]) -> None:
        """Candidato normal: cuerpo de texto editable."""
        self._body_edit = QTextEdit()
        self._body_edit.setPlaceholderText("Texto del candidato")
        self._body_edit.setPlainText(candidate_body_text(proposed))
        self._body_edit.setMinimumHeight(200)
        layout.addWidget(self._body_edit, 1)

    # ── decisiones ────────────────────────────────────────────────────────

    def _candidate_id(self) -> str:
        return str(getattr(self._candidate, "id", "") or "")

    def _close(self) -> None:
        """Cierra el panel sin aceptar ni rechazar (la semilla sigue pendiente)."""
        if self._on_close:
            self._on_close()

    def _apply_edits(self) -> None:
        """Escribe las ediciones del usuario en el candidato antes de aceptar."""
        new_title = self._title_edit.text().strip()
        if new_title:
            self._candidate.title = new_title
        proposed = getattr(self._candidate, "proposed_data", None)
        if not isinstance(proposed, dict):
            return
        body = self._body_edit.toPlainText().strip()
        if self._mode == "edit":
            # El texto editado es lo que se aplicará a canon (ver _apply_edit del servicio).
            proposed["edit_proposed_value"] = body
            if self._target_edit is not None:
                target = self._target_edit.text().strip()
                if target:
                    proposed["edit_target_name"] = target
            # UX5e: el tipo de relación editado viaja en la misma semilla.
            if self._rel_type_edit is not None:
                proposed["edit_relation_type"] = self._rel_type_edit.text().strip()
            target_name = str(proposed.get("edit_target_name") or "")
            proposed["report"] = f"Propuesta de edición para '{target_name}':\n\n{body}"
        elif self._mode == "analysis":
            # Informe de solo lectura: no se reescribe su cuerpo.
            pass
        else:
            # UX5b: el campo de título ES el nombre real de la entidad (sin prefijo).
            if new_title and "name" in proposed:
                proposed["name"] = new_title
            # Reescribe el cuerpo en `extended_description` (la clave que persiste);
            # si no, el primer campo de texto existente.
            target = next((k for k in _BODY_FIELDS if k in proposed), "extended_description")
            proposed[target] = body

    def _accept(self) -> None:
        self._apply_edits()
        result = self._controller.accept(self._candidate_id())
        if isinstance(result, Error):
            self._status.setText(result.error)
            if self._log:
                self._log("error", result.error)
            return
        # BETA1-J06: si la guardia temporal (J04) dejó avisos, hazlos visibles.
        warnings = temporal_warnings_text(self._candidate)
        if warnings:
            self._status.setText(warnings)
            if self._log:
                self._log("warning", warnings)
        elif self._log:
            self._log("info", "Semilla aceptada")
        if self._on_decision:
            self._on_decision(self._candidate_id(), "accept")

    def _reject(self) -> None:
        result = self._controller.reject(self._candidate_id())
        if isinstance(result, Error):
            self._status.setText(result.error)
            if self._log:
                self._log("error", result.error)
            return
        if self._log:
            self._log("info", "Semilla rechazada")
        if self._on_decision:
            self._on_decision(self._candidate_id(), "reject")

    # ── reparar canon (análisis → cambios CONCRETOS vía IA, UX8) ──────────

    def _repair(self) -> None:
        """UX8: delega en el host, que lanza un job IA de reparación y abre el
        panel de cambios concretos (antes→después). Ya NO genera sugerencias
        literales: el modelo redacta el valor final que tendría el canon."""
        if self._on_repair is not None:
            self._on_repair(self._candidate_id())


__all__ = [
    "CandidateReviewPanel",
    "candidate_body_text",
    "analysis_report_text",
    "is_edit_candidate",
    "is_analysis_candidate",
]
