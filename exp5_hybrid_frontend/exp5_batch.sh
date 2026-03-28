#!/bin/bash
# exp5_batch.sh -- Run one batch of experiment 5
# Scheduled via launchd every 5 hours. Session budget with 80% soft cap.
# Resume support means each batch picks up where the last left off.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXP_DIR="${SCRIPT_DIR}"
RUN_NAME="full_n5"
SESSION_BUDGET=200
SOFT_CAP=$(( SESSION_BUDGET * 80 / 100 ))  # 160 calls
LOG_DIR="${EXP_DIR}/runs/${RUN_NAME}"

mkdir -p "${LOG_DIR}"

echo "=== Batch started at $(date -u '+%Y-%m-%dT%H:%M:%SZ') ===" >> "${LOG_DIR}/batch.log"
echo "  Session budget: ${SESSION_BUDGET}, soft cap (80%): ${SOFT_CAP}" >> "${LOG_DIR}/batch.log"

cd "${EXP_DIR}"

# Progress tracking
RAW_DIR="${LOG_DIR}/results/raw"
EXTRACTED_DIR="${LOG_DIR}/results/extracted"
JUDGE_DIR="${LOG_DIR}/results/judge"

if [ -d "${RAW_DIR}" ]; then
    RAW_COUNT=$(find "${RAW_DIR}" -name '*.json' | wc -l | tr -d ' ')
    echo "  Raw completions so far: ${RAW_COUNT}/250" >> "${LOG_DIR}/batch.log"
else
    RAW_COUNT=0
fi

if [ -d "${EXTRACTED_DIR}" ]; then
    EXT_COUNT=$(find "${EXTRACTED_DIR}" -name '*_extracted.json' | wc -l | tr -d ' ')
    echo "  Extracted so far: ${EXT_COUNT}" >> "${LOG_DIR}/batch.log"
fi

if [ -d "${JUDGE_DIR}" ]; then
    JUDGE_COUNT=$(find "${JUDGE_DIR}" -name '*_judge.json' | wc -l | tr -d ' ')
    echo "  Judge scores so far: ${JUDGE_COUNT}/250" >> "${LOG_DIR}/batch.log"
else
    JUDGE_COUNT=0
fi

# Run the pipeline batch with 80% soft cap
python3 -m src.pipeline_v5 \
    --base-dir . \
    --run-name "${RUN_NAME}" \
    --n-runs 5 \
    --judge-model haiku \
    --max-calls "${SOFT_CAP}" \
    2>&1 | tee -a "${LOG_DIR}/batch.log"

# Post-batch progress check
if [ -d "${RAW_DIR}" ] && [ -d "${JUDGE_DIR}" ]; then
    RAW_FINAL=$(find "${RAW_DIR}" -name '*.json' | wc -l | tr -d ' ')
    JUDGE_FINAL=$(find "${JUDGE_DIR}" -name '*_judge.json' | wc -l | tr -d ' ')
    echo "  Post-batch: ${RAW_FINAL}/250 raw, ${JUDGE_FINAL}/250 judged" >> "${LOG_DIR}/batch.log"

    if [ "${RAW_FINAL}" -ge 250 ] && [ "${JUDGE_FINAL}" -ge 250 ]; then
        echo "  EXPERIMENT COMPLETE -- unloading scheduler" >> "${LOG_DIR}/batch.log"
        launchctl unload ~/Library/LaunchAgents/com.experiments.exp5-batch.plist 2>/dev/null || true
    fi
fi

echo "=== Batch finished at $(date -u '+%Y-%m-%dT%H:%M:%SZ') ===" >> "${LOG_DIR}/batch.log"
echo "" >> "${LOG_DIR}/batch.log"
