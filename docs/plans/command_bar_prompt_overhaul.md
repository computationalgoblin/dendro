# PLAN: Reestructuración del prompt de la command bar — cono de autoridad + presupuesto configurable

## Objetivo

Reordenar cómo se construye el mensaje que recibe la IA en la command bar (y,
por extensión, menú contextual y panel de detalle, que comparten pipeline).

Dos bloques de trabajo integrados:

1. **Cono de autoridad** — jerarquía de pesos: DIRIGE > RESTRINGE > INFORMA > ATMÓSFERA.
   Introduce vecindario con decaimiento por distancia, menciones con contenido
   (mini-ficha) y separa el cerco (canon duro + causal) de la atmósfera (género/tono).

2. **Presupuesto de tokens configurable** — el usuario decide el máximo de tokens
   de contexto por tarea o por proyecto; internamente se reparte porcentualmente
   entre las secciones del cono. Cualquier sección que exceda su porcentaje se
   trunca. El prompt del usuario es sagrado: jamás se trunca.

## Mejoras incluidas

```
CÓDIGO  QUÉ                                              FASE
──────────────────────────────────────────────────────────────
M2      Desduplicar creative_brief (split cerco/atmósfera)  4
M3      Eliminar triple repetición "no canon automático"    4
M4      Quitar intent/plan del user message                 4
M6      Resolver duplicación raw_prompt (menú/panel)         7
M7      Presupuesto configurable + reparto porcentual        2
CONO    Vecindario en command bar con decaimiento            1+3+6
CONO    Menciones @ con mini-ficha                           4+6
CONO    Separar cerco (canon duro) de atmósfera              4
```

QUITADAS por decisión del usuario: M1 (whitelist por intent), M5 (few-shot), M8 (compresión inteligente).

## Alcance (10 archivos)

```
NUEVO  packages/application/neighborhood.py              (~100 líneas)
NUEVO  packages/application/prompt_budget.py             (~120 líneas)
EDIT   packages/domain/project_config.py                 (AIConfig +1 campo)
EDIT   packages/application/narrative_context_builder.py (+1 método)
EDIT   packages/application/ai_jobs.py                   (4 helpers + rebuild mensaje)
EDIT   packages/application/command_prompts.py           (M3 cleanup)
EDIT   packages/application/ai_context_actions.py        (M6)
EDIT   hosts/DesktopHostPySide/views/workspaces.py       (vecindario + menciones + tuner)
NUEVO  tests/test_neighborhood.py
NUEVO  tests/test_prompt_budget.py
NUEVO  tests/test_command_bar_prompt_shape.py
```

NO tocar: rag_context.py, prompt_registry.py, ai_request_gateway.py, command_expansion.py, ni widgets.

---

## FASE 1 — neighborhood.py (NUEVO, capa pura)

Sin acceso a proyecto ni Qt. Solo dataclasses y scoring.

```python
DECAY_BY_HOP = {0: 1.0, 1: 1.0, 2: 0.4, 3: 0.1}

def decay_weight(hop: int) -> float:
    """hop 0 = seleccionada; 1 = vecino directo; 2 = 2 saltos; 3 = casi nada.
    Devuelve 0.0 para hop >= 4 (fuera del pack)."""

@dataclass(frozen=True)
class NeighborhoodItem:
    entity_id: str
    name: str
    entity_type: str
    display_type: str
    hop: int
    weight: float
    layer_ids: list[str]
    def to_dict(self) -> dict

@dataclass(frozen=True)
class NeighborhoodRelation:
    relation_id: str
    source_id: str
    target_id: str
    relation_type: str
    hop: int               # hop del extremo MÁS LEJANO de la selección
    weight: float
    def to_dict(self) -> dict

@dataclass(frozen=True)
class NeighborhoodPack:
    items: list[NeighborhoodItem]
    relations: list[NeighborhoodRelation]
    max_hops: int
    warnings: list[str]
    def to_dict(self) -> dict
```

Contrato estricto:
- decay_weight(0)==1.0, (1)==1.0, (2)==0.4, (3)==0.1, (4)==0.0.
- Las entidades semilla (hop 0) NO aparecen en `items` (ya van en selección);
  solo sus vecinos. Pero las relaciones que tocan semillas cuentan como hop 1.

## FASE 2 — prompt_budget.py (NUEVO, presupuesto configurable)

El usuario fija un total de tokens de contexto. El sistema lo reparte
porcentualmente entre las secciones del cono. Lo que excede se trunca.

