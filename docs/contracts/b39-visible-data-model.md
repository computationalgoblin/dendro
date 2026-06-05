# B39 — Modelo de Datos Visible (Hoja / Rama / Anillo)

> **Contrato de terminología UX-B39**
> Versión: 1.0 · Rama: `b39-terminology` · Estado:borrador
> Última actualización: 2026-06-05

---

## 1. Resumen

A partir de **B39** la interfaz de usuario de Dendro / Narrative Architect abandona los
términos genéricos *Entity / Container / Layer* y adopta un vocabulario arbóreo
en español:

| Término UX B39 | Concepto previo | Interno (sin cambios)        |
|----------------|-----------------|------------------------------|
| **Hoja**       | Entity          | `NarrativeEntity`            |
| **Rama**       | Container / Tree| `NarrativeEntity` (CONTENEDOR) / `TreeMeta` |
| **Anillo**     | Layer           | `WorldLayer`                 |

La capa de persistencia **no se modifica**. Este documento describe qué ve el
usuario, qué se oculta y cómo se mapean los conceptos.

---

## 2. Hoja (Leaf)

### 2.1 Definición

Una **Hoja** es la representación UX de toda entidad individual, única y atómica
que **no** es un agrupador. Internamente corresponde a un `NarrativeEntity` cuyo
`entity_type` **no** pertenece al conjunto `BRANCH_TYPES`.

> `BRANCH_TYPES = { FACCION, CULTURA, SISTEMA_MAGICO, RELIGION, INSTITUCION, TRAMA, CONTENEDOR }`

### 2.2 Cuándo usar Hoja

| Es Hoja ✓                         | NO es Hoja ✗                      |
|------------------------------------|------------------------------------|
| personaje                          | facción                            |
| objeto singular                    | cultura                            |
| lugar singular                     | religión                           |
| concepto único                     | institución                        |
| evento puntual                     | sistema mágico                     |
| ley individual                     | trama                              |
| criatura concreta                  | contenedor genérico                |

### 2.3 Campos visibles

| Campo UX            | Fuente interna                              | Notas                              |
|---------------------|---------------------------------------------|------------------------------------|
| nombre              | `name`                                      |                                    |
| tipo                | `entity_type` (etiqueta localizada)         |                                    |
| color               | `color`                                     |                                    |
| descripción breve   | `short_description` / `summary`             |                                    |
| cuerpo              | `body` / `content`                          | texto largo                        |
| anillo / capa       | `world_layer_id` → `WorldLayer.name`        | solo si worldbuilding ON           |
| rama padre          | parent `NarrativeEntity` (CONTENEDOR)       | pertenencia jerárquica             |
| relaciones          | `NarrativeRelation[]` salientes/entrantes   |                                    |
| IA / coherencia     | AI coherence summary                        |                                    |
| acción              | **«convertir en rama»**                     | cambia `entity_type` a CONTENEDOR  |

### 2.4 Campos ocultos (internos, no mostrados en UI)

`id`, representación JSON en bruto, `metadata`, `notes`, `visibility`,
`source_ids`, `created_at`, `updated_at`, `custom_fields`.

---

## 3. Rama (Branch)

### 3.1 Definición

Una **Rama** es la representación UX de todo agrupador, sistema, colectivo o
estructura de árbol. Internamente corresponde a:

- Un `NarrativeEntity` con `entity_type` en `BRANCH_TYPES`, **o**
- Un `TreeMeta` (meta-nodo raíz de un árbol).

### 3.2 Cuándo usar Rama

Ejemplos: facción, cultura, religión, institución, país / reino, región compleja,
sistema mágico, trama, organización.

### 3.3 Campos visibles

| Campo UX            | Fuente interna                              | Notas                              |
|---------------------|---------------------------------------------|------------------------------------|
| nombre              | `name`                                      |                                    |
| tipo                | `entity_type` (etiqueta localizada)         |                                    |
| color               | `color`                                     |                                    |
| descripción breve   | `short_description` / `summary`             |                                    |
| cuerpo              | `body` / `content`                          | texto largo                        |
| anillo / capa       | `world_layer_id` → `WorldLayer.name`        |                                    |
| hojas contenidas    | hijos `NarrativeEntity` (no CONTENEDOR)     | lista / contador                   |
| ramas contenidas    | hijos `NarrativeEntity` (CONTENEDOR)        | lista / contador                   |
| relaciones          | `NarrativeRelation[]`                       |                                    |
| reglas internas     | `rules` / `internal_constraints`            |                                    |
| preguntas abiertas  | `open_questions`                            |                                    |
| IA / coherencia     | AI coherence summary                        |                                    |
| acción              | **«crear anillo desde rama»**               | promueve la rama a `WorldLayer`    |

### 3.4 Campos ocultos

`id`, JSON en bruto, `metadata`, `visibility`, `created_at`, `updated_at`.

---

## 4. Anillo (Ring)

### 4.1 Definición

Un **Anillo** es la representación UX de un estrato causal del mundo
(`WorldLayer`). No es una hoja ni una rama por defecto; es una dimensión
ortogonal que agrinda contenido por capa de realidad / causalidad.

