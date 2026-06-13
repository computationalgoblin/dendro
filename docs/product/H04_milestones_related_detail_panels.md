# H04 - Hitos relacionados en paneles de detalle

## Decision UX

La cronologia no entra en el grafo. El grafo muestra estructura actual, H03
muestra evolucion temporal y los paneles de detalle muestran los hitos que
explican el elemento seleccionado.

La seccion se llama `Causas / Hitos` porque comunica funcion narrativa sin
exponer conceptos tecnicos.

## Hoja

El panel de hoja muestra hitos donde:

- la hoja aparece en `affected_entity_ids`;
- la hoja es la entidad principal en `metadata.primary_entity_id`.

Cada hito aparece como tarjeta compacta con titulo, posicion temporal, resumen,
estado humano, chip de entidad principal y swatch de color.

## Rama

El panel de rama usa la misma seccion `Causas / Hitos`. Muestra hitos vinculados
por `affected_branch_ids`, por `affected_entity_ids` cuando la rama tambien se
representa como entidad contenedora, o por entidad principal.

## Relacion

El panel de relacion muestra hitos vinculados mediante `caused_relation_ids`.
Si se crea un hito desde una relacion, se pre-rellena tambien con las entidades
origen y destino cuando la relacion esta disponible.

## Acciones

- `Ver en cronologia`: abre H03 filtrada por hoja/rama o por relacion.
- `Abrir`: abre H03 con el hito seleccionado.
- `Crear hito vinculado`: aparece solo si existe `create_manual` en el
  controlador de hitos.

Todas las mutaciones pasan por `CausalMilestoneController`. La UI no escribe en
persistencia ni modifica canon fuera de esa ruta.

## Campos visibles

Modo normal muestra solo texto editorial:

- titulo;
- resumen;
- fecha/posicion temporal;
- entidad principal;
- chips de entidades vinculadas;
- estado humano;
- color derivado de entidad principal.

No se muestran IDs, JSON, source IDs ni metadata cruda.

## Limites

- La edicion avanzada de vinculos queda fuera de H04 porque no hay servicio
  dedicado para anadir/quitar vinculos de forma granular.
- H03 ya soporta filtro inicial por relacion para esta integracion, pero no
  expone todavia un selector visual permanente de relaciones.
- Los hitos siguen fuera de `GraphCanvas`.
