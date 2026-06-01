# Desktop UI Manual Test B27.3

Instrucciones generales
- Abrir el proyecto smoke generado por `scripts/smoke_desktop_b27_3.ps1`.
- El script genera un archivo único por timestamp en `C:\dev\narrative-architect\local_ui_bugbash\`.
- Leer la ruta final en `C:\dev\narrative-architect\local_ui_bugbash\latest_project_path.txt`.
- Ejemplo de nombre esperado: `C:\dev\narrative-architect\local_ui_bugbash\desktop_ui_bugbash_project_YYYYMMDD_HHMMSS.json`.
- En cada paso marcar una de estas opciones:
  - OK
  - FALLA
  - NO APLICA
  - DIFERIDO
- Si falla, capturar:
  - pantalla
  - acción exacta
  - resultado observado
  - traceback/log visible
  - si bloquea o no el cierre del bloque

## A. Arranque
1. Acción UI: lanzar la app Desktop.
   - Esperado: la app arranca sin traceback ni cierre inmediato.
   - Si falla marcar: FALLA A1 — arranque.
2. Acción UI: mirar topbar.
   - Esperado: muestra proyecto, schema y provider IA real/simulated con razón legible.
   - Si falla marcar: FALLA A2 — topbar/provider.
3. Acción UI: confirmar LogPanel.
   - Esperado: LogPanel visible y usable.
   - Si falla marcar: FALLA A3 — log panel.

## B. Project
1. Acción UI: abrir proyecto smoke.
   - Esperado: carga el JSON smoke sin traceback.
   - Si falla marcar: FALLA B1 — open project.
2. Acción UI: guardar proyecto.
   - Esperado: save exitoso y sin error silencioso.
   - Si falla marcar: FALLA B2 — save.
3. Acción UI: cerrar y reabrir la app / proyecto.
   - Esperado: no hay pérdida de datos.
   - Si falla marcar: FALLA B3 — reopen persistence.
4. Acción UI: revisar counts del dashboard/topbar.
   - Esperado: counts coherentes con smoke (entidades, relaciones, campaigns, secrets, clues, factions, sessions, writing, baskets).
   - Si falla marcar: FALLA B4 — counts.

## C. Entities
1. Acción UI: abrir pantalla Corpus y listar entidades.
   - Esperado: aparecen personaje, localización, facción y objeto del smoke.
   - Si falla marcar: FALLA C1 — entity list.
2. Acción UI: doble click sobre una entidad.
   - Esperado: abre ficha completa.
   - Si falla marcar: FALLA C2 — entity detail open.
3. Acción UI: inspeccionar ficha.
   - Esperado: muestra id completo, name, type, canon, visibility, descripción, metadata.
   - Si falla marcar: FALLA C3 — entity detail content.
4. Acción UI: revisar relaciones vinculadas desde la ficha.
   - Esperado: aparecen relaciones de la entidad seleccionada.
   - Si falla marcar: FALLA C4 — linked relations.
5. Acción UI: editar entidad.
   - Esperado: cambios persistidos tras refrescar.
   - Si falla marcar: FALLA C5 — entity edit.
6. Acción UI: archive/restore si existe el botón.
   - Esperado: estado cambia realmente.
   - Si falla marcar: FALLA C6 — entity archive/restore.

## D. Relations
1. Acción UI: abrir pantalla Relations y listar relaciones.
   - Esperado: aparece la relación smoke creada.
   - Si falla marcar: FALLA D1 — relation list.
2. Acción UI: doble click sobre una relación.
   - Esperado: abre ficha completa.
   - Si falla marcar: FALLA D2 — relation detail open.
3. Acción UI: inspeccionar ficha.
   - Esperado: source/target con nombres, type, metadata e id completo.
   - Si falla marcar: FALLA D3 — relation detail content.
4. Acción UI: crear relación nueva.
   - Esperado: se agrega realmente y persiste.
   - Si falla marcar: FALLA D4 — relation create.
5. Acción UI: editar/archive si existe.
   - Esperado: el cambio se refleja en lista y detalle.
   - Si falla marcar: FALLA D5 — relation edit/archive.

## E. Candidates
1. Acción UI: abrir Candidates y listar candidates.
   - Esperado: aparece el candidate smoke y/o los candidatos derivados del import.
   - Si falla marcar: FALLA E1 — candidate list.
2. Acción UI: probar filtros state/type/source.
   - Esperado: filtran realmente la lista.
   - Si falla marcar: FALLA E2 — candidate filters.
3. Acción UI: ver detalle.
   - Esperado: se puede inspeccionar el contenido propuesto.
   - Si falla marcar: FALLA E3 — candidate detail.
4. Acción UI: Accept.
   - Esperado: cambia estado real y no duplica entidad/relación indebidamente.
   - Si falla marcar: FALLA E4 — candidate accept.
5. Acción UI: Reject.
   - Esperado: cambia estado real.
   - Si falla marcar: FALLA E5 — candidate reject.
6. Acción UI: ejecutar un CAMBIO_ESTADO.
   - Esperado: no duplica entidad/relación ya existente.
   - Si falla marcar: FALLA E6 — state change duplicate.
7. Acción UI: provocar una acción no soportada si aplica.
   - Esperado: error visible en UI/log, no silencio.
   - Si falla marcar: FALLA E7 — hidden error.

## F. Import
1. Acción UI: seleccionar `import_smoke.txt`.
   - Esperado: no TypeError y no traceback.
   - Si falla marcar: FALLA F1 — file selection/import crash.
2. Acción UI: completar import.
   - Esperado: `ImportService.import_document` recibe format correcto (`txt`) y crea basket.
   - Si falla marcar: FALLA F2 — wrong import format.
3. Acción UI: abrir basket/show.
   - Esperado: candidates visibles.
   - Si falla marcar: FALLA F3 — basket show.
4. Acción UI: Accept import candidate.
   - Esperado: crea Candidate B14 pendiente, no canon directo.
   - Si falla marcar: FALLA F4 — accept import candidate.
5. Acción UI: Reject import candidate.
   - Esperado: no crea Candidate.
   - Si falla marcar: FALLA F5 — reject import candidate.
6. Acción UI: edit/merge si existe.
   - Esperado: opera sobre IDs reales y deja evidencia visible.
   - Si falla marcar: FALLA F6 — edit/merge import.

## G. Campaign
1. Acción UI: crear campaña desde UI.
   - Esperado: alta real sin traceback.
   - Si falla marcar: FALLA G1 — campaign create.
2. Acción UI: ver campaña en lista.
   - Esperado: aparece y puede seleccionarse.
   - Si falla marcar: FALLA G2 — campaign list.
3. Acción UI: ver detail/overview.
   - Esperado: overview real con datos de campaña.
   - Si falla marcar: FALLA G3 — campaign overview.
4. Acción UI: añadir jugador/PC si existe.
   - Esperado: alta real.
   - Si falla marcar: FALLA G4 — campaign player/pc.
5. Acción UI: crear/avanzar clock si existe.
   - Esperado: clock real y persistido.
   - Si falla marcar: FALLA G5 — clock flow.
6. Acción UI: crear sesión seleccionando campaign_id real.
   - Esperado: session queda vinculada a campaña.
   - Si falla marcar: FALLA G6 — session campaign link.

## H. Factions
1. Acción UI: crear entidad tipo facción.
   - Esperado: aparece como entidad normal.
   - Si falla marcar: FALLA H1 — faction entity create.
2. Acción UI: abrir Faction view.
   - Esperado: una entidad FACCION sin extensión aparece como pendiente o detectable.
   - Si falla marcar: FALLA H2 — pending faction entity.
3. Acción UI: crear extension Faction desde UI.
   - Esperado: la facción pasa a gestionable.
   - Si falla marcar: FALLA H3 — faction extension create.
4. Acción UI: ally/enemy.
   - Esperado: relaciones de alianza/enemistad se guardan.
   - Si falla marcar: FALLA H4 — ally/enemy.
5. Acción UI: front/stage/clock si existe.
   - Esperado: flujo real, no placeholder.
   - Si falla marcar: FALLA H5 — front/stage/clock.

## I. Secrets/Clues
1. Acción UI: crear secreto o abrir el existente.
   - Esperado: visible y persistente.
   - Si falla marcar: FALLA I1 — secret create/show.
2. Acción UI: crear pista o abrir la existente.
   - Esperado: visible y persistente.
   - Si falla marcar: FALLA I2 — clue create/show.
3. Acción UI: reveal/deliver.
   - Esperado: estados cambian realmente.
   - Si falla marcar: FALLA I3 — reveal/deliver.
4. Acción UI: revisar estados visibles.
   - Esperado: se muestran revelation_state / delivery_state correctos.
   - Si falla marcar: FALLA I4 — state visibility.
5. Acción UI: knowledge queries si existen.
   - Esperado: salida coherente y sin traceback.
   - Si falla marcar: FALLA I5 — knowledge query.
6. Acción UI: detect issues.
   - Esperado: issues reales visibles.
   - Si falla marcar: FALLA I6 — secret/clue detect issues.

## J. Issues
1. Acción UI: ejecutar validación global.
   - Esperado: genera/actualiza issues visibles.
   - Si falla marcar: FALLA J1 — global validation.
2. Acción UI: ejecutar writing check.
   - Esperado: issues writing visibles si aplica.
   - Si falla marcar: FALLA J2 — writing check.
3. Acción UI: ejecutar secret detect-issues, faction detect-issues y session check si existen.
   - Esperado: resultados visibles.
   - Si falla marcar: FALLA J3 — specialized validators.
4. Acción UI: revisar tabla de issues.
   - Esperado: no duplica issues equivalentes si el servicio lo evita.
   - Si falla marcar: FALLA J4 — issue duplication.
5. Acción UI: resolver/cerrar si existe.
   - Esperado: transición real.
   - Si falla marcar: FALLA J5 — issue resolve/close.

## K. IA
1. Acción UI: configurar env vars OpenCode Zen.
   - Esperado: topbar muestra `openai_compatible/<model>` y no `simulated`.
   - Si falla marcar: FALLA K1 — provider label.
2. Acción UI: pulsar Test provider.
   - Esperado: funciona o muestra error real sin imprimir API key.
   - Si falla marcar: FALLA K2 — provider test.
3. Acción UI: generar candidate desde IA si existe el flujo.
   - Esperado: crea Candidate real.
   - Si falla marcar: FALLA K3 — AI candidate generation.
4. Acción UI: writing expand/critique/rewrite si existen.
   - Esperado: usan provider real.
   - Si falla marcar: FALLA K4 — AI writing.
5. Acción UI: live improvise.
   - Esperado: usa provider real o muestra razón concreta del fallback.
   - Si falla marcar: FALLA K5 — AI live improvise.

## L. Sessions
1. Acción UI: crear sesión.
   - Esperado: alta real.
   - Si falla marcar: FALLA L1 — session create.
2. Acción UI: añadir escena.
   - Esperado: escena visible y persistida.
   - Si falla marcar: FALLA L2 — scene add.
3. Acción UI: reordenar/eliminar escena.
   - Esperado: cambio real.
   - Si falla marcar: FALLA L3 — scene reorder/remove.
4. Acción UI: link clue/secret/faction/clock/entity.
   - Esperado: links reales.
   - Si falla marcar: FALLA L4 — session links.
5. Acción UI: summary/check/issues.
   - Esperado: resultados reales y visibles.
   - Si falla marcar: FALLA L5 — session summary/check/issues.
6. Acción UI: suggest material.
   - Esperado: Candidate real.
   - Si falla marcar: FALLA L6 — session suggest.

## M. Live
1. Acción UI: Open live.
   - Esperado: sesión activada.
   - Si falla marcar: FALLA M1 — live activate.
2. Acción UI: Quick note.
   - Esperado: nota visible en metadata/live o evidenciada por flujo posterior.
   - Si falla marcar: FALLA M2 — live quick note.
3. Acción UI: Decision/event/consequence.
   - Esperado: cada acción muta metadata real.
   - Si falla marcar: FALLA M3 — live text actions.
4. Acción UI: provisional entity / provisional relation.
   - Esperado: se crean con metadata live real, no IDs hardcodeados.
   - Si falla marcar: FALLA M4 — provisional artifacts.
5. Acción UI: deliver clue / reveal secret con selector real.
   - Esperado: opera con IDs reales.
   - Si falla marcar: FALLA M5 — live clue/secret selectors.
6. Acción UI: improvise con contexto real.
   - Esperado: resultado visible y trazable.
   - Si falla marcar: FALLA M6 — live improvise.
7. Acción UI: Done/prepare post.
   - Esperado: resume metadata live para post-session.
   - Si falla marcar: FALLA M7 — prepare post.

## N. Post-session
1. Acción UI: Close session.
   - Esperado: estado completada.
   - Si falla marcar: FALLA N1 — close session.
2. Acción UI: private/player summary.
   - Esperado: textos reales.
   - Si falla marcar: FALLA N2 — summaries.
3. Acción UI: convert live to candidates.
   - Esperado: candidates reales.
   - Si falla marcar: FALLA N3 — live to candidates.
4. Acción UI: ejecutar dos veces.
   - Esperado: no duplica candidates ya convertidos.
   - Si falla marcar: FALLA N4 — duplicate post candidates.
5. Acción UI: post source.
   - Esperado: source real creado.
   - Si falla marcar: FALLA N5 — post source.
6. Acción UI: seeds.
   - Esperado: lista utilizable.
   - Si falla marcar: FALLA N6 — post seeds.
7. Acción UI: accept/reject post candidates.
   - Esperado: cambia estado real.
   - Si falla marcar: FALLA N7 — post accept/reject.

## O. Export
1. Acción UI: Export all GM.
   - Esperado: incluye material GM.
   - Si falla marcar: FALLA O1 — export gm.
2. Acción UI: Export all Player.
   - Esperado: no filtra menos de la cuenta ni rompe por permisos.
   - Si falla marcar: FALLA O2 — export player.
3. Acción UI: Export all Public.
   - Esperado: no muestra private_notes, gm_objectives ni secretos ocultos.
   - Si falla marcar: FALLA O3 — export public leak.
4. Acción UI: Export entity/session/campaign.
   - Esperado: cada export devuelve salida coherente.
   - Si falla marcar: FALLA O4 — export single.

## P. Writing
1. Acción UI: abrir Writing tree.
   - Esperado: carga sin traceback.
   - Si falla marcar: FALLA P1 — writing tree.
2. Acción UI: crear unidad.
   - Esperado: alta real.
   - Si falla marcar: FALLA P2 — writing create.
3. Acción UI: abrir ficha, editar y guardar.
   - Esperado: persistencia real.
   - Si falla marcar: FALLA P3 — writing edit.
4. Acción UI: link entity / coverage / IA actions si existen.
   - Esperado: flujo real o marcado explícitamente no implementado.
   - Si falla marcar: FALLA P4 — writing links/coverage/AI.

## Q. Timeline / Framework / Domains / Layers
1. Acción UI: abrir cada pantalla.
   - Esperado: no traceback.
   - Si falla marcar: FALLA Q1 — screen open.
2. Acción UI: revisar acciones reales disponibles.
   - Esperado: si no existe funcionalidad real, marcar explícitamente P1/P2 o diferido; no contar como cubierta.
   - Si falla marcar: FALLA Q2 — false coverage.

## Criterio de decisión final del usuario
- Si hay una sola FALLA P0, B27.3 no cierra.
- Si no hay FALLA P0 pero quedan FALLAS P1/P2, documentarlas explícitamente en `docs/desktop_ui_bugbash_B27_3.md` antes de hablar de B28.
