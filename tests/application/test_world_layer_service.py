"""Tests for B10-T03: WorldLayerService."""

from packages.application.project_service import ProjectService
from packages.application.world_layer_service import WorldLayerService
from packages.domain.result import Error, Ok


def _setup():
    ps = ProjectService()
    ps.create("Test World")
    svc = WorldLayerService(ps)
    return ps, svc


class TestListLayers:
    def test_list_returns_16_default_layers(self):
        ps, svc = _setup()
        layers = svc.list_layers()
        assert len(layers) == 16

    def test_list_sorted_by_order(self):
        ps, svc = _setup()
        layers = svc.list_layers()
        orders = [wl.order for wl in layers]
        assert orders == sorted(orders)

    def test_list_excludes_hidden_by_default(self):
        ps, svc = _setup()
        svc.hide_layer("layer_premisa")
        layers = svc.list_layers()
        assert len(layers) == 15
        ids = [wl.id for wl in layers]
        assert "layer_premisa" not in ids

    def test_list_include_hidden(self):
        ps, svc = _setup()
        svc.hide_layer("layer_premisa")
        layers = svc.list_layers(include_hidden=True)
        assert len(layers) == 16

    def test_no_project_returns_empty(self):
        ps = ProjectService()
        svc = WorldLayerService(ps)
        assert svc.list_layers() == []


class TestGetLayer:
    def test_get_existing_layer(self):
        ps, svc = _setup()
        result = svc.get_layer("layer_geografia")
        assert isinstance(result, Ok)
        assert result.value.name == "Geografía, clima y recursos"

    def test_get_hidden_layer(self):
        ps, svc = _setup()
        svc.hide_layer("layer_premisa")
        result = svc.get_layer("layer_premisa")
        assert isinstance(result, Ok)

    def test_get_nonexistent_layer(self):
        ps, svc = _setup()
        result = svc.get_layer("no_existe")
        assert isinstance(result, Error)

    def test_no_project_error(self):
        ps = ProjectService()
        svc = WorldLayerService(ps)
        result = svc.get_layer("layer_premisa")
        assert isinstance(result, Error)


class TestCreateLayer:
    def test_creates_with_auto_id(self):
        ps, svc = _setup()
        result = svc.create_layer("Custom Layer")
        assert isinstance(result, Ok)
        assert result.value.id.startswith("layer_user_")
        assert result.value.is_default is False
        assert result.value.is_visible is True

    def test_creates_with_description_and_order(self):
        ps, svc = _setup()
        result = svc.create_layer("Test", description="Desc", order=99)
        assert isinstance(result, Ok)
        assert result.value.description == "Desc"
        assert result.value.order == 99

    def test_empty_name_error(self):
        ps, svc = _setup()
        result = svc.create_layer("")
        assert isinstance(result, Error)

    def test_appears_in_list(self):
        ps, svc = _setup()
        svc.create_layer("Custom")
        layers = svc.list_layers()
        assert len(layers) == 17

    def test_no_project_error(self):
        ps = ProjectService()
        svc = WorldLayerService(ps)
        result = svc.create_layer("Test")
        assert isinstance(result, Error)


class TestHideShowLayer:
    def test_hide_default_layer_ok(self):
        ps, svc = _setup()
        result = svc.hide_layer("layer_premisa")
        assert isinstance(result, Ok)
        layer = svc.get_layer("layer_premisa")
        assert layer.value.is_visible is False

    def test_show_hidden_layer(self):
        ps, svc = _setup()
        svc.hide_layer("layer_premisa")
        result = svc.show_layer("layer_premisa")
        assert isinstance(result, Ok)
        layer = svc.get_layer("layer_premisa")
        assert layer.value.is_visible is True

    def test_hide_nonexistent_error(self):
        ps, svc = _setup()
        result = svc.hide_layer("no_existe")
        assert isinstance(result, Error)

    def test_show_nonexistent_error(self):
        ps, svc = _setup()
        result = svc.show_layer("no_existe")
        assert isinstance(result, Error)

    def test_hide_no_project_error(self):
        ps = ProjectService()
        svc = WorldLayerService(ps)
        result = svc.hide_layer("layer_premisa")
        assert isinstance(result, Error)


class TestReorderLayer:
    def test_reorder_updates_order(self):
        ps, svc = _setup()
        result = svc.reorder_layer("layer_premisa", 100)
        assert isinstance(result, Ok)
        layer = svc.get_layer("layer_premisa")
        assert layer.value.order == 100

    def test_reorder_nonexistent_error(self):
        ps, svc = _setup()
        result = svc.reorder_layer("no_existe", 1)
        assert isinstance(result, Error)

    def test_reorder_no_project_error(self):
        ps = ProjectService()
        svc = WorldLayerService(ps)
        result = svc.reorder_layer("layer_premisa", 1)
        assert isinstance(result, Error)


class TestUpdateLayer:
    def test_update_name(self):
        ps, svc = _setup()
        result = svc.update_layer("layer_premisa", name="Nuevo nombre")
        assert isinstance(result, Ok)
        assert result.value.name == "Nuevo nombre"

    def test_update_nonexistent_error(self):
        ps, svc = _setup()
        result = svc.update_layer("no_existe", name="x")
        assert isinstance(result, Error)
