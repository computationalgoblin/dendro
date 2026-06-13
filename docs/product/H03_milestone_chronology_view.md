# H03 - Milestone chronology view

## Decision

Milestones are shown in their own chronology drawer inside Creation. They are
not graph nodes and do not participate in canvas physics or layout.

```text
Graph = current structure of the world.
Milestones = causal/temporal evolution of the world.
```

## Access

Creation exposes a discreet `Cronologia` action in the secondary toolbar. It
opens the internal drawer with the chronology view. The existing `Hito desde
seleccion` path remains available for creating a milestone from graph context.

## Filters

The first version includes:

- text filter over title, summary and body;
- linked-entity filter;
- status shown as a human badge.

Branch, relation, ring and detail-panel entry points remain H04 scope.

## Ordering

The list is ordered without imposing a Gregorian calendar:

1. `metadata.sort_index`
2. `metadata.chronology_key`, `calendar_key` or `calendar_date`
3. `temporality.absolute_date`, `world_date`, `relative_date`, `period` or `era`
4. creation/title fallback

Milestones without a temporal position are labeled `Sin ubicar`.

## Color

Each card has a color swatch. The swatch uses the primary entity color when
available in `custom_metadata.color`, `ui_color` or `accent_color`; otherwise it
uses a stable derived color from the entity name/id.

The primary entity is read from `metadata.primary_entity_id` and falls back to
the first `affected_entity_ids` entry.

## Editing

The detail panel edits:

- title;
- summary (`description`);
- body (`rationale` and `metadata.body`);
- temporal label (`metadata.chronology_key`);
- relative order (`metadata.sort_index`);
- primary entity (`metadata.primary_entity_id`);
- status.

Save delegates to `CausalMilestoneController.update`, which uses the application
service route. The UI does not write directly to persistence or mutate graph
items.

## Limitations

- No relation/ring/branch filters yet.
- No launch-from-detail-panel action yet.
- No AI/RAG integration.
- No temporal overlay on the graph.

## Follow-up Debt

- H04: `Ver hitos relacionados` from leaf/branch/relation detail panels.
- H05: AI-assisted initial chronology suggestions.
- H06: RAG/context integration.
- H07: temporary causal overlay on the graph without permanent milestone nodes.