```python
# Default si ni el tuner ni el proyecto lo fijan.
DEFAULT_PROMPT_BUDGET_TOKENS = 4000

# Reparto porcentual del cono de autoridad.
# Sobre el total disponible (excluye el prompt del usuario, que es sagrado).
SECTION_PERCENTAGES: dict[str, float] = {
    # --- DIRIGE (8%) ---
    "directivas":           0.04,
    "menciones":            0.04,
    # --- RESTRINGE (27%) ---
    "cerco_canon":          0.14,
    "posicion_causal":      0.13,
    # --- INFORMA (35%) ---
    "seleccion":            0.15,
    "vecindario":           0.20,
    # --- ATMÓSFERA (10%) ---
    "parametros_permanentes": 0.10,
    # --- RESIDUAL (20%) ---
    "contexto_autorizado":  0.20,
}
# Suma = 1.00

# Secciones cuyo contenido es sagrado (nunca se trunca).
SACRED_SECTIONS = frozenset({"prompt_exacto_usuario", "formatos_h05"})


def tokens_to_chars(tokens: int) -> int:
    """Aproximación: 1 token ≈ 3.5 chars en español."""
    return int(tokens * 3.5)


def truncate_to_chars(text: str, max_chars: int) -> str:
    """Trunca respetando límite de palabra. Añade '…' si cortó.
    Simple (sin M8): busca el último espacio antes del límite."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"


def enforce_budget(message: dict, total_budget_tokens: int) -> dict:
    """Aplica SECTION_PERCENTAGES al total y trunca cada sección.

    1. Calcula chars disponibles por sección = tokens_to_chars(total * percentage).
    2. Las secciones en SACRED_SECTIONS se dejan intactas.
    3. Las secciones string → truncate_to_chars.
    4. Las secciones list/dict → json.dumps + truncate_to_chars + json.loads
       (si el JSON truncado no parsea, se queda como string truncado).
    5. Las secciones None/vacías → se omiten del resultado.
    6. No muta la entrada; devuelve una copia."""
```

Notas:
- El presupuesto controla SOLO el contexto construido por la app.
  El RAG mantiene su propio token_budget independiente (1800-3200 por estrategia).
- `truncate_to_chars` es deliberadamente simple (sin M8): corte en palabra + "…".
- Si una sección no existe en el mensaje, simplemente no se procesa.

## FASE 3 — project_config.py (EDIT, +1 campo)

Añadir a `AIConfig` (línea 107) un campo con default retrocompatible:

```python
@dataclass
class AIConfig:
    # ... campos existentes ...
    context_depth: str = "balanced"
    # Presupuesto de tokens de contexto para los prompts de la command bar.
    # El usuario lo override por tarea con el tuner; este es el default del proyecto.
    prompt_budget_tokens: int = 4000
```

Como es un dataclass con default y los proyectos existentes se cargan vía
`from_dict` con `.get()`, los proyectos antiguos sin este campo reciben 4000
automáticamente. No hay migración.

## FASE 4 — ai_jobs.py (EDIT, la parte central)

### 4a. Quitar duplicados de contexto_autorizado (M2)

Reemplazar el passthrough `_context_for_prompt` actual. NO es whitelist por
intent (M1, quitado): es exclusión global de las claves que YA tienen su
sección propia en el mensaje:

```python
# Claves que ya viajan procesadas en otras secciones del mensaje.
# Se excluyen SIEMPRE de contexto_autorizado para evitar duplicación.
_DUPLICATED_CONTEXT_KEYS = frozenset({
    "creative_brief",           # → cerco_canon + parametros_permanentes
    "creative_context",         # → parametros_permanentes
    "branch_creative_context",  # → parametros_permanentes
    "contexto_causal",          # → posicion_causal
    "vecindario",               # → vecindario
})

def _context_for_prompt(context: dict) -> dict:
    """Devuelve el context_scope SIN las claves que ya tienen su sección propia."""
    return {
        k: v for k, v in (context or {}).items()
        if k not in _DUPLICATED_CONTEXT_KEYS
    }
```

### 4b. Partir perfil_creativo_b40 en cerco + atmósfera (M2 + CONO)

