# Prueba visual guiada B30-B43 — Desktop/Creación/IA

Fecha: 2026-06-06
Estado: preparada para ejecución manual en Windows nativo por el usuario.
Ámbito: todos los elementos visuales/producto implementados desde B30 hasta B43.

## 0. Objetivo

Validar de forma guiada que la aplicación Desktop expone y conserva los elementos implementados desde el cierre contractual B30 hasta la migración IA B43, sin confundir:

- cierre documental/WSL con validación Windows OK;
- sugerencia IA con canon;
- candidatos revisables con entidades reales;
- grafo como vista con base de datos/canon.

Esta prueba está pensada para ejecutarse manualmente desde Windows nativo.

## 1. Preparación

### 1.1 Comando de arranque

Desde PowerShell, en la raíz del proyecto:

```powershell
python -m hosts.DesktopHostPySide.main
```

Si se quiere validar regresión automatizada aparte:

```powershell
python scripts/run_all_tests.py
```

Nota: esta guía no sustituye `python scripts/run_all_tests.py`; cubre comportamiento visual/manual.

### 1.2 Proyecto de prueba recomendado

Crear un proyecto nuevo llamado:

```text
QA_B30_B43_Visual
```

Guardar el JSON en una ruta explícita, por ejemplo:

```text
<repo>/tmp/QA_B30_B43_Visual.json
```

Si `tmp/` no existe, crear una carpeta temporal equivalente fuera de datos reales.

### 1.3 Datos mínimos a crear durante la prueba

Usar estos nombres para facilitar verificación:

- Hoja/personaje: `Devian`
- Hoja/personaje: `Akshan`
- Rama/facción: `Hermandad del Acero`
- Rama/contenedor: `Bosque de Ceniza`
- Hoja/lugar: `Santuario del Núcleo Negro`
- Anillo/capa: `Metafísica de los Dioses-Agujero`
- Relación narrativa: `Devian traiciona a Akshan`
- Relación causal: `Metafísica de los Dioses-Agujero condiciona Santuario del Núcleo Negro`

## 2. Matriz de resultado

Marcar cada sección al ejecutar:

| Bloque | Área | Resultado | Notas |
|---|---|---|---|
| B30 | Gate integrado / UI sin placeholders críticos | ☐ PASA ☐ FALLA ☐ N/A | |
| B31 | UX inmersiva Desktop | ☐ PASA ☐ FALLA ☐ N/A | |
| B32 | Hardening/deuda/UX normal vs avanzado | ☐ PASA ☐ FALLA ☐ N/A | |
| B33 | Creación MVP: nodos, relaciones, IA inline | ☐ PASA ☐ FALLA ☐ N/A | |
| B34 | Árboles/Ramas y contexto jerárquico | ☐ PASA ☐ FALLA ☐ N/A | |
| B35 | Coherencia de subgrafo | ☐ PASA ☐ FALLA ☐ N/A | |
| B36 | Capas causales / Worldbuilding | ☐ PASA ☐ FALLA ☐ N/A | |
| B37 | Creación a escala: búsqueda/filtros/foco/cámara | ☐ PASA ☐ FALLA ☐ N/A | |
| B38 | Command bar IA + jobs revisables | ☐ PASA ☐ FALLA ☐ N/A | |
| B39 | Modelo visible Hoja/Rama/Anillo | ☐ PASA ☐ FALLA ☐ N/A | |
| B40 | Config creativa + Wizard | ☐ PASA ☐ FALLA ☐ N/A | |
| B41 | Hitos causales | ☐ PASA ☐ FALLA ☐ N/A | |
| B42 | Hardening IA observable/no simulado | ☐ PASA ☐ FALLA ☐ N/A | |
| B43 | Prompt Registry sin regresión IA inline | ☐ PASA ☐ FALLA ☐ N/A | |

## 3. B30 — Gate integrado y pulido UI

Objetivo: verificar que el estado post-B30 sigue siendo usable como producto base.

### Pasos

1. Arrancar la app.
2. Confirmar que la ventana principal abre sin traceback visible.
3. Crear o abrir proyecto.
4. Verificar que existen accesos principales a espacios de producto:
   - Home / inicio.
   - Creación.
   - Galería o vista de corpus.
   - Sesión/campaña si está visible en la navegación.
5. Entrar y salir de cada espacio principal.
6. Confirmar que no aparecen placeholders bloqueantes tipo:
   - botones primarios deshabilitados sin alternativa;
   - paneles vacíos que sustituyen una funcionalidad implementada;
   - texto de stub/placeholder como experiencia principal.
