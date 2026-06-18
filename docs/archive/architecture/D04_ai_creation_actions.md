# D04 - Acciones IA minimas en Creacion

Fecha: 2026-06-11
Ticket: BETA1-D04
Estado: listo para revision

## Acciones visibles

Creacion expone ahora las acciones minimas de IA sin mutacion directa de canon:

- `Sugerir hoja con IA`: accion existente de toolbar; crea candidatos revisables
  desde contexto de seleccion o proyecto.
- `Rama IA`: nueva accion visible; lanza job revisable para proponer 1-2 ramas.
- `Rel IA`: nueva accion visible; requiere dos hojas o una relacion seleccionada
  y lanza job revisable para candidatos de relacion.
- `Analizar coherencia`: accion existente; abre `CoherencePanel` para seleccion.
- `Resumen`: nueva accion visible; requiere seleccion y lanza job revisable con
  informe narrativo.
- Paneles de detalle:
  - hoja: generar/mejorar descripcion, coherencia, explicar causas;
  - rama: descripcion, coherencia, explicar causas;
  - relacion: generar/mejorar texto y coherencia.

## Contrato

Las nuevas acciones de toolbar usan `_launch_toolbar_ai_job()`, que crea un
`AIJobService` job con contexto actual, lo ejecuta via `_AIJobWorker` y entrega
resultado revisable. No escriben en canvas ni canon directamente.

Las acciones que dependen de seleccion nacen deshabilitadas y se activan desde
`_on_graph_selection_changed()`.

## Deuda para D05

- Unificar trazabilidad visible de acciones contextuales que aun usan
  `AIContextActionService` directamente.
- Mostrar proveedor/fallback de forma consistente en todos los paneles.

## Validacion

- Tests estaticos D04 de acciones visibles y gating por seleccion.
- Tests B38/D03 de jobs y worker siguen pasando.
