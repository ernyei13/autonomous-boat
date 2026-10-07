# ZeroMQ replacement version of the original multithreaded ROS controller
import json
import os
import sys
import threading
import time
import logging
import zmq
import dotenv
from controllers.camera_controller import CameraController, is_headless
from controllers.dummy_sensor_controller import DummyController
from handlers.mqtt_handler import MQTTHandler
from controllers.dronekit_vessel_controller import (
    DroneKitVesselController as VesselController,
)
import cv2
import queue
import base64
import numpy as np

# from controllers.lidar_controller import LidarController
# from collision_avoidance import Avoidance
from collections import deque
import uuid
from geopy import Point
from geopy.distance import distance as geopy_distance

logging.basicConfig(level=logging.INFO)
stop_event = threading.Event()
stop_event = threading.Event()


# ZeroMQ context and sockets
context = zmq.Context()


def zmq_recv_status(status_sub):
    try:
        return json.loads(status_sub.recv(flags=zmq.NOBLOCK))
    except zmq.Again:
        return None


# def monitor_mission(vessel_controller):
#     vessel_controller.monitor_mission_progress()


def vessel_thread(vessel_controller, mqtt_handler):
    # PUB sockets (from threads sending data)
    status_pub = context.socket(zmq.PUB)
    status_pub.bind("tcp://*:5555")

    while not stop_event.is_set():
        start_time = time.time()
        status = vessel_controller.get_status()
        telemetry_data = vessel_controller.get_telemetry()
        mqtt_handler.publish(telemetry_data)
        mqtt_handler.publish(telemetry_data, "all/traffic")

        # monitor_mission(vessel_controller)

        status_pub.send_json(status)

        # telemetry according to speed
        if vessel_controller.get_speed() > 0.5:
            time.sleep(1 / vessel_controller.get_speed())
        else:
            # Wait for 15 seconds before the next data output
            time.sleep(3)

        print(
            f"Ellapsed time for VESSEL thread loop: {time.time() - start_time:.2f} seconds."
        )


def camera_thread(camera_controller, mqtt_handler, image_queue):

    status_sub = context.socket(zmq.SUB)
    status_sub.connect("tcp://localhost:5555")
    status_sub.setsockopt_string(zmq.SUBSCRIBE, "")

    detection_pub = context.socket(zmq.PUB)
    detection_pub.bind("tcp://*:5556")

    fps_interval = (
        1.0 / camera_controller.get_fps()
    )  # << WE MIGHT NEED TO COMPENSATE FOR FPS LATER, BUT FOR NOW WE'LL JUST USE THE VESSEL THREAD'S TIMING

    IS_HEADLESS = is_headless()

    while not stop_event.is_set():
        status = zmq_recv_status(status_sub)
        t_start = time.time()
        if status:
            print("camera_thread is alive.")
            # print (f"Camera status: {status}")

            try:
                # print(status)
                message = camera_controller.detect(
                    status["lat"], status["lon"], status.get("heading")
                )

                # --- ADD THIS DEBUG PRINT ---
                print(f"DEBUG: Camera detected! Payload exists? {'payload' in message}")
                # ----------------------------

                # if len(detections) > 0:
                #     print(f"Detected: {detections}")
                #     mqtt_handler.publish_camera(json.dumps(detections))

                # for detection in detections["detections"]:
                #     # print(f"Detected: {detection}")
                #     mqtt_handler.publish_detections(json.dumps(detection))
                # send only the first detection to the pub socket

                if len(message["detections"]) > 0:
                    detection_pub.send_json(
                        message["detections"][0]
                    )  # Send only the first detection -sorted by distance

                if not IS_HEADLESS:
                    # No GUI? Safe to use standard sleep.

                    # --- NEW: PASS IMAGE TO MAIN THREAD ---
                    # Grab the base64 image string from your message payload
                    if message and message.get("payload"):
                        try:
                            # Push to queue. If main thread is too slow, drop the frame to prevent lag
                            image_queue.put(message["payload"], block=False)
                            print("DEBUG: Image pushed to queue!")  # Add this too
                        except queue.Full:
                            print("DEBUG: Queue is full, dropping frame.")
                            pass

            except Exception as e:
                logging.error(f"Camera detection error: {e}")

        time.sleep(fps_interval)

        # print(
        #     f"Ellapsed time for camera thread loop: {time.time() - t_start:.2f} seconds."
        # )


