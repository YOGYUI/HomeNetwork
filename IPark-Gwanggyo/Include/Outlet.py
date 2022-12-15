import json
from Device import *


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
        repr_txt += f' Room Idx: {self.room_index}, Dev Idx: {self.index}'
        repr_txt += '>'
        return repr_txt
    
    def make_packet_set_state(self, target: int, timestamp: int = 0) -> bytearray:
        packet = self.make_packet_common(0x31, 13, 0x01, timestamp)
        packet[5] = self.room_index & 0x0F
        packet[7] = 0x01 << self.index
        if target:
            packet[7] += 0x80
            packet[11] = 0x09 << self.index  # 확실하지 않음...
        else:
            packet[11] = 0x00
        packet[12] = calculate_bestin_checksum(packet[:-1])
        return packet

    def make_packet_query_state(self, timestamp: int = 0) -> bytearray:
        # 확실하지 않음, 조명 쿼리 패킷과 동일한 것으로 판단됨 (어차피 응답 패킷에 조명/아울렛 정보가 같이 담겨있음)
        packet = self.make_packet_common(0x31, 7, 0x11, timestamp)
        packet[5] = self.room_index & 0x0F
        packet[6] = calculate_bestin_checksum(packet[:-1])
        return packet
