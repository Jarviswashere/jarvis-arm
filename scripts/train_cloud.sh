#!/usr/bin/env bash
# Submit an ACT training job to Hugging Face Jobs and return the policy repo.
#
# Usage:
#   scripts/train_cloud.sh <dataset> <policy_name> [steps] [flavor]
#
#   dataset      short name (so101_block_to_cup_v1, prefixed with $HF_USER) or a full repo id
#   policy_name  short name (act_block_to_cup_v1, pushed as $HF_USER/<policy_name>)
#   steps        training steps, default 20000
#   flavor       HF Jobs hardware, default l4x1 (see: hf jobs hardware)
#
# Example:
#   scripts/train_cloud.sh so101_block_to_cup_v1 act_block_to_cup_v1
#   scripts/train_cloud.sh lerobot/svla_so101_pickplace act_smoke_test 200
#
# The job runs detached. Check it with scripts/train_status.sh <job_id>.
# Cost: flavor price per minute times wall time. See docs/training.md.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/env.sh"

if [ $# -lt 2 ]; then
  sed -n '2,17p' "$0"
  exit 2
fi

DATASET="$1"
POLICY="$2"
STEPS="${3:-20000}"
FLAVOR="${4:-l4x1}"
TIMEOUT="${TRAIN_TIMEOUT:-4h}"

: "${HF_USER:?HF_USER missing. Put it in .env (copy .env.example)}"
case "$DATASET" in */*) ;; *) DATASET="$HF_USER/$DATASET" ;; esac
case "$POLICY" in */*) ;; *) POLICY="$HF_USER/$POLICY" ;; esac
JOB_NAME="${POLICY##*/}"

if ! hf auth whoami >/dev/null 2>&1; then
  echo "FAIL: not logged in to Hugging Face. Run: hf auth login  (write token)" >&2
  exit 1
fi
if ! curl -sf -o /dev/null "https://huggingface.co/api/datasets/$DATASET"; then
  echo "FAIL: dataset $DATASET not found on the Hub (private datasets need the token, public ones must exist)" >&2
  exit 1
fi

CMD=(lerobot-train
  --dataset.repo_id="$DATASET"
  --policy.type=act
  --policy.repo_id="$POLICY"
  --policy.push_to_hub=true
  --policy.device=cuda
  --output_dir="outputs/train/$JOB_NAME"
  --job_name="$JOB_NAME"
  --steps="$STEPS"
  --wandb.enable=false
  --job.target="$FLAVOR"
  --job.timeout="$TIMEOUT"
  --job.detach=true
)

echo "Dataset: $DATASET"
echo "Policy:  $POLICY"
echo "Steps:   $STEPS   Flavor: $FLAVOR   Timeout: $TIMEOUT"
echo "Command:"
printf '  %q' "${CMD[@]}"; echo
echo

START=$(date +%s)
OUT=$("${CMD[@]}" 2>&1 | tee /dev/stderr) || true
JOB_ID=$(echo "$OUT" | sed -n 's/^Job submitted: *//p' | head -1)
if [ -z "$JOB_ID" ]; then
  echo "FAIL: no job id in the output above. Common causes: billing not set on the HF account, or the flavor name is wrong (hf jobs hardware)." >&2
  exit 1
fi

mkdir -p "$ARM_DIR/.state"
echo "$(date -u +%FT%TZ) $JOB_ID $DATASET $POLICY steps=$STEPS flavor=$FLAVOR submitted_at=$START" >> "$ARM_DIR/.state/jobs.log"
echo
echo "Job id:   $JOB_ID"
echo "Status:   scripts/train_status.sh $JOB_ID"
echo "Policy:   https://huggingface.co/$POLICY"
