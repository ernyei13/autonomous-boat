from abc import ABC, abstractmethod


class ISensorDetector(ABC):
    @abstractmethod
    def detect(self, sensor_lon, sensor_lat, sensor_heading, props={}) -> dict:
        pass

    @abstractmethod
    def close(self):
        pass
