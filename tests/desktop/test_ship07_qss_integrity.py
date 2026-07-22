"""BETA2-SHIP-07: ninguna hoja de estilo se rompe por un `}}` literal.

Bug sistémico (auditoría UX): dentro de un `setStyleSheet(f"...")` construido por
concatenación de f-strings, una línea escrita como string PLANO (sin prefijo `f`)
deja el `}}` literal (doble llave) → Qt descarta TODA la hoja → el botón/chip se
pinta como control nativo gris. Se encontraron 7 (Home, asistente de contención,
next_step_chip, image_search, node_detail, portrait_editor, seed_notifications).

Este guard escanea los widgets y detecta la reincidencia: una línea de string
PLANO con `}}` que convive (±4 líneas) con una línea f-string de estilo (`{{`).
Las plantillas `.format()` (todas planas, sin f-string hermana) no dan falso
positivo.
"""

from __future__ import annotations

import re
from pathlib import Path

_WIDGETS = Path("hosts/DesktopHostPySide/widgets")

_PLAIN_DBRACE = re.compile(r'^\s*["\'][^"\']*\}\}')  # string plano que empieza y trae }}
_FSTRING_BRACE = re.compile(r'^\s*f["\'].*\{\{')  # f-string con {{ (típico de QSS)


def test_no_literal_double_brace_in_stylesheet_fstrings():
    offenders: list[str] = []
    for path in _WIDGETS.rglob("*.py"):
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if not _PLAIN_DBRACE.match(line):
                continue
            # ¿hay una línea f-string de estilo cerca? → misma concatenación QSS.
            window = lines[max(0, i - 4) : i + 5]
            if any(_FSTRING_BRACE.match(w) for w in window):
                offenders.append(f"{path.as_posix()}:{i + 1}: {line.strip()}")
    assert not offenders, "QSS con }} literal (hoja descartada):\n" + "\n".join(offenders)
