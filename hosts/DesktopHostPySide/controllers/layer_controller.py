from packages.application.world_layer_service import WorldLayerService
from hosts.DesktopHostPySide.app_trace import _apptrace


class LayerController:
    def __init__(self, project_service=None):
        self.ps = project_service
        self.svc = WorldLayerService(project_service=self.ps)

    def list_all(self):
        _apptrace(f"CTRL LayerController.list_all"[:120])
        result = self.svc.list_layers()
        return getattr(result, "value", [])

    def create(self, data):
        _apptrace(f"CTRL LayerController.create data_keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"[:120])
        if isinstance(data, dict):
            return self.svc.create_layer(
                str(data.get("name", "")),
                str(data.get("description", "")),
                data.get("order"),
            )
        return self.svc.create_layer(str(data))
