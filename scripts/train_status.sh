#!/usr/bin/env bash
# Show the state of a Hugging Face training job and the policy repo link.
#
# Usage:
#   scripts/train_status.sh <job_id>        # one job
#   scripts/train_status.sh                 # the last job submitted by train_cloud.sh
#   scripts/train_status.sh <job_id> --logs # also print the last 40 log lines
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/env.sh"

JOB_ID="${1:-}"
if [ -z "$JOB_ID" ] || [ "$JOB_ID" = "--logs" ]; then
  JOB_ID=$(tail -1 "$ARM_DIR/.state/jobs.log" 2>/dev/null | awk '{print $2}') || true
  [ -z "$JOB_ID" ] && { echo "usage: $0 <job_id> [--logs]  (no jobs submitted yet)" >&2; exit 2; }
fi

INFO=$(hf jobs inspect "$JOB_ID" 2>&1) || { echo "FAIL: cannot inspect $JOB_ID: $INFO" >&2; exit 1; }

# hf jobs inspect prints JSON. Pull the fields we care about with python.
python3 - "$JOB_ID" "$ARM_DIR/.state/jobs.log" <<'EOF' <<<"$INFO"
import json, sys
job_id, log_path = sys.argv[1], sys.argv[2]
raw = sys.stdin.read()
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print(raw); sys.exit(0)
job = data[0] if isinstance(data, list) else data
status = job.get("status", {}) or {}
stage = status.get("stage", "?")
msg = status.get("message") or ""
words = {"RUNNING": "running", "COMPLETED": "done", "ERROR": "failed", "CANCELED": "cancelled"}
print(f"Job:     {job_id}")
print(f"State:   {words.get(stage, stage.lower())}" + (f"  ({msg})" if msg else ""))
for k in ("created_at", "started_at", "ended_at"):
    if job.get(k):
        print(f"{k:9}{job[k]}")
policy = ""
try:
    for line in open(log_path):
        parts = line.split()
        if len(parts) > 3 and parts[1] == job_id:
            policy = parts[3]
except FileNotFoundError:
    pass
if policy:
    print(f"Policy:  https://huggingface.co/{policy}" + ("  (ready)" if stage == "COMPLETED" else "  (not ready yet)"))
EOF

if [ "${2:-}" = "--logs" ] || [ "${1:-}" = "--logs" ]; then
  echo; echo "--- last 40 log lines:"
  hf jobs logs --tail 40 "$JOB_ID" 2>&1 || true
fi
