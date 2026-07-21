# Evolución de esquema

Este documento define la estrategia de versionado de esquema para los archivos
de proyecto de narrative-architect. Aplica a la persistencia de proyectos
(`ProjectStore`), migraciones futuras y compatibilidad hacia atrás.

---

## 1. Estado actual

### Schema version: 39 (cierre de beta, 2026-07-21)

La versión actual y máxima soportada se definen en `packages/persistence/schema.py`
(**la fuente de verdad es siempre el código**, no este documento — v39 al cierre de
beta: subhitos v36, memoria v37, referencias v38, wiki v39; historial completo en §4):

```python
CURRENT_SCHEMA_VERSION: int = 39
MAX_SUPPORTED_VERSION: int = CURRENT_SCHEMA_VERSION
```

### Formato de archivo

Los proyectos se guardan como **JSON** con un campo `schema_version` en la raíz:

```json
{
    "schema_version": 1,
    "id": "abc123def456",
    "name": "Mi Proyecto",
    "created_at": "2026-05-29T10:00:00+00:00",
    "updated_at": "2026-05-29T10:00:00+00:00",
    "metadata": {}
}
```

### Detección y validación

El sistema implementa dos funciones en `packages/persistence/schema.py`:

- **`detect_schema_version(data)`**: extrae `schema_version` del JSON. Retorna 0 si no está presente o no es parseable.
- **`validate_schema_version(version)`**: verifica que la versión esté entre 1 y `MAX_SUPPORTED_VERSION`. Retorna `None` si es válida, o un mensaje de error si no lo es.

### Lectura de datos — flujo

1. `_read_json()` — lee el archivo, parsea JSON.
2. `detect_schema_version()` — extrae la versión del JSON.
3. `validate_schema_version()` — valida que sea soportada.
4. Si la versión es mayor que `MAX_SUPPORTED_VERSION`, se rechaza con un error claro.
5. `Project.from_dict()` — deserializa según la versión detectada.

### Escritura de datos — flujo

1. `Project.to_dict()` — serializa el modelo a dict.
2. `save_project_data()` — añade `schema_version` al dict.
3. `_write_json_atomic()` — escritura segura: temp file → fsync → rename.

---

## 2. Estrategia de migraciones

### Principios generales

1. **Hacia adelante siempre.** Una migración transforma datos de versión N a N+1.
   Nunca existen migraciones hacia atrás. Si se necesita abrir un archivo más nuevo
   con una versión antigua del software, se rechaza con un mensaje claro pidiendo
   actualizar la aplicación (no se intenta "adivinar" el formato).

2. **Una versión por migración.** Cada schema version tiene exactamente una
   migración que la produce. No hay migraciones que salten versiones.

3. **Inmutabilidad de datos viejos.** Una migración no modifica el archivo original.
   Produce un nuevo archivo con la nueva versión. El backup se genera antes de migrar.

4. **Idempotencia.** Una migración aplicada dos veces sobre el mismo dato debe
   producir el mismo resultado (check de version antes de aplicar).

5. **Trazabilidad.** Toda migración debe ser registrada en el historial del proyecto
   como un `HistoryEntry` (cuando exista ese módulo).

### Infraestructura de migraciones (futuro)

Cuando se necesite la primera migración real (v1 → v2), se implementará:

```
packages/persistence/
├── schema.py                    # Versiones, detección, validación
├── store.py                     # ProjectStore (save/load/exists)
└── migrations/
    ├── __init__.py              # Registry de migraciones
    ├── registry.py              # Mapa version -> funcion migradora
    └── v1_to_v2.py              # Primera migración real (cuando exista)
```

#### Registry (propuesta)

