#!/usr/bin/env bash
# Source this before running any LeRobot command from a shell:
#   source scripts/env.sh
# Every wrapper in scripts/ sources it too. It does three things:
#   1. loads .env (ports, ids, HF user) if present
#   2. puts the venv on PATH
#   3. points dyld at Homebrew ffmpeg@8, which torchcodec needs to decode videos
#      (ffmpeg 9 is not supported by torchcodec 0.11, and /opt/homebrew/lib holds a stale ffmpeg-full 8.1.1)

# works when sourced from bash or zsh
if [ -n "${BASH_SOURCE:-}" ]; then
  _arm_env_file="${BASH_SOURCE[0]}"
elif [ -n "${ZSH_VERSION:-}" ]; then
  _arm_env_file="${(%):-%x}"
else
  _arm_env_file="$0"
fi
ARM_DIR="$(cd "$(dirname "$_arm_env_file")/.." && pwd)"
export ARM_DIR
unset _arm_env_file

if [ -f "$ARM_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ARM_DIR/.env"
  set +a
fi

export PATH="$ARM_DIR/.venv/bin:$PATH"
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/ffmpeg@8/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
