"""CampaignController — wraps CampaignService (B27.3)."""
from __future__ import annotations

from packages.application.campaign_service import CampaignService
from packages.application.entity_service import EntityService


class CampaignController:
    def __init__(self, project_service):
        if project_service is None:
            raise ValueError("CampaignController requires project_service")
        self.ps = project_service
        self.es = EntityService(self.ps)
        self.cs = CampaignService(project_service=self.ps, entity_service=self.es)

    def list_all(self):
        return self.cs.list_campaigns()

    def create(self, data):
        return self.cs.create_campaign(data)

    def get(self, campaign_id):
        return self.cs.get_campaign(campaign_id)

    def overview(self, campaign_id):
        return self.cs.get_campaign_overview(campaign_id)

    def update(self, campaign_id, data):
        return self.cs.update_campaign(campaign_id, data)

    def add_player(self, campaign_id, player_name):
        return self.cs.add_player(campaign_id, player_name)

    def create_clock(self, campaign_id, data):
        return self.cs.create_clock(campaign_id, data)

    def advance_clock(self, clock_id, by=1):
        return self.cs.advance_clock(clock_id, by)
