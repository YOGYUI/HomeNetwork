import os
import sys
import time
import threading
from typing import List, Union
import paho.mqtt.client as mqtt
from abc import ABCMeta, abstractmethod
from functools import reduce
CURPATH = os.path.dirname(os.path.abspath(__file__))
INCPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, INCPATH])
sys.path = list(set(sys.path))
del CURPATH, INCPATH
from Common import writeLog, Callback


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

    thread_timer = None

    def __init__(self, name: str = 'Device', **kwargs):
        self.name = name
        if 'room_index' in kwargs.keys():
            self.room_index = kwargs['room_index']
        self.mqtt_client = kwargs.get('mqtt_client')
        self.mqtt_subscribe_topics = list()

        self.sig_set_state = Callback(int)
        self.startThreadTimer()
        writeLog('Device Created >> {}'.format(str(self)), self)

    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += f' Room Idx: {self.room_index}'
        repr_txt += '>'
        return repr_txt

    def release(self):
        self.stopThreadTimer()

    def updateState(self, state: int, **kwargs):
        self.state = state
        if not self.init:
            self.publish_mqtt()
            self.init = True
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
    
    def initThreadTimer(self):
        pass

    def startThreadTimer(self):
        self.initThreadTimer()
        if self.thread_timer is not None:
            self.thread_timer.setDaemon(True)
            self.thread_timer.sig_set_state.connect(self.sig_set_state.emit)
            self.thread_timer.sig_terminated.connect(self.onThreadTimerTerminated)
            self.thread_timer.start()

    def stopThreadTimer(self):
        if self.thread_timer is not None:
            self.thread_timer.stop()

    def onThreadTimerTerminated(self):
        del self.thread_timer
        self.thread_timer = None

    def setTimer(self, flag: int):
        if self.thread_timer is not None:
            self.thread_timer.setFlagRunning(bool(flag))

    def isTimerRunning(self) -> bool:
        if self.thread_timer is not None:
            return self.thread_timer.is_alive() and self.thread_timer.getFlagRunning()
        return False


class ThreadDeviceTimer(threading.Thread):
    _keepAlive: bool = True
    _dev: Device
    _flag_running: bool = False

    def __init__(self, dev: Device, name: str = 'Device Timer Thread'):
        threading.Thread.__init__(self, name=name)
        self._dev = dev
        self._timer_interval = 1  # unit: second
        self.sig_terminated = Callback()
        self.sig_set_state = Callback(int)
    
    def run(self):
        while self._keepAlive:
            if self._flag_running:
                self.loop()
            time.sleep(self._timer_interval)
        self.sig_terminated.emit()

    def stop(self):
        self._keepAlive = False
    
    def setFlagRunning(self, flag: bool):
        self._flag_running = flag
        writeLog(f"<{self._dev}> Set Running: {self._flag_running}", self)
    
    def getFlagRunning(self) -> bool:
        return self._flag_running

    def setParams(self, **kwargs):
        pass

    @abstractmethod
    def loop(self):
        pass
