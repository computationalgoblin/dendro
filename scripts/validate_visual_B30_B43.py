#!/usr/bin/env python3
"""Validación visual interactiva B30-B43 — Narrative Architect / Dendro.

Ejecutar DESDE WINDOWS NATIVO con la app abierta al lado:
    python scripts/validate_visual_B30_B43.py

El script te fuerza a responder cada punto. No avanza sin respuesta.
Al final genera un informe en docs/pruebas/resultados/.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

RESULTS_DIR = Path("docs/pruebas/resultados")


def _sep(char: str = "─", width: int = 70) -> None:
    print(char * width)


def _header(block: str, title: str) -> None:
    print()
    _sep("═")
    print(f"{BOLD}{CYAN}  {block} — {title}{RESET}")
    _sep("═")
    print()


def _instruction(text: str) -> None:
    print(f"{YELLOW}  ► {text}{RESET}")
    print()


def _expect(text: str) -> None:
    print(f"  Esperado: {text}")
    print()


def ask_pass(label: str) -> str:
    """Pregunta Sí/No/Parcial/N/A. No acepta otra cosa."""
    valid = {"s", "n", "p", "na"}
    while True:
        resp = input(f"  {BOLD}[{label}]{RESET} ¿Correcto? (s/n/p/na): ").strip().lower()
        if resp in valid:
            return resp
        print(f"    {RED}Responde: s=sí, n=no, p=parcial, na=no aplica{RESET}")


def ask_notes() -> str:
    """Pregunta notas opcionales."""
    resp = input("  Notas (Enter para saltar): ").strip()
    return resp


def ask_text(prompt: str) -> str:
    resp = input(f"  {prompt}: ").strip()
    return resp


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class CheckResult:
    def __init__(self, block: str, item: str):
        self.block = block
        self.item = item
        self.verdict: str = ""
        self.notes: str = ""

    def to_dict(self) -> dict:
        return {
            "bloque": self.block,
            "item": self.item,
            "veredicto": self.verdict,
            "notas": self.notes,
        }


all_results: list[CheckResult] = []


def check(block: str, item: str, instruction: str, expected: str) -> CheckResult:
    """Muestra instrucción, espera verificación, registra resultado."""
    _instruction(instruction)
    _expect(expected)
    r = CheckResult(block, item)
    r.verdict = ask_pass(item)
    r.notes = ask_notes()
    all_results.append(r)
    return r


# ---------------------------------------------------------------------------
# Intro
# ---------------------------------------------------------------------------

def intro() -> dict:
    print()
    _sep("═")
    print(f"{BOLD}{CYAN}  VALIDACIÓN VISUAL INTERACTIVA B30-B43{RESET}")
    print(f"  Narrative Architect / Dendro — Desktop")
    _sep("═")
    print()
    print("  Este script te guía por TODOS los aspectos visuales/producto")
    print("  implementados desde B30 hasta B43.")
    print()
    print("  Debes tener la app abierta en Windows nativo al lado.")
    print("  Responde s/n/p/na a cada pregunta. No puedes saltar nada.")
    print()

    info = {}
    info["fecha"] = datetime.now().isoformat()
    info["windows"] = ask_text("Versión Windows (ej: 11 24H2)")
    info["python"] = ask_text("Versión Python (ej: 3.12.4)")
    info["rama"] = ask_text("Rama git activa")
    info["json"] = ask_text("Ruta del JSON de prueba (Enter si aún no creado)")
    return info


# ---------------------------------------------------------------------------
# Bloques
# ---------------------------------------------------------------------------

def b30() -> None:
    _header("B30", "Gate integrado y pulido UI base")
    check("B30", "arranque",
          "Arranca la app: python -m hosts.DesktopHostPySide.main",
          "La ventana principal abre sin traceback ni crash visible.")
    check("B30", "navegacion",
          "Entra y sale de cada espacio principal (Home, Creación, Galería, Sesión).",
          "Todos los espacios abren, no hay paneles vacíos que bloqueen el flujo.")
    check("B30", "sin_placeholders",
          "Revisa que no hay botones primarios deshabilitados sin alternativa, "
          "ni paneles stub como experiencia principal.",
          "No hay placeholders bloqueantes.")
    check("B30", "guardar_cargar",
          "Crea/abre un proyecto, guárdalo, cierra la app, reabre el mismo JSON.",
          "Los datos visibles sobreviven cerrar/abrir.")


def b31() -> None:
    _header("B31", "UX inmersiva Desktop")
    check("B31", "home_inmersivo",
          "Observa Home. ¿La pantalla es inmersiva/minimalista, sin IDs/JSON/schema?",
          "Modo normal prioriza lenguaje de autor/producto.")
    check("B31", "paneles_internos",
          "Navega a Creación, selecciona un nodo. ¿El detalle se abre dentro de la app?",
          "Paneles se abren internamente (RightDrawer), no como QDialog externo.")
    check("B31", "limpieza_home",
          "Vuelve a Home. ¿Se limpian paneles contextuales/overlays de Creación?",
          "Home se limpia al volver.")
    check("B31", "modo_avanzado",
          "Activa modo avanzado si existe el control. ¿Aparecen datos técnicos razonables?",
          "Modo avanzado separa datos técnicos de UX normal. Desactiva después.")


def b32() -> None:
    _header("B32", "Hardening / UX normal vs avanzado / deuda")
    check("B32", "sin_etiquetas_tecnicas",
          "En modo normal, recorre Creación, Galería, Configuración. "
          "¿Hay etiquetas tipo 'Corpus técnico', 'Relaciones técnicas', 'Candidatos técnicos'?",
          "No hay etiquetas técnicas en modo normal.")
    check("B32", "avanzado_tecnico",
          "Activa modo avanzado. ¿Lo técnico aparece accesible sin romper modo normal?",
          "Lo técnico queda detrás del modo avanzado.")
    check("B32", "normal_funcional",
          "Desactiva avanzado. ¿Se puede crear/editar contenido sin depender del modo avanzado?",
          "Modo normal sigue siendo funcional.")


def b33() -> None:
    _header("B33", "Creación MVP: hojas, relaciones, IA inline")
    check("B33", "crear_hoja",
          "En Creación, crea una Hoja/personaje llamada 'Devian'.",
          "La hoja aparece en el grafo/lista.")
    check("B33", "crear_segunda_hoja",
          "Crea otra Hoja/personaje llamada 'Akshan'.",
          "Akshan aparece junto a Devian.")
    check("B33", "crear_relacion",
          "Crea una relación entre Devian y Akshan con texto 'Devian traiciona a Akshan'.",
          "La relación aparece en el grafo.")
    check("B33", "panel_detalle",
          "Selecciona Devian. ¿Aparece panel de detalle con datos editables?",
          "Panel de detalle visible y editable.")
    check("B33", "ia_inline",
          "Usa una acción IA inline sobre Devian (redacción/mejora) si está visible.",
          "La IA muestra sugerencia/preview/error pero NO crea canon automáticamente.")
    check("B33", "candidato_no_canon",
          "Revisa si los candidatos/sugerencias se muestran como entidades reales.",
          "Candidatos NO son entidades hasta aceptación explícita.")
    check("B33", "persistencia",
          "Guarda proyecto, cierra y reabre el JSON. ¿Devian y Akshan reaparecen?",
          "Hojas y relaciones persisten tras recarga.")


def b34() -> None:
    _header("B34", "Árboles/Ramas y contexto jerárquico")
    check("B34", "crear_rama",
          "Crea una Rama/agrupación llamada 'Bosque de Ceniza'.",
          "La Rama aparece en el grafo.")
    check("B34", "añadir_miembros",
          "Añade Devian y/o Santuario del Núcleo Negro como miembros de esa Rama.",
          "Los miembros se ven asociados a la Rama.")
    check("B34", "panel_rama",
          "Selecciona la Rama. ¿El panel muestra identidad, función narrativa, miembros?",
          "Panel de Rama completo.")
    check("B34", "collapse_expand",
          "Probar expandir/colapsar la Rama si existe control visual.",
          "Collapse/expand funciona (imperfecto = deuda DC-034, no FALLA).")
    check("B34", "relacion_rama",
          "Crea relación Rama → Hoja o viceversa.",
          "Relación se crea sin error.")
    check("B34", "no_ciclos",
          "Intenta crear ciclo árbol → árbol si el flujo lo expone.",
          "No se permiten ciclos inválidos.")


def b35() -> None:
    _header("B35", "Coherencia de subgrafo")
    check("B35", "analisis",
          "Selecciona un subgrafo con Devian, Akshan y relaciones. "
          "Abre análisis de coherencia.",
          "El análisis ejecuta y muestra resultado.")
    check("B35", "resultado_diferenciado",
          "Revisa que el resultado distingue: contradicciones, huecos, oportunidades.",
          "El resultado está categorizado, no es un bloque plano.")
    check("B35", "reparacion_revisable",
          "Ejecuta reparación de coherencia si existe.",
          "La reparación queda como propuesta/candidato revisable, NO canon directo.")
    check("B35", "aceptar_descartar",
          "Acepta o descarta manualmente una propuesta.",
          "La acción queda registrada; no irreversible sin aceptación.")


def b36() -> None:
    _header("B36", "Worldbuilding por capas causales")
    check("B36", "activar_worldbuilding",
          "Activa modo Worldbuilding en el proyecto si existe interruptor.",
          "Control 'Vista Capas causales' o equivalente aparece.")
    check("B36", "crear_capa",
          "Crea/asigna una capa/anillo llamada 'Metafísica de los Dioses-Agujero'.",
          "La capa se crea y aparece.")
    check("B36", "asignar_capa",
          "Asigna 'Santuario del Núcleo Negro' a una capa inferior.",
          "La asignación funciona.")
    check("B36", "relacion_causal",
          "Crea una relación causal (deriva_de/condiciona/explica/contradice/produce_consecuencia_en).",
          "Relación causal distinguible de pertenencia estructural.")
    check("B36", "ia_capa_inferior",
          "Prueba acción IA 'Expandir hacia capa inferior' si aparece.",
          "Produce sugerencia/preview, no canon automático.")
    check("B36", "ia_causas_superiores",
          "Prueba acción IA 'Explicar desde causas superiores' si aparece.",
          "Produce sugerencia/preview, no canon automático.")
    check("B36", "desactivar_worldbuilding",
          "Desactiva Worldbuilding. ¿Oculta controles sin borrar capas existentes?",
          "Worldbuilding OFF oculta controles; datos preservados.")


def b37() -> None:
    _header("B37", "Creación a escala: búsqueda, filtros, foco, cámara")
    check("B37", "busqueda",
          "Usa búsqueda con término 'Devian'.",
          "Encuentra y resalta/selecciona Devian.")
    check("B37", "busqueda_parcial",
          "Busca un término parcial que exista en descripción o tipo.",
          "Búsqueda parcial funciona.")
    check("B37", "filtros_tipo",
          "Aplica filtros por tipo de entidad.",
          "Filtro funciona; no borra datos, sólo cambia vista.")
    check("B37", "filtros_relacion",
          "Aplica filtros por tipo/familia de relación.",
          "Filtro funciona.")
    check("B37", "filtros_capa",
          "Aplica filtros por capa/anillo si disponibles.",
          "Filtro funciona.")
    check("B37", "foco_arbol",
          "Selecciona una Rama y usa 'Enfocar árbol' si existe.",
          "Foco acerca la vista; es reversible.")
    check("B37", "foco_vecindad",
          "Selecciona una Hoja y usa 'Enfocar vecindad' si existe.",
          "Foco funciona; es reversible.")
    check("B37", "camara",
          "Prueba cámara: centrar selección, encajar todo, reset.",
          "Todas las acciones de cámara son reversibles.")
    check("B37", "bandeja_sugerencias",
          "Revisa la bandeja unificada de sugerencias/candidatos IA.",
          "Muestra candidatos sin canonizarlos.")
    check("B37", "flyout_capas",
          "Mueve el ratón al borde izquierdo del canvas para abrir flyout de capas.",
          "Flyout aparece sin bloquear canvas.")


def b38() -> None:
    _header("B38", "Command bar IA + jobs revisables")
    check("B38", "command_bar_visible",
          "En Creación, localiza la command bar IA.",
          "La command bar es visible y accesible.")
    check("B38", "smoke_personajes",
          "Escribe: 'Créame tres personajes hermanos traidores, tono tragicómico.'\n"
          "Confirma que aparece un job en Jobs/Tareas IA.",
          "Job aparece; UI no se congela; progreso visible.")
    check("B38", "resultado_temático",
          "Abre el resultado del smoke de personajes.",
          "Respeta hermanos + traición mutua + tono tragicómico.")
    check("B38", "no_canon_automatico",
          "Verifica que el resultado NO creó nodos reales automáticamente.",
          "Sin canon automático.")
    check("B38", "aceptar_candidato",
          "Convierte un resultado a candidato, acepta uno.",
          "Aceptación crea entidad real.")
    check("B38", "rechazar_candidato",
          "Rechaza otro candidato.",
          "Rechazo NO crea entidad.")
    check("B38", "smoke_metafisico",
          "Escribe: 'Crea un sistema metafísico de dos agujeros negros que son dioses combatiendo.'\n"
          "Verifica que NO devuelve los mismos personajes del smoke anterior.",
          "Resultado distinto al anterior; habla de agujeros negros/dioses/combate.")
    check("B38", "error_provider",
          "Si es seguro, desconfigura provider/API key o usa provider inválido.\n"
          "Lanza petición simple.",
          "Estado 'failed' con error claro. NO simula éxito.")


def b39() -> None:
    _header("B39", "Modelo visible Hoja/Rama/Anillo")
    check("B39", "lenguaje_normal",
          "Recorre Creación, panel nodo, rama, capa, config.\n"
          "¿El lenguaje usa Hoja/Rama/Anillo/Relación/Candidato?",
          "UX normal usa términos de producto, no técnicos.")
    check("B39", "sin_tecnicos",
          "Busca términos como EntityType.CONTENEDOR, NarrativeEntity, WorldLayer en modo normal.",
          "No aparecen términos técnicos en modo normal.")
    check("B39", "convertir_hoja_rama",
          "Convierte una Hoja a Rama si el control existe.",
          "Transformación explícita y no destructiva.")
    check("B39", "convertir_rama_anillo",
          "Convierte una Rama a Anillo si el control existe.",
          "Transformación no pierde datos.")


def b40() -> None:
    _header("B40", "Configuración creativa + Wizard")
    check("B40", "wizard_aparece",
          "Crea proyecto nuevo. ¿Aparece wizard de creación?",
          "Wizard visible al crear proyecto.")
    check("B40", "wizard_pasos",
          "Recorre los pasos del wizard (bienvenida, género, mundo, dirección, "
          "narrativa, estilo, reglas, IA).",
          "Wizard navegable sin crash.")
    check("B40", "wizard_preset",
          "Aplica un preset creativo y elige ruta JSON explícita.",
          "Preset se aplica; ruta JSON es la elegida.")
    check("B40", "wizard_grafo_vacio",
          "Al terminar el wizard, ¿el grafo está vacío o sólo con datos aceptados?",
          "No hay presets/candidatos como entidades indelebles.")
    check("B40", "config_secciones",
          "Abre configuración del proyecto. ¿Existen las secciones "
          "(Básico, Dirección, Narrativa, Estilo, Reglas, IA, Evitar, Memoria, Ramas)?",
          "Secciones de config visibles.")
    check("B40", "config_edita_persiste",
          "Edita un campo (premisa/resumen/tono), guarda, cierra y reabre.",
          "El campo editado persiste tras recarga.")
    check("B40", "overrides_rama",
          "En una Rama, revisa si existen overrides creativos.",
          "Overrides visibles si implementados.")
    check("B40", "ia_refleja_config",
          "Ejecuta sugerencia IA. ¿Refleja el perfil creativo configurado?",
          "IA usa config creativa como contexto.")


def b41() -> None:
    _header("B41", "Hitos causales")
    check("B41", "crear_hito",
          "Crea un hito llamado 'Nacimiento del Núcleo Negro'.",
          "El hito aparece en panel/lista/grafo.")
    check("B41", "asociar_hito",
          "Asocia el hito a 'Metafísica de los Dioses-Agujero' o a una capa.",
          "Asociación funciona.")
    check("B41", "hito_desde_seleccion",
          "Selecciona elementos del grafo y usa 'Crear hito desde selección' si existe.",
          "Hito se crea desde selección.")
    check("B41", "ia_clasificacion",
          "Prueba acción IA de clasificación/intención de hito si está visible.",
          "IA propone/revisa; no canoniza automáticamente.")
    check("B41", "reviewer_hito",
          "Prueba reviewer de candidato de hito en bandeja/candidatos.",
          "Reviewer funciona.")
    check("B41", "status_quo",
          "Prueba 'status quo explainer' o explicación del estado actual si visible.",
          "Explicación generada o error claro.")
    check("B41", "persistencia_hito",
          "Guarda, cierra, reabre. ¿El hito persiste?",
          "Hito persiste tras recarga.")


def b42() -> None:
    _header("B42", "Hardening IA: gateway, sanitización, observabilidad")
    check("B42", "no_api_keys",
          "Abre Ajustes IA. ¿Se muestran API keys completas en claro?",
          "No se muestran API keys completas en paneles normales.")
    check("B42", "provider_ok",
          "Ejecuta petición IA desde command bar o inline con provider configurado.",
          "Resultado revisable sin éxito simulado.")
    check("B42", "provider_fail",
          "Falla el provider (desconfigura o usa inválido). ¿Error claro?",
          "Error visible; no contenido falso como éxito.")
    check("B42", "observabilidad",
          "Busca panel/log/diagnóstico IA en modo avanzado.",
          "Observabilidad existe y NO expone API keys completas ni secretos.")
    check("B42", "duplicados",
          "Repite petición que produciría candidato duplicado.",
          "Duplicados se marcan/deduplican o no indistinguibles.")


def b43() -> None:
    _header("B43", "Prompt Registry / sin regresión IA inline")
    check("B43", "command_bar_prompt",
          "Ejecuta command bar IA con prompt simple. Observa el texto mostrado.",
          "No hay placeholders sin sustituir como {context}, {selection}, {language}.")
    check("B43", "inline_hoja",
          "Ejecuta IA inline sobre una Hoja.",
          "Responde o falla de forma visible. Sin placeholders rotos.")
    check("B43", "inline_relacion",
          "Ejecuta IA inline sobre una Relación si existe.",
          "Funciona o falla visiblemente.")
    check("B43", "coherencia_prompt",
          "Ejecuta análisis de coherencia.",
          "Sin placeholders sin sustituir.")
    check("B43", "reparacion_prompt",
          "Ejecuta reparación de coherencia si existe.",
          "Sin placeholders rotos; no canoniza automáticamente.")
    check("B43", "sin_texto_registry",
          "En UX normal, ¿aparece texto técnico del Prompt Registry?",
          "No aparece texto del registry en UX normal.")


def persistencia_final() -> None:
    _header("FINAL", "Persistencia cross-bloque")
    _instruction("Guarda el proyecto, cierra la app, reabre y abre el mismo JSON.")
    print("  Verifica que persisten TODOS estos elementos:\n")
    elementos = [
        "Devian (Hoja)",
        "Akshan (Hoja)",
        "Hermandad del Acero (Rama)",
        "Bosque de Ceniza (Rama)",
        "Santuario del Núcleo Negro (Hoja/lugar)",
        "Relaciones creadas",
        "Ramas/árboles",
        "Capas/Anillos",
        "Configuración creativa",
        "Hitos causales",
        "Candidatos aceptados (como canon)",
        "Candidatos rechazados (NO como canon)",
    ]
    for elem in elementos:
        check("FINAL", f"persiste_{elem.split('(')[0].strip().lower().replace(' ', '_')}",
              f"¿Persiste: {elem}?", elem)


def resumen_final(info: dict) -> None:
    _header("RESUMEN", "Resultado global")

    # Contar resultados
    passes = [r for r in all_results if r.verdict == "s"]
    fails = [r for r in all_results if r.verdict == "n"]
    partials = [r for r in all_results if r.verdict == "p"]
    nas = [r for r in all_results if r.verdict == "na"]
    total = len(all_results)

    print(f"  Total checks: {total}")
    print(f"  {GREEN}PASA:   {len(passes)}{RESET}")
    print(f"  {RED}FALLA:  {len(fails)}{RESET}")
    print(f"  {YELLOW}PARCIAL: {len(partials)}{RESET}")
    print(f"  N/A:    {len(nas)}")
    print()

    if fails:
        print(f"{RED}  ╔══ FALLOS BLOQUEANTES ══╗{RESET}")
        for r in fails:
            print(f"  {RED}✗ {r.block} — {r.item}{RESET}")
            if r.notes:
                print(f"    Notas: {r.notes}")
        print()

    if partials:
        print(f"{YELLOW}  ╔══ PARCIALES (deuda no bloqueante) ══╗{RESET}")
        for r in partials:
            print(f"  {YELLOW}⚠ {r.block} — {r.item}{RESET}")
            if r.notes:
                print(f"    Notas: {r.notes}")
        print()

    veredicto_global = "PASA" if not fails else "NO PASA"
    if not fails and partials:
        veredicto_global = "PASA CON DEUDA"

    print(f"  {BOLD}VEREDICTO GLOBAL: {veredicto_global}{RESET}")
    print()

    # Preguntar decisión
    print("  Decisión post-prueba:")
    print("  1) B36-B43 pueden marcarse Windows OK")
    print("  2) Hay que abrir bloque/ticket de hardening Windows")
    print("  3) Hay bugs concretos — reportar")
    decision = ask_text("Opción (1/2/3)")
    notas_decision = ask_text("Notas adicionales")

    # Guardar resultado
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = RESULTS_DIR / f"resultado_B30_B43_{ts}.json"

    report = {
        "meta": info,
        "veredicto_global": veredicto_global,
        "decision": decision,
        "notas_decision": notas_decision,
        "conteo": {
            "total": total,
            "pasa": len(passes),
            "falla": len(fails),
            "parcial": len(partials),
            "na": len(nas),
        },
        "resultados": [r.to_dict() for r in all_results],
    }

    out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print()
    _sep()
    print(f"  {GREEN}Informe guardado en: {out_file}{RESET}")
    _sep()

    # También generar texto plano legible
    txt_file = RESULTS_DIR / f"resultado_B30_B43_{ts}.txt"
    lines = []
    lines.append(f"VALIDACIÓN VISUAL B30-B43 — {info.get('fecha', '')}")
    lines.append(f"Windows: {info.get('windows', '')} | Python: {info.get('python', '')}")
    lines.append(f"Rama: {info.get('rama', '')} | JSON: {info.get('json', '')}")
    lines.append(f"VEREDICTO: {veredicto_global}")
    lines.append(f"Total: {total} | Pasa: {len(passes)} | Falla: {len(fails)} | Parcial: {len(partials)} | N/A: {len(nas)}")
    lines.append("")
    lines.append("═" * 60)
    for r in all_results:
        icon = {"s": "✓", "n": "✗", "p": "⚠", "na": "○"}.get(r.verdict, "?")
        line = f"  {icon} [{r.block}] {r.item}"
        if r.notes:
            line += f"  — {r.notes}"
        lines.append(line)
    lines.append("═" * 60)
    lines.append(f"Decisión: {decision}")
    lines.append(f"Notas: {notas_decision}")
    txt_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Texto plano guardado en: {txt_file}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    os.system("")  # Habilitar ANSI en Windows
    info = intro()

    bloques = [
        ("B30 — Gate integrado", b30),
        ("B31 — UX inmersiva", b31),
        ("B32 — Hardening/avanzado", b32),
        ("B33 — Creación MVP", b33),
        ("B34 — Árboles/Ramas", b34),
        ("B35 — Coherencia subgrafo", b35),
        ("B36 — Capas causales", b36),
        ("B37 — Creación a escala", b37),
        ("B38 — Command bar IA", b38),
        ("B39 — Modelo visible", b39),
        ("B40 — Config creativa", b40),
        ("B41 — Hitos causales", b41),
        ("B42 — Hardening IA", b42),
        ("B43 — Prompt Registry", b43),
        ("FINAL — Persistencia", persistencia_final),
    ]

    for nombre, fn in bloques:
        fn()

    resumen_final(info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
