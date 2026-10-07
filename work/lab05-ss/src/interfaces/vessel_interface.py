from abc import ABC, abstractmethod


class IVesselController(ABC):
    @abstractmethod
    def get_status(self) -> dict:
        pass

    @abstractmethod
    def get_telemetry(self) -> str:
        pass

    # --- Hardware Controls ---
    @abstractmethod
    def stop_vehicle(self):
        pass

    @abstractmethod
    def start_auto_mission(self):
        pass

    @abstractmethod
    def return_to_home(self):
        pass

    @abstractmethod
    def set_manual_mode(self):
        pass

    @abstractmethod
    def set_speed(self, speed):
        pass

    @abstractmethod
    def get_speed(self) -> float:
        pass

    @abstractmethod
    def close_connection(self):
        pass

    @abstractmethod
    def handle_other_traffic(self, traffic_data):
        pass

    @abstractmethod
    def monitor_mission_progress(self):
        pass
