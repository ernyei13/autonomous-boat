# Maritime Lab 04 Companion Setup

This workspace follows Lab 04: Companion Computer & Autopilot Integration.

## Installed

- Lab 04 code: `work/lab04-companion/code`
- Virtual environment: `work/lab04-companion/code/ss_venv`
- Local MQTT broker config: `work/lab04-companion/mosquitto.conf`
- Lab 04 launch helpers: `work/lab04-companion/scripts`
- Existing Lab 03 SITL: `work/ardupilot` and `work/maritime26`

DroneKit's Python 3.10+ compatibility fix has already been applied inside the virtual environment:

```python
class Parameters(collections.abc.MutableMapping, HasObservers):
```

## Local Settings

The lab `.env` file is configured for this Mac:

```text
MQTT_BROKER=127.0.0.1
MQTT_PORT=1883
MQTT_USE_TLS=false
MQTT_USERNAME=local
MQTT_PASSWORD=local
TEAM_NS=localteam
FLEET_NS=${TEAM_NS}/zoltan
```

That means the fleet MQTT topics are:

```text
localteam/zoltan/scout/position
localteam/zoltan/vessel1/position
localteam/zoltan/vessel1/commands
```

## Ports

| Role | SITL instance | MAVLink system id | Python port |
| --- | ---: | ---: | ---: |
| scout | 0 | 1 | 14551 |
| vessel1 | 1 | 2 | 14561 |
| vessel2 | 2 | 3 | 14571 |
| vessel3 | 3 | 4 | 14581 |

Port `14550` is kept for QGroundControl/MAVProxy map traffic.

## Start The Local Broker

Run in its own terminal:

```bash
work/lab04-companion/scripts/start-broker.sh
```

## Project 1: Basic Telemetry

Terminal 1:

```bash
RESET=1 work/lab04-companion/scripts/launch-project1-scout.sh
```

Terminal 2:

```bash
cd work/lab04-companion/code
source ss_venv/bin/activate
python 1_proj/leader_telemetry.py
```

## Project 2: Telemetry Over MQTT

Start the broker first, then run:

```bash
cd work/lab04-companion/code
source ss_venv/bin/activate
python 2_proj/leader_telemetry.py
```

To watch the MQTT messages:

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -t leader/position -v
```

## Project 4: Two Boats

Start the broker, then two simulator terminals:

```bash
RESET=1 work/lab04-companion/scripts/launch-scout-headless.sh
RESET=1 work/lab04-companion/scripts/launch-vessel1-headless.sh
```

Then two Python terminals:

```bash
cd work/lab04-companion/code
source ss_venv/bin/activate
python 4_proj/main.py scout
```

```bash
cd work/lab04-companion/code
source ss_venv/bin/activate
python 4_proj/main.py vessel1
```

Watch both boats on MQTT:

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -t 'localteam/zoltan/+/position' -v
```

## Projects 6-8: Commands And Follow

Project 6 receives commands but only prints the response:

```bash
python 6_proj/scout.py
python 6_proj/vessel.py vessel1
```

Send a command:

```bash
mosquitto_pub -h 127.0.0.1 -p 1883 \
  -t localteam/zoltan/vessel1/commands \
  -m '{"command": "follow"}' -q 1
```

Projects 7 and 8 use the same command topic, but they actually arm and move the follower in `GUIDED` mode:

```bash
python 7_proj/scout.py
python 7_proj/vessel.py vessel1
```

or:

```bash
python 8_proj/scout.py
python 8_proj/vessel.py vessel1
python 8_proj/vessel.py vessel2
python 8_proj/vessel.py vessel3
```

## Stop Everything

```bash
pkill -TERM -f 'mosquitto|mavproxy.py|Tools/autotest/sim_vehicle.py|/build/sitl/bin/ardurover|QGroundControl' || true
sleep 2
pkill -KILL -f 'mosquitto|mavproxy.py|Tools/autotest/sim_vehicle.py|/build/sitl/bin/ardurover|QGroundControl' || true
```

## Verification Performed

- Lab 04 repository cloned.
- Python 3.12 virtual environment created.
- `pip install -r requirements.txt` completed.
- `import paho.mqtt, dotenv, pymavlink` works.
- `import dronekit` works after the DroneKit compatibility fix.
- Local Mosquitto broker accepts publish/subscribe.
- Project 1 connects to SITL on `udp:127.0.0.1:14551` and prints live telemetry.
- Project 2 publishes telemetry to MQTT.
- Project 4 publishes scout and vessel1 telemetry on separate fleet topics.
- Project 6 receives a JSON `follow` command on `localteam/zoltan/vessel1/commands`.
