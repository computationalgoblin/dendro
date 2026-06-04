# B32-DEBT — Hardening de deuda antes de avanzar

## Objetivo

Eliminar o cerrar por decisión explícita la deuda detectada en B32 antes de continuar con nuevas funcionalidades de producto.

Este bloque sustituye temporalmente el avance de:
- B33 Creación MVP estable.
- B34 Árboles y contexto jerárquico.
- B35+ roadmap posterior.

Hasta cerrar este bloque, no se implementan nuevas features salvo bugs P0 que bloqueen la propia limpieza.

## Reglas

1. No añadir funcionalidad nueva.
2. No avanzar Galería, Sesión, Worldbuilding, Árboles ni IA avanzada.
3. Todo cambio debe estar asociado a ticket B32-DEBT aprobado.
4. Toda corrección debe tener prueba o smoke real.
5. Las features que no se eliminen deben quedar en una de estas situaciones:
   - visible y justificada,
   - oculta en modo normal,
   - movida a avanzado/configuración,
   - pospuesta con ticket futuro,
   - eliminada con migración segura.
6. La UI normal no debe mostrar superficies técnicas salvo modo avanzado explícito.
7. Working tree debe quedar limpio al cierre, o la deuda de dirty tree debe quedar resuelta por commit/revert/split aprobado.

## Alcance

### P0

- Regularizar working tree sucio y separar documentación/auditoría de cambios funcionales previos.
- Recuperar validación ejecutable mínima: compileall y arquitectura si pytest está disponible.
- Resolver o formalizar la validación Windows pendiente.
- Corregir contratos rotos que bloquean continuar: TreeDetailPanel B32 static, campos de relación incorrectos si se confirma.

### P1

- Reducir superficie visible de UX normal.
- Eliminar rutas duplicadas para creación/edición de entidades y relaciones.
- Separar pipelines IA:
  - inline text suggestion,
  - candidatos globales,
  - import staging,
  - diagnóstico/incidencias.
- Ocultar Galería/Sesión/Corpus/RelationView/Frameworks/Layers si no corresponden al tipo de proyecto o modo avanzado.

### P2

- Copy visible incoherente.
- Botones deshabilitados sin feedback.
- Top toolbar heterogénea.
- Tests/suites no registrados.

### P3

- Registrar como deuda futura si su eliminación inmediata rompe arquitectura o requiere migración mayor:
  - `Project` demasiado grande,
  - `ProjectStore` CRUD legacy,
  - `Issue` legacy,
  - `domain/layers` legacy,
  - split de `ai_context_actions.py`.

## Fuera de alcance

- Galería nueva.
- Sesión/campaña nueva.
- Worldbuilding causal nuevo.
- Árboles nuevos más allá de regularizar deuda existente.
- Refactor profundo de `Project` o schema sin ticket específico.

## Definición de terminado

- Todos los tickets B32-DEBT cerrados o explícitamente diferidos con decisión documentada.
- `docs/product/product_debt_map.md` actualizado con estado final.
- `docs/product/roadmap_after_B32.md` actualizado si cambia el orden.
- `python -m compileall hosts/DesktopHostPySide packages -q` OK.
- `python -m pytest tests/architecture/ -q` OK si pytest disponible; si no, blocker de entorno documentado.
- Prueba visual Windows para UI si se tocó PySide.
- Working tree limpio.
