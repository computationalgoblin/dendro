from __future__ import annotations

import subprocess
import sys
import time

from packages.application.diagnostic_service import DiagnosticService
from packages.application.entity_service import EntityService
from packages.application.graph_models import GraphFilters
from packages.application.graph_service import GraphService
from packages.application.project_service import ProjectService
from packages.application.query_service import QueryService
from packages.application.relation_service import RelationService
from packages.application.source_service import SourceService
from packages.application.history_service import HistoryService
from packages.persistence.store import ProjectStore
from scripts.generate_large_project import build_large_project


def _graph_service_for(project):
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.active_project = project
    es = EntityService(project_service=ps, store=store)
    rs = RelationService(project_service=ps, store=store)
    ss = SourceService(project_service=ps, store=store)
    hs = HistoryService(project_service=ps)
    qs = QueryService(entity_service=es, relation_service=rs, source_service=ss, history_service=hs)
    return GraphService(query_service=qs, relation_service=rs, entity_service=es)


def test_large_project_generator_is_reproducible_and_connected() -> None:
    p1 = build_large_project(entity_count=120, relation_count=240, history_count=40)
    p2 = build_large_project(entity_count=120, relation_count=240, history_count=40)

    assert [e.id for e in p1.entities] == [e.id for e in p2.entities]
    assert [r.id for r in p1.relations] == [r.id for r in p2.relations]
    assert len(p1.entities) == 120
    assert len(p1.relations) == 240
    assert len(p1.history) == 40


def test_diagnostic_and_graph_handle_large_corpus_under_documented_threshold() -> None:
    project = build_large_project(entity_count=250, relation_count=500, history_count=150)
    graph_service = _graph_service_for(project)

    start = time.perf_counter()
    diagnostic = DiagnosticService().diagnose(project).value
    graph = graph_service.build_graph(GraphFilters(max_nodes=250, max_edges=500)).value
    elapsed = time.perf_counter() - start

    assert diagnostic.counts["entities"] == 250
    assert diagnostic.counts["relations"] == 500
    assert len(graph.nodes) == 250
    assert len(graph.edges) == 500
    assert elapsed < 2.0


def test_generate_large_project_help_smoke() -> None:
    import os
    import pathlib
    workspace = str(pathlib.Path(__file__).resolve().parents[2])
    env = {**os.environ, "PYTHONPATH": workspace}
    result = subprocess.run(
        [sys.executable, "scripts/generate_large_project.py", "--help"],
        cwd=workspace,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    assert "--entities" in result.stdout
    assert "--relations" in result.stdout
