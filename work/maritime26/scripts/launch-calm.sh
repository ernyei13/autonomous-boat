#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh"

reset_flag=""
if [[ "${RESET:-0}" == "1" ]]; then
  reset_flag="-w"
fi

mkdir -p "$MARITIME_ROOT/sitl-test"
cd "$MARITIME_ROOT/sitl-test"

exec python "$ARDUPILOT_ROOT/Tools/autotest/sim_vehicle.py" -N ${reset_flag:+$reset_flag} -v Rover -L Syros \
  --out=udp:127.0.0.1:14550 \
  --add-param-file="$MARITIME_ROOT/custom-parms/boat.parm" \
  --map --console
