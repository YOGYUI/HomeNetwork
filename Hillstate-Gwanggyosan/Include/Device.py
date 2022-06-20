import time
from typing import List, Union
import paho.mqtt.client as mqtt
from abc import ABCMeta, abstractmethod
from functools import reduce
from Common import writeLog


class Device:
    __metaclass__ = ABCMeta

    name: str = 'Device'
    room_index: int = 0  # room index that this device is belongs to
    init: bool = False
    state: int = 0  # mostly, 0 is OFF and 1 is ON
    state_prev: int = 0
    mqtt_client: mqtt.Client = None
    mqtt_publish_topic: str = ''
    mqtt_subscribe_topics: List[str]

    last_published_time: float = time.perf_counter()
    publish_interval_sec: float = 10.

    def __init__(self, name: str = 'Device', **kwargs):
        self.name = name
        if 'room_index' in kwargs.keys():
            self.room_index = kwargs['room_index']
        self.mqtt_client = kwargs.get('mqtt_client')
        self.mqtt_subscribe_topics = list()
        writeLog('Device Created >> {}'.format(str(self)), self)

    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += f' Room Idx: {self.room_index}'
        repr_txt += '>'
        return repr_txt

    def setState(self, state: int):
        self.state = state
        if not self.init:
            self.publish_mqtt()
            self.init = False
        if self.state != self.state_prev:
            self.publish_mqtt()
        self.state_prev = self.state

    @staticmethod
    def calcXORChecksum(data: Union[bytearray, bytes, List[int]]) -> int:
        return reduce(lambda x, y: x ^ y, data, 0)

    @abstractmethod
    def publish_mqtt(self):
        pass

    @abstractmethod
    def makePacketQueryState(self) -> bytearray:
        # 디바이스 상태 조회 처리
        return bytearray()

    @abstractmethod
    def makePacketSetState(self, state: bool) -> bytearray:
        # 디바이스 전원 On/Off
        return bytearray()

    