```python
def _cerco_canon(context: dict) -> dict:
    """RESTRINGE. Canon duro + negative_space. Peso ALTO."""
    brief = context.get("creative_brief") or {}
    canon = brief.get("canon") or {}
    return {
        "hard_rules": canon.get("hard_rules", []),
        "continuity_strictness": canon.get("continuity_strictness", 5),
        "negative_space": brief.get("negative_space") or {},
        "instruccion": (
            "Canon duro: no lo contradigas. Si la petición choca, "
            "devuélvelo como issue/proposal, no lo corrijas."
        ),
    }

def _parametros_permanentes(context: dict) -> dict:
    """ATMÓSFERA. Género/tono/realismo/estilo/idioma. Peso medio."""
    brief = context.get("creative_brief") or {}
    identity = brief.get("identity") or {}
    return {
        "idioma": brief.get("primary_language", "es"),
        "genero": brief.get("genre") or {},
        "tono": brief.get("tone") or {},
        "realismo": brief.get("realism") or {},
        "estilo_narrativo": identity.get("narrative_style") or "",
    }
```

Dejar `_b40_prompt_profile` existente intacta (tests legacy); simplemente dejar
de referenciarla en `build_model_user_message`.

### 4c. Helper de menciones enriquecidas (CONO)

```python
def _mentions_block(context: dict) -> list[dict]:
    """Menciones con mini-ficha si el host la enriqueció."""
    mentions = context.get("mentions")
    if not isinstance(mentions, dict):
        return []
    result = []
    for ref in (mentions.get("refs") or []):
        if not isinstance(ref, dict):
            continue
        entry = {"name": ref.get("name"), "ref_type": ref.get("ref_type")}
        brief = ref.get("brief")
        if isinstance(brief, dict):
            entry.update(brief)
        result.append(entry)
    return result
```

### 4d. Helper selección (CONO)

```python
def _selection_block(context: dict) -> dict:
    return {
        "entity_ids": list(context.get("selected_entity_ids") or []),
        "relation_ids": list(context.get("selected_relation_ids") or []),
        "anillo_activo": context.get("active_ring_id") or context.get("focused_ring_id") or "",
        "focus_label": context.get("focus_label") or "",
    }
```

### 4e. Reescribir build_model_user_message (M4 + M7 + CONO)

```python
from packages.application.prompt_budget import DEFAULT_PROMPT_BUDGET_TOKENS, enforce_budget

def build_model_user_message(plan: AIJobPlan) -> str:
    budget = int(plan.context.get("prompt_budget_tokens") or DEFAULT_PROMPT_BUDGET_TOKENS)
    message: dict[str, Any] = {
        # --- DIRIGE ---
        "prompt_exacto_usuario": plan.prompt,       # sagrado
        # --- RESTRINGE ---
        "cerco_canon": _cerco_canon(plan.context),
        # --- INFORMA ---
        "seleccion": _selection_block(plan.context),
        # --- ATMÓSFERA ---
        "parametros_permanentes": _parametros_permanentes(plan.context),
        # --- RESIDUAL sin duplicados (M2) ---
        "contexto_autorizado": _context_for_prompt(plan.context),
    }
    # Opcionales (solo si existen y no están vacíos):
    directives = _fase2_directives(plan.context)
    if directives:
        message["directivas"] = directives
    mentions = _mentions_block(plan.context)
    if mentions:
        message["menciones"] = mentions
    causal = plan.context.get("contexto_causal")
    if isinstance(causal, dict) and causal:
        message["posicion_causal"] = causal
    vecindario = plan.context.get("vecindario")
    if isinstance(vecindario, dict) and vecindario.get("items"):
        message["vecindario"] = vecindario
    if _wants_chronology_formats(plan):
        message["formatos_h05"] = _CHRONOLOGY_OUTPUT_FORMATS
    # Presupuesto + truncado (M7)
    message = enforce_budget(message, budget)
    return json.dumps(message, ensure_ascii=False, indent=2)
```

Cambios respecto al mensaje actual:
- ELIMINAR claves `intent` y `plan` (M4).
- ELIMINAR `perfil_creativo_b40` (sustituido por cerco + parámetros).
- AÑADIR `menciones`, `vecindario`, `seleccion` como secciones propias.
- `restricciones` se elimina del user message: `no_canon_automatico` vive solo
  en el system prompt (M3); `usar_prompt_exacto` ya está en el system base.
- Aplicar `enforce_budget` antes de serializar (M7).

## FASE 5 — command_prompts.py (EDIT, M3)

En `_BASE_ES` (líneas 16-34) dejar UNA sola mención de la regla de canon:

