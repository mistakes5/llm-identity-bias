#!/bin/bash
# exp4_batch.sh — Run one batch of experiment 4 (50 calls per invocation)
# Scheduled via launchd every 5 hours. Resume support means each batch
# picks up where the last one left off.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXP_DIR="${SCRIPT_DIR}"
RUN_NAME="full_n5"
MAX_CALLS=50
LOG_DIR="${EXP_DIR}/runs/${RUN_NAME}"

mkdir -p "${LOG_DIR}"

echo "=== Batch started at $(date -u '+%Y-%m-%dT%H:%M:%SZ') ===" >> "${LOG_DIR}/batch.log"

cd "${EXP_DIR}"

# Check how many raw files exist (progress tracking)
RAW_DIR="${LOG_DIR}/results/raw"
if [ -d "${RAW_DIR}" ]; then
    RAW_COUNT=$(find "${RAW_DIR}" -name '*.json' | wc -l | tr -d ' ')
    echo "  Raw completions so far: ${RAW_COUNT}/250" >> "${LOG_DIR}/batch.log"
fi

JUDGE_DIR="${LOG_DIR}/results/judge"
if [ -d "${JUDGE_DIR}" ]; then
    JUDGE_COUNT=$(find "${JUDGE_DIR}" -name '*_judge.json' | wc -l | tr -d ' ')
    echo "  Judge scores so far: ${JUDGE_COUNT}/250" >> "${LOG_DIR}/batch.log"
fi

# Run the pipeline batch
python3 -m src.pipeline_v4 \
    --base-dir . \
    --run-name "${RUN_NAME}" \
    --n-runs 5 \
    --judge-model haiku \
    --max-calls "${MAX_CALLS}" \
    2>&1 | tee -a "${LOG_DIR}/batch.log"

# Check if experiment is fully complete (all raw + all judged)
if [ -d "${RAW_DIR}" ] && [ -d "${JUDGE_DIR}" ]; then
    RAW_FINAL=$(find "${RAW_DIR}" -name '*.json' | wc -l | tr -d ' ')
    JUDGE_FINAL=$(find "${JUDGE_DIR}" -name '*_judge.json' | wc -l | tr -d ' ')
    echo "  Post-batch: ${RAW_FINAL}/250 raw, ${JUDGE_FINAL}/250 judged" >> "${LOG_DIR}/batch.log"

    if [ "${RAW_FINAL}" -ge 250 ] && [ "${JUDGE_FINAL}" -ge 250 ]; then
        echo "  EXPERIMENT COMPLETE — unloading scheduler" >> "${LOG_DIR}/batch.log"
        launchctl unload ~/Library/LaunchAgents/com.experiments.exp4-batch.plist 2>/dev/null || true
    fi
fi

echo "=== Batch finished at $(date -u '+%Y-%m-%dT%H:%M:%SZ') ===" >> "${LOG_DIR}/batch.log"
echo "" >> "${LOG_DIR}/batch.log"
