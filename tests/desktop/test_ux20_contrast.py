"""Guarda de contraste de accesibilidad WCAG (BETA1-UX20).

No necesita QApplication: opera sobre tokens y funciones puras.
"""
from __future__ import annotations

from hosts.DesktopHostPySide.widgets import design_system as ds

_AA_NORMAL = 4.5  # WCAG AA, texto normal


def test_sanity_blanco_negro_y_simetria() -> None:
    assert round(ds.contrast_ratio("#FFFFFF", "#000000")) == 21
    assert ds.contrast_ratio("#34301E", "#F4EFE1") == ds.contrast_ratio("#F4EFE1", "#34301E")
    assert ds.contrast_ratio("#777777", "#777777") == 1.0


def test_texto_principal_cumple_AA_en_superficies() -> None:
    for surface in (ds.SURFACE, ds.SURFACE_HI, ds.PAPER):
        assert ds.contrast_ratio(ds.INK_STRONG, surface) >= _AA_NORMAL
        assert ds.contrast_ratio(ds.INK, surface) >= _AA_NORMAL


def test_texto_secundario_cumple_AA_en_surface() -> None:
    # INK_SOFT es el muted legible (subtítulos, captions): debe seguir siendo AA.
    assert ds.contrast_ratio(ds.INK_SOFT, ds.SURFACE) >= _AA_NORMAL


def test_ink_muted_dejo_de_ser_decorativo_y_cumple_AA() -> None:
    """BETA-MULTIAGENT2-FIX-13 (G2-17): este test AFIRMABA lo contrario.

    Decía `2.5 <= ratio(INK_MUTED, SURFACE) < 4.5` y lo justificaba con «INK_MUTED
    es deliberadamente tenue: NO es texto principal». Esa decisión la desmintió la
    realidad del producto: `QLabel#mutedLabel` acabó pintando la justificación
    completa de por qué la IA quiere mover una entidad de anillo
    (`structure_review_panel`), el origen del candidato en la ventana donde se
    ejerce el invariante «la IA nunca escribe canon» (`candidate_review_panel`) y
    las filas de riesgo del Cuaderno de Cultivo. Dendro pintaba la prosa humana a
    10:1 y el razonamiento de la máquina a 2,58:1.

    El rango se invierte a propósito: INK_MUTED es el TERCER nivel de énfasis,
    no un nivel ilegible. Sigue siendo el más claro de los tres — lo que se guarda
    aquí es que no vuelva a bajar del umbral de lectura.
    """
    for surface in (ds.SURFACE, ds.SURFACE_HI, ds.PAPER, ds.WELL):
        assert ds.contrast_ratio(ds.INK_MUTED, surface) >= _AA_NORMAL, surface
    # …y la jerarquía de tres peldaños se conserva (INK más oscuro que INK_SOFT,
    # y este más oscuro que INK_MUTED).
    assert (
        ds.relative_luminance(ds.INK)
        < ds.relative_luminance(ds.INK_SOFT)
        < ds.relative_luminance(ds.INK_MUTED)
    )