def collision_avoidance_thread(vessel_controller):
    status_sub = context.socket(zmq.SUB)
    status_sub.connect("tcp://localhost:5555")
    status_sub.setsockopt_string(zmq.SUBSCRIBE, "")

    detection_sub = context.socket(zmq.SUB)
    detection_sub.connect("tcp://localhost:5556")
    detection_sub.setsockopt_string(zmq.SUBSCRIBE, "")

    buffer = deque(maxlen=2)
    clean_iter = 0
    stop_threshold = 2
    MIN_HEIGHT = 100
    MIN_WIDTH = 200

    while not stop_event.is_set():
        status = zmq_recv_status(status_sub)
        if status:
            print(
                "################collision_avoidance_thread thread is alive.################"
            )
            # No control options used here directly

            try:
                detection = detection_sub.recv_json(flags=zmq.NOBLOCK)
                print(f"Received detection: {detection}")

                if detection["class"] in ["asv", "yellow_object", "red_object"]:
                    print(f"Valid Received detection: {detection}")

                    bbox = detection["bbox"]

                    print(f"Detection bbox: {bbox}")

                    height = abs(bbox[3] - bbox[1])
                    width = abs(bbox[2] - bbox[0])
                    DISTANCE = MIN_HEIGHT / height * 5.0

                    if DISTANCE <= 10:
                        print(
                            f"Collision risk detected from CAMERA! Triggering avoidance. {DISTANCE}"
                        )

                        vessel_lon, vessel_lat = status["lon"], status["lat"]
                        azimuth = detection.get("azimuth", 0.0)
                        # Calculate the GPS coordinates of the detected object

                        origin = Point(vessel_lat, vessel_lon)
                        destination = geopy_distance(meters=DISTANCE).destination(
                            origin, azimuth
                        )

                        buffer.append((destination.longitude, destination.latitude))

                        # if bbox[3]-bbox[1] >= stop_threshold*MIN_HEIGHT |  bbox[2]-bbox[0] >= stop_threshold*MIN_WIDTH:
                        if DISTANCE <= 4:
                            print("Too close  risk detected! Triggering STOP.")
                            vessel_controller.stop_vehicle()
                    elif vessel_controller.traffic:
                        location, distance = vessel_controller.traffic

                        print(
                            f"Nearby vessel detected (Distance ({distance})). Mitigation action Smart RTL"
                        )

                        if distance < 20:
                            vessel_controller.return_to_home()

                    else:
                        print(f"Detection too far away: {DISTANCE} meters, ignoring.")
                        clean_iter = 0

            except zmq.Again:
                clean_iter += 1
                if clean_iter > 10:
                    buffer.clear()  # Clear buffer if no new detection is received afer 3 seconds
                pass

            except Exception as e:
                print(f"Collision avoidance error: {e}")

        time.sleep(0.3)


def main(role, connection_string):
    dotenv.load_dotenv()
    mqtt_handler = None
    vessel_controller = None

    try:
        vessel_controller = VesselController(role.upper(), connection_string)

        mqtt_handler = MQTTHandler(role.upper())
        mqtt_handler.client.user_data_set({"vessel_controller": vessel_controller})

        camera_controller = CameraController(role.upper())

        image_queue = queue.Queue(maxsize=2)
        threads = []

        threads.append(
            threading.Thread(
                target=vessel_thread, args=(vessel_controller, mqtt_handler)
            )
        )
        threads.append(
            threading.Thread(
                target=camera_thread,
                args=(camera_controller, mqtt_handler, image_queue),
            )
        )

        threads.append(
            threading.Thread(
                target=collision_avoidance_thread, args=(vessel_controller,)
            )
        )

        for t in threads:
            t.start()

        # 3. THE NEW MAIN UI LOOP
        HEADLESS_MODE = is_headless()

        while not stop_event.is_set():
            try:
                # Wait up to 0.1 seconds for a new image to arrive
                b64_img = image_queue.get(timeout=0.01)
                if not HEADLESS_MODE:
                    # Decode the base64 string back into a raw image array
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

            except queue.Empty:
                # No new frame arrived yet, just loop again
                pass

        # 4. Cleanup after 'q' is pressed or Ctrl+C
        for t in threads:
            t.join(timeout=2.0)  # Gracefully wait for threads to close

    except KeyboardInterrupt:
        print("Exiting...")
    except Exception as e:
        logging.error(f"Startup error: {e}")
    finally:
        stop_event.set()
        if vessel_controller:
            vessel_controller.close_connection()
        if camera_controller:
            camera_controller.close()

        if mqtt_handler:
            mqtt_handler.disconnect()
        print("Shutdown complete.")


if __name__ == "__main__":
    os.environ["MAVLINK20"] = "1"
    os.environ["MAVLINK_DIALECT"] = "ardupilotmega"
    connection_string = None
    role = None
    if len(sys.argv) == 3:
        role = sys.argv[1]
        connection_string = sys.argv[2]
    elif len(sys.argv) == 2:
        role = sys.argv[1]
        connection_string = f"udp:127.0.0.1:{14560 + int(role[-1]) * 10}"
    else:
        print("Usage: python main.py <role>")
        sys.exit(1)

    main(role, connection_string)
