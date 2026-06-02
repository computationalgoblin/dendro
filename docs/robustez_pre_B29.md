# Auditoría pre-B29 — deuda, migraciones y robustez

Fecha: 2026-06-02
Rama: feature/B29-robustness-maintenance
Base: B28 commit 078b28b

## 1. Contrato B29 detectado

```text
# Bloque 29 — Revisión, optimización, migraciones y robustez de proyecto

## 29.1 Objetivo

Consolidar el sistema para soportar proyectos grandes, evolución de esquema, migraciones, integridad y mantenimiento a largo plazo.

## 29.2 Robustez

El sistema deberá reforzar:

1. Carga de proyectos grandes.
2. Guardado seguro.
3. Recuperación ante errores.
4. Validación de integridad.
5. Migraciones de esquema.
6. Reparación asistida de datos.
7. Compactación o limpieza si procede.
8. Rendimiento de consultas.
9. Rendimiento de grafo.
10. Rendimiento de búsqueda.
11. Gestión de fuentes grandes.
12. Manejo de documentos importados.
13. Historial voluminoso.
14. Candidatos acumulados.
15. Incidencias acumuladas.

## 29.3 Herramientas internas

La aplicación deberá incluir herramientas de diagnóstico para:

1. Revisar integridad.
2. Detectar referencias rotas.
3. Detectar datos obsoletos.
4. Detectar migraciones pendientes.
5. Medir tamaño del proyecto.
6. Revisar entidades sin uso.
7. Revisar historial excesivo.
8. Exportar diagnóstico.
9. Crear copia de seguridad.
10. Restaurar copia de seguridad.

## 29.4 Criterios de aceptación

El bloque se considerará cerrado cuando:

1. Los proyectos existentes puedan migrarse.
2. La validación de integridad sea fiable.
3. El guardado sea resistente a fallo parcial.
4. Existan pruebas de migración.
5. Existan pruebas de carga con corpus grande simulado.
6. Las consultas críticas mantengan rendimiento aceptable.
7. Exista diagnóstico exportable.
8. El sistema pueda recuperar o informar claramente errores de datos.

## 29.5 Queda fuera de este bloque

Quedan fuera:

1. Multiusuario completo.
2. Cloud sync.
3. Marketplace de plantillas.
4. Plugins externos complejos.

---


```

## 2. Baseline ejecutado

| Nombre | Comando | Exit | Tiempo agente (s) | Output |
|---|---|---:|---:|---|
| architecture | `python -m pytest tests/architecture/ -q` | 0 | 2.26 | `.........                                                                [100%] / 9 passed in 1.59s` |
| collect | `python -m pytest --collect-only -q / tail -1` | 0 | 4.624 | `1441 tests collected in 4.06s` |
| diagnostic-target-absent | `test -f packages/application/diagnostic_service.py; echo diagnostic_service_exists=$?` | 0 | 0.054 | `diagnostic_service_exists=1` |
| backup-target-baseline | `python - <<'PY' / from packages.persistence.store import ProjectStore / print("ProjectStore_create_backup", hasattr(ProjectStore, "create_backup")) / print("ProjectStore_restore_backup", hasattr(ProjectStore, "restore_backup")) / PY` | 0 | 0.425 | `ProjectStore_create_backup False / ProjectStore_restore_backup False` |

## 3. Schema y migraciones

- `CURRENT_SCHEMA_VERSION`: 19
- `MAX_SUPPORTED_VERSION`: 19
- Migraciones declaradas: 18
- Cadena detectada: _apply_migration_v1_to_v2, _apply_migration_v2_to_v3, _apply_migration_v3_to_v4, _apply_migration_v4_to_v5, _apply_migration_v5_to_v6, _apply_migration_v6_to_v7, _apply_migration_v7_to_v8, _apply_migration_v8_to_v9, _apply_migration_v9_to_v10, _apply_migration_v10_to_v11, _apply_migration_v11_to_v12, _apply_migration_v12_to_v13, _apply_migration_v13_to_v14, _apply_migration_v14_to_v15, _apply_migration_v15_to_v16, _apply_migration_v16_to_v17, _apply_migration_v17_to_v18, _apply_migration_v18_to_v19

Riesgo B29: backup/restore y repair-plan deben validar schema antes de sustituir datos. No subir schema salvo necesidad real.

## 4. Deuda consolidada preliminar

Fuente autoritativa: cierres de bloque en `docs/cierres/`; HANDOFF se usa como referencia secundaria.

