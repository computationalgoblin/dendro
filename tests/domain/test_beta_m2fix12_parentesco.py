"""BETA-MULTIAGENT2-FIX-12 (G2-16) — la familia de PARENTESCO en el dominio.

El enum tenía 41 tipos de relación y CERO de parentesco: en «un árbol genealógico
para historias» no se podía decir «madre». Aquí se guarda que la familia existe,
que se OFRECE (no basta con el enum: la caja se puebla con
``OFFERED_RELATION_TYPES``), que sus inversos están declarados y —la trampa que
rompería la app— que **parentesco NO es contención**: una madre no puede
convertirse en rama contenedora de su hijo ni arrastrarlo de anillo.
"""

from __future__ import annotations

from packages.application.foco_zones import (
    _CAUSE_AS_SOURCE,
    _EFFECT_AS_SOURCE,
    _relation_signal,
)
from packages.application.temporal_coherence import (
    _CONTAINER_AS_SOURCE,
    _CONTAINER_AS_TARGET,
)
from packages.domain.entity_taxonomy import (
    HIDDEN_RELATION_TYPES,
    OFFERED_RELATION_TYPES,
)
from packages.domain.relation import (
    KINSHIP_RELATION_TYPES,
    RELATION_INVERSES,
    NarrativeRelation,
    RelationType,
    coerce_relation_type,
    inverse_relation_type,
    is_kinship,
)

# Lo que pidieron los dos perfiles que se quedaron fuera: la novela familiar
# («es madre de, es hijo de, casado con, hermano de») y la novela histórica
# (linaje: antepasado/descendiente, y un genérico para primos/tíos/cuñados).
_ESPERADOS = {
    "es_progenitor_de",
    "es_madre_de",
    "es_padre_de",
    "es_hijo_de",
    "es_hermano_de",
    "esta_casado_con",
    "es_antepasado_de",
    "es_descendiente_de",
    "es_familiar_de",
}


def test_beta_m2fix12_familia_de_parentesco_existe() -> None:
    valores = {t.value for t in RelationType}
    faltan = _ESPERADOS - valores
    assert not faltan, f"tipos de parentesco ausentes del dominio: {sorted(faltan)}"
    assert {t.value for t in KINSHIP_RELATION_TYPES} == _ESPERADOS


def test_beta_m2fix12_el_parentesco_se_ofrece_en_la_caja() -> None:
    """No basta con el enum: la caja de la ficha se puebla con lo OFRECIDO."""
    ocultos = KINSHIP_RELATION_TYPES & HIDDEN_RELATION_TYPES
    assert not ocultos, f"parentesco escondido: {sorted(t.value for t in ocultos)}"
    ofrecidos = set(OFFERED_RELATION_TYPES)
    assert KINSHIP_RELATION_TYPES <= ofrecidos


def test_beta_m2fix12_inversos_declarados() -> None:
    """El mapa de inversos es TOTAL y CERRADO sobre el parentesco, y estable.

    `es_madre_de`/`es_padre_de` son especializaciones de género de
    `es_progenitor_de`, así que su inverso (`es_hijo_de`) no vuelve al tipo
    generizado —nadie puede adivinar el género que no se declaró—: vuelve al
    neutro. De ahí que la involución sea estricta solo en el núcleo neutro y que
    el mapa se estabilice a partir del segundo paso.
    """
    for tipo in KINSHIP_RELATION_TYPES:
        inverso = inverse_relation_type(tipo)
        assert inverso is not None, f"{tipo.value} no declara inverso"
        assert inverso in KINSHIP_RELATION_TYPES, f"{tipo.value} sale de la familia"
        # Estabilidad: inv³(x) == inv(x).
        assert inverse_relation_type(inverse_relation_type(inverso)) is inverso

    # Núcleo neutro y simétricos: involución estricta.
    for uno, otro in (
        ("es_progenitor_de", "es_hijo_de"),
        ("es_antepasado_de", "es_descendiente_de"),
        ("es_hermano_de", "es_hermano_de"),
        ("esta_casado_con", "esta_casado_con"),
        ("es_familiar_de", "es_familiar_de"),
    ):
        assert inverse_relation_type(uno) == RelationType(otro)
        assert inverse_relation_type(otro) == RelationType(uno)

    # Género: madre/padre invierten al hijo; el hijo vuelve al neutro.
    assert inverse_relation_type("es_madre_de") is RelationType.ES_HIJO_DE
    assert inverse_relation_type("es_padre_de") is RelationType.ES_HIJO_DE
    assert inverse_relation_type("es_hijo_de") is RelationType.ES_PROGENITOR_DE

    # Los pares que el enum ya practicaba sin declararlos siguen igual.
    assert inverse_relation_type("contiene") is RelationType.PERTENECE_A
    assert inverse_relation_type("pertenece_a") is RelationType.CONTIENE
    assert inverse_relation_type("causo") is RelationType.FUE_CAUSADO_POR

    # Un tipo sin pareja NO inventa simetría.
    assert inverse_relation_type("esta_relacionado_con") is None
    assert inverse_relation_type("mentor_espiritual") is None
    assert RELATION_INVERSES.get(RelationType.ESTA_RELACIONADO_CON) is None


