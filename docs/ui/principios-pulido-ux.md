# Principios de pulido visual (épica BETA1-UX)

Guía viva para el pulido profundo de la UI de escritorio. Refina el lenguaje
existente ("tinta, pergamino y oro botánico"); **no** lo reinventa. Fuente de
verdad de los tokens: [design_system.py](../../hosts/DesktopHostPySide/widgets/design_system.py).

## Identidad

- **Una sola voz de oro** para la acción (`GOLD`/`GOLD_DEEP`/`GOLD_SOFT`/`GOLD_TINT`).
  Nunca un arcoíris de acentos. El verde `SAGE` es secundario y se usa con mesura.
- **Pergamino cálido con escalera tonal real** (`PAPER` → `CANVAS` → `WELL` →
  `SURFACE` → `SURFACE_HI`): la jerarquía y la profundidad se leen por contraste
  de superficies, no por líneas duras.
- **Tinta cálida**, nunca gris neutro. Las **sombras** tampoco: siempre `SHADOW_RGB`.

## Profundidad (elevación)

- Escala discreta `ELEVATION` (niveles 0–3): `(blur, desplazamiento_y, alpha)`.
- En **paneles/cards**: la elevación se consigue por **contraste tonal + borde**,
  nunca con `QGraphicsDropShadowEffect` sobre widgets dinámicos (cachea el render
  y deja zonas en blanco — lección G08).
- En el **canvas**: la profundidad se **pinta a mano** con `paint_soft_shadow(...)`
  (QPainter), apta para superficies que se repintan cada frame.

## Movimiento — "expresivo pero elegante"

Tres niveles de duración y tres curvas con carácter:

| Token | ms | Uso |
|-------|----|-----|
| `MOTION_FAST` | 150 | micro-feedback: hover, foco, press |
| `MOTION_BASE` | 220 | transición estándar: aparición de contenido/paneles |
| `MOTION_SLOW` | 360 | presencia: entradas/salidas con carácter |

| Curva | Uso |
|-------|-----|
| `EASING_STD` (OutCubic) | asentamiento natural (por defecto) |
| `EASING_ENTER` (OutQuint) | entradas con empuje y calma |
| `EASING_EMPHASIS` (InOutCubic) | énfasis simétrico |

El movimiento siempre **falla en silencio**: el pulido nunca rompe la lógica.

## Formas

- Escala de radios coherente: `RADIUS_SM` (9, chips/celdas), `RADIUS_MD`
  (12, botones/inputs/combos), `RADIUS_LG` (16, tarjetas/cajones), `RADIUS_PILL`.
- Pocas medidas, repetidas con disciplina.

## Verificación

Cada tarea de la épica se valida con el arnés `tests/desktop/_visual/`
(capturas `baseline` vs `uxNN`) + tests + ruff. Ver `tests/desktop/_visual/README.md`.
