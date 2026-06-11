from packages.application.world_layer_service import WorldLayerService
from hosts.DesktopHostPySide.app_trace import _apptrace


class LayerController:
    def __init__(self, project_service=None):
        self.ps = project_service
        self.svc = WorldLayerService(project_service=self.ps)

    def list_all(self):
        _apptrace(f"CTRL LayerController.list_all"[:120])
        result = self.svc.list_layers()
        return getattr(result, "value", result)

    def create(self, data):
        _apptrace(f"CTRL LayerController.create data_keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"[:120])
        if isinstance(data, dict):
            return self.svc.create_layer(
                str(data.get("name", "")),
                str(data.get("description", "")),
                data.get("order"),
            )
        return self.svc.create_layer(str(data))

    # BETA1-B03: ring CRUD from the Creation canvas

    def get(self, layer_id):
        _apptrace(f"CTRL LayerController.get layer_id={layer_id!r}"[:120])
        return self.svc.get_layer(layer_id)

    def update(self, layer_id, data):
        _apptrace(f"CTRL LayerController.update layer_id={layer_id!r}"[:120])
        return self.svc.update_layer(layer_id, **(data or {}))

    def hide(self, layer_id):
        """Soft-delete: the ring disappears from views; entities keep their
        layer ids and the layer can be restored with show_layer."""
        _apptrace(f"CTRL LayerController.hide layer_id={layer_id!r}"[:120])
        return self.svc.hide_layer(layer_id)
