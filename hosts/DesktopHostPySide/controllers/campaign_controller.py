"""CampaignController — wraps CampaignService (B27.2-T06)."""
from packages.application.campaign_service import CampaignService
from packages.application.project_service import ProjectService
from packages.persistence.store import ProjectStore

class CampaignController:
    def __init__(self, project_service=None, store=None):
        store = store or ProjectStore()
        self.ps = project_service or ProjectService(store=store)
        self.cs = CampaignService(project_service=self.ps)

    def list_all(self): return self.cs.list_campaigns()
    def create(self, data): return self.cs.create_campaign(data)
    def overview(self, cid): return self.cs.get_campaign_overview(cid)
