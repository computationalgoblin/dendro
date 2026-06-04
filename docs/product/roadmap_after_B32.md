# Roadmap after B32-DEBT

Estado: B32-DEBT cerrado localmente. No avanzar sin validación visual Windows.

## MVP inmediato de Creación

B33 debe reducir Creación a un flujo estable y verificable:

1. Crear nodos desde ruta normal.
2. Editar nodos desde panel de detalle.
3. IA inline de nodos sin candidatos/nodos/relaciones fantasma.
4. Crear relaciones visuales.
5. Editar relaciones desde panel de detalle.
6. IA inline de relaciones sin candidatos automáticos.
7. Persistencia save/load de nodos, relaciones y texto aceptado.
8. Feedback visible inmediato para acciones IA o errores.

## Orden recomendado

### B33 — Creación MVP estable

Objetivo: que crear/editar nodos y relaciones sea fiable, visible y persistente.

No incluir:
- Galería.
- Sesión.
- worldbuilding por capas.
- nuevas features IA globales.

### B34 — Árboles y contexto jerárquico

Objetivo: árboles como contenedores semánticos estables.

Incluye:
- crear árboles.
- meter/sacar nodos en árboles.
- visualizar membresía.
- persistencia save/load.
- IA usa contexto de árbol.

### B35 — Coherencia de subgrafo

Objetivo: análisis local sobre selección/subgrafo/árbol sin mutar canon.

### B36 — Worldbuilding por capas causales

Objetivo: capas solo si `worldbuilding_active=true`; integradas en grafo e IA contextual.

### B37 — Galería limpia

Objetivo: definir si Galería es exploración narrativa, dossier visual o índice editorial.

### B38 — Sesión/campaña

Objetivo: visible solo para proyectos campaña; preparación/live/post separados y útiles.

## Gate antes de B33

- Compileall OK.
- Arquitectura OK.
- Runner arch/desktop/infra/sanity OK.
- Working tree limpio.
- Prueba visual Windows de Home + Creación + IA inline de entidad.