### 4.2 Campos visibles

| Campo UX                        | Fuente interna              | Notas                     |
|---------------------------------|-----------------------------|---------------------------|
| nombre                          | `name`                      |                           |
| orden causal                    | `causal_order`              | posición en la pila       |
| descripción                     | `description`               |                           |
| contador de hojas               | conteo de `NarrativeEntity` | filtrado por `world_layer_id` |
| contador de ramas               | conteo de ramas en la capa  |                           |
| contador de relaciones          | conteo de `NarrativeRelation` |                         |
| acciones: activar / enfocar / filtrar | botones de UI         |                           |

### 4.3 Campos ocultos

`id`, `is_visible`, `is_default`, `metadata` (dict).

---

## 5. Relación (Relationship)

### 5.1 Definición

Vínculo dirigido entre una hoja, rama y/o anillo. Internamente es un
`NarrativeRelation`.

### 5.2 Campos visibles

| Campo UX          | Fuente interna        | Notas                     |
|-------------------|-----------------------|---------------------------|
| origen            | `source_entity_id` → nombre |                        |
| destino           | `target_entity_id` → nombre |                        |
| tipo              | `relation_type` (etiqueta) |                         |
| dirección         | `direction`           |                           |
| color             | `color`               |                           |
| descripción breve | `short_description`   |                           |
| cuerpo            | `body` / `content`    | texto largo               |
| anillo / capa     | `world_layer_id`      |                           |
| IA / coherencia   | AI coherence summary  |                           |

### 5.3 Campos ocultos

`id`, `intensity`, `temporality`, `causality`, `canon_state`,
`visibility_state`, `certainty`, `source`, `created_at`, `updated_at`,
`validity_conditions`, `tags`, `custom_metadata`, `custom_fields`.

---

## 6. Candidato (Candidate)

### 6.1 Definición

Un **Candidato** es una propuesta revisable que **nunca** se convierte
automáticamente en canon. El usuario debe aceptarla explícitamente.

### 6.2 Tipos de candidato

| Tipo UX             | Descripción                                  |
|---------------------|----------------------------------------------|
| hoja candidata      | propuesta de nueva hoja                      |
| rama candidata      | propuesta de nueva rama                      |
| relación candidata  | propuesta de nueva relación                  |
| anillo sugerido     | propuesta de nuevo anillo                    |
| informe             | informe generado por IA, pendiente de revisión |
| pregunta abierta    | pregunta sin resolver, derivada de análisis  |

---

## 7. Compatibilidad (Backward Compatibility)

### 7.1 Principios

1. **El esquema de persistencia no cambia en B39.**
   `NarrativeEntity`, `EntityType.CONTENEDOR`, `WorldLayer` y
   `NarrativeRelation` siguen existiendo tal cual en la base de datos y en la
   API interna.

2. **Los valores del enum `EntityType` se mantienen idénticos internamente.**
   Solo cambian las etiquetas que se muestran en la UI.

3. **Proyectos creados antes de B39 son plenamente compatibles.**
   La migración es puramente cosmética: al abrir un proyecto existente, las
   entidades se muestran automáticamente como hojas o ramas según su
   `entity_type`.

4. **Los endpoints API y los modelos Pydantic conservan los nombres internos.**
   La traducción Hoja/Rama/Anillo ocurre exclusivamente en la capa de
   presentación (UI / frontend).

### 7.2 Tabla de mapeo

| Concepto UX | Tipo interno                    | Cuando                                          |
|-------------|---------------------------------|-------------------------------------------------|
| Hoja        | `NarrativeEntity`               | `entity_type not in BRANCH_TYPES`               |
| Rama        | `NarrativeEntity` o `TreeMeta`  | `entity_type in BRANCH_TYPES` o `entity_type == CONTENEDOR` |
| Anillo      | `WorldLayer`                    | `always`                                        |

Donde:

```
BRANCH_TYPES = {
    FACCION,
    CULTURA,
    SISTEMA_MAGICO,
    RELIGION,
    INSTITUCION,
    TRAMA,
    CONTENEDOR,
}
```

### 7.3 Flujo de decisión (pseudocódigo)

```python
def ux_label(entity: NarrativeEntity) -> str:
    if entity.entity_type in BRANCH_TYPES:
        return "Rama"
    return "Hoja"

def ux_label_layer(layer: WorldLayer) -> str:
    return "Anillo"
```

---

## 8. Notas de implementación

- **Frontend:** reemplazar todas las ocurrencias de "Entity" → "Hoja",
  "Container" → "Rama", "Layer" → "Anillo" en etiquetas, tooltips y textos
  visibles. Mantener los nombres internos en `data-model`, `props` y llamadas API.
- **Backend:** sin cambios en modelos, schemas ni endpoints. Solo añadir
  helpers de mapeo si se desea exponer etiquetas UX localizadas.
- **Tests:** actualizar assertions de UI/texto visible; los tests de integración
  sobre la API interna no requieren cambios.

---

## 9. Historial

| Fecha       | Autor | Cambio                        |
|-------------|-------|-------------------------------|
| 2026-06-05  | —     | Creación del contrato B39     |
