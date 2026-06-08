# Bloque 39 — Control operativo del proyecto

## Estado

Aprobado, implementado y cerrado documentalmente. Ver `docs/cierres/bloque-39-cierre.md`.

## Objetivo

Reducir el caos del proyecto separando con claridad:

- fase activa,
- backlog ejecutable,
- decisiones arquitectónicas,
- deuda conocida,
- definición de terminado,
- validación técnica,
- changelog/cierres,
- límites entre exploración, producto, legacy y deuda.

B39 no añade funcionalidad narrativa nueva. Es un bloque de control, hardening documental y tooling mínimo.

## Motivación

El proyecto ha acumulado muchas capas funcionales: core, persistencia, CLI, Desktop, grafos, IA, worldbuilding, coherencia, command bar, candidatos y validaciones Windows pendientes. El problema principal ya no es solo programar features, sino mantener una única fuente de verdad operativa.

B39 introduce artefactos livianos y verificables para saber:

- qué bloque está activo,
- qué entra y qué no entra,
- qué deuda existe,
- qué decisiones se han tomado,
- cómo validar salud del repo,
- cuándo una tarea está realmente terminada,
- qué queda pendiente de Windows nativo.

## Principios

1. No sustituir Kanban: complementarlo con artefactos legibles en repo.
2. No duplicar contratos autoritativos: referenciarlos y resumir estado operativo.
3. No ocultar deuda: registrarla con IDs estables.
4. No crear burocracia pesada: archivos pequeños, actualizables y útiles.
5. No mezclar features con estabilización: B39 congela features nuevas mientras se instala el sistema de control.
6. No afirmar validaciones no ejecutadas: Windows nativo sigue siendo una puerta explícita.

## Incluye

- `ROADMAP.md` con bloques, estado, gates y próximos pasos.
- `PHASE_CURRENT.md` con fase activa, incluye/excluye, criterios de salida y validaciones.
- `KNOWN_ISSUES.md` con deuda y bugs conocidos, incluyendo pendientes Windows.
- `docs/adr/` y primer ADR del sistema de control operativo.
- `CHANGELOG.md` mínimo, orientado a cierres de bloques.
- Plantillas para fases/tickets/cierres.
- Script único de verificación local que envuelve comandos existentes.
- Tests/sanity de artefactos críticos para evitar que el sistema se pudra.
- Actualización documental de workflow/DoD si procede.

## Excluye

- Nuevas features de Creación.
- Galería.
- Sesión.
- Nuevos modelos de dominio narrativo.
- Reescritura de Kanban.
- CI remoto.
- Refactor masivo.
- Limpieza indiscriminada de código.
- Cierre de deuda sin prueba real.

## Artefactos propuestos

### `ROADMAP.md`

Fuente legible de alto nivel:

- bloques cerrados,
- bloque activo,
- próximos bloques candidatos,
- gates pendientes,
- validaciones Windows pendientes,
- enlace a contratos/cierres.

No sustituye a `docs/contracts/contrato_fases`; lo resume operativamente.

### `PHASE_CURRENT.md`

Una sola fase activa:

- objetivo,
- incluye,
- excluye,
- tickets activos,
- Definition of Done de la fase,
- validaciones obligatorias,
- salida esperada.

Regla: si algo no cabe aquí, no se implementa; va a backlog/deuda.

### `KNOWN_ISSUES.md`

Registro de deuda/bugs aceptados:

- ID estable,
- severidad,
- estado,
- bloque origen,
- evidencia,
- impacto,
- criterio de cierre.

Debe incorporar o referenciar deuda ya conocida sin renumerar de forma destructiva.

### `docs/adr/`

Decisiones arquitectónicas y operativas relevantes.

Primer ADR esperado:

`ADR-001-control-operativo-del-proyecto.md`

Tema: Kanban sigue siendo la ejecución; repo docs contienen fuente humana de fase/deuda/decisiones.

### `CHANGELOG.md`

Resumen humano de cambios relevantes por bloque/commit.

No reemplaza git log ni cierres técnicos, solo ayuda a recuperar contexto.

### Plantillas

- `docs/templates/phase-template.md`
- `docs/templates/ticket-template.md`
- `docs/templates/closure-template.md`

### Verificación única

Script mínimo:

- `scripts/verify_all.sh`
- `scripts/verify_all.ps1` si procede en Windows.

Debe llamar a comandos ya existentes, no reinventar runner:

- compileall,
- arquitectura,
- suites relevantes,
- sanity documental B39.

## Definition of Done B39

B39 solo puede cerrarse si:

- todos los artefactos existen,
- no contradicen contratos existentes,
- cada archivo tiene propósito claro,
- hay tests/sanity para presencia y consistencia mínima,
- `scripts/run_all_tests.py` incluye suite B39 si se añaden tests nuevos,
- `scripts/verify_all.sh` funciona en WSL,
- Windows queda documentado como pendiente o validado con evidencia real,
- Kanban refleja estado real,
- working tree queda limpio.

## Validaciones mínimas

- `python -m compileall hosts/DesktopHostPySide packages tests -q`
- `python -m pytest tests/architecture/ -q`
- `python scripts/run_all_tests.py --suites arch sanity b39`
- `bash scripts/verify_all.sh --fast` o equivalente mínimo
- revisión manual de artefactos: ROADMAP, PHASE_CURRENT, KNOWN_ISSUES, ADR, CHANGELOG

## Riesgos

- Duplicar fuentes de verdad con Kanban.
- Crear documentos largos que nadie actualice.
- Intentar resolver toda la deuda en vez de registrarla.
- Cerrar Windows sin validación real.
- Convertir B39 en un bloque enorme.

## Decisión de alcance

B39 instala el sistema mínimo de control. No limpia toda la deuda ni reorganiza todo el repositorio. El resultado esperado es poder responder rápidamente:

- qué estamos haciendo ahora,
- qué no entra,
- qué está pendiente,
- cómo se valida,
- qué deuda aceptamos,
- qué decisión justifica una frontera.
