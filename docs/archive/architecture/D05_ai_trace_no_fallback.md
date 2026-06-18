# D05 - Trazabilidad IA sin fallback de contenido

Ticket: BETA1-D05

## Decisiones

- La IA no tiene fallback de producto. Si no hay proveedor real configurado, la
  accion falla de forma controlada con "IA no configurada".
- `SimulatedAIProvider` queda limitado a tests o fixtures que lo habiliten de
  forma explicita.
- Los jobs IA registran observabilidad tanto en exito como en fallo.
- Los candidates generados por jobs IA incluyen metadata trazable: provider,
  model, prompt, job id y estado revisable.

## Rutas cubiertas

- `AIJobService`: bloquea `simulated` por defecto, registra error
  `provider_unconfigured` y no genera candidates.
- `AIContextActionService`: bloquea `simulated` por defecto en acciones de nodo,
  relacion, seleccion y grafo.
- Tests pueden usar `allow_simulated=True` cuando necesitan fixtures
  deterministas heredadas.

## Riesgos controlados

- La creacion manual sigue funcionando sin proveedor IA.
- Los errores se devuelven como `Error`, sin tracebacks visibles.
- No se almacenan prompts completos en observabilidad salvo modo debug del log.
