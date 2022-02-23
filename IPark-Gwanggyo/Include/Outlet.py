import json
from Device import Device


class Outlet(Device):
    measurement: float = 0.
    measurement_prev: float = 0.

    def __init__(self, name: str = 'Outlet', index: int = 0, **kwargs):
        self.index = index
        super().__init__(name, **kwargs)

    def publish_mqtt(self):
        """
        curts = time.perf_counter()
        if curts  - self.last_published_time > self.publish_interval_sec:
            obj = {
                "watts": self.measurement
            }
            self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)
            self.last_published_time = curts
        """
        obj = {
            "state": self.state,
            "watts": self.measurement
        }
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)

    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += f' Room Idx: {self.room_index}, Dev Indx: {self.index}'
        repr_txt += '>'
        return repr_txt
