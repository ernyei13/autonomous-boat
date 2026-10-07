#!/usr/bin/env bash

if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  ENV_SCRIPT_PATH="${BASH_SOURCE[0]}"
elif [[ -n "${(%):-%x}" ]]; then
  ENV_SCRIPT_PATH="${(%):-%x}"
else
  ENV_SCRIPT_PATH="$0"
fi

SCRIPT_DIR="$(cd "$(dirname "$ENV_SCRIPT_PATH")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

export WORKSPACE_ROOT
export LAB04_ROOT="$WORKSPACE_ROOT/work/lab04-companion"
export LAB04_CODE="$LAB04_ROOT/code"
export LAB04_VENV="$LAB04_CODE/ss_venv"
export MARITIME_ROOT="$WORKSPACE_ROOT/work/maritime26"
export ARDUPILOT_ROOT="$WORKSPACE_ROOT/work/ardupilot"

export DYLD_LIBRARY_PATH="/opt/homebrew/opt/expat/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
export PATH="$LAB04_VENV/bin:/opt/homebrew/bin:/opt/homebrew/sbin:$PATH"
