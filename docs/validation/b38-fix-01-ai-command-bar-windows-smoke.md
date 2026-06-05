# B38-FIX-01 — Prueba visual Windows: AI Command Bar real

Fecha: 2026-06-05
Estado: pendiente de validación Windows nativa por el usuario.

## Objetivo

Validar que la command bar IA usa el prompt real, ejecuta jobs en segundo plano, muestra progreso y deja resultados revisables sin canonizar automáticamente.

## Precondiciones

- Ejecutar en Windows nativo con entorno local del proyecto.
- Abrir la app con:
  - `python -m hosts.DesktopHostPySide.main`
- Tener un proyecto abierto en Creación.
- Si se quiere resultado IA real, configurar provider real en Ajustes IA.
- Si el provider no está configurado o falla, el job debe quedar `failed`; no debe inventar contenido simulado.

## Smoke 1 — Prompt sensible: hermanos traidores tragicómicos

1. Entrar en Creación.
2. En la command bar escribir:
   `Créame tres personajes que sean hermanos, todos traidores entre sí, en tono tragicómico.`
3. Confirmar que aparece un job en `Jobs` / `Tareas IA`.
4. Confirmar que la app no se congela y la command bar queda usable.
5. Confirmar progreso por fases:
   - Construyendo contexto…
   - Interpretando petición…
   - Consultando IA…
   - Preparando candidatos…
   - Listo para revisar
6. Abrir resultado.
7. Confirmar que respeta:
   - hermanos;
   - traición mutua;
   - tono tragicómico.
8. Confirmar que no crea nodos reales automáticamente.
9. Enviar candidatos a sugerencias.
10. Aceptar un candidato.
11. Confirmar que se crea un nodo real.
12. Rechazar/descartar otro.
13. Confirmar que no se crea.

## Smoke 2 — Worldbuilding/metafísica no devuelve personajes fijos

1. En la command bar escribir:
   `Crea un sistema metafísico basado en dos agujeros negros que son dioses combatiendo.`
2. Confirmar que aparece job y progreso.
3. Confirmar que el resultado habla de:
   - agujeros negros;
   - dioses;
   - combate;
   - consecuencias metafísicas/naturales.
4. Confirmar que no devuelve los mismos tres personajes del smoke anterior.
5. Confirmar que todo queda como candidatos/informe revisable.

## Smoke 3 — Revisión de grafo sin mutación

1. En la command bar escribir:
   `Revisa todo el grafo y proponme mejoras.`
2. Confirmar job largo/no bloqueante.
3. Confirmar panel de Jobs con estado/progreso.
4. Confirmar informe estructurado de mejoras.
5. Confirmar que no crea ni modifica nodos, relaciones, árboles, capas o cuerpos automáticamente.
6. Si el informe aclara límite de análisis por resumen visible/contexto relevante, eso es válido para MVP.

## Smoke 4 — Relaciones para entidades concretas

1. Si existen Devian y Hermandad del Acero, escribir:
   `Propón relaciones para Devian dentro de la Hermandad del Acero.`
2. Confirmar que el scope usa Devian/Hermandad si existen.
3. Confirmar candidatos de relación, no personajes genéricos.
4. Confirmar que aceptar candidato usa servicios reales y que rechazar no muta canon.

## Smoke 5 — Error de provider

1. Desconfigurar temporalmente API key/base URL o usar provider inválido.
2. Lanzar una petición desde command bar.
3. Confirmar que el job queda `failed` con error inline claro.
4. Confirmar que no aparece contenido falso ni simulado como éxito.
5. Restaurar configuración IA real.

## Criterio de aceptación Windows

- [ ] Prompt real usado como instrucción principal.
- [ ] Prompts distintos producen resultados distintos y alineados.
- [ ] Job aparece en panel `Jobs`.
- [ ] UI no se congela.
- [ ] Progreso por fases visible.
- [ ] Resultado revisable antes de canonizar.
- [ ] No hay canon automático.
- [ ] Error provider no simula éxito.

## Resultado

Pendiente de completar por el usuario tras prueba Windows nativa.
