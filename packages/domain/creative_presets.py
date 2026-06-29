"""Presets creativos (PA04).

Cada preset es una config parcial que se fusiona en ``project.creative_config``
(las 5 secciones canónicas). Solo rellenan campos vacíos: nunca pisan lo que el
usuario ya configuró. Los valores categóricos usan los tokens de
[creative_config.py]; los textos libres (tono, estilo, emociones…) son orientativos.
"""
from __future__ import annotations

CREATIVE_PRESETS: dict[str, dict] = {
    "tragedia_intima": {
        "label": "Tragedia íntima",
        "description": "Drama personal, emocional, con final trágico o agridulce.",
        "config": {
            "identidad": {"genero_principal": "drama", "publico": "adulto"},
            "direccion": {
                "emociones": ["melancolía", "ternura", "culpa"],
                "sensacion_final": "Duelo silencioso, eco de lo que pudo ser.",
                "originalidad": "experimental",
                "ambiguedad": "ambiguo_interpretativo",
                "tipo_impacto": ["intimidad", "dilema moral"],
            },
            "motor": {
                "fuente_conflicto": "trauma",
                "mecanismo": "decadencia",
                "causalidad": "psicologica",
                "agencia": "baja",
                "escalada": "lenta",
                "cambio_personaje": "caida",
            },
            "estilo": {
                "tono": "melancólico",
                "realismo": "alto",
                "estilo_narrativo": "Introspectivo y cercano.",
                "densidad": "medio",
                "exposicion": "por_pistas",
            },
        },
    },
    "weird_mystery": {
        "label": "Weird mystery",
        "description": "Misterio que se resiste a explicaciones convencionales.",
        "config": {
            "identidad": {"genero_principal": "weird_fiction", "publico": "adulto"},
            "direccion": {
                "emociones": ["inquietud", "fascinación", "extrañeza"],
                "sensacion_final": "La sensación de que algo no encaja del todo.",
                "originalidad": "muy_autoral",
                "ambiguedad": "ambiguo_interpretativo",
                "tipo_impacto": ["inquietud", "misterio", "extrañeza"],
            },
            "motor": {
                "fuente_conflicto": "destino",
                "mecanismo": "revelacion",
                "causalidad": "simbolica",
                "agencia": "media",
                "escalada": "ciclica",
                "cambio_personaje": "revelacion",
            },
            "estilo": {
                "tono": "inquietante",
                "realismo": "medio",
                "grado_especulativo": "moderado",
                "estilo_narrativo": "Atmosférico, extraño, con lógica propia.",
                "densidad": "denso",
                "exposicion": "misteriosa",
            },
        },
    },
    "thriller_moral": {
        "label": "Thriller moral",
        "description": "Tensión constante donde las decisiones éticas son el motor.",
        "config": {
            "identidad": {"genero_principal": "thriller", "publico": "adulto"},
            "direccion": {
                "emociones": ["tensión", "paranoia", "culpa"],
                "sensacion_final": "La línea entre correcto y necesario queda borrosa.",
                "originalidad": "experimental",
                "ambiguedad": "equilibrado",
                "tipo_impacto": ["dilema moral", "inquietud"],
            },
            "motor": {
                "fuente_conflicto": "poder",
                "mecanismo": "intriga",
                "causalidad": "estricta",
                "agencia": "alta",
                "escalada": "acumulativa",
                "cambio_personaje": "corrupcion",
            },
            "estilo": {
                "tono": "tenso",
                "realismo": "alto",
                "estilo_narrativo": "Tenso, directo, con dilemas constantes.",
                "densidad": "medio",
                "exposicion": "gradual",
            },
        },
    },
    "fantasia_politica": {
        "label": "Fantasía política",
        "description": "Mundos mágicos con intrigas de poder, alianzas y traiciones.",
        "config": {
            "identidad": {"genero_principal": "fantasia", "publico": "adulto_joven"},
            "direccion": {
                "emociones": ["fascinación", "tensión", "esperanza"],
                "sensacion_final": "El poder cambia de manos, pero el precio queda.",
                "originalidad": "experimental",
                "ambiguedad": "equilibrado",
                "tipo_impacto": ["épica", "aventura", "dilema moral"],
            },
            "motor": {
                "fuente_conflicto": "poder",
                "mecanismo": "guerra_de_facciones",
                "causalidad": "politica",
                "agencia": "alta",
                "escalada": "explosiva",
                "cambio_personaje": "maduracion",
            },
            "estilo": {
                "tono": "épico",
                "realismo": "medio",
                "grado_especulativo": "alto",
                "estilo_narrativo": "Épico pero pragmático, con múltiples facciones.",
                "densidad": "medio",
                "exposicion": "gradual",
            },
        },
    },
    "fabula_oscura": {
        "label": "Fábula oscura",
        "description": "Narrativa alegórica con elementos fantásticos y tono siniestro.",
        "config": {
            "identidad": {"genero_principal": "fantasia", "publico": "adulto"},
            "direccion": {
                "emociones": ["inquietud", "fascinación", "melancolía"],
                "sensacion_final": "La moraleja no es la que esperabas.",
                "originalidad": "extrano",
                "ambiguedad": "ambiguo_interpretativo",
                "tipo_impacto": ["belleza", "extrañeza", "inquietud"],
            },
            "motor": {
                "fuente_conflicto": "ideologia",
                "mecanismo": "decadencia",
                "causalidad": "simbolica",
                "agencia": "media",
                "escalada": "episodica",
                "cambio_personaje": "maduracion",
            },
            "estilo": {
                "tono": "oscuro",
                "realismo": "bajo",
                "grado_especulativo": "alto",
                "estilo_narrativo": "Alegórico, poético, con oscuridad subyacente.",
                "densidad": "denso",
                "exposicion": "por_pistas",
            },
        },
    },
    "drama_coral": {
        "label": "Drama coral",
        "description": "Múltiples personajes entrelazados, cada uno con su propio arco.",
        "config": {
            "identidad": {"genero_principal": "drama", "publico": "adulto"},
            "direccion": {
                "emociones": ["melancolía", "ternura", "esperanza"],
                "sensacion_final": "Todas las vidas se tocan, aunque no lo sepan.",
                "originalidad": "familiar_con_giro",
                "ambiguedad": "equilibrado",
                "tipo_impacto": ["intimidad", "melancolía", "belleza"],
            },
            "motor": {
                "fuente_conflicto": "deseo",
                "mecanismo": "viaje",
                "causalidad": "psicologica",
                "agencia": "media",
                "escalada": "ciclica",
                "cambio_personaje": "maduracion",
            },
            "estilo": {
                "tono": "íntimo",
                "realismo": "alto",
                "estilo_narrativo": "Multiperspectiva, íntimo, con ecos entre tramas.",
                "densidad": "medio",
                "exposicion": "gradual",
            },
        },
    },
    "horror_psicologico": {
        "label": "Horror psicológico",
        "description": "Terror que nace de la mente, no de los monstruos.",
        "config": {
            "identidad": {"genero_principal": "terror", "publico": "adulto"},
            "direccion": {
                "emociones": ["horror", "paranoia", "inquietud"],
                "sensacion_final": "No estás seguro de lo que fue real.",
                "originalidad": "experimental",
                "ambiguedad": "ambiguo_interpretativo",
                "tipo_impacto": ["horror", "inquietud", "extrañeza"],
            },
            "motor": {
                "fuente_conflicto": "trauma",
                "mecanismo": "revelacion",
                "causalidad": "psicologica",
                "agencia": "baja",
                "escalada": "ciclica",
                "cambio_personaje": "ruptura",
            },
            "estilo": {
                "tono": "oscuro",
                "realismo": "alto",
                "estilo_narrativo": "Claustrofóbico, gradual, que cuestiona la realidad.",
                "densidad": "denso",
                "exposicion": "fragmentaria",
            },
        },
    },
    "aventura_clasica": {
        "label": "Aventura clásica",
        "description": "Viaje, descubrimiento, crecimiento y regreso transformado.",
        "config": {
            "identidad": {"genero_principal": "fantasia", "publico": "todos"},
            "direccion": {
                "emociones": ["maravilla", "euforia", "esperanza"],
                "sensacion_final": "El viaje valió la pena, aunque costó más de lo esperado.",
                "originalidad": "convencional",
                "ambiguedad": "claro_directo",
                "tipo_impacto": ["aventura", "asombro"],
            },
            "motor": {
                "fuente_conflicto": "supervivencia",
                "mecanismo": "viaje",
                "causalidad": "estricta",
                "agencia": "alta",
                "escalada": "acumulativa",
                "cambio_personaje": "maduracion",
            },
            "estilo": {
                "tono": "luminoso",
                "realismo": "medio",
                "grado_especulativo": "moderado",
                "estilo_narrativo": "Ágil, descriptivo, con sentido de la maravilla.",
                "densidad": "medio",
                "exposicion": "directa",
            },
        },
    },
    "distopia_social": {
        "label": "Distopía social",
        "description": "Sistema opresivo, resistencia, costos de la rebelión.",
        "config": {
            "identidad": {"genero_principal": "distopia", "publico": "adulto_joven"},
            "direccion": {
                "emociones": ["tensión", "paranoia", "esperanza"],
                "sensacion_final": "El sistema cambia, pero ¿realmente mejora?",
                "originalidad": "experimental",
                "ambiguedad": "equilibrado",
                "tipo_impacto": ["dilema moral", "sátira"],
            },
            "motor": {
                "fuente_conflicto": "ideologia",
                "mecanismo": "conspiracion",
                "causalidad": "sistemica",
                "agencia": "condicionada",
                "escalada": "explosiva",
                "cambio_personaje": "radicalizacion",
            },
            "estilo": {
                "tono": "incisivo",
                "realismo": "alto",
                "estilo_narrativo": "Incisivo, satírico en capas, con tensión constante.",
                "densidad": "medio",
                "exposicion": "gradual",
            },
        },
    },
    "realismo_magico_melancolico": {
        "label": "Realismo mágico melancólico",
        "description": "Lo extraordinario tratado como cotidiano, con nostalgia de fondo.",
        "config": {
            "identidad": {"genero_principal": "realismo_magico", "publico": "adulto"},
            "direccion": {
                "emociones": ["nostalgia", "maravilla", "melancolía"],
                "sensacion_final": "La magia se fue, pero dejó huella en los objetos.",
                "originalidad": "experimental",
                "ambiguedad": "ambiguo_interpretativo",
                "tipo_impacto": ["belleza", "melancolía", "asombro"],
            },
            "motor": {
                "fuente_conflicto": "deseo",
                "mecanismo": "viaje",
                "causalidad": "simbolica",
                "agencia": "media",
                "escalada": "ciclica",
                "cambio_personaje": "maduracion",
            },
            "estilo": {
                "tono": "melancólico",
                "realismo": "medio",
                "grado_especulativo": "leve",
                "estilo_narrativo": "Lírico, sensorial, con normalidad ante lo imposible.",
                "densidad": "denso",
                "exposicion": "por_pistas",
            },
        },
    },
}


def get_preset(name: str) -> dict | None:
    """Get a preset by key. Returns None if not found."""
    return CREATIVE_PRESETS.get(name)


def list_presets() -> list[dict]:
    """Return all presets as a list of {key, label, description} dicts."""
    return [
        {"key": k, "label": v["label"], "description": v["description"]}
        for k, v in CREATIVE_PRESETS.items()
    ]


def apply_preset_to_project(project, preset_name: str) -> bool:
    """Aplica un preset al proyecto, rellenando solo campos vacíos.

    No pisa lo que el usuario ya configuró. Devuelve True si se aplicó,
    False si el preset no existe.
    """
    preset = get_preset(preset_name)
    if preset is None:
        return False

    cc = getattr(project, "creative_config", None)
    if cc is None:
        return False

    config = preset.get("config", {})
    for section_name, fields in config.items():
        section = getattr(cc, section_name, None)
        if section is None or not isinstance(fields, dict):
            continue
        for key, value in fields.items():
            current = getattr(section, key, None)
            if isinstance(value, list):
                if not current:
                    setattr(section, key, list(value))
            elif not current:  # str vacío / None
                setattr(section, key, value)
    return True
