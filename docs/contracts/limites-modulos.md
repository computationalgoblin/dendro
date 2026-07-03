# Limites entre modulos

## Estructura de capas

```
┌─────────────────────────────────┐
│             UI                   │
│  (interfaz de escritorio)       │
│  Puede importar: application    │
│  Puede importar: domain         │
│  NUNCA escribe en persistence   │
└─────────────┬───────────────────┘
              │ depende de
              ▼
┌─────────────────────────────────┐
│         Application             │
│  (casos de uso, orquestacion)   │
│  Puede importar: domain         │
└─────────────┬───────────────────┘
              │ depende de
              ▼
┌─────────────────────────────────┐
│    Infrastructure               │
│  (IA, exportacion)              │
│  Puede importar: domain         │
│  Puede importar: application    │
└─────────────┬───────────────────┘
              │ depende de
              ▼
┌─────────────────────────────────┐
│         Persistence             │
│  (almacenamiento, migraciones)  │
│  Puede importar: domain         │
└─────────────┬───────────────────┘
              │ depende de
              ▼
┌─────────────────────────────────┐
│           Domain                │
│  (modelo de dominio puro)       │
│  Solo stdlib Python             │
│  NO depende de ninguna capa     │
└─────────────────────────────────┘
```

## Reglas de dependencia

### Domain (nucleo) — capa 0

- **NO** importa: `application`, `infrastructure`, `persistence`, `ui`
- **SI** importa: sus propios submodulos, stdlib de Python
- **Dependencias externas:** Ninguna. Solo `typing`, `abc`, `dataclasses`, `enum`, `datetime`, `uuid`, `collections`, `json`, `pathlib`, `os`, `io`, `re`, `logging`, `sys` y similares de stdlib.
- **Excepciones:** Ninguna. El dominio debe ser puro.

### Application (casos de uso) — capa 1

- **NO** importa: `infrastructure`, `persistence`, `ui`
- **NO** importa: capas que no sean `domain`
- **SI** importa: `domain`, stdlib
- **Responsabilidad:** Orquestar flujos, validar permisos, coordinar repositorios a traves de puertos/interfaces definidos en `domain`.

### Infrastructure (IA, etc.) — capa 2

- **NO** importa: `persistence`, `ui`
- **SI** importa: `domain`, `application`, stdlib, librerias externas (openai, etc.)
- **Responsabilidad:** Implementar puertos definidos en domain/application para servicios externos.

### Persistence (almacenamiento) — capa 3

- **NO** importa: `application`, `infrastructure`, `ui`
- **SI** importa: `domain`, stdlib, librerias externas de serializacion (json, sqlite, etc.)
- **Responsabilidad:** Implementar repositorios definidos en domain. Guardar y cargar datos de forma segura.

### UI (interfaz) — capa 4

- **NO** importa: `persistence`, `infrastructure`
- **NO** escribe en persistencia directamente
- **SI** importa: `application` (preferentemente), `domain` (lectura de tipos, enums)
- **Responsabilidad:** Presentar datos, recibir acciones del usuario, delegar en application.

## Dependencias entre paquetes (matriz)

| Capa | domain | application | infrastructure | persistence | ui |
|------|--------|-------------|----------------|-------------|-----|
| **domain** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **application** | ✅ | ✅ | ❌ | ❌ | ❌ |
| **infrastructure** | ✅ | ✅ | ✅ | ❌ | ❌ |
| **persistence** | ✅ | ❌ | ❌ | ✅ | ❌ |
| **ui** | ✅ | ✅ | ❌ | ❌ | ✅ |

- ✅ = permitido
- ❌ = prohibido

## Dependencias externas

| Capa | Librerias externas permitidas |
|------|-------------------------------|
| **domain** | **Ninguna.** Solo stdlib. |
| **application** | Ninguna en dominio puro. Puede tener dependencias de solo tipo si son necesarias para contratos. |
| **infrastructure** | Permitidas segun funcionalidad (openai, etc.) |
| **persistence** | Permitidas para almacenamiento (sqlite3 stdlib, aiofiles, orjson, etc.) |
| **ui** | Permitidas segun framework elegido (tkinter, textual, etc.) |

## Contratos entre capas

Las capas superiores se comunican con las inferiores mediante:

1. **Llamadas directas** a modulos publicos de la capa inferior (ej: application llama a funciones de domain).
2. **Puertos/Interfaces** definidos en la capa inferior e implementados por la superior (ej: repositorio definido en domain, implementado en persistence).
3. **Eventos/DTOs** para comunicacion desacoplada (futuro).

## Validacion automatica

Las reglas anteriores se verifican automaticamente mediante:

```bash
python -m pytest tests/architecture/ -v
```

Este test analiza estaticamente los imports de cada paquete usando AST y falla si encuentra violaciones.

## Excepciones documentadas

| Excepcion | Justificacion | Fecha |
|-----------|---------------|-------|
| _(ninguna aun)_ | | |

Toda excepcion a estas reglas debe ser documentada y aprobada por el Architecture Agent.
