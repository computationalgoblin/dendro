# Convenciones de errores, Result y logging

## Result type

El proyecto usa un tipo `Result[T, E]` generico (Ok/Error) para evitar excepciones como flujo de control.

### Variantes

```python
Ok(value: T)     # Exito con valor
Error(error: E)  # Fracaso con error
```

### Funciones de utilidad

| Funcion | Descripcion |
|---------|-------------|
| `is_ok(result)` | True si es Ok |
| `is_error(result)` | True si es Error |
| `unwrap(result)` | Retorna valor Ok, lanza TypeError si es Error |
| `unwrap_error(result)` | Retorna valor Error, lanza TypeError si es Ok |
| `map_result(result, fn)` | Aplica fn al valor Ok |
| `map_error_result(result, fn)` | Aplica fn al valor Error |
| `chain_result(result, fn)` | Encadena funcion que retorna Result |

### Cuando usar Result vs excepciones

| Situacion | Usar |
|-----------|------|
| Validacion de dominio que falla por invariantes | Result |
| Operacion que puede fallar por I/O (persistencia, red) | Result o excepcion |
| Error de programacion (assert, tipo incorrecto) | Excepcion |
| Error de configuracion al arrancar | Excepcion (ConfigurationError) |
| Flujo normal con 2+ caminos de exito/fracaso | Result |

## Jerarquia de excepciones

```
Exception
  └── NarrativeArchitectError
        ├── DomainError          (codigo: DOMAIN_XXX)
        ├── ApplicationError     (codigo: APP_XXX)
        ├── ConfigurationError   (codigo: CONFIG_XXX)
        └── PersistenceError     (codigo: PERSIST_XXX)
```

### Reglas

- Toda excepcion debe heredar de `NarrativeArchitectError`.
- Toda excepcion debe tener un `code` unico (ej: `DOMAIN_042`).
- Capturar `NarrativeArchitectError` captura todos los errores del proyecto.
- Las excepciones de dominio (`DomainError`) solo se usan para violaciones de invariantes.
- Las excepciones de aplicacion (`ApplicationError`) para errores de uso/permisos.

## Logging

### Uso basico

```python
from packages.domain.logging import get_logger

logger = get_logger(__name__)
logger.info("mensaje")
logger.debug("detalle")
logger.warning("cuidado")
logger.error("fallo")
```

### Configuracion

```python
from packages.domain.config import AppConfig, LoggingConfig
from packages.domain.logging import configure_logging

config = AppConfig(
    debug=True,
    logging=LoggingConfig(level="DEBUG")
)
configure_logging(config)
```

### Convenciones

- Usar `get_logger(__name__)` siempre.
- Niveles: DEBUG para detalle, INFO para eventos normales, WARNING para situaciones recuperables, ERROR para fallos.
- No hacer logging desde el modelo de dominio puro (solo desde servicios de aplicacion e infraestructura).
- Formato estructurado por defecto: `[timestamp] LEVEL module | message`.
- `configure_logging()` una vez al arrancar la aplicacion.
