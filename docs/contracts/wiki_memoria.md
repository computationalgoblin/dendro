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

#### 3.2.0 Regla de resolucion de enlaces (BETA2-FIX-07)

**Ningun enlace de una pagina se persiste sin existir en el canon.** Todo
`MemoryCitation` que escribe la IA (`wikilinks`, `citations`, `dependencias` y los
`issues[].anclado_a`) pasa por `structured_reference_service.resolve_page_refs` ANTES de
guardarse. La regla es **determinista, sin IA y de coste cero**, y es la MISMA que la de
las @menciones (reutiliza `build_known_targets`: no hay dos reglas de resolucion en el
repo):

1. `ref_kind=project` se conserva tal cual (no apunta a un elemento concreto).
2. `ref_id` que **ya es un id del canon** se conserva, y su `ref_kind` se **corrige al
   kind real** (la IA escribe `entity` de una rama o de un hito).
3. `ref_id` que es el **nombre exacto** de un elemento se **reescribe con su id** y su kind
   reales. La comparacion **pliega mayusculas y acentos** (`fold_name`), porque el modelo
   no copia los nombres caracter a caracter. Esto rescata la mayoria de los enlaces: en
   los dos mundos del beta, 37 de 40 refs llevaban el NOMBRE en `ref_id` y 30
   eran rescatables por coincidencia exacta.
4. Nombre que corresponde a **varios** elementos (duplicado en el proyecto): **no se
   inventa un ganador**. El enlace **no se persiste** y se cuenta como *ambiguo*.
   `MemoryCitation` no tiene estado de referencia (a diferencia de `StructuredReference`,
   que si modela `AMBIGUA` + `candidate_target_ids`) y darselo seria cambio de esquema:
   mientras no lo tenga, la respuesta honesta es no enlazar.
5. Lo que no encaja en nada de lo anterior se **descarta**. Las **relaciones** solo
   resuelven por id: no tienen nombre corto y no estan indexadas por nombre a conciencia.

**Lo descartado no desaparece en silencio.** `MemoryAIService.update_memory` devuelve en
su `Ok` el recuento `{resueltos, ambiguos, descartados}` y el visor de Memoria lo dice en
la cabecera de la pagina cuando hay algo que contar. No se crean incidencias por cada
enlace caido (inundaria la pagina de ruido).

**Una incidencia que pierde su anclaje SOBREVIVE.** Una contradiccion sin ancla sigue
valiendo; descartar el diagnostico entero por un id malo seria perder mas de lo que se
gana.

**El cuerpo va en prosa limpia.** El prompt nunca ha pedido enlaces dentro del texto (solo
el array `wikilinks`), pero el modelo se inventa `[Nombre](ref_id: Nombre)` y
`[[Nombre]]`. Como el visor pinta el cuerpo en texto plano, esa sintaxis llegaba cruda a
la cara del usuario: `memory_payload` la **limpia dejando el texto visible** (en
`cuerpo`, `resumen_editorial` y `estado_actual`). No se convierte en `wikilinks`: los
enlaces de verdad son los del array, que si se resuelven.

**Sin cambio de forma en disco.** `MemoryCitation` sigue siendo `{ref_kind, ref_id, nota}`;
solo cambian los VALORES que se escriben.

#### 3.2.1 Paginas escritas a mano (BETA2-FIX-11)

La IA es el escritor HABITUAL de las paginas, no el unico autorizado. Quien trabaja **sin
proveedor de IA** tambien tiene wiki: desde el visor de Memoria se **crea** una pagina
eligiendo el elemento por su nombre y se **escribe** su `cuerpo` a mano. Esto no es una
via paralela: usa el mismo `NarrativeMemoryService.upsert_memory`, el mismo modelo y el
mismo sitio en disco (sin cambio de esquema; `cuerpo`/`wikilinks`/`tags` viajan desde v39).

Lo que se persiste y por que:

- `origin = MemoryOrigin.USUARIO` — la pagina lleva escrito quien la escribio, tanto al
  crearla como al editar a mano una que habia escrito la IA (editarla la hace tuya). El
  visor lo dice en la cabecera ("escrita a mano").
