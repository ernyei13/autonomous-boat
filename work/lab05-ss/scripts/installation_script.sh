#!/bin/bash
apt-get update && apt-get install -y python3-venv && python3 -m venv .denv && .denv/bin/pip install --upgrade pip && .denv/bin/pip install  -r requirements.txt && echo 'source /opt/ros/jazzy/setup.bash' >> ~/.bashrc
sudo apt install ros-jazzy-mavros ros-jazzy-mavros-msgs ros-jazzy-mavros-extras screen -y
sudo /opt/ros/jazzy/lib/mavros/install_geographiclib_datasets.sh
sed -i 's/\bcollections.MutableMapping\b/collections.abc.MutableMapping/g' .venv/lib/python3.12/site-packages/dronekit/__init__.py



