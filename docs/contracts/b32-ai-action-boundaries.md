# B32 — Contrato de límites entre IA inline, candidatos, importación e incidencias

Estado: vigente tras B32-DEBT.

## A. IA inline

Uso: ayudar a redactar o revisar texto dentro del panel actual.

Ejemplos:
- cuerpo de entidad en `NodeDetailPanel`
- sugerencia de texto de árbol en `TreeDetailPanel`
- futura sugerencia inline de relación

Reglas:
- Usa `node_text_suggestion` o método inline equivalente.
- No llama a `generate_candidates()`.
- No llama a `run_node_action("improve_text")` desde UI normal.
- No crea `Candidate`.
- No crea nodos ni relaciones.
- Muestra estado visible: generando, error o sugerencia.
- `Aceptar` solo copia texto al formulario; persistencia ocurre al guardar.

## B. Candidatos globales IA

Uso: propuestas que requieren revisión explícita antes de entrar al canon.

Reglas:
- Puede crear `Candidate` no canon.
- Debe pasar por bandeja/revisión.
- Nunca muta canon directamente.
- Debe incluir origen, target, action_type y context_hash.

## C. Importación documental

Uso: documento externo → segmentos → candidatos de importación → revisión.

Reglas:
- No entra al canon directamente.
- Usa `ImportBasket`/`ImportCandidate`.
- En modo normal muestra tarjetas limpias.
- IDs, segmentos y JSON solo en modo avanzado.

## D. Diagnóstico/incidencias

Uso: detectar problemas, contradicciones, deuda narrativa o técnica.

Reglas:
- Produce previews/incidencias, no canon directo.
- No debe estar visible como módulo normal hasta tener UX validada.
- No debe mezclarse con el flujo inline de redacción.

## Prohibición explícita

La UI normal de detalle de entidad/árbol no puede volver a usar `run_node_action("improve_text")` como fallback para texto inline. Si falla el flujo inline, debe mostrar error claro.
