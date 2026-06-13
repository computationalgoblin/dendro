# H01 - Project chronology and temporal milestones contract

## Purpose

The project chronology is the temporal structure of a narrative project. It is
used to order, filter and explain important events, especially milestones that
justify the current state of the world.

## Authoritative model

- `Project.project_chronology` is the project-level chronology/calendar
  container.
- `CausalMilestone` remains the authoritative milestone model.
- `TimelineEvent` remains the broader temporal event model.
- A milestone is not a `NarrativeEntity`, `NarrativeRelation`, branch, leaf or
  graph node.
- The graph/canvas can show or reference milestone information in future views,
  but it is not the storage model for chronology.

## Boundaries

Milestones may reference existing narrative structures through explicit ids:

- leaves/entities through `affected_entity_ids`
- branches through `affected_branch_ids`
- rings/layers through `affected_layer_ids` or `layer_ids`
- relations through `caused_relation_ids`
- other milestones through `causal_parent_hito_ids` and
  `causal_child_hito_ids`

The project chronology references milestones through `milestone_ids`. This keeps
chronological membership separate from graph topology and avoids creating a
parallel canon model.

## Canon and AI

AI may propose milestones, orderings, explanations or coherence findings. It
must do so through candidates, suggestions or issues. AI does not append,
approve, delete or rewrite canonical milestones directly.

Manual or accepted changes must remain traceable through application services
and existing history/candidate mechanisms where applicable.

## Persistence

The chronology is persisted as a project root object:

```json
{
  "project_chronology": {
    "id": "project_chronology",
    "calendar_name": "",
    "description": "",
    "calendar_system": "project",
    "milestone_ids": []
  },
  "causal_milestones": []
}
```

Legacy projects without `project_chronology` migrate to an empty chronology. No
milestones are inferred during migration.

## Out of scope for H01-H02

- Timeline UI or a filtered milestone view.
- Canvas physics or graph layout for milestones.
- RAG indexing/retrieval of chronology.
- New AI workflows beyond preserving the no-direct-canon rule.
