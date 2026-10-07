import random

from interfaces.sensor_interface import ISensorDetector
import time
import uuid


class DummyController(ISensorDetector):
    def __init__(self, role):
        self.role = role
        self.mission_uuid = None
        self.status = {}
        self.name = f"Sensor_{self.role}_{uuid.uuid4()}"
        self.sleeep_time = random.uniform(
            1.0, 3.0
        )  # Simulate processing time for detection

    def get_name(self):
        return self.name

    def detect(self, sensor_lon, sensor_lat, sensor_heading, props={}) -> dict:
        # Implement the detection logic here
        # For now, return a dummy detection result

        time.sleep(self.sleeep_time)  # Simulate some processing time
        print(
            f"Dummy sensor {self.name}  processing time {self.sleeep_time:.2f} seconds."
        )

        return {
            "sensor_lon": sensor_lon,
            "sensor_lat": sensor_lat,
            "sensor_heading": sensor_heading,
            "props": props,
            "detections": [],  # Replace with actual detections
        }

    def close(self):
        # Implement any cleanup logic here if needed
        print(f"Dummy sensor {self.name} closed.")
