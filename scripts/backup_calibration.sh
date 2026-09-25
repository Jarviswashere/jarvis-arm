#!/usr/bin/env bash
# Back up or restore LeRobot calibration files for the two arms.
#
# Usage:
#   scripts/backup_calibration.sh                    # backup both ids from .env
#   scripts/backup_calibration.sh --restore <folder> # copy a backup back into place
#
# LeRobot stores calibration on macOS at
#   ~/.cache/huggingface/lerobot/calibration/robots/so101_follower/<FOLLOWER_ID>.json
#   ~/.cache/huggingface/lerobot/calibration/teleoperators/so101_leader/<LEADER_ID>.json
# Backups go to calibration_backups/<date>_<id>/ and are never deleted.
set -euo pipefail
# shellcheck disable=SC1091
source "$(dirname "$0")/env.sh"

CAL_DIR="${HF_LEROBOT_CALIBRATION:-$HOME/.cache/huggingface/lerobot/calibration}"
BACKUP_ROOT="$ARM_DIR/calibration_backups"
: "${FOLLOWER_ID:?FOLLOWER_ID missing in .env}"
: "${LEADER_ID:?LEADER_ID missing in .env}"

if [ "${1:-}" = "--restore" ]; then
  SRC="${2:?usage: $0 --restore <backup_folder>}"
  [ -d "$SRC" ] || { echo "FAIL: $SRC is not a folder" >&2; exit 1; }
  n=0
  for f in "$SRC"/robots/*/*.json "$SRC"/teleoperators/*/*.json; do
    [ -f "$f" ] || continue
    rel="${f#"$SRC"/}"
    mkdir -p "$(dirname "$CAL_DIR/$rel")"
    cp "$f" "$CAL_DIR/$rel"
    echo "restored $rel"
    n=$((n+1))
  done
  [ "$n" -gt 0 ] || { echo "FAIL: no calibration json found under $SRC" >&2; exit 1; }
  echo "Done. Run a 5-trial smoke test (QUALITY.md section 8) before trusting it."
  exit 0
fi

STAMP="$(date +%Y-%m-%d_%H%M)"
n=0
for spec in "robots:$FOLLOWER_ID" "teleoperators:$LEADER_ID"; do
  kind="${spec%%:*}"; id="${spec##*:}"
  found=$(find "$CAL_DIR/$kind" -name "$id.json" 2>/dev/null | head -1 || true)
  if [ -z "$found" ]; then
    echo "WARN: no calibration file for $id under $CAL_DIR/$kind (not calibrated yet?)"
    continue
  fi
  rel="${found#"$CAL_DIR"/}"
  dest="$BACKUP_ROOT/${STAMP}_${id}/$rel"
  mkdir -p "$(dirname "$dest")"
  cp "$found" "$dest"
  echo "backed up $rel -> ${dest#"$ARM_DIR"/}"
  n=$((n+1))
done
[ "$n" -gt 0 ] || { echo "FAIL: nothing to back up" >&2; exit 1; }
echo "Backups in $BACKUP_ROOT:"
ls -1 "$BACKUP_ROOT" | grep -v '^\.gitkeep$'
