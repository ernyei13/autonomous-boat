# Maritime Lab 03 SITL Setup

This workspace follows the Maritime Lab 03 ArduPilot SITL exercise. The lab page is mostly written for Ubuntu/WSL, so this setup keeps the same ArduPilot release, locations, parameter files, mission, and `sim_vehicle.py` workflow, with macOS-specific dependency and launch wrapping.

## What is installed

- ArduPilot checkout: `work/ardupilot`
- Python environment: `work/venv-ardupilot`
- Lab files: `work/maritime26`
- Release tag: `Rover-4.6.3` / `APMrover2-stable`
- SITL binary: `work/ardupilot/build/sitl/bin/ardurover`

The Lab 03 locations have been added to `work/ardupilot/Tools/autotest/locations.txt`:

```text
Syros=37.439322,24.945616,0.1,180
Piraeus=37.9435,23.6472,0.1,90
Syros2=37.439142,24.945389,0.1,180
Syros3=37.438962,24.945162,0.1,180
Syros4=37.438782,24.944935,0.1,180
```

## Useful commands

From the workspace root:

```bash
source work/maritime26/scripts/env.sh
cd work/ardupilot
python ./waf configure --board sitl
python ./waf rover
```

Start the normal calm-water simulator, equivalent to the lab's Syros launch with `boat.parm`:

```bash
work/maritime26/scripts/launch-calm.sh
```

Start the Meltemi/current-and-waves simulator, equivalent to the lab's motorboat launch with `boat.parm` and `meltemi.parm`:

```bash
work/maritime26/scripts/launch-meltemi.sh
```

Reset the simulated boat memory on launch:

```bash
RESET=1 work/maritime26/scripts/launch-calm.sh
```

Load the sample mission inside the MAVProxy console:

```text
wp load ../missions/simple_nisaki.txt
wp list
mode AUTO
arm throttle
```

For multi-vehicle work, start these in two terminals:

```bash
work/maritime26/scripts/launch-boat1-headless.sh
work/maritime26/scripts/launch-boat2-headless.sh
```

## Direct Lab-Style Commands

If you want the commands expanded instead of using helpers:

```bash
source work/maritime26/scripts/env.sh
cd work/maritime26/sitl-test
python "$ARDUPILOT_ROOT/Tools/autotest/sim_vehicle.py" -N -v Rover -L Syros \
  --out=udp:127.0.0.1:14550 \
  --add-param-file="$MARITIME_ROOT/custom-parms/boat.parm" \
  --map --console
```

For Meltemi:

```bash
source work/maritime26/scripts/env.sh
cd work/maritime26/sitl-test
python "$ARDUPILOT_ROOT/Tools/autotest/sim_vehicle.py" -N -v Rover -f motorboat -L Syros \
  --out=udp:127.0.0.1:14550 \
  --add-param-file="$MARITIME_ROOT/custom-parms/boat.parm" \
  --add-param-file="$MARITIME_ROOT/custom-parms/meltemi.parm" \
  --map --console
```

## macOS note

This machine's Homebrew Python needs Homebrew's expat library at runtime. The helper scripts set:

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib
```

Keep using the helper scripts or source `work/maritime26/scripts/env.sh` before running `sim_vehicle.py` directly.

For direct ArduPilot commands on this Mac, prefer `python ./waf ...` and `python work/ardupilot/Tools/autotest/sim_vehicle.py ...` over relying on script shebangs.

The launch helpers pass `-N` because `build/sitl/bin/ardurover` is already compiled.

The local checkout also includes a small DroneCAN generator workaround so this macOS Python/toolchain can build Rover 4.6.3 reliably.

## Verification Performed

- `ardurover` compiled successfully for SITL.
- Python 3.12.13 venv loads `pyexpat`, MAVProxy console/map modules, and OpenCV.
- `sim_vehicle.py` starts Rover at the lab's `Syros` location with `boat.parm`.
- No simulator or MAVProxy process is left running after setup.
