# D03 - Pipeline no bloqueante de jobs IA

Fecha: 2026-06-11
Ticket: BETA1-D03
Estado: listo para revision

## Objetivo

Garantizar que la command bar de IA trabaja como job revisable en background y
que el servicio de jobs expone estados seguros para la UI.

## Estado tras D03

- `CreationWorkspace` ya ejecuta jobs de command bar mediante `_AIJobWorker`
  (`QThread`), por lo que la llamada al provider no ocurre en el thread UI.
- `AIJobService` mantiene el estado de fases:
  - `building_context`
  - `planning`
  - `waiting_for_model` con mensaje visible `Pensando...`
  - `postprocessing`
  - `ready_for_review`, `failed` o `cancelled`
- `AIJobService` acepta `timeout_seconds`, por defecto 300s.
- El timeout se pasa explicitamente a `provider.chat(...)`.
- Si el provider supera el timeout medido por el runner, el job pasa a `failed`
  con error seguro.
- `cancel_job()` se respeta de forma cooperativa entre fases y antes/despues de
  la llamada al provider.
- El resultado sigue siendo revisable: report/candidates, nunca canon directo.

## Limites conocidos

La cancelacion no puede abortar a la fuerza una llamada HTTP ya iniciada si el
provider ignora el timeout. El contrato D03 garantiza que:

- se pasa timeout al provider;
- el job no se marca como listo si fue cancelado durante la espera;
- al volver del provider se respeta el estado `cancelled`.

D05 debera conectar observabilidad; D04 conectara acciones IA concretas sobre
este runner.

## Validacion

- Tests D03 de timeout, fase `Pensando...`, cancelacion cooperativa y timeout
  pasado al provider.
- Tests B38/B42/D02 siguen pasando.