- `freshness = REGADA` — lo que el autor acaba de escribir esta **vigente**. Es honesto y
  ademas es lo que da la garantia de la seccion 5.1: Regar no pisa una pagina `Regada`.
- El historial recibe su `MEMORIA_ACTUALIZADA` con la causa ("pagina creada a mano" /
  "edicion manual desde la wiki"), como cualquier otra escritura de Memoria.

**Una pagina escrita a mano no la pisa Regar.** La via explicita para que la IA la
reescriba es el boton **«Regenerar con IA»** del propio visor (`MemoryAIService`
`mode="regen"`), que no lleva esa guarda y ademas **propone un diff revisable** antes de
sustituir nada. Es decir: la maquina no te borra lo tuyo por su cuenta, y tu puedes
pedirle que lo reescriba cuando quieras.

Escribir una pagina a mano **no falsea el jardin**: el estado de riego exige un
diagnostico de riego propio (`WateringService`), asi que la entidad sigue "por regar"
aunque su pagina este escrita. Son dos cosas distintas y se quedan distintas.

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

### 4.1 Cuando NO se navega: la wiki vacia no se cobra (BETA2-FIX-06)

**Decision de producto (G2-10).** Si el indice tiene **cero paginas** (`counts["con_pagina"] == 0`)
la navegacion **no se ejecuta**: `WikiNavigator.assemble_context` devuelve `Ok` con un bundle vacio
y `skipped_reason` explicando por que, **sin una sola llamada al proveedor**.

Motivo, medido: el ronda-a-ronda re-envia el indice compacto entero. En un mundo sintetico de 800
entidades y 1.760 relaciones son **73.548 caracteres (~21.000 tokens) por ronda con
`con_pagina = 0`** — no hay una sola pagina que abrir. Con 50 entidades ya son ~9.150 tokens por
ronda por lo mismo. La medicion en un mundo real del beta dio 91.777 caracteres por llamada de
`suggest`/`compose_generation`, **doce veces un riego**, con la wiki practicamente vacia.

Umbral elegido: **N = 0**, el caso incontestable. Con N > 0 la navegacion sigue comprando algo
util (`read_canon`, `search`), asi que no se corta. El plan B no deja a la Sugerencia sin
contexto: `build_suggestion_request` ya arma el contexto compacto por entidad — el mismo que hace
que **Regar escale 1,23x sobre 16x de proyecto**.

**Se dice en voz alta.** El corte NO es una degradacion silenciosa (mismo principio que
BETA-FIX-02): `_attach_wiki_context` devuelve el motivo, `compose_generation` lo publica
como `wiki_skipped` y el host lo saca por el indicador de estado y por un toast.

### 4.2 Tope de tamano por ronda

`max_index_entries` (WS-L) acotaba el **numero** de entradas del indice, no su **tamano**: 400
entradas de hasta 120 caracteres seguian dando ~73.500 caracteres por ronda, y el presupuesto
declarado (`token_budget`, 4.000) **solo media lo traido** (`used_chars`), nunca el indice
re-enviado. Se anade `NavigationRequest.max_round_chars` (**24.000 caracteres ≈ 6.850 tokens**,
tope **duro** y verificable en test): si el mensaje de la ronda no cabe, se recortan entradas del
indice y **se declara el recorte** en el propio mensaje — lo omitido sigue alcanzable por `search`.

## 5. Mantenimiento (la IA cuida la wiki)

### 5.1 Al Regar

Regar un elemento:

