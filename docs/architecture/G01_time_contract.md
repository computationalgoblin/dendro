# G01 — Contrato temporal de Dendro (Fase G: El Tiempo)

Decisiones de producto (usuario, sesión F→G): **año entero + era** ·
**default automático al crear** · **migración a era "Presente"**.

## 1. Concepto

El grafo tiene DOS vistas principales del mismo árbol:

```text
Vista concéntrica  = el árbol desde ARRIBA (anillos = status quo, lo que ES)
Vista cronológica  = el árbol desde el LADO (raíces = historia, lo que FUE)
```

En la cronológica, el eje vertical descendente es el tiempo: las **eras** son
estratos horizontales (misma estética de hendiduras que los anillos), las
**entidades** son líneas de vida (nacen en su año, mueren o continúan) y los
**hitos** ramifican como raíces desde las entidades que afectan.

Consecuencia ontológica: **nada existe en la atemporalidad**. Toda entidad
tiene año de nacimiento (y de muerte si procede). El sistema lo garantiza por
DEFECTO (asignación automática), nunca por bloqueo del flujo de creación.

## 2. Estado real del código (auditoría)

- `CausalMilestone` NO tiene campos temporales (solo created/updated técnicos).
- Ninguna entidad de dominio tiene birth/death/era. No existe modelo `Era`.
- Existe `MilestoneChronologyView` (Hermes H03) — panel en drawer, ordenación
  no temporal-espacial. Se conserva como base/acceso, la vista G04 lo
  trasciende.
- Schema de persistencia actual: v7 → la fase introduce v8.

## 3. Modelo temporal

### 3.1 Era (nuevo, en `packages/domain/era.py`)

```text
Era:
  id: str ("era_<uuid8>")
  name: str
  start_year: int           # inclusive
  end_year: int | None      # None = era abierta (la actual)
  order: int                # desempate visual; el orden real es start_year
  description: str = ""
```

Reglas: las eras de un proyecto no se solapan (validación suave: warning, no
bloqueo); siempre existe al menos una era; el proyecto tiene `present_year:
int` (año "ahora" del mundo, default 0) que vive en la era abierta.

### 3.2 Entidad (campos nuevos en NarrativeEntity)

```text
birth_year: int | None     # None SOLO transitorio pre-migración
death_year: int | None     # None = sigue viva/vigente
```

La era de una entidad es DERIVADA (no almacenada): la era que contiene su
birth_year. Ramas (contenedores) también tienen vida temporal (una facción
nace y cae). Validación: death_year ≥ birth_year.

### 3.3 Hito (campo nuevo en CausalMilestone)

```text
year: int | None           # None transitorio pre-migración
```

Validación suave: el año del hito debería caer dentro de la vida de las
entidades afectadas (warning de coherencia, no bloqueo — un hito póstumo
puede ser legítimo: "su leyenda creció").

## 4. No-atemporalidad por defecto

- Crear hoja/rama (cualquier ruta: menú contextual, IA aceptada, importación):
  `birth_year = project.present_year`, `death_year = None`. Editable después.
- Crear hito: `year = project.present_year`.
- Las rutas de creación existentes (`_create_entity_on_graph`, candidatos
  aceptados, etc.) pasan por `EntityService.create_entity` → el default vive
  EN EL SERVICIO, no en la UI (una sola fuente).

## 5. Migración (v7 → v8)

Al abrir un proyecto v7:
1. Crear `Era(name="Presente", start_year=0, end_year=None, order=0)` si no
   hay eras.
2. `project.present_year = 0` si no existe.
3. Toda entidad sin `birth_year` → 0; hitos sin `year` → 0.
4. Bump schema a v8. Sin pérdida, sin intervención manual, reversible por
   backup (la migración no borra nada).

## 6. UI temporal (G03)

- Paneles editoriales: fila temporal DISCRETA bajo la fila de identidad:
  `Nace [año] · Muere [año|—] · Era (derivada, solo lectura)`. Misma estética
  F (sin romper el layout exacto).
- CRUD de eras: sección "Eras" en el panel de filtros (patrón Anillos) +
  edición de `present_year` del proyecto en el área de proyecto.
- El panel de hito (cronología H03) gana campo año.

## 7. Vista cronológica (G04)

- **Toggle de vista** en el cluster flotante: ◷ deja de abrir el panel y pasa
  a alternar vista concéntrica ↔ cronológica (el panel H03 queda accesible
  desde "Más opciones"/cronología misma).
- Layout determinista (SIN física — el tiempo no se negocia con muelles;
  `_physics_enabled` se suspende en esta vista igual que el layout manda
  sobre la física en el contrato C01):
  - Eje Y descendente = tiempo (escala por años, comprimible por era).
  - Eras = bandas horizontales (hendiduras alternas, estética F).
  - Entidad = línea de vida vertical (de birth_year a death_year o al
    presente), con su nodo-cabeza (misma hoja blanca con halo) en el
    nacimiento; las muertas terminan con un remate sutil.
  - Hitos = nodos pequeños sobre la línea de vida de su(s) entidad(es) en su
    año, ramificando con conectores orgánicos (las "raíces").
  - X = agrupación por anillo efectivo (las columnas heredan el orden causal
    de la otra vista — el lector no pierde el mapa mental).
- Interacción: click/menús contextuales coherentes con la concéntrica
  (seleccionar hito → panel de hito; entidad → su panel editorial); zoom/pan
  y Space+drag idénticos.
- Persistencia de la vista activa como preferencia.

## 8. Plan de tickets

| Ticket | Alcance | Riesgo |
|---|---|---|
| G01 | Este contrato | — |
| G02 | Dominio+persistencia: Era, campos, defaults en servicios, migración v8, EraService/EraController, tests (`test_beta1_time_domain.py`) | Medio (toca dominio — coordinar con Hermes) |
| G03 | UI temporal: fila de fechas en paneles, sección Eras en filtros, present_year, año en hitos | Bajo |
| G04 | Vista cronológica + toggle + layout determinista + tests (`test_beta1_chrono_view.py`) | Alto (canvas nuevo) |
| G05 | Smoke 2-vistas + cierre (`docs/cierres/G05_time_smoke.md`) | — |

## 9. Riesgos

1. **Colisión con Hermes**: dominio y cronología (H03) son suyos también —
   auditar `git status` antes de G02 y commit quirúrgico.
2. Escala temporal extrema (eras de 10.000 años + vidas de 80): compresión
   logarítmica por era si hace falta — decidir en G04 con datos reales.
3. Hitos multi-entidad: un hito que afecta a N entidades ramifica a N líneas
   de vida — limitar conectores visibles si satura (regla estética F).

## 10. Veredicto G01

**PASS** — contrato completo, decisiones de producto cerradas, plan listo.
G02 no arranca sin confirmación del usuario (toca dominio compartido).