```python
_BASE_ES = (
    "Eres el asistente central de creación de Dendro. Respeta el prompt exacto "
    "del usuario, el idioma, género, tono, realismo, estilo y el canon existente. "
    "Toda salida estructural es un candidato revisable: no modificas canon directamente.\n"
    # ... resto sin repetir la regla de canon ...
)
```

Confirmar que `perfil_creativo_b40.instructions` (ai_jobs.py:1004) ya no se
incluye en el mensaje (FASE 4 elimina su uso). Si algún test lo referencia,
dejar la función pero sin usarla en build_model_user_message.

## FASE 6 — narrative_context_builder.py (EDIT, +1 método) + workspaces.py (EDIT)

### 6a. narrative_context_builder.py: build_neighborhood_pack

```python
def build_neighborhood_pack(
    self,
    entity_ids: list[str],
    *,
    audience: str = "gm",
    max_hops: int = 2,
    max_items_per_hop: int = 8,
) -> dict:
    """BFS desde la selección respetando visibilidad. Devuelve NeighborhoodPack.to_dict()."""
```

Algoritmo:
1. semilla = entity_ids filtrados por `_can_include_entity`.
2. BFS nivel por nivel (hop=1, hop=2...):
   - Para cada relación del proyecto, si toca una entidad ya vista Y el otro
     extremo es visible → NeighborhoodItem con weight=decay_weight(hop).
   - La relación → NeighborhoodRelation con hop del extremo más lejano.
3. No re-visitar entidades ya incluidas en hop menor (conjunto `visited`).
4. Capar a max_items_per_hop por hop.
5. Las entidades semilla NO entran en items (ya están en selección).
6. Sin selección → pack vacío con warnings=["no_selection"].

### 6b. workspaces.py: _neighborhood_pack + _enrich_mentions_in_scope

```python
def _neighborhood_pack(self, scope: dict) -> dict:
    project = self._get_active_project()
    if project is None:
        return {}
    selected = [str(x) for x in (scope.get("selected_entity_ids") or []) if x]
    if not selected:
        return {}
    from packages.application.narrative_context_builder import NarrativeContextBuilder
    builder = NarrativeContextBuilder(self.ps)
    return builder.build_neighborhood_pack(selected, audience="gm", max_hops=2)
```

```python
def _enrich_mentions_in_scope(self, scope: dict, project) -> None:
    """Añade brief (mini-ficha) a cada mención resuelta, in-place."""
    mentions = scope.get("mentions")
    if not isinstance(mentions, dict) or project is None:
        return
    refs = mentions.get("refs") or []
    if not refs:
        return
    index = {}
    for e in getattr(project, "entities", []) or []:
        index[str(getattr(e, "id", ""))] = e
    milestones = {}
    ctrl = getattr(self, "_milestone_ctrl", None)
    if ctrl is not None:
        try:
            for m in ctrl.list_all():
                milestones[str(getattr(m, "id", ""))] = m
        except Exception:
            pass
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        rid = str(ref.get("ref_id") or "")
        target = index.get(rid) or milestones.get(rid)
        if target is None:
            continue
        ref["brief"] = {
            "name": str(getattr(target, "name", "") or ""),
            "type": str(getattr(getattr(target, "entity_type", ""), "value", "milestone")),
            "layer_ids": [str(x) for x in (getattr(target, "layer_ids", []) or [])],
            "brief_description": str(getattr(target, "brief_description", "") or "")[:400],
        }
```

### 6c. workspaces.py: _submit_ai_command (insertar vecindario + menciones + budget)

Tras `base_scope = self._current_context_scope()`, antes de `plan_command_jobs`:

```python
causal = self._causal_context_pack(base_scope)
if causal:
    base_scope["contexto_causal"] = causal
vecindario = self._neighborhood_pack(base_scope)
if vecindario:
    base_scope["vecindario"] = vecindario
base_scope["prompt_budget_tokens"] = self._budget_tuner.value()
```

Y dentro del bucle `for planned in plan.jobs:`, tras `scope.update(planned.context_overrides)`:

```python
self._enrich_mentions_in_scope(scope, self._get_active_project())
```

### 6d. workspaces.py: tuner de presupuesto (NUEVO control)

Junto a `_temp_tuner` y `_tokens_tuner` (línea ~2318), añadir:

