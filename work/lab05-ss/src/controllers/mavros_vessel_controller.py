import json
import math
from datetime import datetime, timezone
from interfaces.vessel_interface import IVesselController

from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from sensor_msgs.msg import NavSatFix, BatteryState, Imu
from geometry_msgs.msg import TwistStamped
from std_msgs.msg import Float64
from mavros_msgs.msg import State, Waypoint
from mavros_msgs.srv import SetMode, WaypointPush, WaypointClear

def euler_from_quaternion(x, y, z, w):
        """
        Convert a quaternion into euler angles (roll, pitch, yaw)
        roll is rotation around x in radians (counterclockwise)
        pitch is rotation around y in radians (counterclockwise)
        yaw is rotation around z in radians (counterclockwise)
        """
        t0 = +2.0 * (w * x + y * z)
        t1 = +1.0 - 2.0 * (x * x + y * y)
        roll_x = math.atan2(t0, t1)
     
        t2 = +2.0 * (w * y - z * x)
        t2 = +1.0 if t2 > +1.0 else t2
        t2 = -1.0 if t2 < -1.0 else t2
        pitch_y = math.asin(t2)
     
        t3 = +2.0 * (w * z + x * y)
        t4 = +1.0 - 2.0 * (y * y + z * z)
        yaw_z = math.atan2(t3, t4)
     
        return roll_x, pitch_y, yaw_z # in radians