7. Guardar el proyecto.
8. Cerrar y reabrir la app.
9. Abrir el mismo JSON.

### Esperado

- La app abre, navega y guarda/carga sin pérdida obvia.
- El grafo sigue siendo vista, no fuente de datos.
- Los cambios visibles sobreviven a cerrar/abrir proyecto.
- Si queda deuda UX menor, anotarla; si impide flujo principal, marcar FALLA.

## 4. B31 — Experiencia inmersiva Desktop

Objetivo: repetir la validación visual base B31 en el estado actual.

### Pasos

1. En Home, observar si la pantalla principal es inmersiva/minimalista.
2. Confirmar que modo normal no muestra de entrada:
   - IDs técnicos;
   - JSON;
   - schema;
   - provider/fallback IA técnico;
   - contadores técnicos invasivos.
3. Navegar Home → Creación.
4. Seleccionar un nodo si existe o crear uno en B33 antes de volver a este punto.
5. Confirmar que el detalle se abre en panel interno/RightDrawer, no en ventana modal externa.
6. Volver a Home.
7. Confirmar que se limpian paneles contextuales/overlays que no pertenecen a Home.
8. Activar modo avanzado si existe el control.
9. Confirmar que entonces sí pueden aparecer datos técnicos razonables.
10. Desactivar modo avanzado.

### Esperado

- En modo normal, la app prioriza lenguaje de autor/producto.
- Los paneles se abren dentro de la app.
- Modo avanzado separa datos técnicos de la UX normal.
- No hay `QDialog`/ventanas externas en flujo normal de creación/edición.

## 5. B32 — Hardening / UX normal vs avanzado / deuda visible

Objetivo: validar que la limpieza de deuda y separación normal/avanzado no regresó.

### Pasos

1. En modo normal, revisar Creación, Galería y Configuración.
2. Buscar etiquetas técnicas como:
   - `Corpus técnico`;
   - `Relaciones técnicas`;
   - `Candidatos técnicos`;
   - IDs visibles sin necesidad.
3. Activar modo avanzado.
4. Confirmar que si existen vistas técnicas, están detrás del modo avanzado.
5. Revisar que la navegación normal aún permite crear/editar contenido sin depender del modo avanzado.

### Esperado

- El modo normal no queda inutilizado por ocultar demasiado.
- Lo técnico queda accesible sólo en avanzado.
- No hay deuda nueva visible que bloquee flujos primarios.

## 6. B33 — Creación MVP: hojas, relaciones, IA inline y persistencia

Objetivo: validar que Creación permite crear elementos reales y que IA inline no canoniza sola.

### Pasos

1. Ir a Creación.
2. Crear una Hoja/personaje llamada `Devian`.
3. Crear una Hoja/personaje llamada `Akshan`.
4. Crear una relación entre ambos con descripción `Devian traiciona a Akshan`.
5. Seleccionar `Devian`.
6. Confirmar que aparece su panel de detalle.
7. Editar algún texto descriptivo.
8. Usar una acción IA inline de redacción/mejora si está visible.
9. Confirmar que la IA muestra sugerencia/previsualización/error visible, pero no crea canon automáticamente.
10. Aceptar manualmente una sugerencia si el flujo lo permite.
11. Guardar proyecto.
12. Cerrar y reabrir el JSON.

### Esperado

- Devian y Akshan reaparecen tras recarga.
- La relación reaparece en grafo/lista.
- La IA inline no crea nodos fantasma ni candidatos indelebles.
- Los candidatos/sugerencias no se muestran como entidades reales hasta aceptación explícita.

## 7. B34 — Árboles/Ramas y contexto jerárquico

Objetivo: validar árboles/ramas, pertenencia, collapse/expand y deuda visual conocida.

### Pasos

1. En Creación, crear una Rama/agrupación llamada `Bosque de Ceniza`.
2. Añadir `Devian` y/o `Santuario del Núcleo Negro` como miembros de esa Rama si el flujo lo permite.
3. Seleccionar la Rama.
4. Confirmar que el panel muestra identidad, función narrativa, contenido/miembros y acciones relacionadas.
5. Probar expandir/colapsar la Rama si existe control visual.
6. Intentar crear una relación interna Rama → Hoja o Hoja → Rama.
7. Intentar una operación que pudiera generar ciclo árbol→árbol si el flujo lo expone.

### Esperado

- La Rama agrupa sin convertirse en carpeta técnica.
- Los miembros se ven o se infieren visualmente.
- Collapse/expand funciona al menos durante la sesión.
- No se permite crear ciclos inválidos.
- Si el layout es imperfecto, anotar como deuda DC-034; no marcar FALLA salvo que impida trabajar.

