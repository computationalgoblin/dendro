# ADR 007 — ProjectService stateful con sesión de proyecto activo

**Estado:** Aceptado
**Fecha:** 2026-05-29
**Bloque:** 2
**Ticket asociado:** B02-T02

## Contexto

El `ProjectService` implementado en el Bloque 2 mantiene un atributo
`active_project: Project | None` que representa el proyecto actualmente
abierto en la sesión de aplicación. Es un servicio con estado (*stateful*).

Esto es una decisión pragmática para una aplicación de escritorio donde
solo hay un proyecto abierto a la vez y donde la capa de aplicación orquesta
el ciclo de vida (abrir, modificar, guardar, cerrar).

## Decisión

`ProjectService` mantiene estado de sesión (`active_project`) como parte
de su responsabilidad de orquestación. El dominio (`packages/domain/`)
**no conoce ni accede** a este estado global de sesión.

### Lo que ProjectService sí hace

- `create()` y `open()` establecen `active_project`
- `save()` y `save_as()` operan sobre `active_project`
- `close()` limpia `active_project` (idempotente)
- `validate()`, `get_config()`, `update_config()` pueden recibir un
  proyecto explícito o usar `active_project` por defecto

### Lo que el dominio NO hace

- Ninguna entidad de dominio (`Project`, `Entity`, etc.) sabe si está
  "activa" o "abierta"
- Ninguna clase de dominio referencia `ProjectService`
- Ninguna regla de dominio depende de estado de sesión
- Las dataclasses de dominio son puras: atributos + serialización

## Alternativas descartadas

### Servicio completamente stateless

Cada método recibiría un `Project` explícito como parámetro. Esto duplicaría
el parámetro en cada llamada desde la UI y obligaría a la UI a mantener
la referencia del proyecto activo. Para una app de escritorio con un solo
proyecto abierto, es sobreingeniería sin beneficio real.

### State en una variable global / módulo

Descartado por ser imposible de testear y acoplar toda la aplicación a
un singleton implícito. Con `ProjectService` la inyección es explícita
y los tests pueden crear múltiples instancias.

## Riesgos identificados para bloques futuros

| Riesgo | Mitigación |
|--------|-----------|
| Abrir otro proyecto sin cerrar el actual | Antes de `open()`, verificar `active_project`. Si no es None, preguntar si guardar/dirty. |
| Estado dirty (cambios no guardados) | Añadir flag `is_dirty: bool` en `ProjectService` o en `Project` (más probable: en servicio). El flag se activa en `update_config()` y se limpia en `save()`. |
| Guardar como sin actualizar ruta actual | Añadir `_current_path: Path | None` en `ProjectService` para que `save()` sin parámetro use la ruta conocida. |
| Concurrencia futura (multi-ventana, web) | Este diseño stateful es correcto para app de escritorio single-window. Si en el futuro se soporta multi-ventana o web, `ProjectService` debería ser instanciado por sesión, no singleton. |

## Consecuencias

- **Positivo:** API simple y natural para la capa de UI. La UI solo llama
  a `svc.create("mi mundo")`, `svc.save(path)`, `svc.close()`.
- **Positivo:** El dominio permanece puro y testeable sin dependencia de
  estado de sesión.
- **A vigilar:** Los riesgos arriba listados deben revisitarse en los
  Bloques 3-5 según se añadan entidades y operaciones más complejas.
