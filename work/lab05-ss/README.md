# lab05-ss06
Lab_05 summer school 2026



# Preparation
Initialize environmnent and install requirements.
```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip3 install -r requirements.txt
    
```

Fix for Dronekit :

Replace `
class Parameters(collections.MutableMapping, HasObservers):` with `
class Parameters(collections.abc.MutableMapping, HasObservers):`

Linux:
```
sed -i 's/\bcollections.MutableMapping\b/collections.abc.MutableMapping/g' .venv/lib/python3.12/site-packages/dronekit/__init__.py
```
MacOS specific:
```
sed -i '' 's/[[:<:]]collections.MutableMapping[[:>:]]/collections.abc.MutableMapping/g' .venv/lib/python3.12/site-packages/dronekit/__init__.py
```



create in your root level a `.env` file that contains the following environment variables.

```bash
    PYTHONPATH=src
    USE_MAVROS=true
    MQTT_USERNAME=mqtt-username
    MQTT_PASSWORD=mqtt-username
    MQTT_BROKER=mqtt_server
    MQTT_PORT=1883
    SAFE_FOLLOW_DISTANCE=10
    TELEMETRY_INTERVAL=2
    MAVLINK_DIALECT='ardupilotmega'
```


## Lab05 v0 Main loop + IMU additional info
Initial project setup, some small changes to support dockerised execution. Stripped repo from custom build behaviors
```bash
    git checkout lab05_v0
```

you may run the main as follows:

```bash
    python3 src/main.py ASV0 tcp:127.0.0.1:16010
    python3 src/main.py ASV1 tcp:127.0.0.1:16011
```



## Lab05 v1 Camera Controller 
Retrieve additional data from IMU unit. Accelerometer etc. Create a Camera Controller to handle default system camera and on-board pi-camera.

```bash
git checkout lab05_v2
```
**List of files changing**
```
    - src/main_camera.py # 
    - src/interfaces
        - sensor_interface
    - src/controllers
        - camera_controller
        - vessel_controller
        - mqtt_controller
```  

```bash
    python3 src/main_camera.py ASV0 tcp:127.0.0.1:16010
```

 **NOTE**: if you face segmentation faults with camera downgrade PNNX `pip install pnnx==20260526`


## Lab05 v2  Dummy sensors
Define  some dummy sensors. Demonstrate that sequential execution of sensor data acquisitions leads to longer data acquisition cycles

```bash
    git checkout lab05_v2
```

you may run the main as follows (Note that it can not be executed inside a docker):

```bash
    python3 src/main_dummy.py ASV0 tcp:127.0.0.1:16010
```

**List of files changing**
```
- src/main_dummy.py 
- src/controllersr
    - dummy_sensor_controller
```



## Lab05 v3 ZMQ - Multithreading
Instoduce separation of concerns and multrithreaded execution.  Beware of thread safety issues.

```bash
git checkout lab05_v3
```

**List of files changing**
```
- src/main_zmq.py # 
```

## Lab05 v4 Collision Avoidance
We remove dummy sensors, force all vessel to also publish their position into all/traffic topic. 
Implemeted collision_avoidance function: It reads detections from camera and sets vessel to mode.manual.
and also reads 

```bash
git checkout lab05_v4
```

**List of files changing**
```
- src/main_collision.py #  collision avoidance relies first on camera if object is close, then it also takes into account traffic
- src/main_zmq # cleanup dummy sensors and added collision avoidance that only relies on all/traffic
- src/interfaces
    -vessel_interface # added handle traffic 
- src/handlers
    - mqtt-handler # register to all/traffic
- src/controllers 
    - dronekit-vessel_controller  # implemented handle traffic 

```

Collision scenario:

Terminal A:  ```python3 src/main_zmq_collision.py ASV0 tcp:127.0.0.1:16010``` #with camera

Terminal B:  ```python3 src/main_zmq.py ASV0 tcp:127.0.0.1:16010```




## Lab05 v5 ROS
We wrap funcitonality build up until now into RoS node classes. We replace socket communication with ROS topics. 

```bash
git checkout lab05_v5
```


**List of files changing**
```
- src/main_ros2 
- src/interfaces
    - vessel_interface
- src/nodes
    - vessel_node
    - camera_node
    - mqtt_bridge node
- src/controllers
    - mavros_vessel_controller
```



### Ros Container preparation 
- install devcontainers extension for vs 
- Create a '.devcontainer' folder at root directory
- Create inside .devcontainer folder a devcontainer.json file and paste contents below
    - ```json
        {
            "name": "ROS 2 Development",
            "image": "osrf/ros:jazzy-desktop",
            "runArgs": [
                "--network=ardupilot-network",
                "--name=ros2_dev_container",
                "--hostname=ros2-dev"
            ],
            "customizations": {
                "vscode": {
                    "settings": {
                        "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
                        "python.terminal.activateEnvironment": true
                    },
                    "extensions": [
                        "ms-python.python",
                        "ms-python.vscode-pylance",
                        "ms-iot.vscode-ros"
                    ]
                }
            },
            "postCreateCommand": "chmod +x scripts/installation_script.sh && sudo chmod +x start.sh && scripts/installation_script.sh"
            //"postCreateCommand": "apt-get update && apt-get install -y python3-venv && python3 -m venv .venv && .venv/bin/pip install --upgrade pip && echo 'source /opt/ros/jazzy/setup.bash' >> ~/.bashrc"
        }
        ```
- ATTENTION docker network "ardupilot-network" must exist to ensure communication with other containers.

- **Cmd/Ctrl+Shift+P** > **Dev Containers Re-Open in container**
- Start a terminal inside the container and check if you have ros2 in your system

```bash
root@/workspaces/lab05-ss06# ros2 topic list

/parameter_events
/rosout
```

### Useful ros commands: 
Read the full documentation of ros-cli [here](https://docs.ros.org/en/rolling/Concepts/Basic/About-Command-Line-Tools.html)
```bash
ros2 --help
ros2 topic list. ## lists topics in ROS
ros2 topic echo topic_name # echoes topic_name eg. /asv0/status

ros2 param list # lists parameters
ros2 service list # list services

```

### Mavros support 

- Open folder in devcontainer 
- open a terminal inside the container. **DEPRECATED THIS NOW IS INSTALLED ** 
    - ```bash
        sudo apt update
        sudo apt install ros-jazzy-mavros ros-jazzy-mavros-msgs ros-jazzy-mavros-extras screen -y
        sudo /opt/ros/jazzy/lib/mavros/install_geographiclib_datasets.sh```



### Runing a mavros node 
Ros is modular so we need to run a mavros node in separate window

```bash
ros2 run mavros mavros_node --ros-args -r __ns:=/asv0/mavros -p fcu_url:="tcp://mavproxy-controller:16010" -p tgt_system:=1
```

and on another one:

```bash
source .venv/bin/activate && 
source /opt/ros/jazzy/setup.bash && 
python3 src/main_ros2.py ${VEHICLE_ROLE} ${FCU_PORT}
```



for convenience we have prepared a script that utilizes **screen command**. You may find its full documentation [here](https://www.gnu.org/software/screen/manual/screen.html) 
```bash
./start.sh ASV0 tcp://mavproxy-controller:16010
```

some usefull screen commands:
```
screen -list # show available screens
screen -r name  #connects to the screen "name"
screen -S name  #creates a new screen named "name"

```
the key comnbinations for to detach a screen : `Ctrl+A d`



###

