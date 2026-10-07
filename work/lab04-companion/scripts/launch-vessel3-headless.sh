#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../maritime26/scripts/env.sh"

LAB04_ROOT="$(cd "$MARITIME_ROOT/../lab04-companion" && pwd)"
reset_flag=""
if [[ "${RESET:-0}" == "1" ]]; then
  reset_flag="-w"
fi

mkdir -p "$LAB04_ROOT/run/vessel3"
cd "$LAB04_ROOT/run/vessel3"

exec python "$ARDUPILOT_ROOT/Tools/autotest/sim_vehicle.py" -N ${reset_flag:+$reset_flag} -v Rover --instance 3 --sysid 4 -L Syros4 \
  --add-param-file="$MARITIME_ROOT/custom-parms/boat.parm" \
  --out=udp:127.0.0.1:14550 \
  --out=udp:127.0.0.1:14581
