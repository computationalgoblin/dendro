from packages.application.world_layer_service import WorldLayerService
class LayerController:
    def __init__(self, project_service=None): self.ps = project_service; self.svc = WorldLayerService(project_service=self.ps)
    def list_all(self): return self.svc.list_layers()
    def create(self, data): return self.svc.create_layer(data)
