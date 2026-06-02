# Deuda consolidada B01-B28 — baseline pre-B29

Fuente: extracción automatizada de cierres y HANDOFF. No renumerar DCs.

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
