import os
import sys
import json
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from controllers.camera_controller import CameraController

from nodes.vessel_node import VesselNode

# from nodes.camera_node import CameraNode
# from nodes.collision_node import CollisionAvoidanceNode
from nodes.mqtt_bridge_node import MqttBridgeNode


def main(args=None):
    rclpy.init(args=args)

    role = None
    connection_string = None
    if len(sys.argv) == 3:
        role = sys.argv[1]
        connection_string = sys.argv[2]
    elif len(sys.argv) == 2:
        role = sys.argv[1]
        connection_string = f"udp:127.0.0.1:{14560 + int(role[-1]) * 10}"
    else:
        print("Usage: ros2 run <package> <node> <role>")
        sys.exit(1)

    vessel_node = VesselNode(role, connection_string, use_mavros=True)
    print("Vessel node initialized")
    # camera_node = CameraNode(role)

    mqtt_node = MqttBridgeNode(role)
    mqtt_node.vessel_controller = vessel_node.vessel_controller
    print("Mqtt node initialized")
    # Your custom script connects to MAVROS via standard topics

    # avoidance_node = CollisionAvoidanceNode(role)
    # avoidance_node.vessel_controller = vessel_node.vessel_controller

    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(vessel_node)
    # executor.add_node(camera_node)
    executor.add_node(mqtt_node)
    # executor.add_node(avoidance_node)

    try:
        print("Executor spinnning")
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if vessel_node.vessel_controller is not None:
            vessel_node.vessel_controller.close_connection()

        if hasattr(mqtt_node, "destroy_node"):
            mqtt_node.destroy_node()

        executor.shutdown()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
