#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FAST=0
SUITES="arch sanity b39"

usage() {
  cat <<'USAGE'
Usage: scripts/verify_all.sh [--fast] [--suites "arch sanity b39"]

Runs the project health checks through existing runners.

Options:
  --fast              Run the default lightweight verification set.
  --suites "..."      Override run_all_tests suites.
  -h, --help          Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fast)
      FAST=1
      SUITES="arch sanity b39"
      shift
      ;;
    --suites)
      SUITES="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$SUITES" ]]; then
  echo "--suites cannot be empty" >&2
  exit 2
fi

echo "[verify_all] root: $ROOT"
echo "[verify_all] compileall"
python -m compileall hosts/DesktopHostPySide packages tests -q

echo "[verify_all] architecture"
python -m pytest tests/architecture/ -q

echo "[verify_all] suites: $SUITES"
python scripts/run_all_tests.py --suites $SUITES

echo "[verify_all] PASS"
