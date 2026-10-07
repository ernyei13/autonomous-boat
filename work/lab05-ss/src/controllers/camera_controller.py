from ultralytics import YOLO
import cv2
import os
import base64
import math
import numpy as np
import paho.mqtt.client as mqtt
import sys
from unittest.mock import MagicMock

# Trick the system into thinking the missing KMS modules exist
sys.modules["kms"] = MagicMock()
sys.modules["pykms"] = MagicMock()


try:
    from picamera2 import Picamera2

    USE_PICAMERA = True
    print("Picamera2 found. Using Raspberry Pi camera module.")
except ImportError:
    import cv2

    USE_PICAMERA = False
    print("Picamera2 not found. Falling back to default system camera (OpenCV).")
import json

# start webcam
from time import time, time_ns
from datetime import datetime, timezone
from geopy.distance import geodesic
from geopy import Point
from geopy.distance import distance as geopy_distance
from dotenv import load_dotenv
from interfaces.sensor_interface import ISensorDetector

load_dotenv()


class CameraController(ISensorDetector):
    def __init__(self, role):
        self.role = role.upper()

        self.image_width = 1280
        self.image_height = 720
        self.fps = 10
        self.horizontal_fov_deg = 90
        self.vertical_fov_deg = 60
        # Initialize the Picamera2
        # Initialize the camera entirely headlessly
        self.use_picamera = USE_PICAMERA

        if self.use_picamera:
            self.camera = Picamera2()

            # Create a configuration profile using your class variables
            config = self.camera.create_preview_configuration(
                main={"size": (self.image_width, self.image_height), "format": "RGB888"}
            )
            # Apply the configuration and start the camera
            self.camera.configure(config)
            self.camera.start()
        else:
            # Use OpenCV's VideoCapture for other cameras
            self.camera = cv2.VideoCapture(0)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.image_width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.image_height)
            self.camera.set(cv2.CAP_PROP_FPS, self.fps)
            if not self.camera.isOpened():
                raise RuntimeError("Error: Could not open the default system camera.")

        self.mission_uuid = None
        self.status = {}

        if os.path.exists("./models/best.pt"):
            self.model = YOLO("./models/best.pt")
            # Export the model to NCNN format
            self.model.export(format="ncnn")  # creates 'yolo11n_ncnn_model'
            # Load the exported NCNN model
            # https://docs.ultralytics.com/guides/raspberry-pi/
            self.ncnn_model = YOLO("./models/best_ncnn_model")
        else:
            # model
            self.model = YOLO("./models/yolo11n.pt")
            self.model.export(format="ncnn")  # creates 'yolo11n_ncnn_model'
            self.ncnn_model = YOLO("../models/yolo11n_ncnn_model", task="detect")

        print(self.model.names)
        # object classes
        self.classNames = ["yellow_object", "red_object", "asv", "person", "boat"]

    def get_fps(self):
        return self.fps

    def set_status(self, status):
        self.status = status

    def set_mission_uuid(self, uuid):
        self.mission_uuid = uuid

    def get_frame(self):
        if self.use_picamera:
            # If on Raspberry Pi, use PiCamera's method
            return self.camera.capture_array()
        else:
            # If on Mac/PC, use OpenCV's method
            ret, frame = self.camera.read()
            if not ret:
                return None
            return frame

    def detect(self, sensor_lon, sensor_lat, sensor_heading) -> dict:

        current_time_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        message = {
            "host": self.role.lower(),
            "lon": sensor_lon,
            "lat": sensor_lat,
            "heading": sensor_heading,
            "t": current_time_iso,
            "detections": [],
            "source": "camera",
            "payload": None,
        }

        try:
            frame = self.get_frame()

            if frame is None:
                raise ValueError("Empty frame received from camera.")

            # Run detection
            message, frame = self.frame_detect(
                img=frame,
                camera_lon=sensor_lon,
                camera_lat=sensor_lat,
                camera_alt_m=0.3,
                camera_bearing_deg=sensor_heading,
            )

            # message["detections"] = detections["detections"]

            # message["payload"] = base64.b64encode(buffer).decode("ascii")
            return message
        except Exception as e:
            print(f"Camera detection error: {e}")
            return message

    def frame_detect(
        self,
        img,
        camera_lat=37.7749,
        camera_lon=-122.4194,
        camera_alt_m=0.3,
        camera_bearing_deg=0.0,
    ):

        results = self.ncnn_model(img, stream=True)

        detections = []
        for r in results:
            boxes = r.boxes

            for box in boxes:
                # bounding box
                x1, y1, x2, y2 = box.xyxy[0]
                x1, y1, x2, y2 = (
                    int(x1),
                    int(y1),
                    int(x2),
                    int(y2),
                )  # convert to int values

                # put box in cam
                cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 255), 3)

                # confidence
                confidence = math.ceil((box.conf[0] * 100)) / 100
                # print("Confidence --->",confidence)

                # class name
                cls = int(box.cls[0])
                class_name = r.names[
                    cls
                ]  # This safely asks the model for the actual class name
                # print("Class name -->", self.classNames[cls])

                # object details
                org = [x1, y1]
                font = cv2.FONT_HERSHEY_SIMPLEX
                fontScale = 1
                color = (255, 0, 0)
                thickness = 1

                bbox = (x1, y1, x2, y2)

                lat, lon, distance, azimuth = self.calculate_object_gps_from_bbox(
                    bbox, camera_lat, camera_lon, camera_alt_m, camera_bearing_deg
                )
                if math.isnan(lat) or math.isnan(lon):
                    print(
                        f"Warning: Math error calculating GPS for {class_name}. Skipping detection."
                    )
                    continue  # Skips to the next bounding box without crashing

                # print(
                #     f"Object GPS: class={class_name}, lat={lat}, lon={lon}, distance={distance}, azimuth={azimuth}, bbox = {bbox}"
                # )
                # geopy_distance = geodesic((camera_lat, camera_lon), (lat, lon)).meters

                # azimuth = geodesic((camera_lat, camera_lon), (lat, lon)).initial
                detections.append(
                    {
                        "host": self.role,
                        "mmsi": self.status.get("mmsi"),
                        "mission_uuid": self.mission_uuid,
                        "class": self.classNames[cls],
                        "bbox": bbox,
                        "sensor_lon": camera_lon,
                        "sensor_lat": camera_lat,
                        "lon": lon,
                        "lat": lat,
                        "t": datetime.now().isoformat(),
                        "distance": distance,
                        "azimuth": azimuth,
                        "confidence": confidence,
                        "source": "camera",
                    }
                )

                cv2.putText(
                    img, self.classNames[cls], org, font, fontScale, color, thickness
                )

        _, buffer = cv2.imencode(ext=".jpg", img=img)

        jpg_as_text = base64.b64encode(buffer).decode("ascii")

        sorted_detections = sorted(
            detections, key=lambda d: d.get("distance", float("inf"))
        )

        message = {
            "host": self.role,
            "lon": camera_lon,
            "lat": camera_lat,
            "t": datetime.now().isoformat(),
            "detections": sorted_detections,
            "source": "camera",
            "payload": jpg_as_text,
        }

        # cv2.destroyAllWindows()

        return (message, img)

    def pixel_to_angle(self, x, y, img_width, img_height, h_fov, v_fov):
        # Offset from image center
        x_offset = x - img_width / 2
        y_offset = y - img_height / 2
        # Normalize offsets to range [-1, 1]
        norm_x = x_offset / (img_width / 2)
        norm_y = y_offset / (img_height / 2)
        # Convert to angle in degrees
        angle_x = norm_x * (h_fov / 2)
        angle_y = norm_y * (v_fov / 2)
        return angle_x, angle_y

    def bearing_to_direction(self, base_bearing_deg, relative_angle_deg):
        # Compute absolute bearing
        return (base_bearing_deg + relative_angle_deg) % 360

    def estimate_ground_distance_from_flat_camera(self, altitude_m, vertical_angle_deg):
        # Assumes object is at ground level, and camera is level (0° tilt)
        total_angle_rad = math.radians(vertical_angle_deg)
        if abs(math.tan(total_angle_rad)) < 1e-6:
            return float("inf")  # Prevent division by zero or near-zero
        return altitude_m / abs(math.tan(total_angle_rad))

    def get_gps_from_bearing_distance(self, lat, lon, bearing, dist_m):
        origin = Point(lat, lon)
        destination = geopy_distance(meters=dist_m).destination(origin, bearing)
        return destination.latitude, destination.longitude

    def calculate_object_gps_from_bbox(
        self,
        bbox,  # (x_min, y_min, x_max, y_max)
        camera_lat,
        camera_lon,
        camera_alt_m,
        camera_bearing_deg,
    ):
        try:
            # Compute center of bounding box
            x_min, y_min, x_max, y_max = bbox
            u = (x_min + x_max) / 2.0
            v = (y_min + y_max) / 2.0

            angle_x, angle_y = self.pixel_to_angle(
                u,
                v,
                self.image_width,
                self.image_height,
                self.horizontal_fov_deg,
                self.vertical_fov_deg,
            )

            object_bearing = self.bearing_to_direction(camera_bearing_deg, angle_x)

            distance_m = self.estimate_ground_distance_from_flat_camera(
                camera_alt_m, angle_y
            )

            obj_lat, obj_lon = self.get_gps_from_bearing_distance(
                camera_lat, camera_lon, object_bearing, distance_m
            )

            return obj_lat, obj_lon, distance_m, object_bearing
        except Exception as e:
            # If ANY math or geopy error happens inside this function,
            # catch it here and safely return NaNs instead of crashing.
            # print(f"Math/Geopy error in bbox calculation: {e}")
            return float("nan"), float("nan"), 0.0, 0.0

    def close(self):
        if self.use_picamera:
            self.camera.close()
        else:
            self.camera.release()
        cv2.destroyAllWindows()


