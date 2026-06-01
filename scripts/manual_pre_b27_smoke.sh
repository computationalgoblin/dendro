#!/usr/bin/env bash
# Manual smoke test B01→B26 — pre-B27 audit
set -euo pipefail

WORKDIR="/workspace/manual_pre_b27"
PROJECT="$WORKDIR/demo_pre_b27.json"
LOGFILE="/workspace/ai_outputs/pre_b27_visual_smoke.log"
PY="python3 -m narrative_architect"

rm -rf "$WORKDIR"; mkdir -p "$WORKDIR"
export NARRATIVE_AI_PROVIDER="simulated"
> "$LOGFILE"

log() { echo "[$(date +%T)] $*" | tee -a "$LOGFILE"; }
run() { log "CMD: $*"; $* >> "$LOGFILE" 2>&1 || log "FAILED: $*"; }
json_ok() { run "$*" && python3 -m json.tool "$LOGFILE" >/dev/null 2>&1 && log "JSON OK: $*" || log "JSON FAIL: $*"; }

log "=== PRE-B27 SMOKE TEST ==="

# A. Project
log "--- A. Project ---"
run rm -f .narrative-session.json
run $PY project create "PreB27Demo" --path "$PROJECT"
run $PY project info
run $PY project save
run $PY project close
run $PY project open "$PROJECT"

# B. Entities
log "--- B. Entities ---"
run $PY entity create "Gandalf" --type personaje
run $PY entity create "Rivendel" --type localizacion
run $PY entity create "La Sombra" --type faccion
run $PY entity create "Anillo Unico" --type objeto
GANDALF=$(python3 -c "import json;d=json.load(open('$PROJECT'));print([e['id'] for e in d['entities'] if e['name']=='Gandalf'][0])" 2>/dev/null || echo "")
RIVENDEL=$(python3 -c "import json;d=json.load(open('$PROJECT'));print([e['id'] for e in d['entities'] if e['name']=='Rivendel'][0])" 2>/dev/null || echo "")
log "Gandalf=$GANDALF Rivendel=$RIVENDEL"
run $PY entity list --json
run $PY relation create "$GANDALF" "$RIVENDEL" --type ubicado_en

# C. Candidates
log "--- C. Candidates ---"
run $PY candidate list --json 2>/dev/null || log "MISSING: candidate list"

# D. Campaign
log "--- D. Campaign ---"
run $PY campaign create "La Guerra del Anillo" --system "D&D 5e" --tone "epico"
CAMPAIGN=$(python3 -c "import json;d=json.load(open('$PROJECT'));print(d.get('campaigns',[{}])[0].get('id',''))" 2>/dev/null || echo "")
log "Campaign=$CAMPAIGN"
run $PY campaign player-add "$CAMPAIGN" "Frodo" 2>/dev/null || log "MISSING: campaign player-add"
run $PY campaign clock-create "$CAMPAIGN" "Reloj de Sauron" --max 6 2>/dev/null || log "MISSING: campaign clock-create"

# E. Secrets/Clues
log "--- E. Secrets/Clues ---"
run $PY secret create "El Anillo corrompe" --entity "$GANDALF" 2>/dev/null || log "MISSING: secret create"
run $PY clue create "Mapa de la Comarca" --secret "$GANDALF" 2>/dev/null || log "MISSING: clue create"

# F. Session prep
log "--- F. Session ---"
run $PY session create "Sesion 1" --campaign "$CAMPAIGN" 2>/dev/null || log "MISSING: session create"
SESSION=$(python3 -c "import json;d=json.load(open('$PROJECT'));print(d.get('sessions',[{}])[0].get('id',''))" 2>/dev/null || echo "")
log "Session=$SESSION"
run $PY session show "$SESSION" --json 2>/dev/null || log "MISSING: session show"

# G. Live mode
log "--- G. Live ---"
run $PY session live-open "$SESSION" 2>/dev/null || log "MISSING: session live-open"
run $PY session live-note "$SESSION" "Quick test note" 2>/dev/null || log "MISSING: session live-note"
run $PY session live-done "$SESSION" --json 2>/dev/null || log "MISSING: session live-done"

# H. Post-session
log "--- H. Post-session ---"
run $PY session close "$SESSION" 2>/dev/null || log "MISSING: session close"
run $PY session post-summary "$SESSION" --json 2>/dev/null || log "MISSING: session post-summary"

# I. Export
log "--- I. Export ---"
run $PY export public-summary --audience public --json 2>/dev/null || log "MISSING: export"
run $PY export all --audience gm --json 2>/dev/null || log "MISSING: export all"

# J. Final persist
log "--- J. Persistence ---"
run $PY project save
run $PY project close
run $PY project open "$PROJECT"
run $PY entity list --json
run $PY campaign list --json
run $PY session list --json

# K. AI test
log "--- K. AI ---"
run $PY ai generate-entity --prompt "test" 2>/dev/null || log "MISSING: ai generate-entity"

log "=== SMOKE COMPLETE ==="
log "Log: $LOGFILE"
