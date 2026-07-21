# Checklist de cierre de BETA — Dendro / Narrative Architect

Fecha del cierre técnico: 2026-07-21. Este documento es el sustituto ligero de la
fase G de validación (cancelada 2026-07-03): define qué debe estar firmado para
declarar la BETA terminada. **Todo lo automático ya está en verde**; la puerta
restante es la batería de smokes manuales del usuario.

## A. Puerta técnica (COMPLETA ✅)

- [x] Tablero sin Backlog / In Progress / Review / Blocked en épicas de beta
      (BETA2-STRUCT completa 7/7; residuos BETA1 resueltos o superados).
- [x] Suites automáticas en verde: `core` (2140) + `arch` (11) + `ui` — **baseline
      rojo eliminado** (antes ~26 rojos crónicos de pins/legacy).
- [x] Deuda técnica a cero en `product_debt_map.md` (DC-AUDIT-03 saldada con
      puertos; resto cerrado/mitigado/descartado con justificación).
- [x] Purga física del legacy IA (command bar, RAG léxico, acciones contextuales,
      `_LEGACY_AI_UI`) — el árbol no arrastra superficie retirada.
- [x] Esquema v39; carga de proyectos antiguos sin pérdida (migraciones v1→v39).
- [x] Capas limpias: guard de arquitectura sin allowlist.

## B. Puerta de usuario (PENDIENTE — smokes en plataforma real)

Ejecutar con `python -m hosts.DesktopHostPySide.main` (ventana real, NO offscreen),
idealmente sobre «La Flor de los Almendros». Los guiones detallados de cada épica
están en su cierre (`.kanban/resumenes/BETA2-*-cierre*.md`); esta es la pasada
consolidada mínima:

1. **Arranque y proyecto** — abrir el proyecto de muestra: carga sin pérdida,
   Mapa fluido (L01), zoom-out hasta panorama y teclas 1..0/`[`/`]`/F (L02).
2. **Foco** — pestañas Ficha/Relaciones/Cultivo, retrato persistente, franja de
   cultivo, navegación por anillos, overlay de edición ⛶ (UI2/FOCO).
3. **Jardín/riego** — badge 💧 global, regar una entidad con proveedor real:
   página de wiki escrita, potencia atribuida, frescura unificada (WIKI/JARDIN).
4. **Semillas** — una Sugerencia con petición libre (con y sin análisis de
   intención *arraigo/iluminada*): plan visible en el floater, semillas germinan,
   aceptar florece canon y rechazar marchita (SEM/WIKI-13).
5. **Estructura** — píldora «⚙ N ajustes»: aceptar un ring_move (Mapa+Crono se
   reconstruyen sin expulsar del Foco y persiste tras recargar), una excepción
   ascendente y un branch_move (arrastra el subárbol); «✨ Proponer estructura»
   crea/fusiona anillos con nombres diegéticos (STRUCT, guion completo en
   `.kanban/resumenes/BETA2-STRUCT-cierre.md`).
6. **Cronología y calendario** — wizard de calendario (2 eras encadenadas,
   presente, meses/semana), pill temporal con filtros, subhitos contenidos,
   hover preview (CAL/SUB/HOVER).
7. **Play** — recorrido completo: escena, parada dura, watchdog >60s con
   «Reintentar», propuesta multi-campo inline, desvío, epílogo (PLAY smokes 1+2).
8. **Retratos** — búsqueda Openverse/DDG, encuadre, render en Foco/Mapa/paneles;
   los assets viajan en `<stem>.assets/` (IMG).
9. **Sin proveedor IA** — quitar las env vars: la app funciona, las acciones IA
   fallan con mensaje claro «IA no configurada», sin éxito fingido (D05).
10. **Persistencia** — cerrar y reabrir: todo lo anterior sobrevive la recarga;
    los backups `.bak` rotan.

## C. Firma

- [ ] Smokes 1–10 superados (lo que falle → ticket de remediación y re-smoke).
- [ ] Tablero: mover los tickets `Testing (pend. smoke usuario)` → `Done`.
- [ ] Declarar BETA cerrada en `roadmap.md` y abrir la fase siguiente.
