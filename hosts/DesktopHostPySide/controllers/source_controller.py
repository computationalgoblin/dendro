"""Controlador de fuentes (trazabilidad de lo documentado vs lo inventado).

BETA-MULTIAGENT2-FIX-11 (fase B3): el controlador solo sabía `list_all` y
`create`, así que una fuente se podía crear pero **no enlazar a nada** — que es
justo lo que define el oficio de quien investiga: «esto lo dice López de Ayala y
esto me lo inventé yo» (HIS-05). Los métodos nuevos devuelven `Result` (no listas
desnudas) para no comerse el error como hace el `list_all` histórico.

Ojo al modelo: **no existe `entity.source_ids`**. El enlace es unidireccional y
vive EN LA FUENTE (`derived_entity_ids`/`derived_relation_ids`); la consulta
inversa la resuelve `SourceService.get_sources_for_entity`.
"""

from hosts.DesktopHostPySide.app_trace import _apptrace
from packages.application.source_service import SourceService


class SourceController:
    def __init__(self, project_service=None):
        self.ps = project_service
        self.svc = SourceService(project_service=self.ps)

    def list_all(self):
        _apptrace("CTRL SourceController.list_all"[:120])
        result = self.svc.list_all()
        return getattr(result, "value", [])

    def create(self, data):
        claves = list(data.keys()) if isinstance(data, dict) else type(data).__name__
        _apptrace(f"CTRL SourceController.create data_keys={claves}"[:120])
        return self.svc.create_source(data)

    # ── enlazar la fuente a lo que documenta (FIX-11 B3) ─────────────────

    def link_to_entity(self, source_id, entity_id):
        _apptrace(f"CTRL SourceController.link_to_entity entity={entity_id}"[:120])
        return self.svc.link_to_entity(source_id, entity_id)

    def link_to_relation(self, source_id, relation_id):
        _apptrace(f"CTRL SourceController.link_to_relation relation={relation_id}"[:120])
        return self.svc.link_to_relation(source_id, relation_id)

    def sources_for_entity(self, entity_id):
        return self.svc.get_sources_for_entity(entity_id)

    def sources_for_relation(self, relation_id):
        return self.svc.get_sources_for_relation(relation_id)
