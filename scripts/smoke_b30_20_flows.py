#!/usr/bin/env python3
"""B30-T02: Smoke test de los 20 flujos obligatorios (§30.2).

Ejecuta cada flujo contra el CLI real, captura outputs y verifica
que no hay pérdida de datos tras save/close/open.

Uso:
    python scripts/smoke_b30_20_flows.py [--json] [--verbose]
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, tempfile, time
from pathlib import Path
from typing import Any

# ── Helpers ───────────────────────────────────────────────────────────

WORKSPACE = str(Path(__file__).resolve().parents[1])

def _cli(*args: str, expect_ok: bool = True) -> subprocess.CompletedProcess:
    """Run a CLI command against the test project."""
    cmd = [sys.executable, "-m", "narrative_architect", *args]
    env = {**os.environ, "PYTHONPATH": WORKSPACE, "PYTHONUTF8": "1"}
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       env=env, timeout=30)
    if expect_ok and r.returncode != 0:
        print(f"  FAIL: {' '.join(args)}", file=sys.stderr)
        print(f"    stderr: {r.stderr.strip()[:200]}", file=sys.stderr)
    return r

def _extract_id(output: str) -> str:
    """Extract an ID from CLI output (UUID, short hex, or prefixed)."""
    import re
    # Try UUID first
    m = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', output)
    if m: return m.group(1)
    # Try prefixed short ID in parentheses: (ses_abc123), (plr_abc123), (src_abc123)
    m = re.search(r'\(([a-z]{1,4}_?[0-9a-f]{4,})\)', output)
    if m: return m.group(1)
    # Try plain hex ID in parentheses: (abc123...)
    m = re.search(r'\(([0-9a-f]{8,})\)', output)
    if m: return m.group(1)
    return ""

def _ok(label: str, r: subprocess.CompletedProcess) -> bool:
    """Assert command succeeded."""
    if r.returncode == 0:
        print(f"  OK  {label}")
        return True
    else:
        print(f"  FAIL {label} (exit {r.returncode})")
        if r.stderr: print(f"       {r.stderr.strip()[:200]}")
        return False

# ── Smoke Flows ───────────────────────────────────────────────────────

def run_all(project_path: str, verbose: bool = False) -> dict[str, Any]:
    results: dict[str, Any] = {}
    all_pass = True

    def record(flow: int, name: str, ok: bool, detail: str = ""):
        status = "PASS" if ok else "FAIL"
        results[f"{flow:02d}"] = {"name": name, "status": status, "detail": detail}
        if not ok: nonlocal all_pass; all_pass = False
        return ok

    # ── Flujo 01: Crear proyecto desde cero ──
    print("\n[01] Crear proyecto desde cero")
    r = _cli("project", "create", "SmokeWorld", "--path", project_path)
    record(1, "project create", _ok("create", r), r.stdout.strip()[:100])

    # ── Flujo 02: Crear mundo con entidades y relaciones ──
    print("\n[02] Crear mundo con entidades y relaciones")
    r = _cli("entity", "create", "Frodo", "--type", "personaje")
    ok1 = _ok("entity create Frodo", r)
    frodo_id = _extract_id(r.stdout)

    r = _cli("entity", "create", "Gandalf", "--type", "personaje")
    ok2 = _ok("entity create Gandalf", r)
    gandalf_id = _extract_id(r.stdout)

    r = _cli("entity", "create", "Mordor", "--type", "localizacion")
    ok3 = _ok("entity create Mordor", r)
    mordor_id = _extract_id(r.stdout)

    r = _cli("relation", "create", frodo_id, gandalf_id, "--type", "es_aliado_de")
    ok4 = _ok("relation create Frodo-Gandalf", r)
    rel_id = _extract_id(r.stdout)

    record(2, "entities + relations", ok1 and ok2 and ok3 and ok4,
           f"frodo={frodo_id[:8]} gandalf={gandalf_id[:8]} mordor={mordor_id[:8]}")

    # ── Flujo 03: Organizar entidades en galerías ──
    print("\n[03] Organizar entidades en galerías")
    r = _cli("gallery", "personajes")
    record(3, "gallery personajes", _ok("gallery personajes", r), r.stdout.strip()[:100])

    # ── Flujo 04: Visualizar relaciones en grafo ──
    print("\n[04] Visualizar relaciones en grafo")
    r = _cli("graph", "summary")
    record(4, "graph summary", _ok("graph summary", r), r.stdout.strip()[:100])

    # ── Flujo 05: Configurar capas, tono, género y realismo ──
    print("\n[05] Configurar capas, tono, género y realismo")
    r = _cli("project", "config", "set", "genre.primary_genre", '"alta fantasia"')
    ok1 = _ok("config set genre.primary_genre", r)
    r = _cli("project", "config", "set", "tone.narrative_tone", '"epico"')
    ok2 = _ok("config set tone.narrative_tone", r)
    r = _cli("layer", "list")
    ok3 = _ok("layer list", r)
    record(5, "config layers/tone/genre", ok1 and ok2 and ok3, r.stdout.strip()[:100])

    # ── Flujo 06: Crear marco narrativo ──
    print("\n[06] Crear marco narrativo")
    r = _cli("framework", "create", "La Guerra del Anillo", "--type", "historia")
    ok1 = _ok("framework create", r)
    fw_id = _extract_id(r.stdout)
    record(6, "framework create", ok1, f"fw={fw_id[:8]}")

    # ── Flujo 07: Ejecutar validación de consistencia ──
    print("\n[07] Validación de consistencia")
    r = _cli("issue", "validate")
    record(7, "issue validate", _ok("issue validate", r), r.stdout.strip()[:100])

    # ── Flujo 08: Generar sugerencias IA y aceptarlas ──
    print("\n[08] Generar sugerencias IA")
    r = _cli("ai", "suggest-tags", frodo_id)
    ok1 = _ok("ai suggest-tags", r)
    r = _cli("candidate", "list")
    ok2 = _ok("candidate list", r)
    cand_id = _extract_id(r.stdout)
    if cand_id:
        r = _cli("candidate", "accept", cand_id)
        ok3 = _ok("candidate accept", r)
    else:
        ok3 = True
    record(8, "ai suggest + candidate accept", ok1 and ok2 and ok3, f"cand={cand_id[:8] if cand_id else 'none'}")

    # ── Flujo 09: Importar documento y revisar candidatos ──
    print("\n[09] Importar documento")
    tmp_doc = Path(project_path).parent / "smoke_import.txt"
    tmp_doc.write_text("Frodo encontro el Anillo en el monte del Destino.", encoding="utf-8")
    r = _cli("import", "document", str(tmp_doc))
    ok1 = _ok("import document", r)
    r = _cli("import", "basket", "list")
    ok2 = _ok("import basket list", r)
    tmp_doc.unlink(missing_ok=True)
    record(9, "import document + basket", ok1 and ok2, r.stdout.strip()[:100])

    # ── Flujo 10: Crear historia con escenas ──
    print("\n[10] Crear historia con escenas")
    r = _cli("writing", "create", "El Viaje del Anillo", "--type", "historia")
    ok1 = _ok("writing create", r)
    story_id = _extract_id(r.stdout)
    if story_id:
        r = _cli("writing", "link", story_id, frodo_id)
        ok2 = _ok("writing link", r)
    else:
        ok2 = True
    record(10, "writing create + link", ok1 and ok2, f"story={story_id[:8] if story_id else 'none'}")

    # ── Flujo 11: Crear campaña de rol ──
    print("\n[11] Crear campaña de rol")
    r = _cli("campaign", "create", "La Comunidad del Anillo")
    ok1 = _ok("campaign create", r)
    camp_id = _extract_id(r.stdout)
    record(11, "campaign create", ok1, f"camp={camp_id[:8] if camp_id else 'none'}")

    # ── Flujo 12: Crear personajes jugadores ──
    print("\n[12] Crear personajes jugadores")
    if camp_id:
        r = _cli("campaign", "player-add", camp_id, "player1")
        ok1 = _ok("player-add", r)
        player_id = _extract_id(r.stdout)  # e.g. plr_abc123
        if player_id:
            r = _cli("campaign", "pc-assign", camp_id, player_id, frodo_id)
            ok2 = _ok("pc-assign Frodo", r)
        else:
            ok2 = False
    else:
        ok1 = ok2 = False
    record(12, "campaign player-add + pc-assign", ok1 and ok2)

    # ── Flujo 13: Crear secretos y pistas ──
    print("\n[13] Crear secretos y pistas")
    r = _cli("secret", "create", "El Anillo es maligno", "--entity", mordor_id)
    ok1 = _ok("secret create", r)
    secret_id = _extract_id(r.stdout)
    r = _cli("clue", "create", "Huellas de Hobbit en Mordor", "--entity", mordor_id)
    ok2 = _ok("clue create", r)
    clue_id = _extract_id(r.stdout)
    record(13, "secret + clue create", ok1 and ok2, f"secret={secret_id[:8] if secret_id else 'none'} clue={clue_id[:8] if clue_id else 'none'}")

    # ── Flujo 14: Preparar sesión ──
    print("\n[14] Preparar sesión")
    if camp_id:
        r = _cli("session", "create", "Sesion 1: Salida de Bolsa Cerrado", "--campaign", camp_id, "--number", "1")
        ok1 = _ok("session create", r)
        sess_id = _extract_id(r.stdout)
    else:
        ok1 = False; sess_id = ""
    record(14, "session create", ok1, f"sess={sess_id[:8] if sess_id else 'none'}")

    # ── Flujo 15: Dirigir sesión en vivo ──
    print("\n[15] Dirigir sesión en vivo")
    if sess_id:
        r = _cli("session", "live", "open", sess_id)
        ok1 = _ok("live open", r)
        r = _cli("session", "live", "note", sess_id, "Los Hobbits encuentran a Tom Bombadil")
        ok2 = _ok("live note", r)
        r = _cli("session", "live", "event", sess_id, "Encuentro con los Nazgul")
        ok3 = _ok("live event", r)
        r = _cli("session", "live", "check", sess_id)
        ok4 = _ok("live check", r)
    else:
        ok1 = ok2 = ok3 = ok4 = False
    record(15, "live open/note/event/check", ok1 and ok2 and ok3 and ok4)

    # ── Flujo 16: Registrar cambios ──
    print("\n[16] Registrar cambios (historial)")
    r = _cli("history", "entity", frodo_id)
    ok1 = _ok("history entity", r)
    r = _cli("history", "recent")
    ok2 = _ok("history recent", r)
    record(16, "history entity + recent", ok1 and ok2, r.stdout.strip()[:100])

    # ── Flujo 17: Ejecutar post-sesión ──
    print("\n[17] Ejecutar post-sesión")
    if sess_id:
        r = _cli("session", "live", "done", sess_id)
        ok1 = _ok("live done", r)
        r = _cli("session", "close", sess_id)
        ok2 = _ok("session close", r)
        r = _cli("session", "post-summary", sess_id)
        ok3 = _ok("post-summary", r)
        r = _cli("session", "post-seeds", sess_id)
        ok4 = _ok("post-seeds", r)
    else:
        ok1 = ok2 = ok3 = ok4 = False
    record(17, "live done + close + post-summary + post-seeds", ok1 and ok2 and ok3 and ok4)

    # ── Flujo 18: Exportar resumen seguro para jugadores ──
    print("\n[18] Exportar resumen seguro para jugadores")
    r = _cli("export", "public-summary", "--audience", "player")
    record(18, "export public-summary player", _ok("export player", r), r.stdout.strip()[:100])

    # ── Flujo 19: Exportar documento completo para director ──
    print("\n[19] Exportar documento completo para director")
    r = _cli("export", "all", "--audience", "gm")
    record(19, "export all gm", _ok("export gm", r), r.stdout.strip()[:100])

    # ── Flujo 20: Revisar historial y fuentes ──
    print("\n[20] Revisar historial y fuentes")
    r = _cli("history", "recent")
    ok1 = _ok("history recent", r)
    r = _cli("source", "list")
    ok2 = _ok("source list", r)
    record(20, "history + source", ok1 and ok2, r.stdout.strip()[:100])

    # ── Save/Close/Open verification ──
    print("\n[VER] Verificar persistencia tras close/open")
    r = _cli("project", "close")
    ok_close = _ok("project close", r)
    r = _cli("project", "open", project_path)
    ok_open = _ok("project open", r)
    r = _cli("entity", "show", frodo_id)
    ok_verify = _ok("entity show Frodo after reload", r)
    record(0, "persistence save/close/open", ok_close and ok_open and ok_verify)

    return {"all_pass": all_pass, "flows": results}


def main():
    parser = argparse.ArgumentParser(description="B30-T02: Smoke 20 flujos obligatorios")
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="smoke_b30_") as td:
        proj_path = str(Path(td) / "smoke_test.json")
        print("=" * 60)
        print("  B30-T02: Smoke 20 flujos obligatorios")
        print(f"  Project: {proj_path}")
        print("=" * 60)

        result = run_all(proj_path, verbose=args.verbose)

    print("\n" + "=" * 60)
    passed = sum(1 for f in result["flows"].values() if f["status"] == "PASS")
    total = len(result["flows"])
    print(f"  RESULTADO: {passed}/{total} flujos PASS")
    print("=" * 60)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    sys.exit(0 if result["all_pass"] else 1)


if __name__ == "__main__":
    main()
