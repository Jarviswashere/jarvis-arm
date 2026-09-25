#!/usr/bin/env bash
# Teleoperate the follower from the leader with both cameras shown.
#
# Usage:
#   scripts/teleop.sh                 # cameras + live plot
#   scripts/teleop.sh --no-cameras    # joints only (calibration check)
#   MAX_REL=10 scripts/teleop.sh      # lower step limit (safety gate SG8)
#
# Refuses to run if scripts/check_cameras.py did not pass in the last 30 minutes
# (unless --no-cameras). Prints the full command before running it.
# Tony is at the desk with the e-stop in reach before this runs.
set -euo pipefail
# shellcheck disable=SC1091
source "$(dirname "$0")/env.sh"

: "${FOLLOWER_PORT:?FOLLOWER_PORT missing in .env}"
: "${LEADER_PORT:?LEADER_PORT missing in .env}"
: "${FOLLOWER_ID:?FOLLOWER_ID missing in .env}"
: "${LEADER_ID:?LEADER_ID missing in .env}"

STAMP="$ARM_DIR/.state/cameras_ok"
MAX_AGE_S=1800
CAM_ARGS=()

if [ "${1:-}" != "--no-cameras" ]; then
  if [ ! -f "$STAMP" ]; then
    echo "REFUSED: no camera check on record. Run: scripts/check_cameras.py" >&2
    exit 1
  fi
  age=$(( $(date +%s) - $(cat "$STAMP") ))
  if [ "$age" -gt "$MAX_AGE_S" ]; then
    echo "REFUSED: camera check is $((age/60)) min old (limit 30). Run: scripts/check_cameras.py" >&2
    exit 1
  fi
  CAMERAS=$(python "$ARM_DIR/scripts/cameras_arg.py")
  CAM_ARGS=(--robot.cameras="$CAMERAS" --display_data=true)
fi

CMD=(lerobot-teleoperate
  --robot.type=so101_follower --robot.port="$FOLLOWER_PORT" --robot.id="$FOLLOWER_ID"
  --teleop.type=so101_leader --teleop.port="$LEADER_PORT" --teleop.id="$LEADER_ID"
  --fps=30
)
[ -n "${MAX_REL:-}" ] && CMD+=(--robot.max_relative_target="$MAX_REL")
CMD+=(${CAM_ARGS[@]+"${CAM_ARGS[@]}"})

echo "Command:"; printf '  %q' "${CMD[@]}"; echo; echo
echo "Ctrl-C stops teleop. The follower holds its last position. Use scripts/safe_rest.py after."
exec "${CMD[@]}"