## 8. B35 — Coherencia de subgrafo

Objetivo: validar análisis de coherencia y reparación revisable.

### Pasos

1. Seleccionar un subgrafo con `Devian`, `Akshan`, `Hermandad del Acero` y al menos una relación.
2. Abrir panel/acción de coherencia si está visible.
3. Ejecutar análisis de coherencia.
4. Revisar que el resultado distingue al menos:
   - contradicciones;
   - huecos de motivación;
   - oportunidades de reparación.
5. Si existe acción de reparar, ejecutarla.
6. Confirmar que la reparación queda como propuesta/candidato/sugerencia revisable.
7. Aceptar o descartar manualmente una propuesta.

### Esperado

- El análisis no modifica canon directamente.
- La reparación no crea cambios irreversibles sin aceptación.
- El resultado usa contexto visible/jerárquico cuando hay Rama seleccionada.

## 9. B36 — Worldbuilding por capas causales

Objetivo: validar capas causales, relaciones causales e IA causal.

### Pasos

1. Activar Worldbuilding si existe interruptor de proyecto.
2. Confirmar que aparece control `Vista Capas causales` o equivalente.
3. Activar vista por capas.
4. Crear/asignar una capa/anillo para `Metafísica de los Dioses-Agujero` si el flujo lo permite.
5. Asignar `Santuario del Núcleo Negro` a una capa inferior o relacionada.
6. Crear una relación causal usando alguno de estos tipos si están disponibles:
   - `deriva_de` / Deriva de;
   - `condiciona` / Condiciona;
   - `explica` / Explica;
   - `contradice` / Contradice;
   - `produce_consecuencia_en` / Produce consecuencia en.
7. Seleccionar una Hoja/Rama con capa asignada.
8. Probar acción IA `Expandir hacia capa inferior` si aparece.
9. Probar acción IA `Explicar desde causas superiores` si aparece.

### Esperado

- El control de capas sólo aparece con Worldbuilding ON.
- Los elementos se ordenan/agrupan visualmente por capa causal.
- Las relaciones causales se diferencian de pertenencia estructural.
- Las acciones IA producen sugerencias/previews, no canon automático.
- Worldbuilding OFF oculta controles sin borrar capas existentes.

## 10. B37 — Creación a escala: búsqueda, filtros, foco, cámara, bandeja

Objetivo: validar que Creación sigue usable al crecer el grafo.

### Pasos

1. Crear algunos elementos extra si el grafo está pequeño:
   - 3 personajes/hojas;
   - 2 ramas;
   - 3 relaciones;
   - 2 capas/anillos si Worldbuilding está activo.
2. Usar búsqueda con término `Devian`.
3. Usar búsqueda con término parcial que exista en descripción o tipo.
4. Aplicar filtros por tipo de entidad.
5. Aplicar filtros por tipo/familia de relación.
6. Aplicar filtros por capa/anillo si están disponibles.
7. Aplicar filtros por canon/visibilidad si están disponibles.
8. Seleccionar una Rama y usar `Enfocar árbol` si existe.
9. Seleccionar una Hoja y usar `Enfocar vecindad` si existe.
10. Probar cámara:
    - centrar selección;
    - encajar todo;
    - reset.
11. Revisar la bandeja unificada de sugerencias/candidatos IA.
12. Mover el ratón al borde izquierdo del canvas para abrir el flyout de capas si está implementado.

### Esperado

- Búsqueda/filtros no borran datos; sólo cambian vista.
- Se puede volver a ver todo el grafo.
- Foco y cámara son reversibles.
- La bandeja muestra sugerencias/candidatos sin canonizarlos.
- El flyout de capas aparece sin bloquear el canvas.

## 11. B38 — Command bar IA y jobs revisables

Objetivo: validar command bar provider-backed, jobs, progreso y no-canon automático.

### Precondición IA

- Si hay provider real configurado, se espera resultado real.
- Si no hay provider, el job debe fallar de forma clara; no debe simular éxito.

### Smoke A — personajes tragicómicos

1. En Creación, localizar la command bar IA.
2. Escribir:

```text
Créame tres personajes que sean hermanos, todos traidores entre sí, en tono tragicómico.
```

3. Confirmar que aparece un job en `Jobs` / `Tareas IA`.
4. Confirmar que la UI no se congela.
5. Confirmar progreso por fases si está visible.
6. Abrir resultado.
7. Confirmar que el resultado respeta hermanos + traición mutua + tono tragicómico.
8. Confirmar que no crea nodos reales automáticamente.
9. Enviar/convertir a candidatos si el flujo lo permite.
10. Aceptar un candidato y confirmar que entonces sí crea entidad real.
11. Rechazar otro y confirmar que no crea entidad.