```python
# packages/persistence/migrations/registry.py

MIGRATIONS: dict[int, Callable[[dict], Result[dict, str]]] = {
    1: migrate_v1_to_v2,  # cuando exista
    2: migrate_v2_to_v3,  # etc.
}


def run_migrations(
    data: dict,
    from_version: int,
    to_version: int,
) -> Result[dict, str]:
    """Apply all migrations from from_version to to_version sequentially."""
    current = from_version
    data = dict(data)
    while current < to_version:
        next_version = current + 1
        migrator = MIGRATIONS.get(current)
        if migrator is None:
            return Error(f"No migration found for v{current} -> v{next_version}")
        result = migrator(data)
        if is_error(result):
            return Error(f"Migration v{current} -> v{next_version} failed: {unwrap_error(result)}")
        data = unwrap(result)
        data["schema_version"] = next_version
        current = next_version
    return Ok(data)
```

#### Carga con migración automática (propuesta)

```python
def load_with_migration(path: Path) -> Result[Project, str]:
    data = load_project_data(path)  # puede fallar si version > MAX
    
    version = detect_schema_version(data)
    if version == CURRENT_SCHEMA_VERSION:
        return Project.from_dict(data)
    
    # Migrar automáticamente
    result = run_migrations(data, version, CURRENT_SCHEMA_VERSION)
    if is_error(result):
        return Error(...)
    
    # Guardar versión migrada (con backup del original)
    save_project_data(result.value, path)
    return Project.from_dict(result.value)
```

### Cuándo crear una nueva versión de esquema

Crear una nueva versión cuando:

1. Se añaden **campos obligatorios** a un modelo existente.
2. Se **renombra o elimina** un campo existente.
3. Cambia el **formato de serialización** de un campo (ej: de string a objeto).
4. Cambia la **estructura de colecciones** (ej: de dict a lista de objetos).
5. Se **reorganiza** la jerarquía del JSON (ej: mover campos a sub-objetos).

**No** crear nueva versión cuando:

1. Se añaden campos opcionales (el default cubre la carga de versiones anteriores).
2. Se añaden metadatos en el campo `metadata` existente.
3. Se añaden colecciones vacías que no afectan a la estructura existente.

### Reglas para escribir una migración

1. La función recibe un `dict` con datos de la versión anterior.
2. Retorna `Result[dict, str]` — Ok con los datos transformados, o Error.
3. No modifica el dict de entrada (trabajar sobre una copia).
4. La migración **no** toca el campo `schema_version` (el registry lo gestiona).
5. Documentar en el docstring qué campos se añaden/eliminan/renombran.

### Compatibilidad

| Situación | Comportamiento |
|-----------|---------------|
| Versión = CURRENT_SCHEMA_VERSION | Carga normal, sin migración |
| Versión < CURRENT_SCHEMA_VERSION | Migrar secuencialmente, guardar copia migrada |
| Versión > MAX_SUPPORTED_VERSION | Rechazar con error: "actualice la aplicación" |
| Versión = 0 o negativa | Rechazar con error: "formato no reconocido" |
| Sin campo schema_version | Rechazar con error: "formato no reconocido" |

---

## 3. Procedimiento para añadir una nueva versión

1. Incrementar `CURRENT_SCHEMA_VERSION` en `schema.py`.
2. Incrementar `MAX_SUPPORTED_VERSION` si es necesario.
3. Crear `packages/persistence/migrations/v{N}_to_v{N+1}.py` con la función migradora.
4. Registrar la migración en el `registry.py`.
5. Actualizar `Project.to_dict()` y `Project.from_dict()` para la nueva versión.
6. Añadir tests:
   - Datos v{N} cargan correctamente y migran a v{N+1}.
   - Datos v{N+1} guardan y cargan sin migración.
   - Datos con versión futura se rechazan.
7. Documentar el cambio en este documento (sección 4. Historial de versiones).

---

## 4. Historial de versiones de esquema

