"""Panel único «Salud del proyecto» (BETA2-FIX-11, fase A).

Una sola puerta a «qué va mal», con PESTAÑAS, en vez de varios paneles que dicen
lo mismo con otras palabras. Las pestañas previstas son **Continuidad · Wiki ·
Estructura**; este ticket entrega la de **Wiki** (lint determinista de la wiki de
Memoria) y deja la API (``add_section``) para que las otras se enchufen sin
rediseñar nada:

- *Continuidad* — coherencia temporal del canon: la trae BETA2-FIX-10.
- *Estructura* — el ``StructureReviewPanel`` que ya existe (misma clase, aquí como
  pestaña; su píldora de Creación sigue siendo la puerta en contexto).

Reglas que respeta (mapa de deuda BETA-AUDIT-14 y G2-07):
- **Bajo demanda**: nada se calcula al abrir el panel ni se pinta un contador
  permanente en la esquina de la pantalla. Se revisa cuando el usuario lo pide.
- **Sin IA**: el lint de la wiki es determinista y funciona con el proveedor
  apagado. La única parte que llama al proveedor —contradicciones cruzadas— es un
  botón aparte, deshabilitado con motivo legible cuando no hay proveedor.
- La UI no escribe persistencia: solo lee ``WikiLintService`` (que tampoco muta
  nada) y navega a la página afectada.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import INK_MUTED, PanelScaffold
from packages.domain.result import Ok

#: (atributo del informe, título humano, singular/plural)
_CATEGORIAS: tuple[tuple[str, str, str], ...] = (
    ("broken_links", "enlace roto", "enlaces rotos"),
    ("orphans", "página huérfana", "páginas huérfanas"),
    ("stale", "página obsoleta", "páginas obsoletas"),
    ("contradictions", "contradicción", "contradicciones"),
)

_SIN_PROVEEDOR = (
    "Configura un proveedor de IA para buscar contradicciones entre páginas. "
    "El resto de la revisión no la necesita."
)


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


class WikiHealthTab(QWidget):
    """Pestaña «Wiki»: revisión bajo demanda de la salud de la wiki de Memoria."""

    def __init__(
        self,
        lint_service: Any = None,
        *,
        on_open_page: Callable[[tuple[str, str, str]], None] | None = None,
        element_label: Callable[[str, str], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._lint_service = lint_service
        self._on_open_page = on_open_page
        self._element_label = element_label
        self._report: Any = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        intro = QLabel(
            "Revisa la wiki cuando quieras: enlaces que no llevan a ningún sitio, "
            "páginas de elementos borrados, páginas que quedaron obsoletas y "
            "contradicciones ya anotadas. No cambia nada del canon."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {INK_MUTED};")
        root.addWidget(intro)

        top = QHBoxLayout()
        self.run_btn = QPushButton("Revisar la wiki")
        self.run_btn.setToolTip("Comprobación determinista, sin IA y sin coste")
        self.run_btn.clicked.connect(self.run_lint)
        top.addWidget(self.run_btn)
        self.ai_btn = QPushButton("Buscar contradicciones (IA)")
        self.ai_btn.clicked.connect(self._run_ai)
        top.addWidget(self.ai_btn)
        top.addStretch(1)
        root.addLayout(top)

        self.summary = QLabel("Pulsa «Revisar la wiki» para comprobarla.")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        self.list = QListWidget()
        self.list.itemActivated.connect(self._open_selected)
        self.list.itemDoubleClicked.connect(self._open_selected)
        root.addWidget(self.list, 1)

        bottom = QHBoxLayout()
        self.open_btn = QPushButton("Ir a la página")
        self.open_btn.setToolTip("Abre la página de la wiki afectada")
        self.open_btn.clicked.connect(lambda: self._open_selected(self.list.currentItem()))
        bottom.addWidget(self.open_btn)
        bottom.addStretch(1)
        root.addLayout(bottom)

        self._sync_ai_button()

    # ── proveedor de IA (la parte determinista no lo necesita) ───────────

    def ai_available(self) -> bool:
        job = getattr(self._lint_service, "ai_job_service", None)
        if job is None:
            return False
        check = getattr(job, "provider_unconfigured", None)
        try:
            return not check() if callable(check) else True
        except Exception:  # noqa: BLE001 — un proveedor roto no rompe el panel
            return False

    def _sync_ai_button(self) -> None:
        ok = self.ai_available()
        self.ai_btn.setEnabled(ok)
        self.ai_btn.setToolTip(
            "Una sola llamada al proveedor: busca contradicciones entre páginas distintas."
            if ok
            else _SIN_PROVEEDOR
        )

    # ── lint determinista ────────────────────────────────────────────────

    def counts(self) -> dict[str, int]:
        """Conteo por categoría del último informe ({} si no se ha revisado)."""
        if self._report is None:
            return {}
        return {attr: len(getattr(self._report, attr, []) or []) for attr, _, _ in _CATEGORIAS}

    def run_lint(self) -> bool:
        """Ejecuta el lint (determinista) y pinta el resultado. True si hubo informe."""
        self._sync_ai_button()
        if self._lint_service is None:
            self.summary.setText("No hay proyecto abierto.")
            return False
        result = self._lint_service.lint()
        if not isinstance(result, Ok):
            self._report = None
            self.list.clear()
            self.summary.setText(str(getattr(result, "error", "No se pudo revisar la wiki")))
            return False
        self._report = result.value
        self._render()
        return True

    def _label(self, issue: Any) -> str:
        if self._element_label is not None:
            try:
                nombre = self._element_label(issue.target_kind, issue.target_id)
            except Exception:  # noqa: BLE001 — el nombre nunca rompe la lista
                nombre = ""
        else:
            nombre = ""
        if not nombre:
            nombre = "visión global" if not issue.target_id else issue.target_id[:8]
        return f"{nombre} — {issue.detail}"

    def _render(self) -> None:
        self.list.clear()
        conteos = self.counts()
        total = sum(conteos.values())
        if total == 0:
            self.summary.setText("La wiki está limpia: nada que revisar.")
            return
        partes = [
            _plural(conteos.get(attr, 0), sing, plur)
            for attr, sing, plur in _CATEGORIAS
            if conteos.get(attr, 0)
        ]
        self.summary.setText(" · ".join(partes))
        for attr, sing, plur in _CATEGORIAS:
            issues = list(getattr(self._report, attr, []) or [])
            if not issues:
                continue
            cabecera = QListWidgetItem(_plural(len(issues), sing, plur).upper())
            cabecera.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(cabecera)
            for issue in issues:
                item = QListWidgetItem(f"    {self._label(issue)}")
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    (issue.target_kind, issue.target_id, issue.context),
                )
                self.list.addItem(item)

    # ── contradicciones cruzadas (IA, una sola llamada) ──────────────────

    def _run_ai(self) -> None:
        if self._lint_service is None or not self.ai_available():
            return
        result = self._lint_service.detect_ai_contradictions()
        if not isinstance(result, Ok):
            self.summary.setText(str(getattr(result, "error", "No se pudo consultar a la IA")))
            return
        nuevas = list(result.value or [])
        if self._report is None:
            self.run_lint()
        if self._report is not None:
            self._report.contradictions.extend(nuevas)
            self._render()

    # ── navegación a la página afectada ──────────────────────────────────

    def _open_selected(self, item: QListWidgetItem | None) -> None:
        if item is None or self._on_open_page is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if key:
            self._on_open_page(tuple(key))


class ProjectHealthPanel(QWidget):
    """Panel de proyecto «Salud del proyecto» — una puerta, varias pestañas."""

    def __init__(
        self,
        lint_service: Any = None,
        *,
        on_open_page: Callable[[tuple[str, str, str]], None] | None = None,
        element_label: Callable[[str, str], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        scaffold = PanelScaffold(
            "Salud del proyecto",
            "Revisión bajo demanda. Nada de esto cambia el canon.",
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scaffold)

        self.tabs = QTabWidget()
        scaffold.body.addWidget(self.tabs, 1)

        self.wiki_tab = WikiHealthTab(
            lint_service, on_open_page=on_open_page, element_label=element_label
        )
        self.tabs.addTab(self.wiki_tab, "Wiki")
        self.setMinimumWidth(520)

    def add_section(self, title: str, widget: QWidget, index: int | None = None) -> int:
        """Añade una pestaña (Continuidad, Estructura…). Devuelve su índice."""
        if index is None:
            return self.tabs.addTab(widget, title)
        return self.tabs.insertTab(index, widget, title)

    def show_section(self, title: str) -> bool:
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == title:
                self.tabs.setCurrentIndex(i)
                return True
        return False


__all__ = ["ProjectHealthPanel", "WikiHealthTab"]
