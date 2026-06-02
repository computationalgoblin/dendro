# Performance B29 — corpus grande simulado

## Alcance

Fixture reproducible para medir robustez básica en WSL sin degradar la suite normal.

Script:

```bash
python scripts/generate_large_project.py --help
python scripts/generate_large_project.py --output /tmp/large.json --entities 500 --relations 1000 --history 250
```

## Output real B29-T03

```text
Wrote /tmp/tmp.FV1TY3jlWS/large.json entities=500 relations=1000 history=250
load_seconds=0.0162
diagnostic_seconds=0.0107
entities=500 relations=1000 history=250
bytes=1259700
```

## Umbrales B29

- Generador determinista: IDs estables por índice.
- Diagnóstico + grafo para 250 entidades / 500 relaciones: < 2.0s en test automatizado.
- Load + diagnóstico para 500 entidades / 1000 relaciones / 250 historial: medido en WSL en < 0.1s cada uno.

## Notas

Estos valores son baseline local WSL, no equivalen a validación Windows Desktop. B29 no declara optimización estructural adicional porque no se detectó cuello de botella con el corpus simulado.
