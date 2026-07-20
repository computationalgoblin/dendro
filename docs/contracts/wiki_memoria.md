# Contrato BETA2-WIKI - Memoria como wiki+indice navegable

Estado: vigente para la epica BETA2-WIKI
Fecha: 2026-07-11
Ticket origen: BETA2-WIKI-01
Perfil responsable: arquitectura-producto
Reemplaza a: `memoria_narrativa.md` (BETA2-MEM), ahora deprecado.

Este contrato redefine la Memoria narrativa de Dendro hacia el **metodo Karpathy** (una wiki
que un LLM mantiene sobre unas fuentes, con un indice que se lee primero para decidir que leer
en detalle). Reencuadra la parte IA y recorta la superficie de IA de la app. El sustrato de
dominio de BETA2-MEM se conserva y reutiliza.

## 1. Principio rector

La **Memoria = una wiki que la IA mantiene sobre el canon**. Su proposito no es viajar como un
resumen fijo en cada prompt, sino ser un **indice** que la IA lee **barato** para **decidir que
partes del canon traer** y construir una respuesta coherente **consumiendo lo minimo** de tokens.

```text
Canon confirmado  ->  Wiki (paginas) + Indice (proyeccion del canon)
                  ->  La IA navega el indice primero
                  ->  Abre solo las paginas/canon relevantes
                  ->  Responde con el minimo contexto necesario
```

La IA **navega** la wiki y **la cuida** (la mantiene sana). La IA **nunca escribe canon**: solo
escribe la wiki derivada y propone candidatos revisables.

## 2. Jerarquia de autoridad (sin cambios respecto a BETA2-MEM)

```text
Canon confirmado
  > Referencias estructuradas (@menciones, relaciones, hitos, anillos)
  > Memoria/wiki derivada
  > Propuestas, contradicciones, huecos y cultivo pendiente
```

El canon manda siempre. La wiki interpreta y resume el canon; no lo crea ni lo sustituye. Cuando
la wiki esta actualizada, **acelera** el acceso al canon (indexa), pero no reemplaza al canon como
fuente de verdad: si una pagina y el canon divergen, manda el canon y la pagina queda `Falta regar`.

## 3. Anatomia de la wiki

### 3.1 Indice (determinista, coste IA cero, siempre completo)

El **indice** es una **proyeccion del canon**, calculada al vuelo por `WikiIndexService`
(sin IA, sin persistencia propia). Contiene una entrada por cada elemento canonico
(entidad, anillo, hito, relacion) con:

- `kind`, `id`, `name`, `ring` (cuando aplique),
- `one_line`: 1 linea = el lead de su pagina (`resumen_editorial`) si existe; si no, una
  derivacion determinista de la ficha canonica (nombre + tipo + breve recortado),
- `page_freshness`: frescura de la pagina (`sin_memoria/regada/falta_regar/secada`),
- `has_page`: si existe pagina editorial.

Por construccion el indice **esta siempre sincronizado con el canon** y **nunca esta vacio**:
un proyecto sin ninguna pagina regada tiene, aun asi, un indice completo (todo con
`page_freshness=sin_memoria`). Esto garantiza que la IA siempre dispone de un mapa del proyecto.

### 3.2 Paginas (editoriales, escritas por la IA al Regar)

Una **pagina** es la sintesis editorial de un elemento. Se **modela reutilizando
`NarrativeMemory`** (regla del repo: no crear modelos paralelos), extendido con:

- `cuerpo`: sintesis editorial larga (el "cuerpo de la pagina"),
- `resumen_editorial`: lead/1-linea que consume el indice,
- `wikilinks: list[MemoryCitation]`: enlaces tipados a otros elementos (reutiliza `MemoryCitation`),
- `tags: list[str]`,
- ademas de lo ya existente: `estado_actual`, `issues` (contradicciones/huecos/preguntas/supuestos),
  `citations`/`dependencias`, `freshness`, `origin`, `pending_revision`.

Las paginas son estado **derivado**, no canon. Se persisten en `Project.narrative_memories`.

## 4. Navegacion (bucle de lectura acotado)

El proveedor de IA es de **un solo turno** (no hay tool-calling). La navegacion agentica se
implementa en la **capa de aplicacion** como un **bucle de lectura acotado** (`WikiNavigator`):

1. La app envia una llamada JSON: instrucciones + **indice compacto** + la peticion + resumen de
   lo ya leido.
2. La IA responde `{ reads: [ {op, kind, id, query} ], enough: bool }`, donde `op` es del
   vocabulario cerrado:
   - `open_page(kind, id)`: abre la pagina de wiki de ese elemento,
   - `read_canon(kind, id)`: trae la ficha canonica de ese elemento,
   - `search(query)`: busqueda por palabra clave sobre el indice.
3. La app **cumple los reads de forma determinista** (nunca la IA accede directamente al store) y
   vuelve a llamar, hasta que la IA dice `enough`, se agota el tope de rondas (2-3), se agota el
   presupuesto de tokens, o el JSON es invalido (en cuyo caso para con lo reunido).

Reglas de seguridad del bucle: dedup de reads ya servidos; una ronda que no pide nada nuevo
termina el bucle; nunca se superan `max_rounds`; el coste queda acotado y es observable por ronda.

**Quien navega:** las **Sugerencias** y la **creacion cronologica (Play/walk)**. **Regar no
navega**: mantiene su contexto local compacto de la entidad regada (diagnostico) y **escribe** su
pagina.

## 5. Mantenimiento (la IA cuida la wiki)

### 5.1 Al Regar

Regar un elemento:

1. Escribe/actualiza su **pagina** (`cuerpo`/`resumen_editorial`/`tags`/`wikilinks`) via el job de
   Memoria; auto-aplica (la Memoria no es canon).
