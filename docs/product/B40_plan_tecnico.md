# B40 — Configuración creativa del proyecto y wizard inicial

**Fecha:** 2026-06-05
**Estado:** Plan técnico (T01)
**Dependencias:** B33-B39 cerrados, B39 ontología Hoja/Rama/Anillo

## Estado actual

### Campos creativos que YA EXISTEN

| Ubicación | Campo | Estado |
|-----------|-------|--------|
| `Project.name` | Título | OK |
| `Project.description` | Descripción | OK |
| `Project.project_type` | Formato (campana/novela/otro) | Limitado, ampliar |
| `Project.primary_language` | Idioma principal | OK |
| `Project.worldbuilding_active` | Worldbuilding ON | OK |
| `Project.creative_config` | narrative_style, main_themes, target_audience, creative_rules | Base para expandir |
| `Project.genre` (GenreConfig) | primary_genre, secondary_genres, subgenres, genre_mix_notes | OK, ya tiene listas |
| `Project.tone` (ToneConfig) | narrative_tone, language_formality, humor_level, dark_tone_level | Limitado |
| `Project.realism` (RealismConfig) | realism_level, magic_level, technology_level, fantasy_scale | OK |
| `Project.ai` (AIConfig) | enabled, model_preference, creativity_level | Muy simple |
| `Project.advanced_config` | primary_genre, subgenres, global_tone, contradiction_tolerance, naming_conventions, etc. | Ya tiene campos útiles |
| `NovelaConfig` | format, point_of_view, tense, target_length, narrative_structure | Solo para novela |

### Panel actual (settings_panels.py → ProjectPanel)

Secciones: File management, Project Type, Worldbuilding, Creative Config (4 campos texto), Genre/Tone/Realism (3 combos), Campaign Config (solo si campana), Novela Config (solo si novela).

### Flujo creación actual

1. `MainWindow._new_project()` → dialog texto pide nombre
2. `QFileDialog` pide ruta
3. `ProjectService.create(name)` → Project vacío con defaults
4. Sin wizard, sin género, sin preset

### IA usa config en

- `NarrativeContextBuilder._base_context()` — incluye tone, genre, realism, creative_config
- `ai_context_actions.py` — `_authorized_context()` extrae tone, genre, realism, constraints
- `ai_jobs.py` — system prompt menciona género/tono/realismo/estilo pero no inyecta valores dinámicamente
- `COMMAND_BAR_SYSTEM_PROMPT_ES` — instruye respetar config pero no la enumera

### Persistencia

- Schema v21, migraciones aditivas v1→v21
- `Project.to_dict()` / `Project.from_dict()` serializan todo
- No hay presets de ningún tipo

## Decisiones de diseño

### D1: No crear modelo paralelo

`Project` ya tiene `creative_config` (CreativeProjectConfig), `genre`, `tone`, `realism`, `ai`, `advanced_config`.
En vez de crear un nuevo `CreativeConfig` paralelo, **expandir los existentes**:

- `CreativeProjectConfig` → añadir campos de dirección creativa, motor narrativo, poética, reglas, evitar, memoria
- `AIConfig` → añadir rol, agresividad, output_mode, uncertainty_policy, estrategia
- `ToneConfig` → ampliar con distancia narrativa, densidad, subtexto
- Usar `advanced_config` para lo que ya tiene (contradiction_tolerance, naming_conventions, etc.)

### D2: Estructura nested dentro de CreativeProjectConfig

Añadir sub-objetos dict/dataclass dentro de `CreativeProjectConfig`:

```
CreativeProjectConfig
├── narrative_style          # ya existe
├── main_themes              # ya existe
├── target_audience          # ya existe
├── creative_rules           # ya existe
├── core_premise             # NUEVO
├── short_summary            # NUEVO
├── development_status       # NUEVO
├── creative_intent          # NUEVO: {reader_promise, central_question, desired_emotions, aftertaste, originality, ambiguity, impact_types}
├── narrative_engine         # NUEVO: {conflict_sources, dominant_tension, progression_mechanism, character_change, escalation, character_agency, causality}
├── poetics                  # NUEVO: {narrative_distance, description_density, conceptual_density, subtext_level, dialogue_styles, exposition_modes, recurring_imagery, forbidden_style_habits}
├── canon                    # NUEVO: {hard_rules, soft_preferences, continuity_strictness, contradiction_policy, world_rules, character_rules, timeline_rules}
├── negative_space           # NUEVO: {avoid_tropes, avoid_solutions, avoid_style_habits, avoid_tones, avoid_phrases}
├── taste_memory             # NUEVO: {accepted_patterns, rejected_patterns, user_style_notes, learned_decisions, pending_suggestions}
├── presets_applied          # NUEVO: lista de presets usados
```

### D3: AIConfig expandido

```
AIConfig
├── enabled                  # ya existe
├── model_preference         # ya existe
├── creativity_level         # ya existe (0-10)
├── default_role             # NUEVO: coauthor/editor/dramaturgo/supervisor/worldbuilder/etc
├── change_aggressiveness    # NUEVO: 0-10
├── default_num_options      # NUEVO: 1-5
├── output_mode              # NUEVO: single/contrastive/diagnosis/questions/minimal/structured
├── uncertainty_policy       # NUEVO: ask/conservative/invent/mark_gaps/interpretations
├── default_strategy         # NUEVO: profundizar/contrastar/complicar/etc
├── context_depth            # NUEVO: quick/balanced/deep
```