```python
budget_tuner = RadialTuner(minimum=1000, maximum=12000, value=4000, is_integer=True)
budget_tuner.setToolTip(
    "Tokens de contexto para esta tarea.\n"
    "Se reparten automáticamente: canon/causal 27%, selección 15%, "
    "vecindario 20%, atmósfera 10%, directivas 8%, resto 20%.\n"
    "Más alto = la IA recibe más información; más bajo = respuestas más rápidas."
)
self._budget_tuner = budget_tuner
# Añadir al layout junto a los otros tuners (línea ~2208).
```

En `_sync_tuner_recommendations` (línea 2357): NO resetear el budget tuner por
función (el presupuesto lo decide el usuario/proyecto, no el tipo de tarea).
Pero sí inicializarlo con el default del proyecto al cargar:

```python
# En _sync_tuner_recommendations, al final, NO tocar _budget_tuner.
# En su lugar, inicializarlo cuando se carga un proyecto:
def _load_project_budget_default(self):
    project = self._get_active_project()
    if project is None:
        return
    ai = getattr(project, "ai", None)
    default = getattr(ai, "prompt_budget_tokens", 4000) if ai else 4000
    if hasattr(self, "_budget_tuner") and self._budget_tuner is not None:
        self._budget_tuner.setValue(int(default))
```

Llamar `_load_project_budget_default()` donde se carga/abre un proyecto
(buscar el punto existente donde se resetean otros tuners o se carga el proyecto).

También subir el máximo del `_tokens_tuner` existente de 4000 a 6000 para dar
más margen de generación (el usuario pidió "aumentar el selector").

## FASE 7 — ai_context_actions.py (EDIT, M6)

Resolver la duplicación en jobs `raw_prompt=True` (menú/panel): el target aparece
dos veces (embebido en el prompt + en authorized_context).

En `_run_focused`, tras `self._seed_context_scope(...)`, cuando `raw_prompt=True`,
reducir `authorized_context` a un resumen compacto:

```python
# Dentro de _run_focused, tras _seed_context_scope:
if raw_prompt:
    scope["authorized_context"] = _compact_context_summary(context)
```

`_compact_context_summary` ya existe (línea 59): devuelve solo nombres, counts y
flags, no el contenido completo de la entidad.

## FASE 8 — Tests

### tests/test_neighborhood.py
- decay_weight(0)==1.0, (1)==1.0, (2)==0.4, (3)==0.1, (4)==0.0.
- build_neighborhood_pack con 4 entidades en línea A-B-C-D, selección=[A]:
  items tiene B (hop1, w1.0), C (hop2, w0.4); D no entra con max_hops=2.
  D entra con max_hops=3 (w0.1).
- entidad con secreto no visible → no entra aunque sea vecina.
- sin selección → pack vacío + warning "no_selection".

### tests/test_prompt_budget.py
- tokens_to_chars(4000) == 14000.
- truncate_to_chars("hola mundo cruel", 10) → "hola…" (corta en palabra).
- truncate_to_chars("corto", 100) → "corto" (sin "…").
- enforce_budget con total=4000:
    directivas (4%) → 560 chars máx.
    cerco_canon (14%) → 1960 chars máx.
    vecindario (20%) → 2800 chars máx.
- enforce_budget deja prompt_exacto_usuario intacto sin importar el tamaño.
- enforce_budget no muta la entrada.
- enforce_budget con secciones que faltan → no explota.

### tests/test_command_bar_prompt_shape.py
- build_model_user_message NO contiene "intent" ni "plan" (M4).
- contiene "cerco_canon", "parametros_permanentes", "seleccion" (CONO).
- NO contiene "perfil_creativo_b40" (M2).
- contexto_autorizado NO contiene "creative_brief" (M2 deduplicación).
- contexto_autorizado NO contiene "contexto_causal" ni "vecindario" (M2).
- menciones con brief → aparecen con name+type+layer_ids+brief_description (CONO).
- menciones sin brief → solo name+ref_type.
- vecindario con items → clave presente; vacío → ausente.
- build_model_user_message respeta prompt_budget_tokens: con budget=1000 el
  mensaje es notablemente más corto que con budget=8000.
- smoke: SimulatedAIProvider(allow_simulated=True), create_job(explicit)+execute_job
  no falla y el resultado tiene la estructura esperada.

## FASE 9 — Verificación (solo instantáneo, sin suites largas)

