
"""
FrameworkService — CRUD, coverage, association, templates (B13-T02).
Stateful, linked to ProjectService. No implicit persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.domain.narrative_framework import (
    FrameworkComponent,
    FrameworkGapSeverity,
    FrameworkType,
    NarrativeFramework,
)
from packages.domain.result import Error, Ok, Result


# ── Builtin template catalog ─────────────────────────────────────────

BUILTIN_TEMPLATES: dict[FrameworkType, NarrativeFramework] = {}


def _register(t: FrameworkType, name: str, components: list[dict]) -> None:
    BUILTIN_TEMPLATES[t] = NarrativeFramework(
        name=name, framework_type=t, is_active=False,
        components=[FrameworkComponent(**c) for c in components],
        gap_severity=FrameworkGapSeverity.MEDIA,
    )


_register(FrameworkType.HISTORIA, "Estructura de historia", [
    {"name": "Acto I — Planteamiento", "expected_entity_types": ["personaje", "localizacion"], "is_optional": False},
    {"name": "Acto II — Confrontación", "expected_entity_types": ["evento", "personaje"], "is_optional": False},
    {"name": "Acto III — Resolución", "expected_entity_types": ["evento", "personaje"], "is_optional": False},
])

_register(FrameworkType.ARCO_PERSONAJE, "Arco de personaje", [
    {"name": "Estado inicial", "expected_entity_types": ["personaje"], "is_optional": False},
    {"name": "Incidente incitador", "expected_entity_types": ["evento"], "is_optional": False},
    {"name": "Transformación", "expected_entity_types": ["personaje", "evento"], "is_optional": False},
    {"name": "Estado final", "expected_entity_types": ["personaje"], "is_optional": False},
])

_register(FrameworkType.CAMPANA, "Estructura de campaña", [
    {"name": "Introducción", "expected_entity_types": ["personaje", "localizacion"], "is_optional": False},
    {"name": "Desarrollo", "expected_entity_types": ["evento", "faccion"], "is_optional": False},
    {"name": "Clímax", "expected_entity_types": ["evento"], "is_optional": False},
    {"name": "Conclusión", "expected_entity_types": ["evento"], "is_optional": False},
])

_register(FrameworkType.MISTERIO, "Estructura de misterio", [
    {"name": "El crimen o enigma", "expected_entity_types": ["evento", "localizacion"], "is_optional": False},
    {"name": "La investigación", "expected_entity_types": ["personaje", "pista"], "is_optional": False},
    {"name": "La revelación", "expected_entity_types": ["evento", "secreto"], "is_optional": False},
])

_register(FrameworkType.INVESTIGACION, "Estructura de investigación", [
    {"name": "Hipótesis inicial", "expected_entity_types": ["personaje"], "is_optional": False},
    {"name": "Recolección de pruebas", "expected_entity_types": ["pista", "fuente"], "is_optional": False},
    {"name": "Conclusión", "expected_entity_types": ["evento"], "is_optional": False},
])

_register(FrameworkType.HORROR, "Estructura de horror", [
    {"name": "Normalidad", "expected_entity_types": ["personaje", "localizacion"], "is_optional": False},
    {"name": "Manifestación", "expected_entity_types": ["evento", "personaje"], "is_optional": False},
    {"name": "Confrontación", "expected_entity_types": ["evento", "localizacion"], "is_optional": False},
])

_register(FrameworkType.TRAGEDIA, "Estructura de tragedia", [
    {"name": "Grandeza inicial", "expected_entity_types": ["personaje"], "is_optional": False},
    {"name": "Error trágico", "expected_entity_types": ["evento"], "is_optional": False},
    {"name": "Caída", "expected_entity_types": ["evento", "personaje"], "is_optional": False},
])

_register(FrameworkType.AVENTURA, "Estructura de aventura", [
    {"name": "La llamada", "expected_entity_types": ["personaje", "evento"], "is_optional": False},
    {"name": "El viaje", "expected_entity_types": ["localizacion", "evento"], "is_optional": False},
    {"name": "El tesoro o meta", "expected_entity_types": ["objeto", "localizacion"], "is_optional": False},
    {"name": "El regreso", "expected_entity_types": ["personaje", "localizacion"], "is_optional": False},
])

_register(FrameworkType.SANDBOX, "Estructura sandbox", [
    {"name": "Región o zona", "expected_entity_types": ["localizacion"], "is_optional": False},
    {"name": "Facción principal", "expected_entity_types": ["faccion"], "is_optional": False},
    {"name": "Puntos de interés", "expected_entity_types": ["localizacion", "evento"], "is_optional": False},
])

_register(FrameworkType.FACCIONES, "Estructura de facciones", [
    {"name": "Facción A", "expected_entity_types": ["faccion"], "is_optional": False},
    {"name": "Facción B", "expected_entity_types": ["faccion"], "is_optional": False},
    {"name": "Conflicto central", "expected_entity_types": ["evento"], "is_optional": False},
])

_register(FrameworkType.EPISODICA, "Estructura episódica", [
    {"name": "Episodio 1", "expected_entity_types": ["evento", "personaje"], "is_optional": False},
    {"name": "Episodio 2", "expected_entity_types": ["evento", "personaje"], "is_optional": False},
    {"name": "Episodio 3", "expected_entity_types": ["evento", "personaje"], "is_optional": False},
])

_register(FrameworkType.REVELACION, "Estructura de revelación", [
    {"name": "Conocimiento oculto", "expected_entity_types": ["secreto"], "is_optional": False},
    {"name": "Primeras pistas", "expected_entity_types": ["pista"], "is_optional": False},
    {"name": "Revelación", "expected_entity_types": ["evento", "personaje"], "is_optional": False},
])

_register(FrameworkType.CONSPIRACION, "Estructura de conspiración", [
    {"name": "Actores ocultos", "expected_entity_types": ["faccion", "personaje"], "is_optional": False},
    {"name": "El plan", "expected_entity_types": ["evento", "secreto"], "is_optional": False},
    {"name": "Consecuencias", "expected_entity_types": ["evento"], "is_optional": False},
])

# ── FrameworkService ─────────────────────────────────────────────────


@dataclass
class FrameworkCoverage:
    framework_id: str
    total_components: int
    filled_components: int
    empty_components: int
    deliberate_empty: int
    coverage_pct: float
    components: list[FrameworkComponent]


class FrameworkService:
    """Stateful service for framework CRUD, association, coverage."""

    def __init__(self, project_service: Any) -> None:
        self._ps = project_service

    def _proj(self) -> Any:
        p = self._ps.active_project
        if p is None:
            return Error("No active project")
        return Ok(p)

    # ── CRUD ──────────────────────────────────────────────────────────

    def create_framework(
        self, name: str, framework_type: FrameworkType,
        description: str = "",
    ) -> Result[NarrativeFramework, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        template = BUILTIN_TEMPLATES.get(framework_type)
        if template:
            fw = NarrativeFramework(
                name=name, description=description,
                framework_type=framework_type,
                components=[FrameworkComponent(
                    name=c.name, description=c.description,
                    expected_entity_types=list(c.expected_entity_types),
                    expected_relation_types=list(c.expected_relation_types),
                    is_optional=c.is_optional,
                ) for c in template.components],
            )
        else:
            fw = NarrativeFramework(
                name=name, description=description,
                framework_type=framework_type,
            )
        proj.value.narrative_frameworks.append(fw)
        return Ok(fw)

    def create_from_template(
        self, name: str, template_id: str,
    ) -> Result[NarrativeFramework, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        tmpl = None
        for t in BUILTIN_TEMPLATES.values():
            if t.id == template_id:
                tmpl = t
                break
        if not tmpl:
            for t in proj.value.framework_templates:
                if t.id == template_id:
                    tmpl = t
                    break
        if not tmpl:
            return Error(f"Template '{template_id}' not found")
        fw = NarrativeFramework(
            name=name, framework_type=tmpl.framework_type,
            components=[FrameworkComponent(
                name=c.name, description=c.description,
                expected_entity_types=list(c.expected_entity_types),
                expected_relation_types=list(c.expected_relation_types),
                is_optional=c.is_optional,
            ) for c in tmpl.components],
        )
        proj.value.narrative_frameworks.append(fw)
        return Ok(fw)

    def get_framework(self, fw_id: str) -> Result[NarrativeFramework, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        for fw in proj.value.narrative_frameworks:
            if fw.id == fw_id:
                return Ok(fw)
        return Error(f"Framework '{fw_id}' not found")

    def list_frameworks(
        self, active_only: bool = False,
    ) -> Result[list[NarrativeFramework], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        result = list(proj.value.narrative_frameworks)
        if active_only:
            result = [f for f in result if f.is_active]
        return Ok(result)

    def update_framework(
        self, fw_id: str, data: dict[str, Any],
    ) -> Result[NarrativeFramework, str]:
        rf = self.get_framework(fw_id)
        if isinstance(rf, Error):
            return rf
        fw = rf.value
        for key in ("name", "description"):
            if key in data:
                setattr(fw, key, data[key])
        return Ok(fw)

    def toggle_active(self, fw_id: str) -> Result[NarrativeFramework, str]:
        rf = self.get_framework(fw_id)
        if isinstance(rf, Error):
            return rf
        rf.value.is_active = not rf.value.is_active
        return Ok(rf.value)

    def activate(self, fw_id: str) -> Result[NarrativeFramework, str]:
        rf = self.get_framework(fw_id)
        if isinstance(rf, Error):
            return rf
        rf.value.is_active = True
        return Ok(rf.value)

    def deactivate(self, fw_id: str) -> Result[NarrativeFramework, str]:
        rf = self.get_framework(fw_id)
        if isinstance(rf, Error):
            return rf
        rf.value.is_active = False
        return Ok(rf.value)

    # ── Components ────────────────────────────────────────────────────

    def add_component(
        self, fw_id: str, name: str, description: str = "",
        is_optional: bool = False,
    ) -> Result[FrameworkComponent, str]:
        rf = self.get_framework(fw_id)
        if isinstance(rf, Error):
            return rf
        comp = FrameworkComponent(
            name=name, description=description,
            is_optional=is_optional,
        )
        rf.value.components.append(comp)
        return Ok(comp)

    # ── Association ───────────────────────────────────────────────────

    def associate_entity(
        self, fw_id: str, component_id: str, entity_id: str,
    ) -> Result[FrameworkComponent, str]:
        rc = self._get_component(fw_id, component_id)
        if isinstance(rc, Error):
            return rc
        comp = rc.value
        if entity_id in comp.associated_entity_ids:
            return Error(f"Entity '{entity_id[:8]}' already associated")
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        found = any(e.id == entity_id for e in proj.value.entities)
        if not found:
            return Error(f"Entity '{entity_id[:8]}' not found in project")
        comp.associated_entity_ids.append(entity_id)
        return Ok(comp)

    def associate_relation(
        self, fw_id: str, component_id: str, relation_id: str,
    ) -> Result[FrameworkComponent, str]:
        rc = self._get_component(fw_id, component_id)
        if isinstance(rc, Error):
            return rc
        comp = rc.value
        if relation_id in comp.associated_relation_ids:
            return Error(f"Relation '{relation_id[:8]}' already associated")
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        found = any(r.id == relation_id for r in proj.value.relations)
        if not found:
            return Error(f"Relation '{relation_id[:8]}' not found in project")
        comp.associated_relation_ids.append(relation_id)
        return Ok(comp)

    def _get_component(
        self, fw_id: str, component_id: str,
    ) -> Result[FrameworkComponent, str]:
        rf = self.get_framework(fw_id)
        if isinstance(rf, Error):
            return rf
        for c in rf.value.components:
            if c.id == component_id:
                return Ok(c)
        return Error(f"Component '{component_id[:8]}' not found in framework")

    # ── Coverage ──────────────────────────────────────────────────────

    def get_coverage(
        self, fw_id: str,
    ) -> Result[FrameworkCoverage, str]:
        rf = self.get_framework(fw_id)
        if isinstance(rf, Error):
            return rf
        fw = rf.value
        total = len(fw.components)
        filled = sum(
            1 for c in fw.components
            if c.associated_entity_ids or c.associated_relation_ids
        )
        deliberate = sum(1 for c in fw.components if c.absence_deliberate)
        empty = total - filled - deliberate
        effective = total - deliberate
        pct = (filled / effective * 100) if effective > 0 else 100.0
        return Ok(FrameworkCoverage(
            framework_id=fw.id,
            total_components=total,
            filled_components=filled,
            empty_components=empty,
            deliberate_empty=deliberate,
            coverage_pct=round(pct, 1),
            components=list(fw.components),
        ))

    def detect_empty_components(
        self, fw_id: str,
    ) -> Result[list[FrameworkComponent], str]:
        rf = self.get_framework(fw_id)
        if isinstance(rf, Error):
            return rf
        return Ok([
            c for c in rf.value.components
            if not c.associated_entity_ids
            and not c.associated_relation_ids
            and not c.absence_deliberate
        ])

    def mark_absence_deliberate(
        self, fw_id: str, component_id: str,
    ) -> Result[FrameworkComponent, str]:
        rc = self._get_component(fw_id, component_id)
        if isinstance(rc, Error):
            return rc
        rc.value.absence_deliberate = True
        return Ok(rc.value)

    def duplicate_framework(
        self, fw_id: str, new_name: str,
    ) -> Result[NarrativeFramework, str]:
        rf = self.get_framework(fw_id)
        if isinstance(rf, Error):
            return rf
        original = rf.value
        dup = NarrativeFramework(
            name=new_name,
            description=original.description,
            framework_type=original.framework_type,
            components=[FrameworkComponent(
                name=c.name, description=c.description,
                expected_entity_types=list(c.expected_entity_types),
                expected_relation_types=list(c.expected_relation_types),
                is_optional=c.is_optional,
            ) for c in original.components],
            rules=list(original.rules),
            expected_fields=list(original.expected_fields),
            suggested_relations=list(original.suggested_relations),
            domain_id=original.domain_id,
            layer_ids=list(original.layer_ids),
            gap_severity=original.gap_severity,
        )
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        proj.value.narrative_frameworks.append(dup)
        return Ok(dup)

    # ── Templates ─────────────────────────────────────────────────────

    def list_templates(
        self,
    ) -> Result[list[NarrativeFramework], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        result = list(BUILTIN_TEMPLATES.values())
        result.extend(proj.value.framework_templates)
        return Ok(result)

    def save_as_template(
        self, fw_id: str, template_name: str,
    ) -> Result[NarrativeFramework, str]:
        rf = self.get_framework(fw_id)
        if isinstance(rf, Error):
            return rf
        original = rf.value
        tmpl = NarrativeFramework(
            name=template_name,
            description=original.description,
            framework_type=original.framework_type,
            components=[FrameworkComponent(
                name=c.name, description=c.description,
                expected_entity_types=list(c.expected_entity_types),
                expected_relation_types=list(c.expected_relation_types),
                is_optional=c.is_optional,
            ) for c in original.components],
            rules=list(original.rules),
            expected_fields=list(original.expected_fields),
            suggested_relations=list(original.suggested_relations),
            domain_id=original.domain_id,
            layer_ids=list(original.layer_ids),
            gap_severity=original.gap_severity,
            metadata={"template_name": template_name},
        )
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        proj.value.framework_templates.append(tmpl)
        return Ok(tmpl)


__all__ = ["FrameworkService", "FrameworkCoverage", "BUILTIN_TEMPLATES"]