def test_beta_m2fix12_is_kinship() -> None:
    assert is_kinship("es_madre_de")
    assert is_kinship(RelationType.ESTA_CASADO_CON)
    assert not is_kinship("esta_relacionado_con")
    assert not is_kinship("mentor_espiritual")
    assert not is_kinship(None)


def test_beta_m2fix12_carga_tolerante_intacta() -> None:
    """El endurecimiento es de la ruta de ESCRITURA, no de la de carga.

    Un proyecto viejo con un tipo desconocido tiene que abrir sin romper y sin
    perder la relación (`from_dict` es también `Project.from_dict`).
    """
    rel = NarrativeRelation.from_dict(
        {"source_id": "a", "target_id": "b", "relation_type": "mentor_espiritual"}
    )
    assert rel.relation_type is RelationType.ESTA_RELACIONADO_CON
    assert rel.source_id == "a" and rel.target_id == "b"

    # Alias legado de BETA-MULTIAGENT-FIX-04 (RONDA 1): el typo "cono..." sigue
    # resolviendo al tipo bueno.
    viejo = NarrativeRelation.from_dict(
        {"source_id": "a", "target_id": "b", "relation_type": "cono..."}
    )
    assert viejo.relation_type is RelationType.CONOCE

    # Y un parentesco carga como parentesco.
    madre = NarrativeRelation.from_dict(
        {"source_id": "a", "target_id": "b", "relation_type": "es_madre_de"}
    )
    assert madre.relation_type is RelationType.ES_MADRE_DE
    assert madre.to_dict()["relation_type"] == "es_madre_de"

    # `coerce_relation_type` sigue devolviendo None para lo desconocido: ese es
    # el contrato que usa el servicio para rechazar en vez de aplanar.
    assert coerce_relation_type("mentor_espiritual") is None
    assert coerce_relation_type("ES_MADRE_DE") is RelationType.ES_MADRE_DE


def test_beta_m2fix12_parentesco_no_es_contencion() -> None:
    """Trampa A9: si un parentesco entrara en los conjuntos de contención, una
    madre se convertiría en RAMA contenedora de su hijo y se lo llevaría de
    anillo."""
    for nombre, conjunto in (
        ("temporal_coherence._CONTAINER_AS_SOURCE", _CONTAINER_AS_SOURCE),
        ("temporal_coherence._CONTAINER_AS_TARGET", _CONTAINER_AS_TARGET),
        ("foco_zones._CAUSE_AS_SOURCE", _CAUSE_AS_SOURCE),
        ("foco_zones._EFFECT_AS_SOURCE", _EFFECT_AS_SOURCE),
    ):
        intrusos = KINSHIP_RELATION_TYPES & frozenset(conjunto)
        assert not intrusos, f"{nombre} trata el parentesco como contención: {intrusos}"

    # foco_zones compara además contra los DOS tipos de contención literales
    # (`contiene`/`pertenece_a`): ningún parentesco emite señal de zona.
    for tipo in KINSHIP_RELATION_TYPES:
        rel = NarrativeRelation(source_id="madre", target_id="hijo", relation_type=tipo)
        assert _relation_signal(rel, "madre") is None, tipo.value
        assert _relation_signal(rel, "hijo") is None, tipo.value

    # Y los tipos de contención siguen sin ser parentesco.
    assert not is_kinship(RelationType.CONTIENE)
    assert not is_kinship(RelationType.PERTENECE_A)
    assert not is_kinship(RelationType.ESTA_UBICADO_EN)
    assert not is_kinship(RelationType.GOBIERNA)
