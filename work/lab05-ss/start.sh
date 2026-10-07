#!/bin/bash

# Read the arguments passed by systemd
VEHICLE_ROLE=$1
FCU_PORT=$2

# Safety check
if [ -z "$VEHICLE_ROLE" ] || [ -z "$FCU_PORT" ]; then
    echo "Error: Missing arguments."
    exit 1
fi

WORKSPACE_DIR="."

# Start MAVROS
/usr/bin/screen -dmS ros2 bash -c "source /opt/ros/jazzy/setup.bash && ros2 run mavros mavros_node --ros-args -r __ns:=/${VEHICLE_ROLE,,}/mavros -p fcu_url:=${FCU_PORT}"

# Start Python Node
/usr/bin/screen -dmS python bash -c "source .denv/bin/activate && source /opt/ros/jazzy/setup.bash && python3 src/main_ros2.py ${VEHICLE_ROLE} ${FCU_PORT}"