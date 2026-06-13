"""Minimal in-memory RAG service for E03.

Retrieval and ContextPack construction are implemented in later E tickets. This
service owns project indexes so UI/application code has one stable entry point.
"""
from __future__ import annotations

from typing import Any

from packages.application.corpus_indexer import CorpusIndexer, IndexingOptions, NarrativeCorpusIndex
from packages.domain.result import Error, Ok, Result


class RAGService:
    def __init__(self, indexer: CorpusIndexer | None = None):
        self.indexer = indexer or CorpusIndexer()
        self._indices: dict[str, NarrativeCorpusIndex] = {}
        self._statuses: dict[str, dict[str, object]] = {}

    def index_project(
        self,
        project: Any,
        *,
        options: IndexingOptions | None = None,
        previous_index: NarrativeCorpusIndex | None = None,
    ) -> Result:
        project_id = str(getattr(project, "id", "") or "")
        if not project_id:
            return Error("Proyecto sin id para indexacion RAG")
        previous = previous_index or self._indices.get(project_id)
        self._statuses[project_id] = {
            "project_id": project_id,
            "indexed": previous is not None,
            "state": "indexing",
            "total": len(previous) if previous is not None else 0,
            "by_kind": previous.counts_by_kind() if previous is not None else {},
            "message": "Indexando contexto narrativo",
            "warnings": [],
        }
        try:
            index = self.indexer.index_project(project, previous_index=previous, options=options)
        except Exception as exc:
            self._statuses[project_id] = {
                "project_id": project_id,
                "indexed": previous is not None,
                "state": "error",
                "total": len(previous) if previous is not None else 0,
                "by_kind": previous.counts_by_kind() if previous is not None else {},
                "message": str(exc),
                "warnings": [],
            }
            return Error(str(exc))
        self._indices[project_id] = index
        self._statuses[project_id] = {
            "project_id": index.project_id,
            "indexed": True,
            "state": "indexed",
            "total": len(index),
            "by_kind": index.counts_by_kind(),
            "updated_at": index.updated_at,
            "message": f"Indexado ({len(index)} elementos)",
            "warnings": list(index.stats.warnings),
        }
        return Ok(index)

    def ensure_index(self, project: Any, *, options: IndexingOptions | None = None) -> Result:
        return self.index_project(project, options=options)

    def get_index(self, project_id: str) -> Result:
        index = self._indices.get(str(project_id))
        if index is None:
            return Error("Indice RAG no encontrado")
        return Ok(index)

    def clear_index(self, project_id: str | None = None) -> Result:
        if project_id is None:
            self._indices.clear()
            self._statuses.clear()
            return Ok(True)
        key = str(project_id)
        self._indices.pop(key, None)
        self._statuses.pop(key, None)
        return Ok(True)

    def index_status(self, project_id: str) -> dict[str, object]:
        key = str(project_id)
        status = self._statuses.get(key)
        if status is not None:
            return dict(status)
        index = self._indices.get(key)
        if index is None:
            return {
                "project_id": key,
                "indexed": False,
                "state": "pending",
                "total": 0,
                "by_kind": {},
                "message": "Pendiente",
                "warnings": [],
            }
        return {
            "project_id": index.project_id,
            "indexed": True,
            "state": "indexed",
            "total": len(index),
            "by_kind": index.counts_by_kind(),
            "updated_at": index.updated_at,
            "message": f"Indexado ({len(index)} elementos)",
            "warnings": list(index.stats.warnings),
        }


__all__ = ["RAGService"]
