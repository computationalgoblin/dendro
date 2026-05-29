# Convencion de pruebas

## Estructura de tests

```
tests/
├── conftest.py              — Fixtures base (todas las suites)
├── test_sanity.py           — Tests de sanidad y estructura
├── domain/
│   ├── conftest.py          — Fixtures especificas de dominio
│   ├── test_result.py
│   ├── test_config.py
│   ├── test_exceptions.py
│   └── test_logging.py
├── application/             — (futuro)
│   ├── conftest.py
│   └── ...
├── persistence/             — (futuro)
│   ├── conftest.py
│   └── ...
├── ui/                      — (futuro)
│   └── ...
└── architecture/
    └── test_dependency_rules.py
```

## Reglas

### 1. Nombrado

| Elemento | Formato | Ejemplo |
|----------|---------|---------|
| Archivo | `test_<descripcion>.py` | `test_result.py` |
| Clase | `Test<Descripcion>` | `TestResultCreation` |
| Metodo | `test_<descripcion>` | `test_unwrap_ok` |
| Fixture | `<descripcion>` | `app_config` |

### 2. Ejecucion

```bash
# Todas las pruebas
python -m pytest tests/ -v

# Solo dominio
python -m pytest tests/domain/ -v

# Solo smoke/sanidad
python -m pytest tests/ -m smoke -v

# Solo integracion
python -m pytest tests/ -m integration -v

# Con cobertura
python -m pytest tests/ --cov=packages --cov-report=term-missing

# Sin cache (forzar re-ejecucion)
python -m pytest tests/ --cache-clear -v
```

### 3. Marcadores

| Marker | Uso |
|--------|-----|
| `@pytest.mark.smoke` | Pruebas de sanidad que deben pasar siempre |
| `@pytest.mark.unit` | Pruebas unitarias puras (sin I/O) |
| `@pytest.mark.integration` | Pruebas que usan I/O (archivos, DB, red) |
| `@pytest.mark.slow` | Pruebas lentas (>5s) |
| `@pytest.mark.domain` | Pruebas de la capa de dominio |
| `@pytest.mark.application` | Pruebas de la capa de aplicacion |

### 4. Aislamiento

- Cada test debe ser independiente: no compartir estado con otros tests.
- Usar fixtures de `conftest.py` para estado compartido (config, datos de prueba).
- El fixture `_reset_settings` (autouse) garantiza que la configuracion no se filtra entre tests.
- Usar `tmp_path` (built-in de pytest) para archivos temporales.
- No usar variables globales mutables entre tests.

### 5. Dominio

- Los tests de dominio NO deben requerir I/O (archivos, BD, red).
- Los tests de dominio deben ejecutarse en < 2s la suite completa.
- No usar fixtures de integracion en tests de dominio.
- Los tests deben ser puros: misma entrada -> misma salida.

### 6. Integracion

- Marcar con `@pytest.mark.integration`.
- Usar `tmp_path` o `tempfile.TemporaryDirectory` para archivos.
- Usar mocks para APIs externas (nunca llamar a APIs reales).
- Pueden ser lentos (hasta 5s cada uno).

### 7. Linter

- Ejecutar `ruff check packages/ tests/` antes de cada commit.
- Ejecutar `ruff format packages/ tests/ --check` para verificar formato.
- No cerrar un ticket si hay errores de linter.

### 8. Cobertura

- La suite completa debe mantener cobertura > 80% en `packages/`.
- No es obligatorio en Bloque 1, pero debe monitorizarse.
- Generar reporte: `python -m pytest tests/ --cov=packages --cov-report=html`

### 9. Smoke tests

- Se ejecutan con `-m smoke`.
- Deben completarse en < 3s.
- Verifican: imports basicos, estructura de proyecto, dependencias de capas.

### 10. Fixtures base disponibles

**En `tests/conftest.py`:**

| Fixture | Descripcion |
|---------|-------------|
| `app_config` | AppConfig por defecto |
| `debug_config` | AppConfig con debug=True, level=DEBUG |
| `temp_data_dir` | Path temporal para datos |
| `app_config_with_temp_dir` | AppConfig + directorio temporal |
| `test_logger_name` | Nombre unico para logger |

**En `tests/domain/conftest.py`:**

| Fixture | Descripcion |
|---------|-------------|
| `domain_config` | AppConfig minimo para dominio |
| `sample_ok_result` | Ok(42) predefinido |
| `sample_error_result` | Error("fail") predefinido |
