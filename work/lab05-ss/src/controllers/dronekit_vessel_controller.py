from dronekit import (
    connect,
    VehicleMode,
    Command,
    LocationGlobal,
    LocationGlobalRelative,
)
from dronekit.mavlink import mavutil
from dronekit import Vehicle
from datetime import datetime, timezone
from interfaces.vessel_interface import IVesselController
import os
import json, time
from pymavlink import mavutil
import math
import copy
import queue
from shapely.geometry import LineString
from pyproj import Geod


class DroneKitVesselController(IVesselController):
    def __init__(self, role, conn_string=None):

        # Convert role to uppercase for consistency
        self.role = role.upper()

        # Get the connection string based on the role
        connection_string = conn_string
        if conn_string is None:
            connection_string = self.get_connection_string()

        # Initialize connection to the vehicle
        print(f"Connecting to vehicle on: {connection_string}")

        # default 30 seconds timeout in some cases is not enough for SITL
        self.vehicle = connect(
            connection_string, wait_ready=True, timeout=120, heartbeat_timeout=60
        )
        self.geod = Geod(ellps="WGS84")
        self.mission_uuid = ""  # Initialize mission UUID to None

        # --- Register the Listeners Here ---
        self.vehicle.add_message_listener("ESC_TELEMETRY", self.esc_telemetry_callback)
        self.traffic = None

    def esc_telemetry_callback(self, vehicle, name, message):
        """
        Callback function for ESC_TELEMETRY messages.
        """
        # ESC_TELEMETRY fields are often arrays or single values depending on MAVLink version
        # We'll use getattr or index checks to be safe
        try:
            v_val = (
                message.voltage[0]
                if isinstance(message.voltage, list)
                else message.voltage
            )
            i_val = (
                message.current[0]
                if isinstance(message.current, list)
                else message.current
            )

            print("--- ESC Data ---")
            print(f"ESC Index: {message.index}")
            print(f"Voltage: {v_val * 0.01:.2f}V")
            print(f"Current: {i_val * 0.01:.2f}A")
            print(
                f"RPM: {message.rpm[0] if isinstance(message.rpm, list) else message.rpm}"
            )
        except (IndexError, TypeError):
            # Handle cases where data might be missing or formatted differently
            pass

    def get_connection_string(self):
        connection_string = os.getenv(f"{self.role}_CONNECTION_STRING")
        if not connection_string:
            raise ValueError(f"Missing connection string for role: {self.role}")
        return connection_string

    def get_status(self):
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        heading = self.vehicle.heading
        ground_speed = round(self.vehicle.groundspeed, 2)
        lat = self.vehicle.location.global_frame.lat
        lon = self.vehicle.location.global_frame.lon

        battery_level = self.vehicle.battery.level
        battery_current = self.vehicle.battery.current
        battery_voltage = self.vehicle.battery.voltage

        pitch = self.vehicle.attitude.pitch
        roll = self.vehicle.attitude.roll
        yaw = self.vehicle.attitude.yaw

        vx = self.vehicle.velocity[0]
        vy = self.vehicle.velocity[1]
        vz = self.vehicle.velocity[2]

        pitchspeed = self.vehicle._pitchspeed
        rollspeed = self.vehicle._rollspeed
        yawspeed = self.vehicle._yawspeed

        # self.vehicle._eph

        status = {
            "asv": self.role,
            "timestamp": timestamp,
            "station": 00000,
            "mmsi": 99999 + int(self.role[-1]),
            "lon": lon,
            "lat": lat,
            "sog": ground_speed,
            "cog": heading,
            "heading": heading,
            "status": 0,
            "blevel": battery_level,
            "bcur": battery_current,
            "bvol": battery_voltage,
            "pitch": pitch,
            "roll": roll,
            "yaw": yaw,
            "pitchspeed": pitchspeed,
            "rollspeed": rollspeed,
            "yawspeed": yawspeed,
            "vx": vx,
            "vy": vy,
            "vz": vz,
            "mission_uuid": self.mission_uuid,
            "mission_line": "",
        }

        return status

    def get_telemetry(self):
        original_dict = self.get_status()
        selected_keys = [
            "asv",
            "timestamp",
            "station",
            "mmsi",
            "lon",
            "lat",
            "sog",
            "cog",
            "heading",
            "status",
            "blevel",
            "bcur",
            "bvol",
            "pitch",
            "yaw",
            "roll",
            "pitchspeed",
            "rollspeed",
            "yawspeed",
            "vx",
            "vy",
            "vz",
            "mission_uuid",
            "mission_line",
        ]
        payload = {k: original_dict[k] for k in selected_keys if k in original_dict}
        return json.dumps(payload)

    def set_uuid(self, uuid):
        self.mission_uuid = uuid

    def get_uuid(self):
        return self.mission_uuid

    def get_current_mission(self):
        return [cmd for cmd in self.vehicle.commands]

    def stop_vehicle(self):
        print("Setting vehicle to LOITER mode.")
        self.vehicle.mode = VehicleMode("MANUAL")

    def get_speed(self):
        return self.vehicle.groundspeed

    def set_speed(self, speed):
        print(f"Setting speed to {speed}")
        # self.set_manual_mode()
        self.vehicle.groundspeed = speed
        self.vehicle.airspeed = speed
        # self.vehicle.parameters["SPEED"]=speed
        self.vehicle.parameters.set("SPEED", speed, 3, True)

    # put vehicle to AUTO - should start auto mission, as long as waypoints are stored in autopilot
    def start_auto_mission(self):
        print("Starting mission in AUTO mode")
        self.vehicle.mode = VehicleMode("LOITER")
        self.arm_vehicle()
        self.vehicle.mode = VehicleMode("AUTO")

    # ARM vehicle - default timeout to arm: 10 secs
    def arm_vehicle(self, timeout=10):
        print("Arming vehicle...")
        self.vehicle.armed = True

        start_time = time.time()
        while not self.vehicle.armed and time.time() - start_time < timeout:
            print("Waiting for vehicle to arm...")
            time.sleep(1)

        if self.vehicle.armed:
            print("Vehicle is armed.")
            return True
        else:
            print(f"Failed to arm the vehicle within {timeout} seconds.")
            return False

    # try to SMART RTL - better than straight RTL, but still not great..
    def return_to_home(self):
        print("Setting vehicle to SMART_RTL mode.")
        self.vehicle.mode = VehicleMode("SMART_RTL")

    def guided_goto(self, waypoints):
        self.vehicle.mode = VehicleMode("GUIDED")
        for p in waypoints:
            next_waypoint = LocationGlobalRelative(p[0], p[1], 0.0)

        # self.vehicle.simple_goto(next_waypoint, groundspeed=10)
        self.vehicle.simple_goto(next_waypoint, groundspeed=self.vehicle.groundspeed)
        pass

    def handle_other_traffic(self, traffic_data):
        if not traffic_data:
            return
        try:
            traffic_json = json.loads(traffic_data)
            other_asv = traffic_json.get("asv", "").lower()
            if self.role.lower() == other_asv:
                # Ignore messages from self
                return
            else:
                # print(f"Handling other traffic: {traffic_json}")
                # Here you can implement logic to handle the other traffic data
                # For example, you might want to log it, adjust your path, etc.
                last_location = self.vehicle.location.global_frame
                wp_location = LocationGlobal(
                    traffic_json["lat"], traffic_json["lon"], 0
                )  # altitude set to 0
                distance = self.get_distance_metres(last_location, wp_location)
                print(f"NEARBY VESSEL DETECTED:  {other_asv} at distance  {distance}")
                DISTANCE_THRESHOLD = 20
                if self.traffic is None:
                    if distance < DISTANCE_THRESHOLD:
                        self.traffic = (wp_location, distance)
                else:
                    prev_location, prev_distance = self.traffic
                    old_distance = min(
                        self.get_distance_metres(last_location, prev_location),
                        prev_distance,
                    )

                    if distance < old_distance:
                        self.traffic = (wp_location, distance)
                    elif old_distance >= DISTANCE_THRESHOLD:
                        self.traffic = None
                    else:
                        self.traffic = (prev_location, old_distance)

                return

        except json.JSONDecodeError:
            print(f"Invalid json message: {e}")
            return

        except Exception as e:
            print(f"Error occurred while handling other traffic: {e}")
            return

    # set to manual. Could be done by adjusting throttle channels,
    # but probably this is safer and works. TODO - NEEDS TESTING.
    def set_manual_mode(self):
        print("Stopping vehicle and switching to MANUAL mode.")

        self.vehicle.mode = VehicleMode("LOITER")

        # Wait for the vehicle to come to a stop
        # TODO - test this
        time.sleep(3)

        self.vehicle.mode = VehicleMode("MANUAL")

        print("Vehicle is now stopped and in MANUAL mode.")

    # TODO move it to utilities
    def get_distance_metres(self, loc1, loc2):
        # Use a more accurate method for calculating distance over the Earth's surface
        dlat = math.radians(loc2.lat - loc1.lat)
        dlon = math.radians(loc2.lon - loc1.lon)
        a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(
            math.radians(loc1.lat)
        ) * math.cos(math.radians(loc2.lat)) * math.sin(dlon / 2) * math.sin(dlon / 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = 6371000 * c  # Earth's radius in meters
        return distance

    def monitor_mission_progress(self):
        pass

    def close_connection(self):
        self.vehicle.close()
        print("Vehicle connection closed.")
