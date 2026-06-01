# AI Provider pre-B27

## Estado actual

SimulatedAIProvider es el default. Implementado en B15-T02.

## Nuevo: OpenAICompatibleProvider

Provider configurable que funciona con cualquier endpoint OpenAI-compatible.

### Activación

```bash
export NARRATIVE_AI_PROVIDER=openai_compatible
export NARRATIVE_AI_BASE_URL=https://api.openai.com
export NARRATIVE_AI_API_KEY=sk-...
export NARRATIVE_AI_MODEL=gpt-4o-mini
```

Si faltan env vars → fallback automático a SimulatedAIProvider.

### En local sin API

```bash
export NARRATIVE_AI_PROVIDER=simulated
python3 -m narrative_architect ai generate-entity --prompt "test"
```

### Para tests

```python
from packages.infrastructure.openai_compatible_provider import get_provider
provider = get_provider()  # siempre devuelve algo (simulado si no hay config)
```

### No hacer

- No commitear API keys
- No exponer keys en logs
- No hacer llamadas reales en CI

## Qué queda para B27

- Integrar provider en OrchestratorService, WritingService, LiveModeService
- Reemplazar fallback SimulatedAIProvider por OpenAICompatibleProvider cuando haya config
- Validación estructural de outputs IA
- Streaming, herramientas, function calling (B28+)
