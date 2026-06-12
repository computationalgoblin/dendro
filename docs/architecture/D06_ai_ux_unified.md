# D06 - UX IA unificada

Ticket: BETA1-D06

## Decisiones

- La command bar es la entrada principal de IA global.
- Los paneles de hoja, rama y relacion muestran una sola entrada IA: prompt +
  consultar.
- Las acciones IA estructurales sobre seleccion viven en el menu secundario del
  grafo, no en la toolbar.
- El menu secundario conserva multiseleccion si el usuario hace click derecho
  sobre un elemento ya seleccionado.
- La toolbar oculta botones IA redundantes para evitar caminos paralelos.

## Acciones contextuales

- Sugerir hojas.
- Sugerir ramas.
- Sugerir relaciones.
- Analizar coherencia.

Todas se enrutan como jobs IA revisables mediante el mismo pipeline de command
bar. No mutan canon directamente.

## Resultado editable

Los paneles mantienen la sugerencia en un area editable. Hoja y relacion
permiten refinado por prompt sobre seleccion de texto; rama mantiene prompt
unico para regenerar el resultado desde el contexto de la rama.