IMPORTANTE: el usuario ejecuta los tests manualmente. NO lanzar `pytest` sobre
suites existentes (tests/desktop/, tests/application/) — consumen tiempo y tokens
de API por esperar resultados. Solo se permiten verificaciones instantáneas:

```bash
1. git diff --stat    # comparar con la lista de 11 archivos; si hay más, ABORTAR
2. grep -rn "perfil_creativo_b40\|\"intent\":\|\"plan\":" packages/application/ai_jobs.py \
       | grep "message\["    # 0 resultados (ya no en el mensaje)
3. grep -rn "prompt_budget_tokens" packages/domain/project_config.py  # campo existe
4. grep -rn "_budget_tuner" hosts/DesktopHostPySide/views/workspaces.py  # tuner creado
5. python -c "from packages.application.neighborhood import decay_weight; \
     assert decay_weight(0)==1.0 and decay_weight(4)==0.0; print('OK')"  # smoke import
6. python -c "from packages.application.prompt_budget import enforce_budget; \
     print('OK')"  # smoke import
```

Los 3 archivos de test (FASE 8) se escriben pero NO se ejecutan durante la sesión.
El usuario los corre a mano cuando quiera:

```bash
# El usuario ejecuta esto manualmente tras la sesión:
pytest tests/test_neighborhood.py tests/test_prompt_budget.py \
       tests/test_command_bar_prompt_shape.py -q
```

## Criterios de aceptación

1. El user_message tiene las secciones del cono (dirige/restringe/informa/atmósfera)
   y NO tiene `intent`, `plan`, `perfil_creativo_b40` ni `restricciones`.
2. Un "Crear Hoja" con entidad seleccionada produce `vecindario` con vecinos hop 1 (peso 1.0).
3. Un prompt con "@EntidadExistente" muestra esa entidad en `menciones` con mini-ficha.
4. `contexto_autorizado` NO contiene creative_brief, contexto_causal ni vecindario.
5. `enforce_budget` reparte el total por porcentajes y deja el prompt intacto.
6. El tuner `_budget_tuner` (1000-12000) viaja como `prompt_budget_tokens` en el scope.
7. AIConfig tiene `prompt_budget_tokens` con default 4000.
8. Jobs raw_prompt del menú/panel no duplican la entidad en authorized_context.
9. Todos los tests existentes pasan.
10. `git diff --stat` muestra exactamente los 11 archivos esperados.

---

## Reglas de seguridad para la ejecución

```
REGLA CRÍTICA (incidente documentado en este repo):
- Prohibido `git checkout -- .` o `git clean` durante el trabajo.
- Prohibido editar archivos fuera de los listados.
- Tras cada archivo, `git diff --stat <archivo>` y confirmar scope.
- Si diff muestra borrados masivos no esperados, PARAR inmediatamente.
- Usar Edit (old_string/new_string quirúrgicos) para archivos existentes.
  Usar Write solo para los 3 archivos NUEVOS + los 3 tests.
- FASE 9 paso 1 es no negociable.

REGLA DE TESTS (ahorro de tokens de API):
- PROHIBIDO lanzar `pytest` sobre suites existentes (tests/desktop/,
  tests/application/, o cualquier suite que pueda tardar >10s).
- PROHIBIDO lanzar Xvfb o levantar la UI para testear.
- Los tests se ESCRIBEN pero NO se ejecutan durante esta sesión.
- Solo se permiten: git diff, grep, y `python -c "import..."` (smoke import).
- El usuario ejecutará los tests manualmente cuando quiera.
```

## Reparto porcentual de referencia (documentar en prompt_budget.py)

```
                      % del budget    qué es
──────────────────────────────────────────────────────
directivas              4%            count, @refs, modo (DIRIGE)
menciones               4%            mini-fichas @ (DIRIGE)
cerco_canon            14%            hard_rules, negative_space (RESTRINGE)
posicion_causal        13%            anillos→ramas→hojas (RESTRINGE)
seleccion              15%            entidad objetivo (INFORMA)
vecindario             20%            vecinos con decaimiento (INFORMA)
parametros_permanentes 10%            género/tono/estilo (ATMÓSFERA)
contexto_autorizado    20%            resto del scope sin duplicados (RESIDUAL)
──────────────────────────────────────────────────────
TOTAL                 100%            (prompt del usuario = sagrado, fuera del budget)
```

Con un budget de 4000 tokens: directivas=160tok, cerco=560tok, causal=520tok,
selección=600tok, vecindario=800tok, atmósfera=400tok, residual=800tok.
