# Bloque I - Importacion narrativa avanzada de documentos

## Objetivo

Transformar la importacion de TXT, Markdown y PDF textual en una pipeline
narrativa robusta que convierta material externo en un lote revisable de
propuestas para Dendro.

La importacion puede proponer hojas, ramas, relaciones, anillos, hitos, aliases,
resumenes, vinculos causales, dudas y referencias a fuente. No puede modificar
canon directamente.

## Principio central

```text
Documento importado -> analisis -> candidates -> revision -> aceptacion -> canon
```

Prohibido:

```text
Documento importado -> entidades canon directas
Documento importado -> relaciones canon directas
Documento importado -> hitos canon directos
```

## Tickets

| Ticket | Titulo | Perfil | Depende de |
|--------|--------|--------|------------|
| I01 | Contrato de importacion narrativa | architecture/application | E05, H07 |
| I02 | Extraccion documental y chunking narrativo | application/infrastructure | I01 |
| I03 | Extraccion IA estructurada desde chunks | ai/application | I02 |
| I04 | Fusion, deduplicacion y resolucion de aliases | application | I03 |
| I05 | Review Workspace de importacion | ui/application | I04 |
| I06 | Integracion con RAG | ai/application | I05, E05 |
| I07 | Importacion end-to-end | qa/architecture | I06 |

## Salidas esperadas

- `ImportBatch`
- `EntityCandidate`
- `BranchCandidate`
- `RelationCandidate`
- `MilestoneCandidate`
- `RingSuggestion`
- `ImportIssue`
- `SourceReference`
- `MergeSuggestion`

## Reglas

- Todo candidate conserva referencias a la fuente original.
- La aceptacion usa servicios normales de aplicacion.
- El rechazo no modifica canon ni borra la fuente.
- La edicion modifica el candidate, no el canon.
- RAG debe distinguir `raw_import`, `reviewed` y `accepted`.
- Los candidates aceptados pueden indexarse como canon.
- Los rejected no se recuperan por defecto.

## Veredicto del bloque

PASS si documentos se extraen, chunks conservan fuente, IA produce candidates
estructurados, deduplicacion funciona, el usuario revisa antes de canon, la
aceptacion crea grafo/hitos, RAG distingue raw/reviewed/canon y no hay
tracebacks.

PARTIAL si TXT/Markdown funciona, PDF textual funciona parcialmente, la
deduplicacion es basica, el review es usable y OCR queda como deuda.

BLOCKED si la importacion crea canon sin revision, se pierden fuentes, la IA
inventa IDs, accepted/rejected no se respetan, el grafo queda corrupto, hay
perdida de datos o la UI queda bloqueada.
