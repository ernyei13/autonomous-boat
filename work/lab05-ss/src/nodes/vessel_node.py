#!/usr/bin/env python3

import sys
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

# Import Both Backends
from controllers.dronekit_vessel_controller import DroneKitVesselController
from controllers.mavros_vessel_controller import MavrosVesselController


class VesselNode(Node):
    def __init__(self, role, connection_string, use_mavros=False):
        super().__init__(f'{role}_vessel_node')
        self.role = role.upper()
        self.connection_string = connection_string
        self.use_mavros = use_mavros

        self.vessel_controller = None
        self.timer = None

        self.init_timer = self.create_timer(0.1, self.init_hardware_callback)

        # Publishers
        self.telemetry_pub = self.create_publisher(
            String, f"/{self.role.lower()}/telemetry", 10
        )
        self.status_pub = self.create_publisher(
            String, f"/{self.role.lower()}/status", 10
        )

        # Subscriptions
        self.command_sub = self.create_subscription(
            String, f"/{self.role.lower()}/incoming_commands", self.command_callback, 10
        )

    def init_hardware_callback(self):
        self.init_timer.cancel()

        try:
            # FACTORY INJECTION
            if self.use_mavros:
                self.get_logger().info("Initializing native ROS2 MAVROS backend...")
                self.vessel_controller = MavrosVesselController(ros2_node=self)
                self.get_logger().info("Connected to ROS2 MAVROS backend...")
            else:
                self.get_logger().info("Initializing legacy DroneKit backend...")
                self.vessel_controller = DroneKitVesselController(
                    self.role, self.connection_string
                )

            self.timer = self.create_timer(1, self.vessel_callback)
            
        except Exception as e:
            # THIS WILL CATCH THE SILENT CRASHES!
            self.get_logger().error(f"CRITICAL ERROR during initialization: {e}")

    def vessel_callback(self):
        try:
            self.vessel_controller.monitor_mission_progress()
        except Exception as e:
            self.get_logger().error(f"Hardware sync error: {e}")
            return

        telemetry_data = self.vessel_controller.get_telemetry()
        status = self.vessel_controller.get_status()

        if telemetry_data:
            msg = String()
            msg.data = telemetry_data  # Already a JSON string from the controller
            self.telemetry_pub.publish(msg)

        if status:
            s_msg = String()
            s_msg.data = json.dumps(status)
            self.status_pub.publish(s_msg)

    def command_callback(self, msg):
        try:
            json_message = json.loads(msg.data)
            cmd = json_message.get("command", "").lower()
            payload = json_message.get("payload", [])
            speed = json_message.get("speed")
            cmd_uuid = json_message.get("uuid")

            if cmd == "stop":
                self.vessel_controller.stop_vehicle()
            elif cmd == "start":
                self.vessel_controller.start_auto_mission()
                if speed:
                    self.vessel_controller.set_speed(speed)
            elif cmd == "return":
                self.vessel_controller.return_to_home()
            elif cmd == "manual":
                self.vessel_controller.set_manual_mode()
        except Exception as e:
            self.get_logger().error(f"Command execution failed: {e}")


# ... (main function stays the exact same)
