"""Pestaña «Continuidad» del panel «Salud del proyecto» (BETA-MULTIAGENT2-FIX-10).

El validador temporal determinista existía desde BETA1-J02 y solo se ejecutaba al
ACEPTAR un candidato de IA: la app vigilaba lo que propone la máquina y no lo que
escribe el autor. Esta es la puerta que faltaba — bilocaciones, muertos que
reaparecen, conocimiento anterior a su revelación, consecuencias antes que su
causa y setups sin recoger.

Decisiones de superficie:

- **Una sola puerta a «qué va mal».** Es una PESTAÑA de «Salud del proyecto»
  (FIX-11), no un panel nuevo compitiendo con Wiki y Estructura.
- **Coste IA cero.** Ni proveedor, ni red, ni botón de IA: todo lo que hay aquí
  lo calcula ``ContinuityService`` de forma determinista.
- **Agrupado, no volcado.** Sobre el mundo del tester el validador crudo escupe
  19 avisos idénticos de calendario; aquí van plegados en un grupo, separados de
  las contradicciones de la historia y acompañados de su causa real (la datación
  desincronizada). Un panel con 19 tarjetas iguales es el fracaso que
  BETA-AUDIT-14 quiso evitar.
- **La UI no escribe persistencia**: descartar un aviso se le PIDE al servicio, y
  el guardado a disco se delega en el host (``on_dismissed``).
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
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import INK_MUTED
from packages.application.continuity_service import (
    FAMILIA_CALENDARIO,
    FAMILIA_TITULOS,
)
from packages.domain.result import Ok

#: Filas por grupo antes de plegar en «… y N más» (mismo criterio que el panel
#: de Estructura tras FIX-05: el ruido es el enemigo del producto).
_MAX_FILAS = 12

_SIN_AVISOS = "Sin avisos de continuidad: nada se contradice con las fechas que hay."

#: Explicación por grupo, escrita UNA vez bajo su cabecera en vez de repetida en
#: cada fila. El aviso de datación desincronizada es la CAUSA de los avisos de
#: calendario (§5 del hallazgo): sin decirlo, el usuario ve 19 síntomas y ningún
#: origen. La del calendario solo se pinta si de verdad hay desincronización.
_NOTAS: dict[str, str] = {
    "T14_DATING_DESYNC": (
        "Estas fichas tienen dos dataciones que no coinciden. Vuelve a guardar su "
        "datación (Ficha → fechas) y se sincronizan."
    ),
    "T02_OUTSIDE_ERAS": (
        "Ojo: estas fechas salen del lapso guardado, que NO coincide con lo que "
        "enseña la Ficha. Sincroniza la datación y la mayoría desaparecerá."
    ),
}


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


class ContinuityTab(QWidget):
    """Revisión determinista de la coherencia temporal y causal del canon."""

    def __init__(
        self,
        service: Any = None,
        *,
        on_dismissed: Callable[[], Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._on_dismissed = on_dismissed
        self._groups: list[Any] = []
        self._threads: list[Any] = []
        self._revisado = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        intro = QLabel(
            "Lo que tu propia historia se contradice: alguien en dos sitios a la vez, "
            "un muerto que reaparece, quien sabe algo antes de que se revele, una "
            "consecuencia fechada antes que su causa. Determinista, sin IA, y no "
            "cambia nada del canon: son avisos, no bloqueos."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {INK_MUTED};")
        root.addWidget(intro)

        top = QHBoxLayout()
        self.run_btn = QPushButton("Revisar la continuidad")
        self.run_btn.setToolTip("Comprobación determinista, sin IA y sin coste")
        self.run_btn.clicked.connect(self.refresh)
        top.addWidget(self.run_btn)
        top.addStretch(1)
        root.addLayout(top)

        self.summary = QLabel("Pulsa «Revisar la continuidad» para comprobarla.")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        self.list = QListWidget()
        self.list.currentItemChanged.connect(lambda *_: self._sync_dismiss_button())
        root.addWidget(self.list, 1)

        bottom = QHBoxLayout()
        self.dismiss_btn = QPushButton("No es un problema")
        self.dismiss_btn.setToolTip(
            "Descarta este aviso concreto. Volverá si el elemento cambia."
        )
        self.dismiss_btn.clicked.connect(self._dismiss_selected)
        self.dismiss_btn.setEnabled(False)
        bottom.addWidget(self.dismiss_btn)
        bottom.addStretch(1)
        root.addLayout(bottom)

        self.threads_label = QLabel()
        self.threads_label.setWordWrap(True)
        self.threads_label.setVisible(False)
        root.addWidget(self.threads_label)
        self.threads_list = QListWidget()
        self.threads_list.setMaximumHeight(140)
        self.threads_list.setVisible(False)
        root.addWidget(self.threads_list)

    # ── ciclo de vida ────────────────────────────────────────────────────

    def showEvent(self, event):  # noqa: N802 — API de Qt
        """Primera vez que se ve la pestaña: se calcula sola (coste IA cero).

        No hay contador permanente en ninguna esquina (G2-07): el cálculo vive
        aquí dentro, donde el usuario vino a buscarlo.
        """
        super().showEvent(event)
        if not self._revisado:
            self.refresh()

    # ── lectura ──────────────────────────────────────────────────────────

    def counts(self) -> dict[str, int]:
        """Recuento por código del último repaso ({} si no se ha revisado)."""
        return {g.code: g.count for g in self._groups}

    def total(self) -> int:
        return sum(g.count for g in self._groups)

    def refresh(self) -> bool:
        """Recalcula y pinta. ``True`` si hubo repaso (haya avisos o no)."""
        if self._service is None:
            self.summary.setText("No hay proyecto abierto.")
            return False
        result = self._service.grouped()
        if not isinstance(result, Ok):
            self._groups = []
            self._threads = []
            self.list.clear()
            self.summary.setText(
                str(getattr(result, "error", "No se pudo revisar la continuidad"))
            )
            return False
        self._revisado = True
        self._groups = list(result.value or [])
        self._threads = self._read_threads()
        self._render()
        return True

    def _read_threads(self) -> list[Any]:
        """«Plantado sin recoger» (FIX-09). Si no hay consulta, sección vacía."""
        leer = getattr(self._service, "loose_threads", None)
        if not callable(leer):
            return []
        try:
            resultado = leer()
        except Exception:  # noqa: BLE001 — una sección no puede tumbar la pestaña
            return []
        return list(resultado.value or []) if isinstance(resultado, Ok) else []

    # ── pintado ──────────────────────────────────────────────────────────

    def _render(self) -> None:
        self.list.clear()
        self._render_threads()
        total = self.total()
        if total == 0:
            self.summary.setText(_SIN_AVISOS)
            self._sync_dismiss_button()
            return

        por_familia: dict[str, list[Any]] = {}
        for grupo in self._groups:
            por_familia.setdefault(grupo.family, []).append(grupo)
        partes = [
            f"{sum(g.count for g in grupos)} en «{FAMILIA_TITULOS.get(familia, familia)}»"
            for familia, grupos in por_familia.items()
        ]
        self.summary.setText(f"{_plural(total, 'aviso', 'avisos')}: " + " · ".join(partes))

        desincronizadas = self.counts().get("T14_DATING_DESYNC", 0)
        for familia, grupos in por_familia.items():
            self._add_static(FAMILIA_TITULOS.get(familia, familia).upper())
            for grupo in grupos:
                self._add_static(f"  {grupo.count} · {grupo.title}")
                nota = _NOTAS.get(grupo.code)
                if nota and (grupo.family != FAMILIA_CALENDARIO or desincronizadas):
                    self._add_static(f"    {nota}")
                for issue in grupo.issues[:_MAX_FILAS]:
                    item = QListWidgetItem(f"      {issue.message}")
                    item.setData(
                        Qt.ItemDataRole.UserRole, self._service.fingerprint(issue)
                    )
                    self.list.addItem(item)
                restantes = grupo.count - _MAX_FILAS
                if restantes > 0:
                    self._add_static(f"      … y {restantes} más")
        self._sync_dismiss_button()

    def _add_static(self, texto: str) -> None:
        item = QListWidgetItem(texto)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.list.addItem(item)

    def _render_threads(self) -> None:
        if not self._threads:
            self.threads_label.setVisible(False)
            self.threads_list.setVisible(False)
            self.threads_list.clear()
            return
        self.threads_label.setText(
            f"Plantado sin recoger — {_plural(len(self._threads), 'hito', 'hitos')} que "
            "ningún hito posterior recoge. No es un error: es tu lista de hilos abiertos."
        )
        self.threads_label.setVisible(True)
        self.threads_list.clear()
        for hito in self._threads[:_MAX_FILAS]:
            año = getattr(hito, "year", None)
            titulo = getattr(hito, "title", "") or getattr(hito, "id", "")
            self.threads_list.addItem(f"{titulo}" + (f"  ({año})" if año is not None else ""))
        restantes = len(self._threads) - _MAX_FILAS
        if restantes > 0:
            self.threads_list.addItem(f"… y {restantes} más")
        self.threads_list.setVisible(True)

    # ── descarte (lo aplica el SERVICIO; la UI no escribe) ───────────────

    def _selected_fingerprint(self) -> str:
        item = self.list.currentItem()
        if item is None:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "")

    def _sync_dismiss_button(self) -> None:
        self.dismiss_btn.setEnabled(bool(self._selected_fingerprint()))

    def _dismiss_selected(self) -> bool:
        fingerprint = self._selected_fingerprint()
        if not fingerprint or self._service is None:
            return False
        resultado = self._service.dismiss(fingerprint)
        if not isinstance(resultado, Ok):
            self.summary.setText(
                str(getattr(resultado, "error", "No se pudo descartar el aviso"))
            )
            return False
        if self._on_dismissed is not None:
            try:
                self._on_dismissed()
            except Exception:  # noqa: BLE001 — el guardado nunca tumba la pestaña
                pass
        self.refresh()
        return True


__all__ = ["ContinuityTab"]
