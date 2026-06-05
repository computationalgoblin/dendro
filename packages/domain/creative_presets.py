"""
Creative presets for project configuration (B40).

Each preset is a partial config dict that can be merged into a project's
creative_config.  Presets only set a subset of fields — anything not set
falls back to the CreativeProjectConfig defaults.
"""

from __future__ import annotations

CREATIVE_PRESETS: dict[str, dict] = {
    "tragedia_intima": {
        "label": "Tragedia íntima",
        "description": "Drama personal, emocional, con final trágico o agridulce.",
        "creative_config": {
            "narrative_style": "Introspectivo y cercano.",
            "target_audience": "adulto",
            "creative_intent": {
                "desired_emotions": ["melancolía", "ternura", "culpa"],
                "aftertaste": "Duelo silencioso, eco de lo que pudo ser.",
                "originality": 6,
                "ambiguity": 7,
                "impact_types": ["intimidad", "dilema moral", "melancolía"],
            },
            "narrative_engine": {
                "conflict_sources": ["interno", "interpersonal"],
                "dominant_tension": "friccion_emocional",
                "progression_mechanism": "perdida",
                "character_change": "sacrifica",
                "escalation": "gradual",
                "character_agency": 3,
                "causality": 7,
            },
            "poetics": {
                "narrative_distance": "cercana",
                "description_density": 6,
                "subtext_level": 8,
                "dialogue_styles": ["lacónico", "con mucho subtexto"],
                "exposition_modes": ["implícita", "ambiental"],
            },
            "canon": {
                "continuity_strictness": 8,
                "contradiction_policy": "intentional_only",
            },
        },
        "genre": {"primary_genre": "drama"},
        "tone": {"narrative_tone": "melancolico", "dark_tone_level": "alto"},
        "ai": {"default_strategy": "intensificar", "change_aggressiveness": 3},
    },

    "weird_mystery": {
        "label": "Weird mystery",
        "description": "Misterio que se resiste a explicaciones convencionales.",
        "creative_config": {
            "narrative_style": "Atmosférico, extraño, con lógica propia.",
            "target_audience": "adulto",
            "creative_intent": {
                "desired_emotions": ["inquietud", "fascinación", "extrañeza"],
                "aftertaste": "La sensación de que algo no encaja del todo.",
                "originality": 9,
                "ambiguity": 9,
                "impact_types": ["inquietud", "misterio", "extrañeza"],
            },
            "narrative_engine": {
                "conflict_sources": ["metafísico", "moral"],
                "dominant_tension": "misterio",
                "progression_mechanism": "revelacion",
                "character_change": "descubre_verdad_incomoda",
                "escalation": "falsa_calma",
                "character_agency": 4,
                "causality": 4,
            },
            "poetics": {
                "narrative_distance": "media",
                "description_density": 7,
                "conceptual_density": 8,
                "subtext_level": 9,
                "dialogue_styles": ["evasivo", "fragmentado"],
                "exposition_modes": ["implícita", "mediante contradicciones"],
                "recurring_imagery": ["espejos rotos", "habitaciones que cambian", "silencios largos"],
            },
            "canon": {
                "continuity_strictness": 5,
                "contradiction_policy": "if_interesting",
            },
        },
        "genre": {"primary_genre": "weird_fiction"},
        "tone": {"narrative_tone": "inquietante", "dark_tone_level": "medio"},
        "ai": {"default_strategy": "extranar", "change_aggressiveness": 5},
    },

    "thriller_moral": {
        "label": "Thriller moral",
        "description": "Tensión constante donde las decisiones éticas son el motor.",
        "creative_config": {
            "narrative_style": "Tenso, directo, con dilemas constantes.",
            "target_audience": "adulto",
            "creative_intent": {
                "desired_emotions": ["tensión", "paranoia", "culpa"],
                "aftertaste": "La línea entre correcto y necesario queda borrosa.",
                "originality": 6,
                "ambiguity": 6,
                "impact_types": ["dilema moral", "inquietud"],
            },
            "narrative_engine": {
                "conflict_sources": ["moral", "político", "social"],
                "dominant_tension": "dilema_etico",
                "progression_mechanism": "decision_irreversible",
                "character_change": "corrompe",
                "escalation": "lineal",
                "character_agency": 7,
                "causality": 8,
            },
            "poetics": {
                "narrative_distance": "cercana",
                "description_density": 4,
                "subtext_level": 6,
                "dialogue_styles": ["directo", "irónico"],
                "exposition_modes": ["mediante conflicto", "mediante acciones"],
            },
            "canon": {
                "continuity_strictness": 9,
                "contradiction_policy": "intentional_only",
            },
        },
        "genre": {"primary_genre": "thriller"},
        "tone": {"narrative_tone": "tenso", "dark_tone_level": "alto"},
        "ai": {"default_strategy": "complicar", "change_aggressiveness": 4},
    },

    "fantasia_politica": {
        "label": "Fantasía política",
        "description": "Mundos mágicos con intrigas de poder, alianzas y traiciones.",
        "creative_config": {
            "narrative_style": "Épico pero pragmático, con múltiples facciones.",
            "target_audience": "adulto_joven",
            "creative_intent": {
                "desired_emotions": ["fascinación", "tensión", "esperanza"],
                "aftertaste": "El poder cambia de manos, pero el precio queda.",
                "originality": 7,
                "ambiguity": 5,
                "impact_types": ["épica", "aventura", "dilema moral"],
            },
            "narrative_engine": {
                "conflict_sources": ["político", "bélico", "social"],
                "dominant_tension": "conflicto_politico",
                "progression_mechanism": "choque_intereses",
                "character_change": "transforma",
                "escalation": "en_espiral",
                "character_agency": 7,
                "causality": 7,
            },
            "poetics": {
                "narrative_distance": "media",
                "description_density": 6,
                "conceptual_density": 6,
                "subtext_level": 6,
                "dialogue_styles": ["teatral", "con mucho subtexto"],
                "exposition_modes": ["mediante conflicto", "mediante diálogo"],
            },
            "canon": {
                "continuity_strictness": 8,
                "contradiction_policy": "intentional_only",
            },
        },
        "genre": {"primary_genre": "fantasia"},
        "tone": {"narrative_tone": "equilibrado"},
        "ai": {"default_strategy": "contrastar", "change_aggressiveness": 5},
    },

    "fabula_oscura": {
        "label": "Fábula oscura",
        "description": "Narrativa alegórica con elementos fantásticos y tono siniestro.",
        "creative_config": {
            "narrative_style": "Alegórico, poético, con oscuridad subyacente.",
            "target_audience": "adulto",
            "creative_intent": {
                "desired_emotions": ["inquietud", "fascinación", "melancolía"],
                "aftertaste": "La moraleja no es la que esperabas.",
                "originality": 8,
                "ambiguity": 8,
                "impact_types": ["belleza", "extrañeza", "inquietud"],
            },
            "narrative_engine": {
                "conflict_sources": ["moral", "cósmico"],
                "dominant_tension": "ironia_dramatica",
                "progression_mechanism": "consecuencia_imprevista",
                "character_change": "aprende",
                "escalation": "fragmentaria",
                "character_agency": 4,
                "causality": 5,
            },
            "poetics": {
                "narrative_distance": "observacional",
                "description_density": 7,
                "conceptual_density": 7,
                "subtext_level": 9,
                "dialogue_styles": ["poético", "evasivo"],
                "exposition_modes": ["ambiental", "implícita"],
            },
            "canon": {
                "continuity_strictness": 6,
                "contradiction_policy": "if_interesting",
            },
        },
        "genre": {"primary_genre": "fantasia"},
        "tone": {"narrative_tone": "oscuro", "dark_tone_level": "medio"},
        "ai": {"default_strategy": "subvertir", "change_aggressiveness": 5},
    },

    "drama_coral": {
        "label": "Drama coral",
        "description": "Múltiples personajes entrelazados, cada uno con su propio arco.",
        "creative_config": {
            "narrative_style": "Multiperspectiva, íntimo, con ecos entre tramas.",
            "target_audience": "adulto",
            "creative_intent": {
                "desired_emotions": ["melancolía", "ternura", "esperanza"],
                "aftertaste": "Todas las vidas se tocan, aunque no lo sepan.",
                "originality": 5,
                "ambiguity": 6,
                "impact_types": ["intimidad", "melancolía", "belleza"],
            },
            "narrative_engine": {
                "conflict_sources": ["interpersonal", "familiar", "social"],
                "dominant_tension": "friccion_emocional",
                "progression_mechanism": "transformacion_personal",
                "character_change": "transforma",
                "escalation": "ciclica",
                "character_agency": 6,
                "causality": 6,
            },
            "poetics": {
                "narrative_distance": "cercana",
                "description_density": 5,
                "subtext_level": 7,
                "dialogue_styles": ["naturalista", "con mucho subtexto"],
                "exposition_modes": ["mediante diálogo", "implícita"],
            },
            "canon": {
                "continuity_strictness": 7,
                "contradiction_policy": "intentional_only",
            },
        },
        "genre": {"primary_genre": "drama"},
        "tone": {"narrative_tone": "equilibrado"},
        "ai": {"default_strategy": "conectar", "change_aggressiveness": 4},
    },

    "horror_psicologico": {
        "label": "Horror psicológico",
        "description": "Terror que nace de la mente, no de los monstruos.",
        "creative_config": {
            "narrative_style": "Claustrofóbico, gradual, que cuestiona la realidad.",
            "target_audience": "adulto",
            "creative_intent": {
                "desired_emotions": ["horror", "paranoia", "inquietud"],
                "aftertaste": "No estás seguro de lo que fue real.",
                "originality": 7,
                "ambiguity": 9,
                "impact_types": ["horror", "inquietud", "extrañeza"],
            },
            "narrative_engine": {
                "conflict_sources": ["interno", "metafísico"],
                "dominant_tension": "terror_psicologico",
                "progression_mechanism": "revelacion",
                "character_change": "pierde_agencia",
                "escalation": "falsa_calma",
                "character_agency": 3,
                "causality": 4,
            },
            "poetics": {
                "narrative_distance": "muy_cercana",
                "description_density": 7,
                "subtext_level": 9,
                "dialogue_styles": ["fragmentado", "evasivo"],
                "exposition_modes": ["implícita", "mediante contradicciones"],
            },
            "canon": {
                "continuity_strictness": 5,
                "contradiction_policy": "if_interesting",
            },
        },
        "genre": {"primary_genre": "terror"},
        "tone": {"narrative_tone": "oscuro", "dark_tone_level": "alto"},
        "ai": {"default_strategy": "extranar", "change_aggressiveness": 5},
    },

    "aventura_clasica": {
        "label": "Aventura clásica",
        "description": "Viaje, descubrimiento, crecimiento y regreso transformado.",
        "creative_config": {
            "narrative_style": "Ágil, descriptivo, con sentido de la maravilla.",
            "target_audience": "todos",
            "creative_intent": {
                "desired_emotions": ["maravilla", "euforia", "esperanza"],
                "aftertaste": "El viaje valió la pena, aunque costó más de lo esperado.",
                "originality": 4,
                "ambiguity": 3,
                "impact_types": ["aventura", "asombro"],
            },
            "narrative_engine": {
                "conflict_sources": ["bélico", "ambiental"],
                "dominant_tension": "amenaza_fisica",
                "progression_mechanism": "descubrimiento",
                "character_change": "gana_agencia",
                "escalation": "gradual",
                "character_agency": 8,
                "causality": 7,
            },
            "poetics": {
                "narrative_distance": "media",
                "description_density": 7,
                "subtext_level": 3,
                "dialogue_styles": ["directo", "naturalista"],
                "exposition_modes": ["directa", "ambiental"],
            },
            "canon": {
                "continuity_strictness": 7,
                "contradiction_policy": "not_allowed",
            },
        },
        "genre": {"primary_genre": "fantasia"},
        "tone": {"narrative_tone": "ligero", "humor_level": "bajo"},
        "ai": {"default_strategy": "profundizar", "change_aggressiveness": 5},
    },

    "distopia_social": {
        "label": "Distopía social",
        "description": "Sistema opresivo, resistencia, costos de la rebelión.",
        "creative_config": {
            "narrative_style": "Incisivo, satírico en capas, con tensión constante.",
            "target_audience": "adulto_joven",
            "creative_intent": {
                "desired_emotions": ["tensión", "paranoia", "esperanza"],
                "aftertaste": "El sistema cambia, pero ¿realmente mejora?",
                "originality": 6,
                "ambiguity": 6,
                "impact_types": ["dilema moral", "sátira"],
            },
            "narrative_engine": {
                "conflict_sources": ["político", "social", "económico"],
                "dominant_tension": "paranoia_social",
                "progression_mechanism": "coste_acumulativo",
                "character_change": "libera",
                "escalation": "en_espiral",
                "character_agency": 5,
                "causality": 7,
            },
            "poetics": {
                "narrative_distance": "media",
                "description_density": 5,
                "conceptual_density": 7,
                "subtext_level": 7,
                "dialogue_styles": ["irónico", "directo"],
                "exposition_modes": ["mediante conflicto", "dosificada"],
            },
            "canon": {
                "continuity_strictness": 8,
                "contradiction_policy": "intentional_only",
            },
        },
        "genre": {"primary_genre": "distopia"},
        "tone": {"narrative_tone": "equilibrado", "dark_tone_level": "medio"},
        "ai": {"default_strategy": "complicar", "change_aggressiveness": 5},
    },

    "realismo_magico_melancolico": {
        "label": "Realismo mágico melancólico",
        "description": "Lo extraordinario tratado como cotidiano, con nostalgia de fondo.",
        "creative_config": {
            "narrative_style": "Lírico, sensorial, con normalidad ante lo imposible.",
            "target_audience": "adulto",
            "creative_intent": {
                "desired_emotions": ["nostalgia", "maravilla", "melancolía"],
                "aftertaste": "La magia se fue, pero dejó huella en los objetos.",
                "originality": 7,
                "ambiguity": 7,
                "impact_types": ["belleza", "melancolía", "asombro"],
            },
            "narrative_engine": {
                "conflict_sources": ["familiar", "social", "ambiental"],
                "dominant_tension": "friccion_emocional",
                "progression_mechanism": "transformacion_personal",
                "character_change": "aprende",
                "escalation": "ciclica",
                "character_agency": 5,
                "causality": 4,
            },
            "poetics": {
                "narrative_distance": "cercana",
                "description_density": 8,
                "conceptual_density": 6,
                "subtext_level": 7,
                "dialogue_styles": ["poético", "naturalista"],
                "exposition_modes": ["ambiental", "implícita"],
            },
            "canon": {
                "continuity_strictness": 5,
                "contradiction_policy": "if_interesting",
            },
        },
        "genre": {"primary_genre": "realismo_magico"},
        "tone": {"narrative_tone": "melancolico"},
        "ai": {"default_strategy": "profundizar", "change_aggressiveness": 4},
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
    """Apply a preset to a project, merging config values.

    Does NOT overwrite fields the user has already set to non-default values.
    Only fills in empty/missing fields from the preset.

    Returns True if preset was applied, False if preset not found.
    """
    preset = get_preset(preset_name)
    if preset is None:
        return False

    from packages.domain.project_config import (
        AIConfig,
        GenreConfig,
        ToneConfig,
    )

    cc = project.creative_config

    # Apply creative_config fields from preset (only if currently empty/default)
    preset_cc = preset.get("creative_config", {})
    for key, value in preset_cc.items():
        current = getattr(cc, key, None)
        if isinstance(value, dict):
            # Merge dict: add keys that are empty/missing
            if not current:
                current = {}
            merged = dict(current)
            for dk, dv in value.items():
                if dk not in merged or not merged[dk]:
                    merged[dk] = dv
            setattr(cc, key, merged)
        elif isinstance(value, list):
            if not current:
                setattr(cc, key, list(value))
        elif isinstance(value, (int, float)):
            if not current or current == getattr(type(cc)(), key, None):
                setattr(cc, key, value)
        elif isinstance(value, str):
            if not current:
                setattr(cc, key, value)

    # Apply genre preset
    preset_genre = preset.get("genre", {})
    if preset_genre and isinstance(project.genre, GenreConfig):
        for k, v in preset_genre.items():
            if not getattr(project.genre, k, ""):
                setattr(project.genre, k, v)

    # Apply tone preset
    preset_tone = preset.get("tone", {})
    if preset_tone and isinstance(project.tone, ToneConfig):
        for k, v in preset_tone.items():
            current = getattr(project.tone, k, "neutral")
            if current in ("neutral", "none", ""):
                setattr(project.tone, k, v)

    # Apply AI preset
    preset_ai = preset.get("ai", {})
    if preset_ai and isinstance(project.ai, AIConfig):
        for k, v in preset_ai.items():
            default_val = getattr(AIConfig(), k, None)
            current = getattr(project.ai, k, default_val)
            if current == default_val:
                setattr(project.ai, k, v)

    # Track applied preset
    if preset_name not in cc.presets_applied:
        cc.presets_applied.append(preset_name)

    return True
