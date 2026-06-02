#!/usr/bin/env python
"""Generate a deterministic large project corpus for B29 performance tests."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.source_history import HistoryEntry
from packages.domain.result import Error
from packages.persistence.store import ProjectStore


def build_large_project(
    entity_count: int = 500,
    relation_count: int = 1000,
    history_count: int = 250,
) -> Project:
    """Build a deterministic, connected project corpus."""
    project = Project(id="large-project-b29", name="Large Project B29")
    entity_types = list(EntityType)
    for idx in range(entity_count):
        project.entities.append(
            NarrativeEntity(
                id=f"ent-{idx:05d}",
                name=f"Entidad {idx:05d}",
                entity_type=entity_types[idx % len(entity_types)],
                tags=[f"tag-{idx % 10}"],
                domain_ids=["mundo" if idx % 2 == 0 else "historia"],
                layer_ids=[f"layer-{idx % 5}"],
            )
        )

    relation_types = list(RelationType)
    if entity_count > 1:
        for idx in range(relation_count):
            source_idx = idx % entity_count
            target_idx = (idx * 7 + 1) % entity_count
            if target_idx == source_idx:
                target_idx = (target_idx + 1) % entity_count
            project.relations.append(
                NarrativeRelation(
                    id=f"rel-{idx:05d}",
                    source_id=f"ent-{source_idx:05d}",
                    target_id=f"ent-{target_idx:05d}",
                    relation_type=relation_types[idx % len(relation_types)],
                    description=f"Relación sintética {idx}",
                )
            )

    for idx in range(history_count):
        project.history.append(
            HistoryEntry(
                id=f"hist-{idx:05d}",
                affected_entity_id=f"ent-{idx % max(entity_count, 1):05d}" if entity_count else None,
                reason=f"Evento sintético {idx}",
                operation="performance_fixture",
            )
        )
    return project


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic B29 large project corpus")
    parser.add_argument("--output", type=Path, default=Path("large_project_b29.json"))
    parser.add_argument("--entities", type=int, default=500)
    parser.add_argument("--relations", type=int, default=1000)
    parser.add_argument("--history", type=int, default=250)
    args = parser.parse_args()

    project = build_large_project(
        entity_count=args.entities,
        relation_count=args.relations,
        history_count=args.history,
    )
    result = ProjectStore().save(project, args.output)
    if isinstance(result, Error):
        print(result.error)
        return 1
    print(f"Wrote {args.output} entities={len(project.entities)} relations={len(project.relations)} history={len(project.history)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
