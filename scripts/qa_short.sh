#!/usr/bin/env bash
# htop-tycoon v3.0 — short QA playthrough (spec §7.7 row 1)
# Runs 1800 ticks at 4x speed with --headless, captures log to .omo/evidence/manual_qa_short.txt
# Usage: bash scripts/qa_short.sh [seed]
set -euo pipefail

SEED="${1:-42}"
TICKS=1800
EVIDENCE_DIR=".omo/evidence"
LOG="${EVIDENCE_DIR}/manual_qa_short.txt"

mkdir -p "${EVIDENCE_DIR}"

echo "# htop-tycoon manual_qa_short: seed=${SEED} ticks=${TICKS} speed=4x" > "${LOG}"
echo "# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "${LOG}"
echo "" >> "${LOG}"

uv run python -m htop_tycoon \
  --seed="${SEED}" \
  --ticks="${TICKS}" \
  --headless \
  --no-autosave \
  --autosave-path="/tmp/qa_short_save.json" \
  2>&1 | tee -a "${LOG}"

echo "" >> "${LOG}"
echo "# End of log. Total lines: $(wc -l < "${LOG}")" >> "${LOG}"

echo "Wrote ${LOG}"