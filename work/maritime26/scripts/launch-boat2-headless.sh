#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh"

reset_flag=""
if [[ "${RESET:-0}" == "1" ]]; then
  reset_flag="-w"
fi

mkdir -p "$MARITIME_ROOT/sitl-test2"
cd "$MARITIME_ROOT/sitl-test2"

exec python "$ARDUPILOT_ROOT/Tools/autotest/sim_vehicle.py" -N ${reset_flag:+$reset_flag} -v Rover --instance 1 --sysid 2 -L Syros2 \
  --add-param-file="$MARITIME_ROOT/custom-parms/boat.parm" \
  --out=udp:127.0.0.1:14560 \
  --out=udp:127.0.0.1:14550