2. **Refresca el indice** automaticamente (el indice es proyeccion; al cambiar la pagina cambia su
   entrada).
3. **Marca `Falta regar` las paginas relacionadas** propagando por **potencialidad causal**: se
   reutiliza el motor de impacto (`NarrativeImpactService.propagate_change`), que marca los
   dependientes directos y **desciende por rank de anillo** segun la **potencia causal** del
   elemento (un cambio en un elemento de mayor potencia causal impacta tambien a anillos
   inferiores). No se crean paginas vacias; no se pisan estados `Secada`.

Se preserva la guarda existente: Regar no regenera una pagina que ya esta `Regada`.

### 5.2 Lint bajo demanda

`WikiLintService` hace una pasada de salud, determinista, que detecta: paginas **huerfanas**
(target inexistente), **enlaces rotos** (wikilinks/citas a ids ausentes), afirmaciones **stale**
(`Falta regar`/`Secada`) y **contradicciones** ya modeladas. Opcionalmente, una unica llamada IA
(sin bucle) detecta contradicciones cruzadas. Todo se ancla como `MemoryIssue` revisable; nunca
canon.

### 5.3 Reconstruccion en lote

Existe una accion opcional "reconstruir wiki" que puebla/actualiza paginas por lotes (patron del
riego por lotes: cancelable, con autorizacion de coste previa).

## 6. Recorte de la superficie de IA

La IA de Dendro se reduce a **cuatro mecanicas** sobre el sustrato wiki+indice:

1. **Regar** (diagnostico de metricas de salud que guian la creacion),
2. **Sugerencias** (inspiradas en esas metricas; unica via que acepta prompt de texto libre del
   usuario; germinan como Semillas revisables),
3. **Memoria/wiki** (mantener y navegar),
4. **Creacion cronologica (Play/walk)**.

Se **retira de la UI** (y se marca legacy en backend para borrado posterior): la command bar
(Accion x Ambito + texto libre), las acciones IA de menu contextual, las barras IA de los paneles
de detalle, la generacion suelta de la toolbar, la coherencia (analizar/reparar) y el texto inline.
Se **retira tambien el RAG lexico**: la wiki+indice es el **unico** mecanismo de recuperacion.

Los workers de generacion que las Sugerencias reutilizan por dentro
(`suggest_relations`/`edit_entities`/`generate_entities`) se **conservan como internos** aunque
pierdan su punto de entrada en la UI.

### 6.1 Analisis de intencion en Sugerencias (BETA2-WIKI-13)

Elegir el tipo de output SOLO por la metrica no honra peticiones como "crea una rama". Reglas:

- **nutrida / calidad**: el tipo lo fija la metrica (`edit_entities`). Sin cambios.
- **arraigo / iluminada**: una Sugerencia puede requerir crear entidades, ramas, relaciones o
  hitos, o editar. Corre primero un **job de analisis de intencion** ligero
  (`SuggestionIntentService`, `raw_json_completion`) que lee peticion + contexto + wiki navegada y
  decide un **plan** de tipos de output (NO escribe contenido, NO toca canon, NO elige el usuario la
  categoria a mano). Un unico job **compuesto** (`AIJobType.SUGGEST_COMPOSITE`) genera el mix segun
  el plan; `stage_results` es agnostico y lo estadia todo (hojas/ramas/relations/hitos/entity_edits)
  como Semillas revisables.
- **Decisiones**: el plan es **feedback** (no gating: la aprobacion real es al aceptar cada Semilla);
  se **analiza siempre** (con o sin peticion). Sin proveedor, el plan cae a un **fallback
  determinista** por metrica (arraigo->relacion, iluminada->hoja) y el flujo sigue.
- **Coordinacion**: `WateringService.compose_generation` = navegacion wiki + analisis de intencion +
  composicion del prompt, off-thread (worker `_SuggestionPrepWorker`); el plan viaja como texto de
  estado al indicador de IA. La IA nunca escribe canon.

## 7. Config del proyecto y prompt del usuario

Toda tarea IA respeta **siempre** la configuracion creativa del proyecto (seccion determinista del
prompt, sin cambios). El **prompt de texto libre del usuario** solo alimenta las **Sugerencias**
(Regar y Play/walk no lo necesitan); el campo de texto libre de la antigua command bar se reubica
como un campo "peticion/matiz" opcional dentro del flujo de Sugerencias.

## 8. Servicios (separados y coordinados)

No hay fachada unica; cada servicio tiene contrato nitido y es Result-based; la UI nunca escribe
persistencia:

- `WikiIndexService` — proyeccion determinista del indice (sin IA).
- `WikiNavigator` — bucle de lectura acotado sobre el proveedor de un turno.
- `WikiLintService` — salud de la wiki (determinista + opcion IA de un turno).
- `WateringService` (extendido) — Regar escribe pagina + dispara la propagacion causal.
- `MemoryAIService`/`NarrativeMemoryService` (existentes) — job de Memoria y CRUD de paginas.

## 9. Observabilidad e invariantes

- Cada ronda del bucle de navegacion es observable (rondas usadas, presupuesto, reads) via el log
  de observabilidad IA; sin filtrar secretos.
- **Invariantes** (verificables): la IA nunca muta canon; el indice esta siempre completo; el bucle
  nunca supera su tope; la app funciona sin proveedor IA (indice/lint/CRUD deterministas siguen);
  cargar proyectos antiguos no pierde datos (migracion aditiva).

## 10. Persistencia

`NarrativeMemory` extendido se persiste en `Project.narrative_memories`. Migracion **aditiva**
v38->v39 (asegura la coleccion y bumpea version; los campos nuevos son tolerantes en `from_dict`).
Proyectos v38 cargan sin perdida: sus paginas quedan con `cuerpo=""` hasta el proximo Regar.
