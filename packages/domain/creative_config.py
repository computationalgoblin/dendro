"""Configuración creativa canónica del proyecto (PA04).

Modelo de dominio puro (stdlib only). Sustituye a las tres generaciones de
configuración previas (project_config.py Gen A, advanced_config.py Gen B y la
CreativeProjectConfig con dicts sin esquema de B40) por **un único set canónico
de 30 campos** repartidos en 5 secciones tipadas.

El **idioma** del proyecto NO vive aquí: se mantiene en `Project.primary_language`
para no duplicarlo (la sección Identidad de la UI lo edita allí). Las 5 secciones
suman 29 campos; con el idioma son los 30 acordados.

Las listas de categorías (``*_OPCIONES``) son la fuente única de verdad para la
UI (desplegables), la migración de esquema y la validación ligera de ``from_dict``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Catálogos de categorías (fuente única para UI + migración)
# ---------------------------------------------------------------------------

ESTADO_OPCIONES = [
    "borrador",
    "exploracion",
    "canon_en_consolidacion",
    "produccion",
    "campana_activa",
]

ORIGINALIDAD_OPCIONES = [
    "convencional",
    "familiar_con_giro",
    "experimental",
    "extrano",
    "muy_autoral",
]

AMBIGUEDAD_OPCIONES = [
    "claro_directo",
    "equilibrado",
    "ambiguo_interpretativo",
]

FUENTE_CONFLICTO_OPCIONES = [
    "poder",
    "supervivencia",
    "deuda",
    "deseo",
    "trauma",
    "ideologia",
    "religion",
    "escasez",
    "destino",
]

MECANISMO_OPCIONES = [
    "intriga",
    "investigacion",
    "guerra_de_facciones",
    "viaje",
    "decadencia",
    "conspiracion",
    "supervivencia",
    "revelacion",
]

CAUSALIDAD_OPCIONES = [
    "suave",
    "simbolica",
    "estricta",
    "politica",
    "psicologica",
    "sistemica",
]

AGENCIA_OPCIONES = [
    "alta",
    "media",
    "baja",
    "tragica",
    "condicionada",
]

ESCALADA_OPCIONES = [
    "lenta",
    "episodica",
    "acumulativa",
    "explosiva",
    "ciclica",
]

CAMBIO_PERSONAJE_OPCIONES = [
    "corrupcion",
    "redencion",
    "caida",
    "maduracion",
    "radicalizacion",
    "revelacion",
    "ruptura",
]

REALISMO_OPCIONES = [
    "bajo",
    "medio",
    "alto",
]

GRADO_ESPECULATIVO_OPCIONES = [
    "realista",
    "leve",
    "moderado",
    "alto",
    "fantastico_pleno",
]

DENSIDAD_OPCIONES = [
    "ligero",
    "medio",
    "denso",
]

EXPOSICION_OPCIONES = [
    "directa",
    "gradual",
    "por_pistas",
    "fragmentaria",
    "misteriosa",
]


def _str(value: object, default: str = "") -> str:
    return value.strip() if isinstance(value, str) else default


def _str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


# ---------------------------------------------------------------------------
# Secciones (5)
# ---------------------------------------------------------------------------


@dataclass
class Identidad:
    """Qué estamos creando. (idioma vive en Project.primary_language)."""

    premisa: str = ""
    resumen_corto: str = ""
    genero_principal: str = ""
    subgeneros: list[str] = field(default_factory=list)
    formato: str = ""
    publico: str = ""
    estado: str = ""

    def to_dict(self) -> dict:
        return {
            "premisa": self.premisa,
            "resumen_corto": self.resumen_corto,
            "genero_principal": self.genero_principal,
            "subgeneros": list(self.subgeneros),
            "formato": self.formato,
            "publico": self.publico,
            "estado": self.estado,
        }

    @classmethod
    def from_dict(cls, data: object) -> "Identidad":
        d = data if isinstance(data, dict) else {}
        return cls(
            premisa=_str(d.get("premisa")),
            resumen_corto=_str(d.get("resumen_corto")),
            genero_principal=_str(d.get("genero_principal")),
            subgeneros=_str_list(d.get("subgeneros")),
            formato=_str(d.get("formato")),
            publico=_str(d.get("publico")),
            estado=_str(d.get("estado")),
        )


@dataclass
class DireccionCreativa:
    """Hacia dónde debe empujar la IA."""

    promesa: str = ""
    pregunta_dramatica: str = ""
    temas: list[str] = field(default_factory=list)
    emociones: list[str] = field(default_factory=list)
    sensacion_final: str = ""
    originalidad: str = ""
    ambiguedad: str = ""
    tipo_impacto: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "promesa": self.promesa,
            "pregunta_dramatica": self.pregunta_dramatica,
            "temas": list(self.temas),
            "emociones": list(self.emociones),
            "sensacion_final": self.sensacion_final,
            "originalidad": self.originalidad,
            "ambiguedad": self.ambiguedad,
            "tipo_impacto": list(self.tipo_impacto),
        }

    @classmethod
    def from_dict(cls, data: object) -> "DireccionCreativa":
        d = data if isinstance(data, dict) else {}
        return cls(
            promesa=_str(d.get("promesa")),
            pregunta_dramatica=_str(d.get("pregunta_dramatica")),
            temas=_str_list(d.get("temas")),
            emociones=_str_list(d.get("emociones")),
            sensacion_final=_str(d.get("sensacion_final")),
            originalidad=_str(d.get("originalidad")),
            ambiguedad=_str(d.get("ambiguedad")),
            tipo_impacto=_str_list(d.get("tipo_impacto")),
        )


@dataclass
class MotorNarrativo:
    """Claves de coherencia narrativa."""

    fuente_conflicto: str = ""
    mecanismo: str = ""
    causalidad: str = ""
    agencia: str = ""
    escalada: str = ""
    cambio_personaje: str = ""

    def to_dict(self) -> dict:
        return {
            "fuente_conflicto": self.fuente_conflicto,
            "mecanismo": self.mecanismo,
            "causalidad": self.causalidad,
            "agencia": self.agencia,
            "escalada": self.escalada,
            "cambio_personaje": self.cambio_personaje,
        }

    @classmethod
    def from_dict(cls, data: object) -> "MotorNarrativo":
        d = data if isinstance(data, dict) else {}
        return cls(
            fuente_conflicto=_str(d.get("fuente_conflicto")),
            mecanismo=_str(d.get("mecanismo")),
            causalidad=_str(d.get("causalidad")),
            agencia=_str(d.get("agencia")),
            escalada=_str(d.get("escalada")),
            cambio_personaje=_str(d.get("cambio_personaje")),
        )


@dataclass
class EstiloTono:
    """Estilo, tono y lógica del mundo."""

    tono: str = ""
    realismo: str = ""
    grado_especulativo: str = ""
    estilo_narrativo: str = ""
    densidad: str = ""
    exposicion: str = ""

    def to_dict(self) -> dict:
        return {
            "tono": self.tono,
            "realismo": self.realismo,
            "grado_especulativo": self.grado_especulativo,
            "estilo_narrativo": self.estilo_narrativo,
            "densidad": self.densidad,
            "exposicion": self.exposicion,
        }

    @classmethod
    def from_dict(cls, data: object) -> "EstiloTono":
        d = data if isinstance(data, dict) else {}
        return cls(
            tono=_str(d.get("tono")),
            realismo=_str(d.get("realismo")),
            grado_especulativo=_str(d.get("grado_especulativo")),
            estilo_narrativo=_str(d.get("estilo_narrativo")),
            densidad=_str(d.get("densidad")),
            exposicion=_str(d.get("exposicion")),
        )


@dataclass
class ReglasLimites:
    """Lo que la IA nunca debe romper."""

    reglas_canon: list[str] = field(default_factory=list)
    evitar: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "reglas_canon": list(self.reglas_canon),
            "evitar": list(self.evitar),
        }

    @classmethod
    def from_dict(cls, data: object) -> "ReglasLimites":
        d = data if isinstance(data, dict) else {}
        return cls(
            reglas_canon=_str_list(d.get("reglas_canon")),
            evitar=_str_list(d.get("evitar")),
        )


# ---------------------------------------------------------------------------
# Config creativa canónica (compone las 5 secciones)
# ---------------------------------------------------------------------------


@dataclass
class CreativeProjectConfig:
    """Configuración creativa canónica del proyecto (PA04).

    Compone las 5 secciones. Es la única estructura de configuración creativa;
    sustituye a Gen A/B y a los dicts sin esquema de B40.
    """

    identidad: Identidad = field(default_factory=Identidad)
    direccion: DireccionCreativa = field(default_factory=DireccionCreativa)
    motor: MotorNarrativo = field(default_factory=MotorNarrativo)
    estilo: EstiloTono = field(default_factory=EstiloTono)
    reglas: ReglasLimites = field(default_factory=ReglasLimites)

    def to_dict(self) -> dict:
        return {
            "identidad": self.identidad.to_dict(),
            "direccion": self.direccion.to_dict(),
            "motor": self.motor.to_dict(),
            "estilo": self.estilo.to_dict(),
            "reglas": self.reglas.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: object) -> "CreativeProjectConfig":
        d = data if isinstance(data, dict) else {}
        return cls(
            identidad=Identidad.from_dict(d.get("identidad")),
            direccion=DireccionCreativa.from_dict(d.get("direccion")),
            motor=MotorNarrativo.from_dict(d.get("motor")),
            estilo=EstiloTono.from_dict(d.get("estilo")),
            reglas=ReglasLimites.from_dict(d.get("reglas")),
        )
