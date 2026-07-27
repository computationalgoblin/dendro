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
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import PanelScaffold
from packages.domain.result import Error

# Campos de texto del candidato por orden de preferencia para el cuerpo legible.
_BODY_FIELDS = ("extended_description", "body", "brief_description", "description", "summary")


def is_edit_candidate(proposed_data: Any) -> bool:
    """True si el candidato propone una EDICIÓN aplicable a canon."""
    if not isinstance(proposed_data, dict):
        return False
    if str(proposed_data.get("edit_proposed_value") or "").strip():
        return True
    # PLAY-15: patch multi-campo (edit_fields) también es edición.
    fields = proposed_data.get("edit_fields")
    if isinstance(fields, dict) and fields:
        return True
    # UX5e: una edición de relación puede cambiar SOLO el tipo (sin contenido nuevo)
    # y sigue siendo una edición.
    return proposed_data.get("edit_kind") == "relation_edits" and bool(
        str(proposed_data.get("edit_relation_type") or "").strip()
    )


def _field_value_text(value: Any) -> str:
    """PLAY-15: representación editable de un valor de campo (lista → comas)."""
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    enum_value = getattr(value, "value", None)
    if enum_value is not None and not isinstance(value, (str, int, float, bool)):
        return str(enum_value)
    return str(value)


def _coerce_like(original: Any, text: str) -> Any:
    """PLAY-15: devuelve el texto editado con el TIPO del valor original."""
    text = str(text or "").strip()
    if isinstance(original, bool):
        return text.lower() in ("true", "sí", "si", "1")
    if isinstance(original, int):
        try:
            return int(text)
        except ValueError:
            return original
    if isinstance(original, list):
        return [part.strip() for part in text.split(",") if part.strip()]
    return text


def is_analysis_candidate(proposed_data: Any) -> bool:
    """True si el candidato es un informe analítico (coherencia/revisión)."""
    if not isinstance(proposed_data, dict) or is_edit_candidate(proposed_data):
        return False
    if str(proposed_data.get("report") or "").strip():
        return True
    return any(proposed_data.get(k) for k in ("issues", "proposals", "open_questions"))


# BETA2-STRUCT: tipos de PROPUESTA ESTRUCTURAL (reubicación de anillos). No son
# candidatos narrativos ni ediciones ordinarias: su payload es datos estructurados
# (§17) que NO deben editarse como texto ni escribirse de vuelta al aceptar.
_STRUCTURAL_KINDS = frozenset({"ring_move", "ascending_exception", "branch_move", "ring_merge"})


def is_structural_candidate(proposed_data: Any) -> bool:
    """True si el candidato es una propuesta estructural (mover/marcar anillos)."""
    return isinstance(proposed_data, dict) and proposed_data.get("kind") in _STRUCTURAL_KINDS


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


