import json
from typing import List
from Device import *


class Thermostat(Device):
    temperature_current: float = 0.
    temperature_current_prev: float = 0.
    temperature_setting: float = 0.
    temperature_setting_prev: float = 0.
    packet_set_temperature: List[str]

    def __init__(self, name: str = 'Thermostat', **kwargs):
        super().__init__(name, **kwargs)
        self.packet_set_temperature = [''] * 71  # 5.0 ~ 40.0, step=0.5

    def publish_mqtt(self):
        obj = {
            "state": 'HEAT' if self.state == 1 else 'OFF',
            "currentTemperature": self.temperature_current,
            "targetTemperature": self.temperature_setting
        }
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)

    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += f' Room Idx: {self.room_index}'
        repr_txt += '>'
        return repr_txt

    def make_packet_set_state(self, target: int, timestamp: int = 0) -> bytearray:
        packet = self.make_packet_common(0x28, 14, 0x12, timestamp)
        packet[5] = self.room_index & 0x0F
        if target:
            packet[6] = 0x01
        else:
            packet[6] = 0x02
        packet[13] = calculate_bestin_checksum(packet[:-1])
        return packet

    def make_packet_query_state(self, timestamp: int = 0) -> bytearray:
        packet = self.make_packet_common(0x28, 7, 0x11, timestamp)
        packet[5] = self.room_index & 0x0F
        packet[6] = calculate_bestin_checksum(packet[:-1])
        return packet
    
    def make_packet_set_temperature(self, target: float, timestamp: int = 0) -> bytearray:
        packet = self.make_packet_common(0x28, 14, 0x12, timestamp)
        packet[5] = self.room_index & 0x0F
        value_int = int(target)
        value_float = target - value_int
        packet[7] = value_int & 0xFF
        if value_float != 0:
            packet[7] += 0x40
        packet[13] = calculate_bestin_checksum(packet[:-1])
        return packet
