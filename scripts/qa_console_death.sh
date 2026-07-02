#!/usr/bin/env bash
# htop-tycoon v3.0 — console discontinuation QA (spec §7.7 row 4)
# Forces licensed consoles to discontinue at year 8, runs to year ~8+ (3000+ ticks),
# captures log + final state.json.
set -euo pipefail

SEED="${1:-42}"
TICKS=3000
FORCE_YEAR=8
EVIDENCE_DIR=".omo/evidence"
LOG="${EVIDENCE_DIR}/manual_qa_console_death.txt"
STATE="${EVIDENCE_DIR}/console_death_final_state.json"

mkdir -p "${EVIDENCE_DIR}"

echo "# htop-tycoon manual_qa_console_death: seed=${SEED} ticks=${TICKS} force_year=${FORCE_YEAR}" > "${LOG}"
echo "# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "${LOG}"
echo "" >> "${LOG}"

uv run python -m htop_tycoon \
  --seed="${SEED}" \
  --ticks="${TICKS}" \
  --headless \
  --force-console-discontinue="${FORCE_YEAR}" \
  --no-autosave \
  --autosave-path="/tmp/qa_console_death_save.json" \
  2>&1 | tee -a "${LOG}"

# Save a final state.json for inspection
uv run python - <<'PYEOF' >> "${LOG}" 2>&1
import json
from pathlib import Path
from htop_tycoon.domain import GameState
from htop_tycoon.engine.rng import GameRNG
from htop_tycoon.engine.tick import run_day

state = GameState(rng_seed=42)
for _ in range(3000):
    rng = GameRNG(state.rng_seed + state.day)
    state, _ = run_day(state, rng)

# Patch consoles same as --force-console-discontinue
import dataclasses
new_consoles = []
for cm in state.market.consoles:
    if cm.requires_license and cm.discontinue_year is None:
        new_consoles.append(dataclasses.replace(cm, discontinue_year=8))
    else:
        new_consoles.append(cm)
state = state.replace(market=dataclasses.replace(state.market, consoles=tuple(new_consoles)))

# Now run remaining ticks so decline curve plays out
for _ in range(3000):
    rng = GameRNG(state.rng_seed + state.day)
    state, _ = run_day(state, rng)

target = Path(".omo/evidence/console_death_final_state.json")
target.parent.mkdir(parents=True, exist_ok=True)
from htop_tycoon.persistence import serialize_state
target.write_text(serialize_state(state))
print(f"# Saved final state to {target}")
PYEOF

echo "" >> "${LOG}"
echo "# Console discontinuation events:" >> "${LOG}"
grep "console_discontinue\|game ended" "${LOG}" >> "${LOG}" || echo "# (no console discontinue events in this run)" >> "${LOG}"
echo "" >> "${LOG}"
echo "# Wrote ${LOG} and ${STATE}" >> "${LOG}"

echo "Wrote ${LOG} and final state to ${STATE}"