def source_badge_text(candidate: Any) -> str:
    """fila 33: etiqueta legible del origen del candidato (usuario vs IA) y, si
    aplica, su confianza. La revisión distingue de un vistazo qué propuso la IA."""
    source = str(getattr(candidate, "source", "") or "").lower()
    if source.startswith("ai") or source == "ia":
        origin = "🤖 IA"
    elif source in ("manual", "usuario", "user"):
        origin = "🧑 Usuario"
    else:
        origin = source or "origen desconocido"
    parts = [f"Origen: {origin}"]
    confidence = getattr(candidate, "confidence", None)
    if isinstance(confidence, (int, float)) and 0 < float(confidence) <= 1:
        parts.append(f"confianza {int(round(float(confidence) * 100))}%")
    return " · ".join(parts)


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
        # PLAY-15: editores por campo de un patch multi-campo {campo: (editor, original)}.
        self._field_edits: dict[str, tuple[QTextEdit, Any]] = {}
        self._rel_type_edit: QLineEdit | None = None  # UX5e: tipo en ediciones de relación
        proposed = dict(getattr(candidate, "proposed_data", {}) or {})
        if is_structural_candidate(proposed):
            self._mode = "structural"
        elif is_edit_candidate(proposed):
            self._mode = "edit"
        elif is_analysis_candidate(proposed):
            self._mode = "analysis"
        else:
            self._mode = "default"
        self._build(proposed)

    # ── construcción ──────────────────────────────────────────────────────

    def _build(self, proposed: dict[str, Any]) -> None:
        # UX22: estructura unificada sobre PanelScaffold (cabecera + cuerpo + acciones).
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        kind = getattr(getattr(self._candidate, "candidate_type", None), "value", "")
        badge_text = str(kind).replace("_", " ").upper() or "SEMILLA"
        scaffold = PanelScaffold("Revisión de semilla", badge=badge_text, badge_tone="gold")
        outer.addWidget(scaffold)
        layout = scaffold.body  # las _build_* añaden el contenido aquí

        # fila 33: badge de fuente (usuario/IA) + confianza, para no confundir lo
        # propuesto por la IA con lo introducido por el usuario.
        source_label = QLabel(source_badge_text(self._candidate))
        source_label.setObjectName("mutedLabel")
        layout.addWidget(source_label)

        # UX5b: para candidatos de entidad el campo editable ES el nombre real
        # (`proposed_data["name"]`), no la etiqueta "Hoja candidata: …" — así el
        # nombre se puede editar y nunca se canoniza con ese prefijo.
        default_name = str(proposed.get("name") or "").strip()
        if self._mode == "default" and default_name:
            title_initial = default_name
            placeholder = "Nombre de la entidad"
        else:
            title_initial = str(getattr(self._candidate, "title", "") or "")
            placeholder = "Encabezado de la semilla"
        self._title_edit = QLineEdit(title_initial)
        self._title_edit.setPlaceholderText(placeholder)
        layout.addWidget(self._title_edit)

        if self._mode == "structural":
            self._build_structural(layout, proposed)
        elif self._mode == "edit":
            self._build_edit(layout, proposed)
        elif self._mode == "analysis":
            self._build_analysis(layout, proposed)
        else:
            self._build_default(layout, proposed)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        # UX22: barra de acciones del scaffold (secundarios a la izquierda, primario
        # a la derecha).
        row = scaffold.add_action_bar()
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

    def _build_edit(self, layout: QVBoxLayout, proposed: dict[str, Any]) -> None:
        """Candidato de EDICIÓN: objetivo editable + texto propuesto editable."""
        layout.addWidget(QLabel("Objetivo de la edición:"))
        self._target_edit = QLineEdit(str(proposed.get("edit_target_name") or ""))
        self._target_edit.setPlaceholderText("Nombre de la entidad/elemento a editar")
        layout.addWidget(self._target_edit)

        # PLAY-15: patch multi-campo — una fila before/after por campo, cada
        # «después» editable antes de aplicar (precedente visual: RepairReviewPanel).
        fields = proposed.get("edit_fields")
        if isinstance(fields, dict) and fields:
            self._field_edits = {}
            for key, value in fields.items():
                field_label = QLabel(f"Campo: {key}")
                field_label.setObjectName("mutedLabel")
                layout.addWidget(field_label)
                before = self._current_field_value(proposed, str(key))
                if before:
                    layout.addWidget(QLabel("Antes (canon actual):"))
                    before_box = QTextEdit()
                    before_box.setReadOnly(True)
                    before_box.setObjectName("mutedLabel")
                    before_box.setPlainText(before)
                    before_box.setMaximumHeight(90)
                    layout.addWidget(before_box)
                layout.addWidget(QLabel("Propuesto (editable antes de aplicar):"))
                editor = QTextEdit()
                editor.setPlainText(_field_value_text(value))
                editor.setMaximumHeight(110)
                layout.addWidget(editor)
                self._field_edits[str(key)] = (editor, value)
            return

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
            field_label.setObjectName("mutedLabel")
            layout.addWidget(field_label)
            # fila 33: diff antes/después — muestra el valor actual de canon (solo
            # lectura) para comparar con la propuesta antes de aplicar.
            before = self._current_target_value(proposed)
            if before:
                layout.addWidget(QLabel("Antes (canon actual):"))
                before_box = QTextEdit()
                before_box.setReadOnly(True)
                before_box.setObjectName("mutedLabel")
                before_box.setPlainText(before)
                before_box.setMaximumHeight(140)
                layout.addWidget(before_box)
            layout.addWidget(QLabel("Texto propuesto (editable antes de aplicar):"))

        self._body_edit = QTextEdit()
        self._body_edit.setPlaceholderText("Texto que se aplicará a canon al aceptar")
        self._body_edit.setPlainText(candidate_body_text(proposed))
        self._body_edit.setMinimumHeight(220)
        layout.addWidget(self._body_edit, 1)

    def _current_field_value(self, proposed: dict[str, Any], key: str) -> str:
        """PLAY-15: valor actual en canon de UN campo del patch (diff por fila)."""
        ctrl = self._controller
        ps = getattr(ctrl, "ps", None)
        project = getattr(ps, "active_project", None) if ps is not None else None
        if project is None:
            return ""
        kind = str(proposed.get("edit_kind") or "entity_edits")
        target_id = str(proposed.get("edit_target_id") or "")
        name = str(proposed.get("edit_target_name") or "").strip().lower()
        if kind == "milestone_edits":
            items = getattr(project, "causal_milestones", []) or []
            obj = next(
                (m for m in items if str(getattr(m, "id", "")) == target_id), None
            ) or next((m for m in items if str(getattr(m, "title", "")).lower() == name), None)
        else:
            obj = next(
                (
                    e
                    for e in getattr(project, "entities", []) or []
                    if str(getattr(e, "name", "")).strip().lower() == name
                ),
                None,
            )
        if obj is None:
            return ""
        return _field_value_text(getattr(obj, key, ""))

    def _current_target_value(self, proposed: dict[str, Any]) -> str:
        """fila 33: valor actual en canon del campo que la edición pretende cambiar
        (para el diff antes/después). Solo lectura del dominio vía el controller; ""
        si no se puede resolver el objetivo."""
        ctrl = self._controller
        ps = getattr(ctrl, "ps", None)
        project = getattr(ps, "active_project", None) if ps is not None else None
        if project is None:
            return ""
        target_id = str(proposed.get("edit_target_id") or "")
        target_name = str(proposed.get("edit_target_name") or "").strip()
        entity = None
        for e in getattr(project, "entities", []) or []:
            if target_id and str(getattr(e, "id", "")) == target_id:
                entity = e
                break
            if not target_id and target_name and str(getattr(e, "name", "")).strip() == target_name:
                entity = e
                break
        if entity is None:
            return ""
        field = str(proposed.get("edit_field") or "body")
        attr = "extended_description" if field == "body" else field
        value = getattr(entity, attr, None)
        if not value:
            for fallback in _BODY_FIELDS:
                value = getattr(entity, fallback, None)
                if value:
                    break
        return str(value or "")

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

    def _build_structural(self, layout: QVBoxLayout, proposed: dict[str, Any]) -> None:
        """Propuesta ESTRUCTURAL (§17) en SOLO LECTURA: nunca edita el payload."""
        current = str(proposed.get("current_ring_id") or "") or "Sin anillo"
        target = str(proposed.get("target_ring_id") or "")
        move = QLabel(f"Anillo:  {current}  →  {target}")
        move.setWordWrap(True)
        layout.addWidget(move)
        box = QTextEdit()
        box.setReadOnly(True)
        box.setObjectName("mutedLabel")
        parts: list[str] = []
        reasons = [str(r) for r in (proposed.get("reasons") or [])]
        if reasons:
            parts.append("Razones:\n" + "\n".join(f"• {r}" for r in reasons))
        consequences = [str(c) for c in (proposed.get("expected_consequences") or [])]
        if consequences:
            parts.append("Consecuencias esperadas:\n" + "\n".join(f"• {c}" for c in consequences))
        support = proposed.get("supporting_relation_ids") or []
        if support:
            parts.append(f"Relaciones que lo justifican: {len(support)}")
        box.setPlainText("\n\n".join(parts))
        box.setMinimumHeight(200)
        layout.addWidget(box, 1)

    def _build_default(self, layout: QVBoxLayout, proposed: dict[str, Any]) -> None:
        """Candidato normal: cuerpo de texto editable."""
        self._body_edit = QTextEdit()
        self._body_edit.setPlaceholderText("Texto de la semilla")
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
        # BETA2-STRUCT: una propuesta estructural es SOLO LECTURA — su payload §17 se
        # acepta tal cual (jamás se reescribe con título/cuerpo del formulario).
        if self._mode == "structural":
            return
        # PLAY-15: patch multi-campo — recoge cada editor conservando el tipo
        # original del valor (año int, listas por comas) y termina aquí.
        if self._mode == "edit" and self._field_edits:
            proposed["edit_fields"] = {
                key: _coerce_like(original, editor.toPlainText())
                for key, (editor, original) in self._field_edits.items()
            }
            if self._target_edit is not None:
                target = self._target_edit.text().strip()
                if target:
                    proposed["edit_target_name"] = target
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
        if not warnings:
            self._status.setText("Aceptado ✓")  # UX17: acuse breve antes de cerrar
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
        self._status.setText("Descartado")  # UX17: acuse breve antes de cerrar
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
