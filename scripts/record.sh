#!/usr/bin/env bash
# Record a dataset with the leader arm and both cameras, and push it to the Hub.
#
# Usage:
#   scripts/record.sh <skill> <num_episodes> "<task string>" [version]
#   scripts/record.sh block_to_cup 50 "Put the red block in the white cup"      # -> $HF_USER/so101_block_to_cup_v1
#   scripts/record.sh block_to_cup 5  "Put the red block in the white cup" test # -> ..._vtest
#   RESUME=1 scripts/record.sh block_to_cup 10 "..."   # add 10 more episodes to the same dataset
#
# Naming rule: <robot>_<skill>_v<N>. Episode 20 s, reset 10 s, streaming encode, 2 encoder threads.
# Keys while recording: right arrow or n = next episode, left arrow or r = redo, Esc or q = stop and upload.
# Demo rules: start at rest, steady speed, half-second pause before grasp and before release, end at rest,
# watch the camera windows not the arm, redo a failed demo.
set -euo pipefail
# shellcheck disable=SC1091
source "$(dirname "$0")/env.sh"

if [ $# -lt 3 ]; then sed -n '2,13p' "$0"; exit 2; fi
SKILL="$1"; N="$2"; TASK="$3"; VER="${4:-1}"
: "${HF_USER:?HF_USER missing in .env}"
: "${FOLLOWER_PORT:?FOLLOWER_PORT missing in .env}"
: "${LEADER_PORT:?LEADER_PORT missing in .env}"
: "${FOLLOWER_ID:?FOLLOWER_ID missing in .env}"
: "${LEADER_ID:?LEADER_ID missing in .env}"
REPO="$HF_USER/so101_${SKILL}_v${VER}"

STAMP="$ARM_DIR/.state/cameras_ok"
if [ ! -f "$STAMP" ] || [ $(( $(date +%s) - $(cat "$STAMP") )) -gt 1800 ]; then
  echo "REFUSED: camera check missing or older than 30 min. Run: scripts/check_cameras.py" >&2; exit 1
fi
CAMERAS=$(python "$ARM_DIR/scripts/cameras_arg.py")
hf auth whoami >/dev/null 2>&1 || { echo "FAIL: not logged in. Run: hf auth login" >&2; exit 1; }

CMD=(python -m lerobot.scripts.lerobot_record
  --robot.type=so101_follower --robot.port="$FOLLOWER_PORT" --robot.id="$FOLLOWER_ID"
  --teleop.type=so101_leader --teleop.port="$LEADER_PORT" --teleop.id="$LEADER_ID"
  --robot.cameras="$CAMERAS" --display_data=true
  --dataset.repo_id="$REPO" --dataset.single_task="$TASK"
  --dataset.num_episodes="$N" --dataset.episode_time_s=20 --dataset.reset_time_s=10 --dataset.fps=30
  --dataset.push_to_hub=true --dataset.streaming_encoding=true --dataset.encoder_threads=2
)
[ "${RESUME:-0}" = "1" ] && CMD+=(--resume=true)

echo "Dataset: https://huggingface.co/datasets/$REPO"
echo "Command:"; printf '  %q' "${CMD[@]}"; echo; echo
echo "After it finishes: scripts/dataset_report.py $REPO"
exec "${CMD[@]}"
