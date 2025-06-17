import time
from typing import List
import paho.mqtt.client as mqtt
from abc import ABCMeta, abstractmethod
from Common import writeLog, calculate_bestin_checksum


class Device:
    __metaclass__ = ABCMeta

    name: str = 'Device'
    room_index: int = 0
    init: bool = False
    state: int = 0  # mostly, 0 is OFF and 1 is ON
    state_prev: int = 0
    """
    packet_set_state_on: str = ''
    packet_set_state_off: str = ''
    packet_get_state: str = ''
    """
    mqtt_client: mqtt.Client = None
    mqtt_state_topic: str = ''
    mqtt_subscribe_topics: List[str]

    last_published_time: float = time.perf_counter()
    publish_interval_sec: float = 10.

    def __init__(self, name: str = 'Device', **kwargs):
        self.name = name
        if 'room_index' in kwargs.keys():
            self.room_index = kwargs['room_index']
        self.mqtt_client = kwargs.get('mqtt_client')
        self.mqtt_subscribe_topics = list()
        # writeLog('Device Created >> Name: {}, Room Index: {}'.format(self.name, self.room_index), self)
        writeLog('Device Created >> {}'.format(str(self)), self)

    @abstractmethod
    def publish_mqtt(self):
        pass

    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += f' Room Idx: {self.room_index}'
        repr_txt += '>'
        return repr_txt

    def make_packet_common(self, header: int, length: int, packet_type: int, timestamp: int = 0) -> bytearray:
        packet = bytearray([
            0x02, 
            header & 0xFF, 
            length & 0xFF, 
            packet_type & 0xFF, 
            timestamp & 0xFF
        ])
        packet.extend(bytearray([0] * (length - 5)))
        return packet

    @abstractmethod
    def make_packet_set_state(self, target: int, timestamp: int = 0) -> bytearray:
        pass

    @abstractmethod
    def make_packet_query_state(self, timestamp: int = 0) -> bytearray:
        pass
