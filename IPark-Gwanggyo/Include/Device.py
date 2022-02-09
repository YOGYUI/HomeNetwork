import time
from typing import List
import paho.mqtt.client as mqtt
from abc import ABCMeta, abstractmethod
from Common import writeLog


class Device:
    __metaclass__ = ABCMeta

    name: str = 'Device'
    room_index: int = 0
    init: bool = False
    state: int = 0  # mostly, 0 is OFF and 1 is ON
    state_prev: int = 0
    packet_set_state_on: str = ''
    packet_set_state_off: str = ''
    packet_get_state: str = ''
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
        writeLog('Device Created >> Name: {}, Room Index: {}'.format(self.name, self.room_index), self)

    @abstractmethod
    def publish_mqtt(self):
        pass
