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

export ARDUPILOT_ROOT="$WORKSPACE_ROOT/work/ardupilot"
export MARITIME_ROOT="$WORKSPACE_ROOT/work/maritime26"
export ARDUPILOT_VENV="$WORKSPACE_ROOT/work/venv-ardupilot"

# Homebrew Python on this macOS build needs Homebrew's newer expat at runtime.
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/expat/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"

export PATH="$ARDUPILOT_VENV/bin:$ARDUPILOT_ROOT/Tools/autotest:/opt/homebrew/opt/ccache/libexec:/opt/homebrew/opt/coreutils/libexec/gnubin:/opt/homebrew/opt/gawk/libexec/gnubin:$PATH"
