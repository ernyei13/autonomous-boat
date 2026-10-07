#!/usr/bin/env python3

import os
import sys
import json
import time
from datetime import datetime
import dotenv
import paho.mqtt.client as mqtt

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class MqttBridgeNode(Node):
    def __init__(self, role):
        super().__init__('mqtt_bridge_node')
       

        # 1. Declare and retrieve ROS2 Parameters (with fallback to .env)
        dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
        
        self.declare_parameter('role', role.lower())
        if role is not None:
            self.role = role.upper()
        else:
            self.role = self.get_parameter('role').get_parameter_value().string_value.upper()
        
        self.broker = os.getenv('MQTT_BROKER', 'localhost')
        self.port = int(os.getenv('MQTT_PORT', '1883'))
        self.username = os.getenv('MQTT_USERNAME')
        self.password = os.getenv('MQTT_PASSWORD')
        
        # Topics Configuration
        self.topic = f"{self.role.lower()}/position"
        self.command_topic = f"{self.role.lower()}/commands"
        self.ack_topic = f"{self.role.lower()}/commands_ack"
        self.camera_topic = f"{self.role.lower()}/camera"
        self.detections_topic = f"{self.role.lower()}/detections"
        
    
        # 2. ROS2 Interfaces (Publishers & Subscribers)
        # Publishes incoming external MQTT commands to the internal ROS2 ecosystem
        self.ros_command_pub = self.create_publisher(String, f'/{self.role.lower()}/incoming_commands', 10)
        
        # Subscribes to internal data sources that need to go out to the cloud
        self.ros_telemetry_sub = self.create_subscription(String, f'/{self.role.lower()}/telemetry', self.ros_telemetry_callback, 1)
        self.ros_detection_sub = self.create_subscription(String, f'/{self.role.lower()}/detections', self.ros_detection_callback, 1)
        self.ros_camera_sub = self.create_subscription(String, f'/{self.role.lower()}/camera', self.ros_camera_callback, 1)

        # 3. Setup Paho MQTT Client
        self.client = mqtt.Client()
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        
        try:
            self.client.connect(self.broker, self.port, 60)
            self.get_logger().info(f"Connected to MQTT broker {self.broker}:{self.port}")
        except Exception as e:
            self.get_logger().error(f"Failed to connect to MQTT broker: {e}")
            raise e

        self.client.on_message = self.mqtt_message_callback
        self.client.subscribe(self.command_topic)
        
        # Start the background MQTT thread network loop
        self.client.loop_start()
        self.get_logger().info(f"MQTT loop started")

    def ros_telemetry_callback(self, msg):
        """Listens to internal telemetry updates and forwards them to MQTT telemetry broker."""
        # Typically, vessel_thread publishes telemetry here; we direct it straight to the outer cloud.
        self.publish_to_mqtt(self.topic, msg.data)

    def ros_camera_callback(self, msg):
        """Publish the full log of camera to mqttt"""
        self.publish_to_mqtt(self.camera_topic, msg.data)

    def ros_detection_callback(self, msg):
        """Listens to CV/Lidar detections and sends them to the external cloud broker."""
        self.publish_to_mqtt(self.detections_topic, msg.data)

    def publish_to_mqtt(self, topic, payload):
        """Helper to safely handle MQTT data transfers."""
        result = self.client.publish(topic, payload)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            self.get_logger().debug(f"Successfully pushed updates to cloud topic: {topic}")
        else:
            self.get_logger().error(f"MQTT publish drop out code: {result.rc}")

    def mqtt_message_callback(self, client, userdata, message):
        """Triggered when an external command is received over MQTT."""
        try:
            decoded_message = message.payload.decode('utf-8').strip()
            self.get_logger().info(f"External Cloud MQTT String caught: {decoded_message}")
            
            json_message = json.loads(decoded_message)
            name = json_message.get('name', '').upper()

            if name != self.role:
                self.get_logger().warn(f"Message targeted for {name}, missing match with {self.role}. Drop.")
                return

            # Native ROS2 approach: Push the raw JSON payload downstream 
            # The Main VesselNode or ControlNode will subscribe to 'vessel/incoming_commands' to execute it.
            ros_msg = String()
            ros_msg.data = decoded_message
            self.ros_command_pub.publish(ros_msg)
            
            # Send immediate ingestion receipt back to cloud broker
            command_type = json_message.get('command', 'unknown')
            self.publish_acknowledgment(f"Command '{command_type}' registered and routing downstream.")

        except json.JSONDecodeError:
            self.get_logger().error("Invalid JSON format received over MQTT.")
            self.publish_acknowledgment("Invalid JSON format received")
        except Exception as e:
            self.get_logger().error(f"Error in MQTT callback routing: {e}")

    def publish_acknowledgment(self, message):
        self.publish_to_mqtt(self.ack_topic, message)

    def destroy_node(self):
        # Overwrite node destructor to handle clean thread closeouts
        self.get_logger().info("Stopping MQTT background thread loops...")
        self.client.loop_stop()
        self.client.disconnect()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MqttBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()

if __name__ == '__main__':
    main()