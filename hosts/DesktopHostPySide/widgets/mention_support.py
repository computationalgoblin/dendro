"""Soporte de @menciones para editores de prosa (BETA2-MEM-03).

Añade a un ``QTextEdit`` (o ``QPlainTextEdit``) lo que la command bar ya tenía en
su ``QLineEdit``: autocompletar tras ``@`` con los elementos del proyecto y un
resaltado ligero de las @menciones. No convierte el editor en un wiki: el texto
se guarda tal cual (modelo sidecar); la referencia estructurada la resuelve
``StructuredReferenceService`` al guardar.

Cuando el usuario elige del desplegable un nombre ÚNICO, se registra un *hint*
``alias -> (kind, id)`` que fija el id exacto (ambigüedad imposible por
construcción). Nombres duplicados no generan hint: el guardado los marca como
ambiguos/reparables.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QRegularExpression, QStringListModel, Qt
from PySide6.QtGui import (
    QColor,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import QCompleter

# Acento dorado del sistema de diseño Dendro (pergamino cálido + oro).
_MENTION_COLOR = QColor("#9C6B1E")

TargetsProvider = Callable[[], "list[tuple[str, str, str]]"]


class _MentionHighlighter(QSyntaxHighlighter):
    """Resalta ``@palabra`` de forma ligera (reconocible, no wiki)."""

    def __init__(self, document):
        super().__init__(document)
        self._fmt = QTextCharFormat()
        self._fmt.setForeground(_MENTION_COLOR)
        self._fmt.setFontWeight(75)
        self._re = QRegularExpression(r"@[^\s@,;]+")

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (API Qt)
        it = self._re.globalMatch(text)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(), m.capturedLength(), self._fmt)


class MentionSupport:
    """Adjunta autocompletar + resaltado + captura de hints a un editor de texto."""

    def __init__(self, text_edit, targets_provider: TargetsProvider):
        self._edit = text_edit
        self._targets = targets_provider
        self._hints: dict[str, tuple[str, str]] = {}

        self._model = QStringListModel(text_edit)
        completer = QCompleter(self._model, text_edit)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setWidget(text_edit)
        completer.activated[str].connect(self._insert_completion)
        self._completer = completer

        self._highlighter = _MentionHighlighter(text_edit.document())
        text_edit.textChanged.connect(self._on_text_changed)

    # ── API pública ─────────────────────────────────────────────────────

    def hints(self) -> dict[str, tuple[str, str]]:
        """alias.lower() -> (kind, target_id) de los picks de nombre único."""
        return dict(self._hints)

    # ── fragmento en el cursor ──────────────────────────────────────────

    def _fragment(self) -> tuple[int, str] | None:
        cursor = self._edit.textCursor()
        pos = cursor.position()
        before = self._edit.toPlainText()[:pos]
        at = before.rfind("@")
        if at < 0:
            return None
        fragment = before[at + 1 :]
        if any(ch in fragment for ch in (",", "@", "\n", ";")):
            return None
        return at, fragment

    def _on_text_changed(self) -> None:
        frag = self._fragment()
        if frag is None:
            self._completer.popup().hide()
            return
        _at, fragment = frag
        names = sorted({n for _i, n, _k in self._targets() if n.strip()})
        self._model.setStringList(names)
        self._completer.setCompletionPrefix(fragment)
        if self._completer.completionCount() == 0:
            self._completer.popup().hide()
            return
        rect = self._edit.cursorRect()
        rect.setWidth(self._completer.popup().sizeHintForColumn(0) + 24)
        self._completer.complete(rect)

    def _insert_completion(self, choice: str) -> None:
        frag = self._fragment()
        if frag is None:
            return
        at, _fragment = frag
        cursor = self._edit.textCursor()
        pos = cursor.position()
        # Reemplaza el fragmento "@parcial" por "@Elegido " (id se fija vía hint).
        cursor.setPosition(at)
        cursor.setPosition(pos, QTextCursor.KeepAnchor)
        cursor.insertText(f"@{choice} ")
        self._edit.setTextCursor(cursor)
        self._record_hint(choice)

    def _record_hint(self, name: str) -> None:
        """Registra el id exacto solo si el nombre elegido es único."""
        matches = [(i, k) for i, n, k in self._targets() if n == name]
        distinct_ids = {i for i, _k in matches}
        if len(distinct_ids) == 1:
            i, k = matches[0]
            self._hints[name.lower()] = (k, i)


def attach_mention_support(text_edit, targets_provider: TargetsProvider) -> MentionSupport:
    """Adjunta @menciones a un editor y devuelve el handle (expone ``.hints()``)."""
    return MentionSupport(text_edit, targets_provider)


__all__ = ["MentionSupport", "attach_mention_support"]
