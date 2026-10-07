from datetime import datetime
import time
import paho.mqtt.client as mqtt
import os
from dotenv import load_dotenv
import json

# Load environment variables from the .env file located two directories above
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


class MQTTHandler:
    def __init__(self, role):
        self.role = role.upper()

        # Initialize MQTT connection details from role-specific environment variables
        self.broker = os.getenv("MQTT_BROKER")
        self.port = int(os.getenv("MQTT_PORT"))
        self.username = os.getenv(
            "MQTT_USERNAME"
        )  # os.getenv(f'{self.role}_MQTT_USERNAME')
        self.password = os.getenv(
            "MQTT_PASSWORD"
        )  # os.getenv(f'{self.role}_MQTT_PASSWORD')

        self.topic = (
            f"{self.role.lower()}/position"  # os.getenv(f'{self.role}_POSITION_TOPIC')
        )
        self.command_topic = (
            f"{self.role.lower()}/commands"  # os.getenv(f'{self.role}_COMMANDS')
        )
        self.ack_topic = f"{self.role.lower()}/commands_ack"  # os.getenv(f'{self.role}_COMMANDS_ACK')
        self.camera_topic = (
            f"{self.role.lower()}/camera"  # os.getenv(f'{self.role}_POSITION_TOPIC')
        )
        self.detections_topic = f"{self.role.lower()}/detections"  # os.getenv(f'{self.role}_POSITION_TOPIC'). #rename to perception topic in the future
        self.alltraffic = "all/traffic"  # os.getenv(f'{self.role}_POSITION_TOPIC'). #rename to perception topic in the future

        if not all(
            [
                self.broker,
                self.port,
                self.username,
                self.password,
                self.topic,
                self.command_topic,
                self.ack_topic,
            ]
        ):
            raise ValueError(
                f"Missing required MQTT configuration for role: {self.role}"
            )

        # Initialize MQTT client and set up connection
        self.client = mqtt.Client()
        self.client.username_pw_set(self.username, self.password)
        self.client.connect(self.broker, self.port, 60)
        print(f"Connected to broker {self.broker} on port {self.port}")

        # Register the command callback
        self.client.on_message = self.command_callback
        self.client.loop_start()

        # Subscribe to the commands topic during initialization
        self.subscribe(self.command_topic)
        self.subscribe(
            self.alltraffic
        )  # Subscribe to the all/telemetry topic for receiving telemetry from other vessels

    def subscribe(self, topic):
        result = self.client.subscribe(topic)
        if result[0] == mqtt.MQTT_ERR_SUCCESS:
            print(f"Subscribed to topic: {topic}, result: {result}")
        else:
            print(f"Failed to subscribe to topic: {topic}, result: {result}")

    def publish(self, payload, topic=None):
        # Append the username to the payload
        # payload_with_username = f"{payload}, USER: {self.username}"

        # Publish the modified payload to the MQTT broker
        # result = self.client.publish(self.topic, payload_with_username)

        # currrently using it without appended username
        if topic:
            result = self.client.publish(topic, payload)
        else:
            result = self.client.publish(self.topic, payload)

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(
                f"Successfully published to MQTT topic: {topic if topic else  self.topic}"
            )
            # print(f"Transmitting to  {self.topic} ...",end="\r")
        else:
            print(f"Failed to publish to MQTT: {result.rc}")

    def command_callback(self, client, userdata, message):
        vessel_controller = userdata.get("vessel_controller")

        if vessel_controller is None:
            print("Warning: vessel_controller not found in userdata")
            return

        try:
            # print(f"##############{message.topic}#############")
            if message.topic == self.alltraffic:
                # Handle telemetry messages from other vessels
                decoded_message = message.payload.decode("utf-8").strip()

                vessel_controller.handle_other_traffic(decoded_message)
                # You can add further processing of the telemetry data here if needed
                return

            print("Callback triggered")
            # Decode the received message payload
            decoded_message = message.payload.decode("utf-8").strip()
            print(f"Message received: {decoded_message}")

            # Parse the JSON message
            try:
                json_message = json.loads(decoded_message)
                name = json_message.get("name", "").upper()
                command = json_message.get("command", "").lower()
                payload = json_message.get("payload", [])
                speed = json_message.get("speed")
                uuid = json_message.get("uuid")

                # Check if the message is for this role
                if name != self.role:
                    print(
                        f"Received message for {name}, but this is {self.role}. Ignoring."
                    )
                    return

                # print(f"Received command: {command}")
                print(f"Received command: ...")

                # Handle specific commands
                if command == "stop":
                    vessel_controller.stop_vehicle()
                    self.publish_acknowledgment("command stop acknowledged")

                elif command == "start":
                    vessel_controller.start_auto_mission()
                    if speed:
                        vessel_controller.set_speed(speed)
                    self.publish_acknowledgment("command start acknowledged")

                elif command == "return":
                    vessel_controller.return_to_home()
                    self.publish_acknowledgment("command return acknowledged")

                elif command == "manual":
                    vessel_controller.set_manual_mode()
                    self.publish_acknowledgment("command manual acknowledged")

                else:
                    print(f"Unknown command received: {command}")
                    self.publish_acknowledgment(f"Unknown command: {command}")

            except json.JSONDecodeError:
                print("Invalid JSON format received")
                self.publish_acknowledgment("Invalid JSON format received")

        except Exception as e:
            print(f"Error in command_callback: {e}")

    def publish_acknowledgment(self, message):
        # Publish acknowledgment to the <role>/commands_ack topic
        result = self.client.publish(self.ack_topic, message)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"Published acknowledgment: {message}")
        else:
            print(f"Failed to publish acknowledgment: {result.rc}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
