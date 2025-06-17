import json
from Device import *


class Light(Device):
    def __init__(self, name: str = 'Light', index: int = 0, **kwargs):
        self.index = index
        super().__init__(name, **kwargs)

    def publish_mqtt(self):
        obj = {"state": self.state}
        self.mqtt_client.publish(self.mqtt_state_topic, json.dumps(obj), 1)

    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += f' Room Idx: {self.room_index}, Dev Idx: {self.index}'
        repr_txt += '>'
        return repr_txt

    def make_packet_set_state(self, target: int, timestamp: int = 0) -> bytearray:
        packet = self.make_packet_common(0x31, 13, 0x01, timestamp)
        packet[5] = self.room_index & 0x0F
        packet[6] = 0x01 << self.index
        if target:
            packet[6] += 0x80
            packet[11] = 0x04
        else:
            packet[11] = 0x00
        packet[12] = calculate_bestin_checksum(packet[:-1])
        return packet

    def make_packet_query_state(self, timestamp: int = 0) -> bytearray:
        packet = self.make_packet_common(0x31, 7, 0x11, timestamp)
        packet[5] = self.room_index & 0x0F
        packet[6] = calculate_bestin_checksum(packet[:-1])
        return packet
