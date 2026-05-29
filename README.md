# narrative-architect

Aplicación de escritorio para creación narrativa, worldbuilding, escritura y
dirección de partidas de rol asistida por IA.

El núcleo conceptual es una **base de conocimiento narrativa estructurada**:
no un chatbot, no una wiki pasiva, no un VTT y no un grafo decorativo.
La IA asiste, sugiere y genera candidatos, pero **nunca modifica el canon
directamente** sin aceptación explícita del usuario.

## Estado actual

Fundación de proyecto completada. Ver tickets en `.kanban/tickets/`.

**Próximo ticket:** `B01-T02` — Configuración base, logging y manejo de errores
(actualmente en Backlog).

## Estructura del repositorio

```
.kanban/                    — Sistema Kanban (tickets, templates, resúmenes)
├── KANBAN.md              — Visión general del Kanban
├── tickets/               — Tickets individuales (B01-T01, B01-T02...)
├── templates/             — Plantillas
└── resumenes/             — Resúmenes técnicos de cierre

packages/
├── domain/                — Modelo de dominio puro (sin dependencias externas)
├── application/           — Casos de uso, comandos, servicios
├── infrastructure/        — IA, importadores, exportadores, adaptadores
├── persistence/           — Almacenamiento, repositorios, migraciones
└── ui/                    — Interfaz de escritorio

docs/
├── contracts/             — Contratos autoritativos
│   ├── contrato_fases     — Orden de implementación por bloques
│   ├── reglas-trabajo.md  — Reglas operativas de desarrollo
│   └── perfiles/          — Perfiles de agente
├── architecture/          — Documentos de arquitectura
│   └── contrato_arquitectura.md

tests/                     — Pruebas
├── test_sanity.py         — Pruebas de sanidad
└── architecture/          — Pruebas de reglas de dependencia

AGENTS.md                  — Reglas fundamentales del proyecto
```

## Desarrollo con Docker

```bash
# Construir
docker compose build

# Entrar al contenedor
docker compose run --rm dev
```

Dentro del contenedor:

```bash
# Ejecutar pruebas
pytest

# Lint
ruff check packages/ tests/
```

## Arquitectura limpia

```
Interfaz → Aplicación → Dominio
Infraestructura → Aplicación/Dominio mediante adaptadores
Persistencia → Dominio mediante repositorios
IA/Importadores/Exportadores → Aplicación mediante servicios desacoplados
```

El dominio **no depende** de UI, IA, PDF, frameworks visuales ni proveedores externos.

## Principios

1. **El core manda** — el modelo de dominio es la fuente de verdad.
2. **El grafo no es la base de datos** — es una vista interactiva.
3. **La IA no modifica canon** — produce candidatos, no muta.
4. **Importación documental no entra directo a canon** — pasa por bandeja de revisión.
5. **Todo cambio relevante es trazable** — origen, estado, historial.
6. **Secretos y visibilidad se respetan siempre** — no filtrar información no autorizada.
7. **No modelos paralelos** — si el core lo representa, reutilizar.
8. **La UI no escribe en persistencia** — siempre a través de servicios.
9. **La aplicación funciona sin IA** — la IA es asistencia opcional.
10. **Contratos prevalecen** — sobre sugerencias creativas de agentes.

## Kanban

El trabajo se organiza mediante Kanban en `.kanban/`.

Columnas: Backlog → Ready → In Progress → Review → Testing → Done
(con Blocked para bloqueos)

Todo trabajo nace de un ticket. No se implementa funcionalidad sin ticket.

## Perfiles de agente

Ver `docs/contracts/perfiles/` para las definiciones completas de cada perfil.