1. Escribe/actualiza su **pagina** (`cuerpo`/`resumen_editorial`/`tags`/`wikilinks`) via el job de
   Memoria; auto-aplica (la Memoria no es canon). Sus enlaces se **resuelven contra el
   canon antes de persistirse** segun la seccion 3.2.0; una pagina recien escrita no puede
   nacer con enlaces rotos.

   **Que recibe la IA para poder acertar (BETA2-FIX-07).** Regar sigue sin
   navegar, pero su contexto local **enumera los ids**: cada vecina, cada hito y cada
   relacion viajan como `nombre (kind:id)`. Antes el unico id del prompt era el del propio
   elemento y por eso las unicas refs que resolvian en el beta eran las auto-citas: se le
   exigia al modelo un id que nadie le habia dado.

   **La direccion de la relacion es parte del contexto, no un adorno.** Cada relacion se
   marca `[sale]` (este elemento es el ORIGEN) o `[entra]` (es el DESTINO), con los dos
   extremos escritos. El renderizado anterior (`sirve_a→Nadia Kerr`) era identico viniera
   la relacion de entrada o de salida y se lee en espanol como «(yo) sirvo a Nadia»: la
   pagina de quien recibia el servicio se declaraba subordinada, invirtiendo el canon. No
   fue una alucinacion del modelo — transcribio lo que le dijimos.

   **El recorte se declara.** El contexto lista como mucho 12 relaciones; cuando hay mas,
   el propio texto dice cuantas quedan fuera (seccion 9: no truncar callando).
2. **Refresca el indice** automaticamente (el indice es proyeccion; al cambiar la pagina cambia su
   entrada).
3. **Marca `Falta regar` solo a quien DEPENDE de la pagina reescrita** — no a todo su
   vecindario. Se reutiliza el motor de impacto (`NarrativeImpactService.propagate_change`)
   pero **restringido a las vias de dependencia real** `mencion` (alguien @menciona al
   elemento regado) y `cita_memoria` (una pagina lo cita), via el parametro `only_via`. No se
   crean paginas vacias; no se pisan estados `Secada`. Se mantiene la **exclusion del lote**
   (`exclude_ids`) y `include_self=False`.

   **Regla vigente desde 2026-08-04 (BETA2-FIX-05, G2-05). Racional.**
   Este parrafo decia lo contrario («para riegos SEPARADOS la propagacion se mantiene a
   conciencia»). La ronda 2 del beta lo desmonto con numeros: la directora de
   arte regó cuatro entidades en **16 min 30 s de IA real** y su balance neto fue **cero**
   verdes, porque regar B devolvia a `Falta regar` la pagina de A regada un minuto antes.
   Las razones para invertir la regla:
   - **Regar no cambia canon.** `WateringService.water_entity` lo declara («JAMAS toca
     canon»): reescribe una pagina de wiki. `NarrativeImpactService` se declara motor del
     impacto de un cambio **canonico**. Regar era una operacion no canonica alimentando un
     motor de cambios canonicos: ese era el bug conceptual.
   - **Por la via `relacion`, esa propagacion SOLO podia destruir trabajo pagado.** El
     marcado (`_mark`) no crea paginas ausentes y no degrada las que ya estan `Falta regar`:
     los unicos elementos que podia tocar eran las paginas **vigentes**. No existia el
     «dependiente desactualizado» al que avisar.
   - **El ping-pong era estructural, no una carrera.** Como Regar no regenera una pagina ya
     `Regada`, el ciclo entre dos vecinas A y B es determinista: dos vecinas **jamas** podian
     estar verdes a la vez fuera de un mismo lote. Con 30 fichas y 37 relaciones el Mapa
     estaba condenado a ~93 % marron: la metafora del jardin era matematicamente incapaz de
     alcanzar su propio estado sano.

   Lo que **no** cambia: un cambio de **CANON** (`update_entity`/`update_relation`/
   `update_hito`/`accept_candidate`) sigue propagando por TODAS las vias, incluida
   `relacion`, con el descenso por rank de anillo. La distincion codificada es
   **«cambio el canon» (marca)** vs **«se reescribio otra pagina de wiki» (no marca)**.

4. **La caducidad del diagnostico de riego (`WateringService._is_stale`) mira el canon
   PROPIO del elemento**, no el de sus vecinas (misma fecha y ticket). Caduca si se edito su
   ficha, si se edito una **relacion suya**, o si su vecindario cambio de **forma** (altas,
   bajas, vecina borrada: el contexto que se envio a la IA ya no existe). **No** caduca
   porque se editara el CONTENIDO de una vecina —ni de una de 2º grado de relevancia alta—:
   esa era una tercera via de invalidacion, no descrita en ningun contrato, que por si sola
   mantenia sedientas las cuatro entidades regadas del mundo real del beta, incluida la unica
   cuya pagina seguia `Regada`. La señal no se pierde: viaja por el punto 3 aplicado al
   cambio de canon (se marca la PAGINA de quien depende de verdad) y la unificacion de
   frescura la refleja en el jardin. Renegociado a conciencia en
   `tests/application/test_watering_service_states.py::TestNeighborhoodInvalidation`.

