from packages.application.world_layer_service import WorldLayerService


class LayerController:
    def __init__(self, project_service=None):
        self.ps = project_service
        self.svc = WorldLayerService(project_service=self.ps)

    def list_all(self):
        result = self.svc.list_layers()
        return getattr(result, "value", [])

    def create(self, data):
        if isinstance(data, dict):
            return self.svc.create_layer(
                str(data.get("name", "")),
                str(data.get("description", "")),
                data.get("order"),
            )
        return self.svc.create_layer(str(data))
