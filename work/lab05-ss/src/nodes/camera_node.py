import sys
import json
import math  # <-- Add this!
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from controllers.camera_controller import CameraController


class CameraNode(Node):
    def __init__(self, role):
        super().__init__("camera_node")

        self.role = role.lower()
        self.camera_controller = CameraController(role.upper())
        self.last_status = None

        # --- Subscriptions ---
        # Listens to the local status topic populated by VesselNode
        self.create_subscription(
            String, f"/{self.role}/status", self.status_callback, 10
        )

        # --- Publishers ---
        # Published targets will be picked up by MqttBridgeNode & CollisionAvoidanceNode
        self.detection_pub = self.create_publisher(
            String, f"/{self.role}/detections", 10
        )
        self.camera_log_pub = self.create_publisher(
            String, f"/{self.role}/camera", 10
        )  # For full detection arrays

        # --- Timer Loop ---
        fps_interval = 1.0 / self.camera_controller.get_fps()
        self.timer = self.create_timer(fps_interval, self.process_camera_pipeline)

        self.get_logger().info(
            f"CameraNode operational at {self.camera_controller.get_fps()} FPS."
        )

    def status_callback(self, msg):
        try:
            self.last_status = json.loads(msg.data)
        except Exception as e:
            self.get_logger().error(f"Failed to parse status payload: {e}")

    def process_camera_pipeline(self):
        # Drop out if we haven't received a status heartbeat packet yet
        if not self.last_status:
            return

        status = self.last_status

        # 1. Dynamically configure the camera controller via the incoming status map
        try:
            self.camera_controller.set_status(status)
            self.camera_controller.mission_uuid = status.get("mission_uuid")

            # Ensure your controller knows if raw frames or detections are explicitly allowed
        except Exception as e:
            self.get_logger().error(f"Camera state synchronization error: {e}")
            return

        # 2. Frame processing execution pipeline
        try:
            # Initialize variables to prevent scope issues during recording/sending

            # Extract coordinates safely
            lat = status.get("lat", 0.0)
            lon = status.get("lon", 0.0)
            heading = status.get("heading", 0.0)

            # Safety Check: Drop out of the detection loop if GPS hasn't locked
            if math.isnan(lat) or math.isnan(lon) or math.isnan(heading):
                self.get_logger().warn(
                    "Awaiting GPS 3D lock... skipping geo-projection.",
                    throttle_duration_sec=5.0,
                )
                return

            # Only run detection if coordinates are finite
            message = self.camera_controller.detect(lat, lon, heading)

            # Publish the entire detection object map
            log_msg = String()
            log_msg.data = json.dumps(message)
            self.camera_log_pub.publish(log_msg)

            # Route target tracks downstream into the local ROS2 ecosystem
            if "detections" in message and len(message["detections"]) > 0:
                # Replicates: mqtt_handler.publish_detections for ALL targets
                # The MqttBridgeNode subscribes to this topic and pushes them up to the cloud automatically.
                # Send only the FIRST (closest sorted) target to the local collision thread to maintain low processing overhead
                primary_detection = message["detections"][0]
                detection_msg = String()
                detection_msg.data = json.dumps(primary_detection)
                self.detection_pub.publish(detection_msg)

        except Exception as e:
            self.get_logger().error(f"Camera perception execution error: {e}")
