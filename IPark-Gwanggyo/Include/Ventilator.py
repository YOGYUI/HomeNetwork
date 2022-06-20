import json
from typing import List
from Device import Device


class Ventilator(Device):
    state_natural: int = 0
    rotation_speed: int = 0
    rotation_speed_prev: int = 0
    timer_remain: int = 0
    packet_set_rotation_speed: List[str]

    def __init__(self, name: str = 'Ventilator', **kwargs):
        super().__init__(name, **kwargs)
        self.packet_set_rotation_speed = [''] * 3

    def publish_mqtt(self):
        obj = {
            "state": self.state,
            "rotationspeed": int(self.rotation_speed / 3 * 100)
        }
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)

    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += '>'
        return repr_txt
