# E01 - Contrato RAG narrativo avanzado

## Objetivo

El RAG de Dendro es una capa de recuperacion narrativa integrada en la pipeline
IA existente. No es un buscador aislado y no crea una segunda pipeline.

Regla de producto:

```text
La IA no debe leer todo.
La IA debe recibir el contexto correcto.
```

## Pipeline

La secuencia autoritativa para Fase E es:

```text
UI intent
-> AI request
-> RetrievalPlan
-> RAG retrieval
-> ContextPack
-> sanitizer
-> prompt
-> provider
-> output validation
-> candidate / preview / issue
```

AIJobService sigue siendo el runner principal para command bar y acciones IA.
El RAG se inserta entre planificacion de job y construccion del prompt.
No se permite crear otro runner de IA paralelo.

## Corpus Indexable

El corpus debe poder representar:

- Entidades / hojas: nombre, tipo, resumen, cuerpo, notas permitidas, anillo,
  rama padre, relaciones principales y tags.
- Ramas: nombre, tipo, resumen, cuerpo, miembros, subramas, anillo y relaciones.
- Relaciones: origen, destino, tipo, descripcion, cuerpo/notas, intensidad y
  estado cuando exista.
- Anillos / worldbuilding layers: nombre, descripcion, orden causal, entidades
  contenidas, reglas o notas.
- Hitos / cronologia: titulo, resumen, cuerpo, fecha/posicion temporal, fecha
  exacta si existe, entidades vinculadas, relaciones vinculadas, anillos
  vinculados, entidad principal y consecuencia narrativa.
- Candidates / suggestions: tipo, objetivo, propuesta, estado, origen IA,
  decision de aceptacion/rechazo.
- Issues / coherencia: tipo, severidad, elementos afectados, descripcion,
  estado, origen y decisiones previas.
- Importaciones documentales: segmentos aceptados o en bandeja segun scope,
  fuente, estado de revision y referencias.
- Configuracion creativa: genero, tono, estilo, reglas, promesa al lector,
  estrategia IA y restricciones.

## Reglas De Canon Y Privacidad

- El core de dominio sigue siendo la fuente de verdad.
- El grafo es solo una vista, no el corpus persistente.
- Candidates aceptados pueden recuperarse como canon.
- Candidates pendientes solo se recuperan cuando el `RetrievalPlan` lo pida.
- Candidates rechazados no se recuperan salvo modo debug explicito.
- Importaciones no aceptadas no se recuperan salvo acciones de revision/import.
- Elementos archivados o descartados quedan fuera salvo scope explicito.
- Visibilidad privada/secreta se filtra segun audience. Mientras no exista un
  sistema completo de perfiles activos, se usa el filtro disponible mas cercano
  de `NarrativeContextBuilder`.

## RetrievalPlan

`RetrievalPlan` describe que contexto se necesita antes de recuperar nada.
Campos minimos:

- `intent_type`
- `query`
- `selected_entity_ids`
- `selected_relation_ids`
- `active_layer_ids`
- `include_kinds`
- `strategy`: precision, balanced, breadth, causal o chronological
- `token_budget`
- `timeout_ms`
- `include_pending_candidates`
- `include_rejected_candidates`
- `include_unaccepted_imports`
- `audience`

La planificacion depende de la intencion IA. Ejemplos:

- Generar descripcion: entidad seleccionada, entidades similares, anillo y tono.
- Sugerir relaciones: vecindad, entidades compatibles, ramas cercanas y huecos
  del grafo.
- Analizar coherencia: subgrafo seleccionado, relaciones, hitos causales e
  issues previas.
- Sugerir hito: cronologia, entidades vinculadas e hitos vecinos.
- Explicar causas: hitos, anillos superiores, relaciones causales y contexto
  historico.

## ContextPack

El RAG devuelve `ContextPack`, nunca un string bruto.

Cada `ContextItem` incluye:

- `kind`
- `ref_id`
- `source`
- `score`
- `reason`
- `priority`
- `tokens_estimated`
- `rendered_text`
- `references`
- `warnings`
- `metadata`

El `ContextPack` incluye:

- `plan`
- `items`
- `warnings`
- `tokens_budget`
- `tokens_estimated`
- `truncated`

El prompt final se construye desde `ContextPack` bajo presupuesto de tokens.

## Recuperacion Hibrida

El RAG narrativo combina:

- busqueda semantica;
- keyword/FTS;
- vecindad del grafo;
- relaciones;
- anillos;
- ramas;
- hitos y cronologia;
- candidates;
- issues;
- configuracion creativa;
- importaciones documentales.

Los embeddings son una senal mas, no el sistema completo.

## No Bloqueo

Tickets posteriores deben implementar:

- indexacion en background;
- reindexacion incremental;
- recuperacion con timeout;
- estado visible;
- degradacion limpia.

Degradacion limpia no significa inventar contenido. Si no hay embeddings, el RAG
puede usar keyword/estructura o devolver `ContextPack` vacio con warnings.
La IA no debe recibir un fallback simulado.

## Fuera De Alcance De E01

- Persistir indices.
- Implementar embeddings reales.
- Integrar recuperacion efectiva en `AIJobService`.
- UI de estado RAG.
- Busqueda final para usuario.