| Fuente | Línea | ID(s) | Evidencia |
|---|---:|---|---|
| `docs/agents/HANDOFF.md` | 79 | DC-022 | / DC-022 / Deuda global previa; no modificada por B28 / Media / Global / |
| `docs/cierres/bloque-17-cierre.md` | 216 | DC-032 | ### 6.5 Sin test de persistencia real de 'import_baskets' (DC-032) |
| `docs/cierres/bloque-17-cierre.md` | 230 | DC-025 | / DC-025 / 'import review un-reject' no implementado (mencionado en mensajes de error) / Baja / El mensaje de error indica el comando que haría falta. Se implementará cuando haya demanda real. / |
| `docs/cierres/bloque-17-cierre.md` | 231 | DC-026 | / DC-026 / 'import review edit' no implementado / Baja / Editar un candidato antes de aceptar requeriría UI adicional. Postergado. / |
| `docs/cierres/bloque-17-cierre.md` | 232 | DC-027 | / DC-027 / 'import review merge' (fusionar candidatos) no implementado / Baja / El estado FUSIONADO existe en el enum pero no hay operación. Postergado. / |
| `docs/cierres/bloque-17-cierre.md` | 237 | DC-032 | / DC-032 / Sin test automatizado de persistencia real de 'import_baskets' (save/load roundtrip) — los tests usan FakeProjectService / Media / El smoke manual lo cubre, pero la regresión automatizada no. Añadir test con ProjectStore real. / |
| `docs/cierres/bloque-18-cierre.md` | 78 | DC-001..DC-032 | / DC-001..DC-032 / Sin cambios (arrastrada) / — / B19+ / |
| `docs/cierres/bloque-19-cierre.md` | 76 | DC-001..DC-034 | / DC-001..DC-034 / Sin cambios (arrastrada) / — / B20+ / |
| `docs/cierres/bloque-19-cierre.md` | 77 | DC-035 | / DC-035 / IA writing usa provider simulado; falta integración con proveedor IA real y validación de outputs writing / Baja / B27+ / |
| `docs/cierres/bloque-20-cierre.md` | 86 | DC-001..DC-036 | / DC-001..DC-036 / Sin cambios (arrastrada desde B19) / — / B21+ / |
| `docs/cierres/bloque-20-cierre.md` | 87 | DC-037 | / DC-037 / CampaignService sin integración con HistoryService formal (usa campaign.history textual) / Baja / B21+ / |
| `docs/cierres/bloque-21-cierre.md` | 85 | DC-001..DC-036 | / DC-001..DC-036 / Sin cambios (arrastrada) / — / B22+ / |
| `docs/cierres/bloque-21-cierre.md` | 86 | DC-037 | / DC-037 / CampaignService sin HistoryService formal (arrastrada) / Baja / B22+ / |
| `docs/cierres/bloque-21-cierre.md` | 87 | DC-038 | / DC-038 / SecretsService sin integración con HistoryService / Baja / B22+ / |
| `docs/cierres/bloque-22-cierre.md` | 79 | DC-001..DC-036 | / DC-001..DC-036 / Sin cambios (arrastrada) / — / B23+ / |
| `docs/cierres/bloque-22-cierre.md` | 84 | DC-041 | / DC-041 / FactionService sin integración con HistoryService formal / Baja / B23+ / |
| `docs/cierres/bloque-23-cierre.md` | 78 | DC-001..DC-041 | / DC-001..DC-041 / Sin cambios (arrastrada) / — / B24+ / |
| `docs/cierres/bloque-23-cierre.md` | 79 | DC-042 | / DC-042 / SessionService sin integración con HistoryService formal / Baja / B24+ / |
| `docs/cierres/bloque-24-cierre.md` | 82 | DC-001..DC-041 | / DC-001..DC-041 / Sin cambios (arrastrada) / — / B25+ / |
| `docs/cierres/bloque-24-cierre.md` | 83 | DC-042 | / DC-042 / SessionService sin HistoryService (arrastrada) / Baja / B25+ / |
| `docs/cierres/bloque-24-cierre.md` | 84 | DC-043 | / DC-043 / LiveModeService sin integración con HistoryService formal / Baja / B25+ / |
| `docs/cierres/bloque-25-cierre.md` | 87 | DC-045, DC-025 | / DC-045 / AnalysisService sin tests unitarios dedicados (significado HANDOFF huérfano de DC-025) / Media / B29 / |
| `docs/cierres/bloque-26-cierre.md` | 21 | DC-026 | / 9 / Deuda importación resuelta (§B26-T00) / ✅ / DC-026,027,028,046 cerradas (edit, merge, pymupdf, partial CLI) / |
| `docs/cierres/bloque-26-cierre.md` | 69 | DC-026 | / DC-026 / import review edit no implementado / B26-T00 / |
| `docs/cierres/bloque-26-cierre.md` | 70 | DC-027 | / DC-027 / import review merge no implementado / B26-T00 / |
| `docs/cierres/bloque-28-cierre.md` | 260 | DC-022 | / DC-022 / Abierta previa / Deuda global previa documentada; no modificada por B28 / Global / |
| `docs/cierres/bloque-28-cierre.md` | 261 | DC-B28-UI-WIN | / DC-B28-UI-WIN / Abierta / B28 incluyó CLI y no validación Desktop nativa Windows. No se tocó Desktop UI para evitar cambios visuales fuera de alcance. / B30 / validación Windows / |

## 5. Riesgos concretos para B29-T01..T06

- B29-T01 debe ser read-only: diagnóstico puede leer `Project` y producir reporte, pero no llamar a servicios mutadores ni save.
- B29-T02 debe usar patrón Windows-safe `_write_json_atomic`; restore debe crear backup previo o fallback y validar JSON/schema antes de reemplazar.
- B29-T03 debe aislar performance para no degradar suite normal; corpus reproducible y comandos con output real.
- B29-T04 debe verificar dispatch real en `main()`, no solo parser/help.
- B29-T06 debe consumir DiagnosticService y generar plan no destructivo; no crear `apply/execute`.

## 6. Ajuste de tickets

No se detecta gap que obligue a renumerar ni cambiar B29-T01..T06. T00 confirma el orden actual:
B29-T01 diagnóstico → B29-T02 backup/restore → B29-T03 performance → B29-T04 CLI → B29-T06 repair-plan → B29-T05 cierre.