Se preserva la guarda existente: Regar no regenera una pagina que ya esta `Regada`. Esa
misma guarda es la que protege las **paginas escritas a mano** (seccion 3.2.1), que nacen
`Regada`: el autor no pierde su texto por regar el elemento. Para reescribirla hay que
pedirlo explicitamente con «Regenerar con IA», que propone un diff antes de sustituir.

### 5.2 Lint bajo demanda

`WikiLintService` hace una pasada de salud, determinista, que detecta: paginas **huerfanas**
(target inexistente), **enlaces rotos** (wikilinks/citas/dependencias **y anclajes de
incidencia**, `issues[].anclado_a`, a ids ausentes — BETA2-FIX-07), afirmaciones
**stale** (`Falta regar`/`Secada`) y **contradicciones** ya modeladas. Opcionalmente, una unica llamada IA
(sin bucle) detecta contradicciones cruzadas. Todo se ancla como `MemoryIssue` revisable; nunca
canon.

**Donde vive (BETA2-FIX-11).** El lint tiene pantalla: la pestaña **Wiki** del
panel de proyecto **«Salud del proyecto»** (`ProjectHealthPanel`, pestañas previstas
Continuidad · Wiki · Estructura). Reglas de esa superficie: se ejecuta **al pulsar**, no al
abrir; **no deja contador permanente** en la esquina de la pantalla (la app ya tiene dos:
sed y estructura); la parte determinista funciona **con el proveedor apagado** y solo el
boton de contradicciones cruzadas se deshabilita, con motivo legible; y cada fila **salta a
la pagina afectada** por su nombre, nunca por uuid.

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

### 6.2 Rigor de lo generado y trazabilidad de lo aceptado (BETA2-FIX-08)

El camino de DIAGNOSTICO (Regar/Memoria) era honesto por esquema (`risks`, `issues` con
contradiccion/hueco/pregunta_abierta/supuesto) y el GENERATIVO no tenia donde serlo. Reglas:

- **Marca de base por pieza**: cada objeto de `suggest_composite` declara `base` ∈
  {`canon`, `inferido`, `inventado`} + `base_nota` (en que se apoya). `stage_results` la lee y la
  guarda en `Candidate.metadata["base"]`/`["base_nota"]`; el panel de revision la muestra. Si el
  modelo no la manda, la pieza queda `no_declarada`: **la marca nunca se inventa**.
- **Licencia de invencion acotada**: el base sigue permitiendo inventar **ficcion del mundo**, pero
  no rellenar datos, y la **peticion del usuario manda** sobre esa licencia (si pide abstenerse, se
  abstiene y lo dice en `report`). El recorte de `_NON_CREATION_INTENTS` no cambia: riego y memoria
  no reciben ni esta seccion ni la marca de base.
- **Confianza**: solo se muestra si la **declara el modelo** (`metadata["confianza_declarada"]`).
  El literal del codigo (0,60/0,62) ya no se pinta como si fuera una medida.
- **Tipo narrativo en el contexto**: el bloque `CANON:` del prompt de Memoria lleva
  `tipo_narrativo` (una rama es un CONTENEDOR que agrupa, no una cosa del mundo).
- **Trazabilidad al aceptar**: la aceptacion rellena los huecos que ya persistian —
  `milestone.candidate_id`/`source_ids`, `entity.origin`, `relation.source`,
  `custom_metadata["candidate_id"]`— crea **una** `Source` de tipo `sugerencia_ia_aceptada` por
  aceptacion (enlazada por `derived_entity_ids`/`derived_relation_ids`) y registra el evento
  `HistoryEventType.ACEPTACION_SUGERENCIA`. Sin migracion de esquema. La trazabilidad es un efecto
  **derivado**: si falla, se anota en la metadata del candidato y el accept sigue siendo `Ok`.

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
