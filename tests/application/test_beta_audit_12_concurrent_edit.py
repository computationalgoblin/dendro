"""BETA-AUDIT-12: guardar no puede pisar en silencio lo que escribió otro.

No había NINGUNA protección contra edición concurrente: cero `filelock`, cero `flock`,
cero comprobación de `st_mtime` en `persistence/` ni en `project_service.py`. Con el
proyecto en una carpeta sincronizada (OneDrive, Drive, Dropbox) o abierto dos veces, el
último en guardar se llevaba por delante el trabajo del otro sin que nadie se enterara
— agravado porque el proyecto es un JSON monolítico que se reescribe entero.

Decisión de producto (2026-08-02): **rama (b), el mínimo honesto**. No se declara el
producto monousuario (sería renunciar a un caso de uso real: el mismo autor en dos
equipos con la carpeta sincronizada) ni se monta bloqueo fuerte. Se detecta el
conflicto al guardar y **nunca se pierde nada**: lo que hay en memoria se vuelca a un
fichero aparte y el usuario decide.
"""

from __future__ import annotations

import json

from packages.application.project_service import ProjectService
from packages.domain.entity import NarrativeEntity
from packages.domain.result import Error, Ok


def _proyecto_en_disco(ruta, nombre="Mundo compartido"):
    svc = ProjectService()
    assert isinstance(svc.create(name=nombre), Ok)
    assert isinstance(svc.save(ruta), Ok)
    return svc


def _tocar_por_fuera(ruta):
    """Simula a la otra copia de Dendro escribiendo el mismo fichero."""
    import os
    import time

    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos["name"] = "Editado por otro"
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    # mtime distinto y garantizado, sin depender de la resolución del reloj.
    futuro = time.time() + 10
    os.utime(ruta, (futuro, futuro))


def test_guardar_detecta_una_modificacion_externa(tmp_path):
    ruta = tmp_path / "mundo.json"
    _proyecto_en_disco(ruta)

    otro = ProjectService()
    assert isinstance(otro.open(ruta), Ok)
    otro.active_project.entities.append(NarrativeEntity(name="Mi trabajo"))

    _tocar_por_fuera(ruta)

    resultado = otro.save(ruta)
    assert isinstance(resultado, Error), "sobrescribió el trabajo de otro en silencio"
    assert "cambiado fuera de Dendro" in resultado.error


def test_el_trabajo_en_memoria_acaba_en_un_fichero_de_conflicto(tmp_path):
    ruta = tmp_path / "mundo.json"
    _proyecto_en_disco(ruta)
    otro = ProjectService()
    assert isinstance(otro.open(ruta), Ok)
    otro.active_project.entities.append(NarrativeEntity(name="No me pierdas"))
    _tocar_por_fuera(ruta)

    resultado = otro.save(ruta)
    assert isinstance(resultado, Error)
    conflictos = list(tmp_path.glob("mundo-conflicto-*.json"))
    assert conflictos, "se detectó el conflicto pero se perdió lo que había en memoria"
    guardado = json.loads(conflictos[0].read_text(encoding="utf-8"))
    assert any(e["name"] == "No me pierdas" for e in guardado["entities"])
    # Y el fichero original conserva lo que escribió el otro.
    assert json.loads(ruta.read_text(encoding="utf-8"))["name"] == "Editado por otro"


def test_dos_autoguardados_seguidos_no_dan_falso_positivo(tmp_path):
    """Trampa nº1: tras guardar hay que refrescar la huella o el 2.º guardado falla."""
    ruta = tmp_path / "mundo.json"
    svc = _proyecto_en_disco(ruta)
    assert isinstance(svc.open(ruta), Ok)
    for i in range(3):
        svc.active_project.entities.append(NarrativeEntity(name=f"E{i}"))
        assert isinstance(svc.save(ruta), Ok), f"el guardado nº{i + 2} se detectó a sí mismo"


def test_guardar_en_otra_ruta_nunca_da_falso_positivo(tmp_path):
    ruta = tmp_path / "mundo.json"
    svc = _proyecto_en_disco(ruta)
    assert isinstance(svc.open(ruta), Ok)
    _tocar_por_fuera(ruta)
    # `save_as` a un sitio distinto no pisa nada de nadie.
    assert isinstance(svc.save_as(tmp_path / "copia.json"), Ok)


def test_un_proyecto_nuevo_sin_abrir_guarda_sin_ruido(tmp_path):
    svc = ProjectService()
    assert isinstance(svc.create(name="Recién creado"), Ok)
    assert isinstance(svc.save(tmp_path / "nuevo.json"), Ok)


def test_cerrar_libera_la_vigilancia(tmp_path):
    ruta = tmp_path / "mundo.json"
    svc = _proyecto_en_disco(ruta)
    assert isinstance(svc.open(ruta), Ok)
    assert isinstance(svc.close(), Ok)
    assert isinstance(svc.create(name="Otro"), Ok)
    _tocar_por_fuera(ruta)
    # Tras cerrar y crear otro proyecto, esa ruta ya no se vigila.
    assert isinstance(svc.save(ruta), Ok)


def test_si_borran_el_fichero_guardar_lo_recrea(tmp_path):
    ruta = tmp_path / "mundo.json"
    svc = _proyecto_en_disco(ruta)
    assert isinstance(svc.open(ruta), Ok)
    ruta.unlink()
    assert isinstance(svc.save(ruta), Ok), "no había nada que pisar: debía recrearlo"
    assert ruta.exists()
