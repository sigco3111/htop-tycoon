#!/usr/bin/env bash
# htop-tycoon v3.0 — 4-strategy × N-year comparison QA (spec §7.7 row 2)
# Runs all 4 default strategies for N in-game years (default 10 = 3650 ticks)
# and produces a comparison table at .omo/evidence/manual_qa_strategies.txt
# Usage: bash scripts/qa_strategy_compare.sh [seed] [years]
set -euo pipefail

SEED="${1:-42}"
YEARS="${2:-10}"
TICKS=$((365 * YEARS))
EVIDENCE_DIR=".omo/evidence"
STRATEGIES=(aggressive conservative balanced genre_focus)

mkdir -p "${EVIDENCE_DIR}"

echo "# htop-tycoon manual_qa_strategies: seed=${SEED} years=${YEARS} ticks=${TICKS}" > "${EVIDENCE_DIR}/manual_qa_strategies.txt"
echo "# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "${EVIDENCE_DIR}/manual_qa_strategies.txt"
echo "" >> "${EVIDENCE_DIR}/manual_qa_strategies.txt"

# Run each strategy; capture per-strategy log + final metrics
for s in "${STRATEGIES[@]}"; do
  LOG="${EVIDENCE_DIR}/strategy_${s}.log"
  echo "# Running strategy=${s} ticks=${TICKS}..."
  uv run python -m htop_tycoon \
    --seed="${SEED}" \
    --ticks="${TICKS}" \
    --headless \
    --strategy="${s}" \
    --no-autosave \
    --autosave-path="/tmp/qa_${s}_save.json" \
    2>&1 | tee "${LOG}" > /dev/null
done

# Build comparison table by extracting "final day=" lines
echo "# Comparison (final state per strategy):" >> "${EVIDENCE_DIR}/manual_qa_strategies.txt"
printf "%-15s | %-10s | %-12s | %-12s | %-15s\n" "strategy" "final_day" "cash" "fans" "ending" >> "${EVIDENCE_DIR}/manual_qa_strategies.txt"
echo "----------------+------------+--------------+--------------+-----------------" >> "${EVIDENCE_DIR}/manual_qa_strategies.txt"
for s in "${STRATEGIES[@]}"; do
  FINAL=$(grep -E "^# final day=" "${EVIDENCE_DIR}/strategy_${s}.log" | head -1 || echo "")
  if [ -n "${FINAL}" ]; then
    echo "${FINAL}" | awk -v s="${s}" '{
      # "# final day=NN cash=NN fans=NN ending=NAME autosave_writes=NN"
      day=""; cash=""; fans=""; ending=""
      for (i=1; i<=NF; i++) {
        if ($i ~ /day=/) day = substr($i, 5)
        else if ($i ~ /cash=/) cash = substr($i, 6)
        else if ($i ~ /fans=/) fans = substr($i, 6)
        else if ($i ~ /ending=/) ending = substr($i, 8)
      }
      printf "%-15s | %-10s | %-12s | %-12s | %-15s\n", s, day, cash, fans, ending
    }' >> "${EVIDENCE_DIR}/manual_qa_strategies.txt"
  else
    printf "%-15s | %-10s | %-12s | %-12s | %-15s\n" "${s}" "?" "?" "?" "?" >> "${EVIDENCE_DIR}/manual_qa_strategies.txt"
  fi
done

echo "" >> "${EVIDENCE_DIR}/manual_qa_strategies.txt"
echo "# Per-strategy full logs:" >> "${EVIDENCE_DIR}/manual_qa_strategies.txt"
for s in "${STRATEGIES[@]}"; do
  echo "  - ${EVIDENCE_DIR}/strategy_${s}.log" >> "${EVIDENCE_DIR}/manual_qa_strategies.txt"
done

echo "Wrote ${EVIDENCE_DIR}/manual_qa_strategies.txt + 4 strategy logs"