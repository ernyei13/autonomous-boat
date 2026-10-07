import time
import sys
import os
from controllers.camera_controller import CameraController, is_headless
from controllers.dummy_sensor_controller import DummyController
from handlers.mqtt_handler import MQTTHandler
from controllers.dronekit_vessel_controller import (
    DroneKitVesselController as VesselController,
)
import dotenv
import json

import cv2
import queue
import base64
import numpy as np


def main(role, connection_string):
    dotenv.load_dotenv()
    # test
    # need to initialize before - finally didn't like it otherwise.
    mqtt_handler = None
    vessel_controller = None
    telemetry_interval = (
        int(os.getenv("TELEMETRY_INTERVAL")) if os.getenv("TELEMETRY_INTERVAL") else 1
    )

    HEADLESS_MODE = is_headless()
    try:
        # Initialize MQTT handler and vessel controller
        vessel_controller = VesselController(role.upper(), connection_string)
        camera_controller = CameraController(role.upper())
        dummy_sensor_1 = DummyController(role.upper())
        dummy_sensor_2 = DummyController(role.upper())
        dummy_sensor_3 = DummyController(role.upper())

        mqtt_handler = MQTTHandler(role.upper())
        mqtt_handler.client.user_data_set({"vessel_controller": vessel_controller})

        # Main loop to get telemetry data and publish it every 15 seconds
        detections = []
        while True:
            # Get telemetry data from the vessel
            t_start = time.time()
            t_data = vessel_controller.get_telemetry()
            telemetry_data = json.loads(t_data)
            # print(telemetry_data)

            try:

                camera_message = camera_controller.detect(
                    telemetry_data["lon"],
                    telemetry_data["lat"],
                    telemetry_data["heading"],
                )

                dummy_message_1 = dummy_sensor_1.detect(
                    telemetry_data["lon"],
                    telemetry_data["lat"],
                    telemetry_data["heading"],
                )

                dummy_message_2 = dummy_sensor_2.detect(
                    telemetry_data["lon"],
                    telemetry_data["lat"],
                    telemetry_data["heading"],
                )

                dummy_message_3 = dummy_sensor_3.detect(
                    telemetry_data["lon"],
                    telemetry_data["lat"],
                    telemetry_data["heading"],
                )

                if camera_message and camera_message.get("payload"):
                    # Publish detection data to the MQTT broker
                    if not HEADLESS_MODE:
                        # Decode the base64 string back into a raw image array

                        b64_img = camera_message["payload"]
                        img_bytes = base64.b64decode(b64_img)
                        np_arr = np.frombuffer(img_bytes, np.uint8)
                        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                        if frame is not None:
                            cv2.imshow("Detections", frame)

                            # Let waitKey handle the UI events!
                            if cv2.waitKey(1) & 0xFF == ord("q"):
                                print("User pressed 'q'. Shutting down...")
                                stop_event.set()  # Tells all background threads to die
                                break

            except Exception as e:
                print(f"Detection error: {e}")
                detections = []

            # Publish telemetry data to the MQTT broker
            mqtt_handler.publish(t_data)

            # telemetry according to speed
            if vessel_controller.get_speed() > 0.5:
                time.sleep(0.1 / vessel_controller.get_speed())
            else:
                # Wait for 15 seconds before the next data output
                time.sleep(0.3)

            print(
                f"Ellapsed time for telemetry loop: {time.time() - t_start:.2f} seconds."
            )

    except KeyboardInterrupt:
        # TODO - maybe catch ctrl-c if u wanna do something
        print("Exiting script...")

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        # Ensure both MQTT and vehicle connections are closed before exiting
        if vessel_controller:
            vessel_controller.close_connection()
        if camera_controller:
            camera_controller.close()
        if mqtt_handler:
            mqtt_handler.disconnect()
        print("All connections closed. Exiting.")


if __name__ == "__main__":
    os.environ["MAVLINK20"] = "1"  # required to connect to mavproxy with docker
    os.environ["MAVLINK_DIALECT"] = (
        "ardupilotmega"  # required to connect to mavproxy with docker
    )
    connection_string = None
    role = None
    if len(sys.argv) == 3:
        role = sys.argv[1]
        connection_string = sys.argv[2]
    elif len(sys.argv) == 2:
        role = sys.argv[1]
        connection_string = f"udp:127.0.0.1:{14560+int(role[-1])*10}"
    else:
        print("Usage: python main.py <role>")
        print("Specify the role of the rover (e.g., 'SCOUT', 'TEAM1')")
        sys.exit(1)

    main(role, connection_string)