### Smoke B — sistema metafísico

1. Escribir:

```text
Crea un sistema metafísico basado en dos agujeros negros que son dioses combatiendo.
```

2. Confirmar que no devuelve los mismos personajes del smoke anterior.
3. Confirmar que habla de agujeros negros, dioses, combate y consecuencias.
4. Confirmar que queda revisable.

### Smoke C — error provider

1. Si es seguro hacerlo, desconfigurar temporalmente provider/API key o usar provider inválido.
2. Lanzar una petición simple.
3. Confirmar estado `failed` con error claro.
4. Confirmar que no aparece contenido falso como éxito.
5. Restaurar configuración.

### Esperado

- Prompt real llega al provider.
- Prompts distintos producen resultados distintos.
- Job visible y no bloqueante.
- No hay canon automático.
- Error provider no simula contenido.

## 12. B39 — Modelo visible Hoja/Rama/Anillo

Objetivo: validar lenguaje visible simplificado sin romper modelo interno.

### Pasos

1. Recorrer Creación, panel de nodo, panel de árbol/rama, panel de capa/anillo y configuración.
2. Confirmar que el lenguaje normal usa:
   - Hoja para individuo/elemento;
   - Rama para agrupación;
   - Anillo para capa causal/estrato;
   - Relación para vínculo;
   - Candidato para propuesta.
3. Confirmar que no aparecen términos técnicos como `EntityType.CONTENEDOR`, `NarrativeEntity`, `WorldLayer` en modo normal.
4. Convertir una Hoja a Rama si el control existe.
5. Convertir una Rama a Anillo si el control existe.
6. Confirmar que la transformación es explícita y no destructiva.

### Esperado

- UX normal usa Hoja/Rama/Anillo.
- Los datos no desaparecen al transformar.
- Si modo avanzado muestra nombres internos, no es fallo.

## 13. B40 — Configuración creativa + Wizard

Objetivo: validar wizard inicial, panel de configuración y herencia creativa.

### Pasos — Wizard

1. Crear proyecto nuevo desde Home o menú Proyecto.
2. Confirmar que aparece wizard de creación.
3. Recorrer los 8 pasos esperados si están visibles:
   - bienvenida/preset;
   - género;
   - mundo;
   - dirección;
   - narrativa;
   - estilo;
   - reglas/canon;
   - IA.
4. Aplicar un preset creativo.
5. Elegir ruta JSON explícita.
6. Finalizar.
7. Confirmar que el proyecto abierto corresponde a ese JSON elegido.
8. Confirmar que el grafo inicial está vacío o sólo con datos aceptados explícitamente.
9. Confirmar que presets/candidatos no aparecen como entidades indelebles.

### Pasos — Panel config

1. Abrir configuración del proyecto.
2. Confirmar 9 secciones/tabs aproximadas:
   - Básico;
   - Dirección;
   - Narrativa;
   - Estilo;
   - Reglas;
   - IA;
   - Evitar / espacio negativo;
   - Memoria / gustos;
   - Ramas.
3. Editar un campo visible, por ejemplo premisa/resumen/tono.
4. Guardar.
5. Cerrar y reabrir proyecto.
6. Confirmar que el campo persiste.
7. En una Rama, revisar si existen overrides creativos.
8. Confirmar que la IA contextual refleja el perfil creativo cuando se ejecuta una sugerencia.

### Esperado

- Wizard no pierde ruta de guardado.
- Proyecto nuevo no se contamina con candidatos como canon.
- Config creativa persiste.
- La configuración alimenta IA como contexto, sin obligar a canonizar.

## 14. B41 — Hitos causales

Objetivo: validar creación, visualización y revisión de hitos causales.

### Pasos

1. En Creación o panel causal, localizar opción de `Hitos causales` / `Milestones causales` / `Hito`.
2. Crear un hito llamado:

```text
Nacimiento del Núcleo Negro
```

3. Asociarlo a `Metafísica de los Dioses-Agujero` o a una capa/anillo si el flujo lo permite.
4. Confirmar que aparece en panel/lista/grafo correspondiente.
5. Seleccionar elementos del grafo y usar `Crear hito desde selección` si existe.
6. Probar una acción IA de clasificación/intención de hito si está visible.
7. Probar reviewer de candidato de hito si aparece en bandeja/candidatos.
8. Probar `status quo explainer` o explicación del estado actual si está visible.
9. Guardar, cerrar y reabrir.

