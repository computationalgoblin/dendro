"""Controller de nodos fantasma (BETA2-FOCO-11).

Wrapper fino sobre ``GhostService`` (patrón de la casa: la UI habla con
controllers; los servicios de aplicación son los únicos que mutan el
proyecto). Construye sus dependencias reales a partir del ProjectService.
"""

from __future__ import annotations

from hosts.DesktopHostPySide.app_trace import _apptrace
from packages.application.entity_service import EntityService
from packages.application.ghost_service import GhostService
from packages.application.history_service import HistoryService
from packages.application.relation_service import RelationService


class GhostController:
    def __init__(self, project_service):
        if project_service is None:
            raise ValueError("GhostController requires project_service")
        self.ps = project_service
        self.service = GhostService(
            project_service,
            EntityService(project_service),
            RelationService(project_service),
            HistoryService(project_service),
        )

    def create_ghost(self, data):
        _apptrace("CTRL GhostController.create_ghost")
        return self.service.create_ghost(data)

    def create_ghost_relation(self, source_id, target_id, relation_type=None, description=""):
        _apptrace(
            f"CTRL GhostController.create_ghost_relation src={source_id!r} tgt={target_id!r}"[:120]
        )
        return self.service.create_ghost_relation(source_id, target_id, relation_type, description)

    def convert_to_entity(self, ghost_id):
        _apptrace(f"CTRL GhostController.convert_to_entity ghost={ghost_id!r}"[:120])
        return self.service.convert_to_entity(ghost_id)

    def link_to_existing(self, ghost_id, entity_id):
        _apptrace(f"CTRL GhostController.link_to_existing ghost={ghost_id!r}"[:120])
        return self.service.link_to_existing(ghost_id, entity_id)

    def discard(self, ghost_id):
        _apptrace(f"CTRL GhostController.discard ghost={ghost_id!r}"[:120])
        return self.service.discard(ghost_id)

    @staticmethod
    def is_ghost(obj) -> bool:
        return GhostService.is_ghost(obj)