| Versión | Descripción | Fecha | Ticket |
|---------|------------|-------|--------|
| 1 | Versión inicial. Project básico (id, name, timestamps, metadata). | 2026-05-29 | B01-T05 |
| 2..32 | _(historial intermedio no documentado aquí; ver las funciones `_apply_migration_vN_to_vN+1` en `packages/persistence/schema.py` y sus tests `tests/persistence/test_schema_*.py`)_ | — | — |
| 33 | Jardín narrativo (riego): colecciones aditivas `watering_diagnostics` y `watering_paused_entity_ids` a nivel de proyecto (vacías al migrar; canon intacto). Nuevo `CanonState.FANTASMA` para nodos/relaciones fantasma (no requiere migración de datos). Nota de realidad: las migraciones viven como funciones en `schema.py` con la cadena de carga en `store.load_project_data`; no existe carpeta `migrations/` ni registry (los pasos 3-4 de §3 describen una propuesta futura). | 2026-07-03 | BETA2-FOCO-01 |

---

## 5. Claves reservadas de `custom_metadata`

`NarrativeEntity.custom_metadata` es de forma libre, pero algunas claves con
prefijo `_` tienen contrato de producto (añadirlas NO requiere nueva versión
de esquema — son campos opcionales, §2):

| Clave | Contenido | Desde |
|-------|-----------|-------|
| `_node_color` | Color hex explícito del nodo en el lienzo (vacío = paleta por tipo). | BETA1 |
| `_image_path` | Retrato de la entidad: ruta **relativa** al asset store del proyecto (`<stem>.assets/`, p. ej. `images/3fa9c2d41b7e88aa.png`). Una ruta **absoluta** es legado BETA1-F04: se sigue leyendo mientras el archivo exista y se normaliza al asset store al reencuadrar. Gestión: `packages/application/image_asset_service.py` (nombres content-addressed `sha256[:16]`; la UI nunca escribe assets directamente). | BETA2-IMG-01 (2026-07-05) |
| `_image_crop` | Encuadre del retrato: `{"cx": 0..1, "cy": 0..1, "zoom": >=1}` (centro fraccional + zoom sobre el recorte cuadrado máximo). Modelo puro en `packages/application/portrait_crop.py`; ausencia ⇒ encuadre por defecto (0.5, 0.5, 1.0). | BETA2-IMG-01 (2026-07-05) |
| `_causal_potency_basal` | Potencia causal basal (int 0..100) de una entidad = potencialidad de propagación causal. La **atribuye la IA al Regar** de forma semántica (`potencial_causal` del payload → `set_basal_potency`); el detector estructural (BETA2-STRUCT) la LEE para proponer reubicaciones de anillo. Gestión: `packages/application/causal_potency.py`. | BETA2-MEM-08 · atribución IA BETA2-STRUCT-09 (2026-07-12) |
| `_causal_ascending_exception` | (En **relaciones**) marca de excepción ascendente (`apalancamiento`/`catalizador`/`vulnerabilidad`/`acumulacion`/`amplificacion`): permite que un cambio inferior escale a un anillo superior en el motor de impacto. | BETA2-MEM-08 |
| `_struct_dismissed` | Lista de *fingerprints* de ajustes estructurales **rechazados** (se suprimen hasta que el fingerprint cambia por topología). Gestión: `packages/application/structural_analysis_service.py`. | BETA2-STRUCT-01 (2026-07-12) |
| `_struct_snoozed` | Mapa `{fingerprint: index_revision}` de ajustes estructurales **aplazados** (se suprimen hasta el siguiente cambio de canon). | BETA2-STRUCT-01 (2026-07-12) |

Los binarios de imagen viven FUERA del JSON, en la carpeta hermana
`<stem>.assets/images/`; mover un proyecto conserva los retratos si la carpeta
viaja junto al JSON. Archivo ausente ⇒ las superficies degradan al render sin
imagen (nunca error).

---

## 6. Referencias

- `packages/persistence/schema.py` — implementación actual de versionado
- `packages/persistence/store.py` — ProjectStore con save/load atómico
- `docs/contracts/convenciones-nombres.md` — convenciones de nombres
- `docs/contracts/limites-modulos.md` — reglas de dependencia entre capas
- `docs/contracts/convenciones-errores.md` — Result type y manejo de errores