### D4: BranchConfig como campo en custom_metadata

No crear modelo paralelo. Las ramas ya tienen `custom_metadata` (dict).
Añadir helper `BranchConfig` que lee/escribe desde `entity.custom_metadata["branch_config"]`:

```
BranchConfig (en custom_metadata)
├── inherits_from_project    # true por defecto
├── local_narrative_function # string
├── local_motifs             # list[str]
├── local_tone_override      # string
├── local_ai_role            # string
├── local_rules              # list[str]
├── overrides                # dict de campos sobrescritos
```

Resolver config efectiva: helper `resolve_effective_config(project, entity)` que devuelve config merged.

### D5: Presets como dict estático + archivo JSON

`packages/domain/creative_presets.py` con 10 presets predefinidos.
Cada preset es un dict parcial que se mergea en creative_config al aplicar.

### D6: Wizard como QDialog con QStackedWidget

Pasos: Identidad → Dirección → Motor → Estilo → Reglas → IA → Evitar → Resumen.
8 pasos. Cada paso = un QWidget. Botones IA en cada paso usan AIJobService si hay provider, si no botón deshabilitado.

### D7: Migración v21 → v22

Aditiva. Campos nuevos con defaults. Proyectos viejos abren sin error.
Si `creative_config` no tiene sub-objetos nuevos, se crean vacíos con defaults.

## Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `packages/domain/project.py` | Expandir CreativeProjectConfig con nuevos campos |
| `packages/domain/project_config.py` | Expandir AIConfig, ToneConfig |
| `packages/domain/creative_presets.py` | NUEVO — 10 presets |
| `packages/domain/branch_config.py` | NUEVO — helper para overrides de rama |
| `packages/application/project_service.py` | `create()` acepta config dict + preset |
| `packages/application/creative_config_service.py` | NUEVO — CRUD de config + presets + herencia |
| `packages/application/narrative_context_builder.py` | Incluir config expandida |
| `packages/application/ai_context_actions.py` | Incluir canon duro, evitar, memoria |
| `packages/application/ai_jobs.py` | System prompt usa config expandida |
| `packages/persistence/schema.py` | Migración v21→v22 |
| `hosts/DesktopHostPySide/widgets/settings_panels.py` | Reescribir ProjectPanel con submenús |
| `hosts/DesktopHostPySide/widgets/creative_config_panel.py` | NUEVO — panel con tabs/acordeones |
| `hosts/DesktopHostPySide/widgets/config_wizard.py` | NUEVO — wizard 8 pasos |
| `hosts/DesktopHostPySide/widgets/preset_selector.py` | NUEVO — selector de presets |
| `hosts/DesktopHostPySide/main_window.py` | `_new_project()` lanza wizard |
| `tests/application/test_b40_creative_config.py` | NUEVO — tests config |
| `tests/desktop/test_b40_wizard.py` | NUEVO — tests wizard |
| `scripts/run_all_tests.py` | Añadir suite b40 |

## Orden de implementación

```
Fase 1 — Modelo y persistencia (T02)
  1. Expandir CreativeProjectConfig, AIConfig, ToneConfig
  2. Crear creative_presets.py
  3. Crear branch_config.py helper
  4. Migración v21→v22
  5. Tests unitarios de modelo

Fase 2 — Panel de configuración (T03)
  6. CreativeConfigPanel con 9 tabs
  7. Componentes reutilizables (TagInput, SliderField, RuleListEditor)
  8. Integración con ProjectPanel existente
  9. Tests UI estáticos

Fase 3 — Wizard (T04)
  10. ConfigWizard dialog 8 pasos
  11. Integración en MainWindow._new_project()
  12. Presets como opción en wizard
  13. Tests wizard

Fase 4 — Integración IA (T05)
  14. CreativeConfigService
  15. NarrativeContextBuilder ampliado
  16. AIContextActions ampliado
  17. System prompt ampliado
  18. Tests de integración IA

Fase 5 — Overrides de rama (T06)
  19. BranchConfig helper
  20. UI de overrides en tree_detail_panel
  21. resolve_effective_config
  22. Tests de herencia

Fase 6 — Smoke y cierre (T07)
  23. Smoke completo
  24. Validaciones
  25. Cierre documentado
```

## Riesgos

| Riesgo | Mitigación |
|--------|-----------|
| Proyectos viejos no abren | Migración aditiva con defaults seguros |
| Panel demasiado largo | Tabs + acordeones + campos colapsables |
| Wizard pesado | Cada paso es opcional, skip permitido |
| IA sin provider | Botones IA deshabilitados, no mock silencioso |
| Overrides de rama complejos | MVP: solo config global + overrides simples |
| Rotura B33-B38 | Tests de regresión en cada fase |

## No incluye

- Galería
- Sesión/campaña (salvo lo ya existente)
- Embeddings/cache avanzado
- Importación documental
- Rediseño completo del graph layout
