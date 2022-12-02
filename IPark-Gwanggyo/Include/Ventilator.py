import json
from typing import List
from Device import *


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

    def make_packet_set_state(self, target: int, timestamp: int = 0) -> bytearray:
        packet = bytearray([0x02, 0x61, 0x01, timestamp & 0xFF, 0x00])
        if target:
            packet.append(0x01)
        else:
            packet.append(0x00)
        packet.extend([0x01, 0x00, 0x00])
        packet.append(calculate_bestin_checksum(packet))
        return packet

    def make_packet_query_state(self, timestamp: int = 0) -> bytearray:
        packet = bytearray([0x02, 0x61, 0x00, timestamp & 0xFF, 0x00])
        packet.extend([0x00, 0x00, 0x00, 0x00])
        packet.append(calculate_bestin_checksum(packet))
        return packet
    
    def make_packet_set_rotation_speed(self, target: int, timestamp: int = 0) -> bytearray:
        target = max(1, min(3, target))
        packet = bytearray([0x02, 0x61, 0x03, timestamp & 0xFF, 0x00, 0x00, target, 0x00, 0x00])
        packet.append(calculate_bestin_checksum(packet))
        return packet
