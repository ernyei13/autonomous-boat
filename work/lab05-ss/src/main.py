import time
import sys
import os
from handlers.mqtt_handler import MQTTHandler
from controllers.dronekit_vessel_controller import (
    DroneKitVesselController as VesselController,
)
import dotenv


def main(role, connection_string):
    dotenv.load_dotenv()
    # test
    # need to initialize before - finally didn't like it otherwise.
    mqtt_handler = None
    vessel_controller = None
    telemetry_interval = (
        int(os.getenv("TELEMETRY_INTERVAL")) if os.getenv("TELEMETRY_INTERVAL") else 1
    )

    try:
        # Initialize MQTT handler and vessel controller
        vessel_controller = VesselController(role.upper(), connection_string)
        mqtt_handler = MQTTHandler(role.upper())
        mqtt_handler.client.user_data_set({"vessel_controller": vessel_controller})

        # Main loop to get telemetry data and publish it every 15 seconds
        while True:
            # Get telemetry data from the vessel
            telemetry_data = vessel_controller.get_telemetry()
            # print(telemetry_data)

            # Publish telemetry data to the MQTT broker
            mqtt_handler.publish(telemetry_data)

            # telemetry according to speed
            if vessel_controller.get_speed() > 0.5:
                time.sleep(1 / vessel_controller.get_speed())
            else:
                # Wait for 15 seconds before the next data output
                time.sleep(3)

    except KeyboardInterrupt:
        # TODO - maybe catch ctrl-c if u wanna do something
        print("Exiting script...")

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        # Ensure both MQTT and vehicle connections are closed before exiting
        if vessel_controller:
            vessel_controller.close_connection()
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