### Esperado

- El hito persiste tras recarga.
- Los hitos no duplican entidades core salvo diseño explícito.
- La IA propone/revisa; no canoniza automáticamente.
- El hito se integra con grafo/contexto causal.

## 15. B42 — Hardening IA: gateway, sanitización, validación, observabilidad

Objetivo: validar desde UI que la IA endurecida no filtra, no simula éxito y comunica errores.

### Pasos

1. Abrir Ajustes IA si existe.
2. Confirmar que no se muestran API keys completas en claro en paneles normales.
3. Ejecutar una petición IA desde command bar o panel inline.
4. Si el provider está configurado, confirmar resultado revisable.
5. Si el provider falla, confirmar error claro.
6. Buscar si existe panel/log/diagnóstico IA en modo avanzado.
7. Confirmar que no expone API keys completas ni secretos en observabilidad.
8. Repetir una petición que produciría candidato duplicado.
9. Confirmar que duplicados se marcan/deduplican o no se muestran como copias indistinguibles.

### Esperado

- No hay éxito simulado cuando provider falla.
- No se filtran secretos/API keys en UI normal.
- La observabilidad es útil pero segura.
- Las salidas IA inválidas se muestran como error o resultado no aceptable, no como canon.

## 16. B43 — Prompt Registry y migración de prompts IA

Objetivo: validar que los flujos migrados siguen funcionando sin prompts inline rotos.

### Pasos

1. Ejecutar command bar IA con un prompt simple.
2. Ejecutar IA inline sobre una Hoja.
3. Ejecutar IA inline sobre una Relación si existe.
4. Ejecutar análisis de coherencia.
5. Ejecutar reparación de coherencia si existe.
6. En todos los casos, observar el texto mostrado al usuario.

### Esperado

- No aparecen placeholders de prompt como `{context}`, `{selection}`, `{language}` sin sustituir.
- No aparece texto técnico del registry en UX normal.
- Command bar, inline leaf, inline relation, coherence y repair siguen respondiendo o fallando de forma visible.
- Nada se canoniza automáticamente.

## 17. Persistencia final cross-bloque

Objetivo: confirmar que lo creado durante la prueba sobrevive a cierre/apertura.

### Pasos

1. Guardar proyecto.
2. Cerrar la aplicación.
3. Reabrir con:

```powershell
python -m hosts.DesktopHostPySide.main
```

4. Abrir el JSON `QA_B30_B43_Visual.json`.
5. Verificar que persisten:
   - Devian;
   - Akshan;
   - Hermandad del Acero;
   - Bosque de Ceniza;
   - Santuario del Núcleo Negro;
   - relaciones creadas;
   - ramas/árboles;
   - capas/anillos;
   - configuración creativa;
   - hitos causales;
   - candidatos aceptados;
   - candidatos rechazados no convertidos en canon.

### Esperado

- Todo elemento aceptado explícitamente persiste.
- Lo rechazado o pendiente no aparece como canon.
- El grafo reconstruye desde entidades/relaciones reales.

## 18. Resultado final de la prueba

Completar al finalizar:

```text
Fecha ejecución:
Windows / Python / rama:
Proyecto JSON usado:

Resultado global: PASA / NO PASA / PASA CON DEUDA

Bloqueantes:
1.
2.
3.

Deuda visual no bloqueante:
1.
2.
3.

Capturas tomadas:
1.
2.
3.

Decisión:
[ ] B36-B43 pueden marcarse Windows OK.
[ ] Hay que abrir bloque/ticket de hardening Windows.
[ ] Hay bugs concretos; adjuntar sección con pasos exactos.
```

## 19. Formato recomendado para reportar fallos

Para cada fallo, usar:

```text
Bloque:
Sección de esta guía:
Comando / pantalla:
Pasos exactos:
Resultado esperado:
Resultado observado:
Traceback/log si existe:
Captura:
Severidad: bloqueante / media / baja
```

## 20. Criterio de aceptación global

La prueba pasa si:

- La app arranca en Windows nativo.
- Se puede crear/abrir/guardar/reabrir proyecto.
- Creación permite trabajar con Hojas, Ramas, Relaciones, Anillos/capas e Hitos.
- Búsqueda/filtros/foco/cámara son reversibles.
- IA produce resultados revisables o errores claros.
- Ningún flujo IA canoniza automáticamente.
- Configuración creativa persiste y no contamina el grafo inicial.
- Modo normal no expone datos técnicos innecesarios.
- Modo avanzado conserva acceso técnico si hace falta.
- La persistencia final conserva sólo lo aceptado explícitamente.