def is_headless():
    """Returns True if the system has no display attached."""
    # Mac/Windows might not use DISPLAY in the same way, but Docker/Linux does.
    # We check if both standard Linux display variables are missing.
    display = os.environ.get("DISPLAY")
    wayland = os.environ.get("WAYLAND_DISPLAY")

    # If we are on a system where both are None, we assume headless.
    return display is None and wayland is None


if __name__ == "__main__":

    role = os.environ.get("ROLE", "asv0")
    camera_controller = CameraController(role.upper())

    # 1. Determine if we are headless once at startup
    HEADLESS_MODE = is_headless()
    if HEADLESS_MODE:
        print("🖥️  Running in HEADLESS mode. GUI disabled. Outputs will be logged.")
    else:
        print("🖥️  Display detected. GUI enabled.")

    # OpenCV waitKey requires milliseconds, not seconds
    fps = camera_controller.get_fps()
    # Fallback to 30ms (~33 fps) if get_fps returns 0 or None
    delay_ms = int((1.0 / fps) * 1000) if fps and fps > 0 else 30

    SENSOR_LON = 0.0  # Example longitude
    SENSOR_LAT = 0.0  # Example latitude
    SENSOR_HEADING = 0  # Example heading

    try:
        while True:

            print("###############HEADLESS_MODE:", HEADLESS_MODE)
            camera_controller.detect(
                SENSOR_LON,
                SENSOR_LAT,
                SENSOR_HEADING,
            )

            if not HEADLESS_MODE:
                key = cv2.waitKey(delay_ms) & 0xFF
                if key == ord("q"):
                    print("User pressed 'q'. Quitting...")
                    break

            # CRITICAL FIX: cv2.waitKey() handles the display update AND the FPS sleep time.
            # It waits for 'delay_ms'. If you press the 'q' key on your keyboard during that time, it breaks the loop.
            key = cv2.waitKey(delay_ms) & 0xFF
            if key == ord("q"):
                print("User pressed 'q'. Quitting...")
                break

    except KeyboardInterrupt:
        print("Detection stopped via console (Ctrl+C)")
    except Exception as e:
        print(f"Camera detection error: {e}")
    finally:
        # MANDATORY CLEANUP: If you don't do this you'll have to force-quit terminal to release it.
        camera_controller.close()

        print("Camera and windows safely closed.")