class MavrosVesselController(IVesselController):
    def __init__(self, ros2_node):
        self.node = ros2_node
        self.role = ros2_node.role.upper()
        
        self.waypoints = []
        self.mission_uuid = ""
        self.wkt = ""
        
        # Vehicle State Variables matching Dronekit
        self.current_lat = 0.0
        self.current_lon = 0.0
        self.current_heading = 0
        self.current_speed = 0.0  # Speed over ground
        self.current_mode = "UNKNOWN"
        self.is_armed = False
        
        # Extended Battery State
        self.battery_level = 100.0
        self.battery_voltage = 0.0
        self.battery_current = 0.0

        # IMU & Velocity State
        self.pitch = 0.0
        self.roll = 0.0
        self.yaw = 0.0
        self.pitchspeed = 0.0
        self.rollspeed = 0.0
        self.yawspeed = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.vz = 0.0
        
        # Configuration Flags matching Dronekit exactly
        self.flags = {
            "video_on": True, "video_write_on": True, "temp_mission_on": True,
            "collision_avoidance_on": True, "video_raw_on": True,
            "video_detections_on": True, "lidar_detections_on": True
        }


        # Create a QoS profile that matches MAVROS sensor outputs
        best_effort_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Subscribers
        ns = f'/{self.role.lower()}/mavros'
        self.node.create_subscription(NavSatFix, f'{ns}/global_position/global', self._gps_cb, best_effort_qos)
        self.node.create_subscription(Float64, f'{ns}/global_position/compass_hdg', self._compass_cb, best_effort_qos)
        self.node.create_subscription(Imu, f'{ns}/imu/data', self._imu_cb, best_effort_qos)
        self.node.create_subscription(TwistStamped, f'{ns}/local_position/velocity_local', self._vel_cb, best_effort_qos)
        self.node.create_subscription(BatteryState, f'{ns}/battery', self._batt_cb, best_effort_qos)
        
        state_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL, # <--- THIS IS REQUIRED FOR MAVROS
            depth=10
        )

        # State stays reliable
        self.node.create_subscription(State, f'{ns}/state', self._state_cb, state_qos)

        # Service Clients
        self.set_mode_cli = self.node.create_client(SetMode, f'{ns}/set_mode')
        self.wp_push_cli = self.node.create_client(WaypointPush, f'{ns}/mission/push')
        self.wp_clear_cli = self.node.create_client(WaypointClear, f'{ns}/mission/clear')

    # --- ROS2 Callbacks ---
    def _gps_cb(self, msg):
        self.current_lat = msg.latitude
        self.current_lon = msg.longitude
    
    def _compass_cb(self, msg):
        self.current_heading = msg.data

    def _imu_cb(self, msg):
        # Extract angular velocities
        self.rollspeed = msg.angular_velocity.x
        self.pitchspeed = msg.angular_velocity.y
        self.yawspeed = msg.angular_velocity.z

        # Convert quaternion orientation to Euler angles (roll, pitch, yaw)
        q = msg.orientation
        roll, pitch, yaw = euler_from_quaternion(q.x, q.y, q.z, q.w)
        self.roll = roll
        self.pitch = pitch
        self.yaw = yaw

    def _vel_cb(self, msg):
        # Extract linear velocities
        self.vx = msg.twist.linear.x
        self.vy = msg.twist.linear.y
        self.vz = msg.twist.linear.z
        
        # Calculate 2D Ground Speed (SOG) from Vx and Vy (m/s)
        self.current_speed = math.sqrt(self.vx**2 + self.vy**2)

    def _state_cb(self, msg):
        self.current_mode = msg.mode
        self.is_armed = msg.armed

    def _batt_cb(self, msg):
        # percentage is usually 0.0 to 1.0 in standard sensor_msgs/BatteryState
        self.battery_level = msg.percentage * 100.0 
        self.battery_voltage = msg.voltage
        # Some flight controllers report negative current for discharging
        self.battery_current = abs(msg.current)

    # --- Interface Implementation ---
    def get_status(self) -> dict:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        return {
            "asv": self.role, "timestamp": timestamp, "station": 00000,
            "mmsi": 99999 + int(self.role[-1]), "lon": self.current_lon, "lat": self.current_lat,
            "sog": round(self.current_speed, 2), "cog": int(self.current_heading), "heading": int(self.current_heading),
            "status": 0, "blevel": int(self.battery_level), "bcur": self.battery_current, "bvol": self.battery_voltage,
            "pitch": self.pitch, "roll": self.roll, "yaw": self.yaw,
            "pitchspeed": self.pitchspeed, "rollspeed": self.rollspeed, "yawspeed": self.yawspeed,
            "vx": self.vx, "vy": self.vy, "vz": self.vz,
            "mission_uuid": self.mission_uuid, "mission_line": self.wkt,
            **self.flags
        }

    def get_telemetry(self) -> str:
        original_dict = self.get_status()
        selected_keys = ["asv", "timestamp", "station", "mmsi", "lon", "lat", "sog", "cog", 
                         "heading", "status", "blevel", "bcur", "bvol","pitch","yaw","roll",
                         "pitchspeed","rollspeed","yawspeed","vx","vy","vz", "mission_uuid","mission_line"]
        payload = {k: original_dict[k] for k in selected_keys if k in original_dict}
        return json.dumps(payload)

    def monitor_mission_progress(self):
        # In MAVROS, mission progress is tracked via /mavros/mission/waypoints topic.
        pass 

    # --- Hardware Commands ---
    def _call_mode(self, custom_mode):
        if self.set_mode_cli.wait_for_service(timeout_sec=1.0):
            req = SetMode.Request(custom_mode=custom_mode)
            self.set_mode_cli.call_async(req)

    def stop_vehicle(self): self._call_mode("HOLD")
    def start_auto_mission(self): self._call_mode("AUTO")
    def return_to_home(self): self._call_mode("RTL")
    def set_manual_mode(self): self._call_mode("MANUAL")
    
    def set_speed(self, speed): self.current_speed = float(speed)
    def get_speed(self) -> float: return self.current_speed
    def close_connection(self): pass

    # # --- Mission Commands ---
    # def store_waypoints(self, waypoints: list):
    #     self.waypoints = waypoints
    #     if not self.wp_push_cli.wait_for_service(timeout_sec=1.0):
    #         return
        
    #     req = WaypointPush.Request()
    #     for idx, pt in enumerate(waypoints):
    #         wp = Waypoint()
    #         wp.frame = 6 # MAV_FRAME_GLOBAL_RELATIVE_ALT
    #         wp.command = 16 # MAV_CMD_NAV_WAYPOINT
    #         wp.is_current = True if idx == 0 else False
    #         wp.autocontinue = True
    #         wp.x_lat = float(pt[0] if isinstance(pt, list) else pt.get('lat'))
    #         wp.y_long = float(pt[1] if isinstance(pt, list) else pt.get('lon'))
    #         req.waypoints.append(wp)
            
    #     self.wp_push_cli.call_async(req)

    # def clear_waypoints(self):
    #     self.waypoints = []
    #     if self.wp_clear_cli.wait_for_service(timeout_sec=1.0):
    #         self.wp_clear_cli.call_async(WaypointClear.Request())

    # def start_temporary_mission(self, waypoints: list, uuid: str) -> bool:
    #     # SAFETY LOCK: Wait for EKF Origin
    #     if self.current_lat == 0.0 or self.current_lon == 0.0:
    #         self.node.get_logger().warn("Cannot start mission: Waiting for GPS/EKF Origin!")
    #         return False

    #     self.mission_uuid = uuid
    #     self.store_waypoints(waypoints)
    #     self.start_auto_mission()
    #     return True

    def get_future_waypoints(self) -> list:
        return self.waypoints

    def set_uuid(self, uuid: str):
        self.mission_uuid = uuid

    # --- Toggles ---
   

    def handle_other_traffic(self, traffic_data):
            pass