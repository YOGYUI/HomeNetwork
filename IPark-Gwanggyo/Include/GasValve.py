import json
from Device import *


class GasValve(Device):
    def __init__(self, name: str = 'GasValve', **kwargs):
        super().__init__(name, **kwargs)

    def publish_mqtt(self):
        # 0 = closed, 1 = opened, 2 = opening/closing
        obj = {"state": int(self.state == 1)}
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)

    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += '>'
        return repr_txt

    def make_packet_set_state(self, target: int, timestamp: int = 0) -> bytearray:
        if target:
            return bytearray([])  # not allowed open valve
        packet = bytearray([0x02, 0x31, 0x02, timestamp & 0xFF])
        packet.extend(bytearray([0x00] * 5))
        packet.append(calculate_bestin_checksum(packet))
        return packet

    def make_packet_query_state(self, timestamp: int = 0) -> bytearray:
        packet = bytearray([0x02, 0x31, 0x00, timestamp & 0xFF])
        packet.extend(bytearray([0x00] * 5))
        packet.append(calculate_bestin_checksum(packet))
        return packet
