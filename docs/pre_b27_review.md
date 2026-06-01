# Revisión pre-B27

**Fecha:** 2026-05-31

## Estado general

| Métrica | Valor |
|---------|-------|
| Bloques completados | 26/30 (87%) |
| Schema | v18 |
| Tests non-UI | 1117 passed |
| Arquitectura | 9/9 |
| Working tree | clean |
| Último commit | `3075225` |

## Arquitectura real

| Capa | Módulos |
|------|---------|
| domain | entity, relation, candidate_issue, ai_models, analysis_models, import_models, temporal_models, writing_models, campaign_models, secrets_models, faction_models, session_models |
| application | project_service, entity_service, relation_service, candidate_service, issue_service, history_service, orchestrator_service, analysis_service, import_service, timeline_service, writing_service, campaign_service, secrets_service, faction_service, session_service, live_mode_service, post_session_service, export_service |
| persistence | schema, store (v18) |
| ui | cli + 14 specialized modules |
| infrastructure | ai_provider (simulated), openai_compatible_provider, text_extractor |

## Contratos críticos consolidados

- Candidate antes que canon (B14)
- IA no muta canon directamente (B15)
- visibility/audience filters (B26)
- Session.metadata["live"] → post-session (B24→B25)
- PostSessionService idempotente (B25)
- HistoryService centralizado (B25)
- ExportService gm/player/public (B26)
- Provisional entities: borrador por defecto, force_canon explícito (B24)

## Deuda abierta tras B26

| ID | Descripción | Gravedad | Destino |
|----|-------------|----------|---------|
| DC-001..DC-024 | Sin evidencia documental | ambigua | — |
| DC-033 | get_ordered_events sin partial_order real | baja | B29 |
| DC-034 | TimelineEvent sync con NarrativeEntity(EVENTO) | baja | B29 |
| DC-035 | IA writing provider real | baja | B27 |
| DC-036 | get_tree no escala >1000 | baja | B29 |
| DC-040 | CLI flakes secrets/clues (5) | baja | hardening |
| DC-044 | improvise fallback determinista | baja | B27 |
| DC-045 | AnalysisService tests | media | B29 |

## Riesgos antes de B27

- Provider IA real puede saltarse filtros de contexto
- Export public/player debe filtrar correctamente
- Candidates IA deben ser revisables
- CLI flakes pueden confundir pruebas visuales

## Provider IA pre-B27

- OpenAICompatibleProvider implementado
- Fallback automático a SimulatedAIProvider
- Activación por env vars (no API keys en repo)
- Ver `docs/ai_provider_pre_b27.md`

## Validaciones base

```
1117 passed in 10.57s (domain + persistence + application + architecture)
9/9 arquitectura
ruff: not installed in env
```
