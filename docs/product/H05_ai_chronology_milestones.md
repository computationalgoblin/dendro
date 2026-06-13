# H05 - IA para calendario e hitos

## Contrato

H05 incorpora configuracion manual de cronologia/calendario de proyecto y una
capa IA opcional para proponer calendarios e hitos. La IA nunca modifica canon
directamente: sus resultados entran como candidatos revisables.

No hay fallback de IA. Si no existe proveedor real configurado, el job falla de
forma visible y no genera contenido simulado.

## Superficie de usuario

- Wizard de nuevo proyecto: pagina `Cronologia` con tres opciones: no anadir
  calendario, calendario vago o calendario completo.
- Configuracion de proyecto: panel manual de cronologia.
- Vista H03 de cronologia: panel manual junto al listado de hitos causales.
- Paneles de hoja/rama/relacion: accion `Sugerir hito` dentro de
  `Causas / Hitos`.
- Command bar: ruta principal para pedir calendarios, hitos, ubicaciones
  temporales o ajustes en lenguaje natural.

## Modelo

- La fuente de verdad sigue siendo `Project.project_chronology`.
- Los hitos siguen siendo `CausalMilestone`.
- El grafo no almacena calendarios ni hitos como nodos visuales.
- Las propuestas IA se guardan como `Candidate` con `proposed_data.kind`:
  - `project_chronology_suggestion`
  - `causal_milestone`

## Modos de calendario

- `none`: no hay calendario; los hitos se pueden ordenar manualmente.
- `vague_periods`: periodos amplios por defecto: Antiguedad, Historia reciente
  y Actualidad. No permite fechas exactas.
- `full_calendar`: calendario completo con eras pasadas, duracion en anos por
  era, meses, duracion en dias por mes, dias de semana, fecha actual exacta y
  soporte de fechas exactas en hitos.

## Fechas exactas

En calendarios completos, la configuracion acepta entradas de duracion variable:

- Eras: `Era Imperial: 1200`
- Meses: `Febrero: 28`

La fecha actual del proyecto se guarda como `current_date` con `era`, `year`,
`month` y `day`. Los hitos pueden guardar `metadata.exact_date` con la misma
forma; su `chronology_key` se actualiza con una etiqueta legible.

## Aceptacion

- Aceptar un candidato de calendario llama a `ProjectChronologyService`.
- Aceptar un candidato de hito crea `CausalMilestone` y lo vincula a
  `project_chronology.milestone_ids`.
- Los hitos sugeridos por IA solo se anclan a IDs reales presentes en el scope
  de seleccion; no se aceptan IDs inventados por el modelo.

## Limites

- No se toca `GraphCanvas`, fisica ni layout.
- No hay calendario visual completo.
- No hay selector avanzado de fechas exactas.
- No hay RAG.
