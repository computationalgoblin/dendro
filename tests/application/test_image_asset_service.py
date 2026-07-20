"""Tests de packages/application/image_asset_service.py (BETA2-IMG-01)."""

import hashlib

import pytest

from packages.application.image_asset_service import (
    ImageAssetService,
    assets_root_for,
)
from packages.domain.result import Error, Ok

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-image-data"


@pytest.fixture
def project_path(tmp_path):
    path = tmp_path / "mi-mundo.json"
    path.write_text("{}", encoding="utf-8")
    return path


@pytest.fixture
def service():
    return ImageAssetService()


class TestAssetsRoot:
    def test_carpeta_hermana_con_stem(self, project_path):
        root = assets_root_for(project_path)
        assert root == project_path.parent / "mi-mundo.assets"


class TestImportBytes:
    def test_crea_archivo_content_addressed(self, service, project_path):
        result = service.import_image_bytes(project_path, PNG_BYTES, ".png")
        assert isinstance(result, Ok)
        rel = result.value
        digest = hashlib.sha256(PNG_BYTES).hexdigest()[:16]
        assert rel == f"images/{digest}.png"
        stored = assets_root_for(project_path) / "images" / f"{digest}.png"
        assert stored.read_bytes() == PNG_BYTES

    def test_dedup_reimportar_no_duplica(self, service, project_path):
        first = service.import_image_bytes(project_path, PNG_BYTES, ".png")
        second = service.import_image_bytes(project_path, PNG_BYTES, "png")
        assert isinstance(first, Ok) and isinstance(second, Ok)
        assert first.value == second.value
        images_dir = assets_root_for(project_path) / "images"
        assert len(list(images_dir.iterdir())) == 1

    def test_jpeg_se_normaliza_a_jpg(self, service, project_path):
        result = service.import_image_bytes(project_path, PNG_BYTES, ".JPEG")
        assert isinstance(result, Ok)
        assert result.value.endswith(".jpg")

    def test_datos_vacios_es_error(self, service, project_path):
        result = service.import_image_bytes(project_path, b"", ".png")
        assert isinstance(result, Error)

    def test_extension_no_soportada_es_error(self, service, project_path):
        result = service.import_image_bytes(project_path, PNG_BYTES, ".gif")
        assert isinstance(result, Error)
        assert "gif" in result.error

    def test_error_io_devuelve_error(self, service, project_path, monkeypatch):
        monkeypatch.setattr(
            "pathlib.Path.write_bytes",
            lambda self, data: (_ for _ in ()).throw(OSError("disco lleno")),
        )
        result = service.import_image_bytes(project_path, PNG_BYTES, ".png")
        assert isinstance(result, Error)
        assert "disco lleno" in result.error


class TestImportFile:
    def test_importa_desde_archivo(self, service, project_path, tmp_path):
        source = tmp_path / "retrato.webp"
        source.write_bytes(PNG_BYTES)
        result = service.import_image_file(project_path, source)
        assert isinstance(result, Ok)
        assert result.value.endswith(".webp")
        assert service.resolve(project_path, result.value).exists()

    def test_archivo_inexistente_es_error(self, service, project_path, tmp_path):
        result = service.import_image_file(project_path, tmp_path / "no-existe.png")
        assert isinstance(result, Error)


class TestResolve:
    def test_resuelve_bajo_el_asset_store(self, service, project_path):
        resolved = service.resolve(project_path, "images/abc.png")
        assert resolved == assets_root_for(project_path) / "images" / "abc.png"


class TestDeleteIfUnreferenced:
    def test_borra_huerfano(self, service, project_path):
        rel = service.import_image_bytes(project_path, PNG_BYTES, ".png").value
        result = service.delete_if_unreferenced(project_path, rel, referenced=set())
        assert result == Ok(True)
        assert not service.resolve(project_path, rel).exists()

    def test_respeta_referenciado(self, service, project_path):
        rel = service.import_image_bytes(project_path, PNG_BYTES, ".png").value
        result = service.delete_if_unreferenced(project_path, rel, referenced={rel})
        assert result == Ok(False)
        assert service.resolve(project_path, rel).exists()

    def test_inexistente_o_vacio_no_hace_nada(self, service, project_path):
        assert service.delete_if_unreferenced(project_path, "images/nada.png", set()) == Ok(False)
        assert service.delete_if_unreferenced(project_path, "", set()) == Ok(False)


class TestCopyAssets:
    def test_copia_al_destino_de_guardar_como(self, service, project_path, tmp_path):
        rel = service.import_image_bytes(project_path, PNG_BYTES, ".png").value
        new_path = tmp_path / "otra-carpeta" / "copia.json"
        new_path.parent.mkdir()
        result = service.copy_assets(project_path, new_path)
        assert result == Ok(1)
        assert service.resolve(new_path, rel).read_bytes() == PNG_BYTES

    def test_sin_assets_origen_ok_cero(self, service, project_path, tmp_path):
        assert service.copy_assets(project_path, tmp_path / "b.json") == Ok(0)

    def test_mismo_destino_ok_cero(self, service, project_path):
        service.import_image_bytes(project_path, PNG_BYTES, ".png")
        assert service.copy_assets(project_path, project_path) == Ok(0)
