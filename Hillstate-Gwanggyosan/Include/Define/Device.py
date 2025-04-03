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
from Common import writeLog, DeviceType, Callback


class Device:
    __metaclass__ = ABCMeta

    name: str = 'Device'
    unique_id: str = 'device'
    dev_type: DeviceType = DeviceType.UNKNOWN
    index: int = 0  # device index (distinguish same dev type)
    room_index: int = 0  # room index (that this device is belongs to)
    init: bool = False
    state: int = 0  # mostly, 0 is OFF and 1 is ON
    state_prev: int = 0
    mqtt_client: mqtt.Client = None
    mqtt_publish_topic: str = ''
    mqtt_subscribe_topic: str = ''
    ha_discovery_prefix: str = 'homeassistant'

    last_published_time: float = time.perf_counter()

    thread_timer_onoff = None
    timer_onoff_params: dict

    rs485_port_index: int = -1

    def __init__(self, name: str = 'Device', index: int = 0, room_index: int = 0):
        self.index = index
        self.room_index = room_index
        if name is None:
            self.setDefaultName()
        else:
            self.name = name

        self.sig_set_state = Callback(int)
        self.timer_onoff_params = {
            'on_time': 10,  # unit: minute
            'off_time': 50,  # unit: minute
            'repeat': True,  # boolean
            'off_when_terminate': True  # device 켜진 상태에서 타이머 종료될 때 동작
        }
        writeLog(f'{str(self)} Created', self)

    def __repr__(self) -> str:
        # repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))}) '
        # repr_txt = f'<{self.__class__.__name__}, {self.name}, '
        repr_txt = f'<{self.name}, '
        repr_txt += f'Dev Idx: {self.index}, '
        repr_txt += f'Room Idx: {self.room_index}'
        repr_txt += '>'
        return repr_txt

    def release(self):
        self.stopThreadTimerOnOff()

    def setDefaultName(self):
        self.name = 'Device'

    def updateState(self, state: int, **kwargs):
        self.state = state
        if not self.init:
            self.publishMQTT()
            self.init = True
        if self.state != self.state_prev:
            self.publishMQTT()
        self.state_prev = self.state

    def getType(self) -> DeviceType:
        return self.dev_type

    def getIndex(self) -> int:
        return self.index

    def getRoomIndex(self) -> int:
        return self.room_index

    def setMqttClient(self, client: mqtt.Client):
        self.mqtt_client = client

    def setMqttPublishTopic(self, topic: str):
        self.mqtt_publish_topic = topic

    def setMqttSubscribeTopic(self, topic: str):
        self.mqtt_subscribe_topic = topic

    def setTimerOnOffOnTime(self, value: int):
        self.timer_onoff_params['on_time'] = value
    
    def setTimerOnOffOffTime(self, value: int):
        self.timer_onoff_params['off_time'] = value

    def setTimerOnOffRepeat(self, value: bool):
        self.timer_onoff_params['repeat'] = value

    def setHomeAssistantDiscoveryPrefix(self, prefix: str):
        self.ha_discovery_prefix = prefix

    @staticmethod
    def calcXORChecksum(data: Union[bytearray, bytes, List[int]]) -> int:
        return reduce(lambda x, y: x ^ y, data, 0)

    @abstractmethod
    def publishMQTT(self):
        pass

    @abstractmethod
    def configMQTT(self, retain: bool = False):
        pass

    @abstractmethod
    def makePacketQueryState(self) -> bytearray:
        # 디바이스 상태 조회 처리
        return bytearray()

    @abstractmethod
    def makePacketSetState(self, state: bool) -> bytearray:
        # 디바이스 전원 On/Off
        return bytearray()
    
    def startTimerOnOff(self):
        self.startThreadTimerOnOff()

    def stopTimerOnOff(self):
        self.stopThreadTimerOnOff()

    def startThreadTimerOnOff(self):
        if self.thread_timer_onoff is None:
            self.thread_timer_onoff = ThreadDeviceTimerOnOff(self)
            self.thread_timer_onoff.setDaemon(True)
            self.thread_timer_onoff.sig_set_state.connect(self.sig_set_state.emit)
            self.thread_timer_onoff.sig_terminated.connect(self.onThreadTimerOnOffTerminated)
            on_time = self.timer_onoff_params['on_time']
            off_time = self.timer_onoff_params['off_time']
            repeat = self.timer_onoff_params['repeat']
            self.thread_timer_onoff.setParams(on_time, off_time, repeat)
            self.thread_timer_onoff.start()

    def stopThreadTimerOnOff(self):
        if self.thread_timer_onoff is not None:
            self.thread_timer_onoff.stop()

    def onThreadTimerOnOffTerminated(self):
        del self.thread_timer_onoff
        self.thread_timer_onoff = None
        if self.timer_onoff_params['off_when_terminate']:
            self.sig_set_state.emit(0)
        else:
            self.publishMQTT()

    def isTimerOnOffRunning(self) -> bool:
        if self.thread_timer_onoff is not None:
            return self.thread_timer_onoff.is_alive()
        return False
    
    def setTimerOnOffParams(self, on_time: float, off_time: float, repeat: bool):
        self.timer_onoff_params['on_time'] = on_time
        self.timer_onoff_params['off_time'] = off_time
        self.timer_onoff_params['repeat'] = repeat
        writeLog(f'{self} Set On/Off Timer Params: {self.timer_onoff_params}')
        if self.thread_timer_onoff is not None:
            self.thread_timer_onoff.setParams(on_time, off_time, repeat)

    def setRS485PortIndex(self, index: int):
        self.rs485_port_index = index


class ThreadDeviceTimerOnOff(threading.Thread):
    _keepAlive: bool = True
    _dev: Device
    _on_time: float = 10.  # unit: minute
    _off_time: float = 50.  # unit: minute
    _repeat: bool = True

    def __init__(self, dev: Device):
        threading.Thread.__init__(self, name=f'Device({dev}) On/Off Timer Thread')
        self._dev = dev
        self._timer_interval = 1  # unit: second
        self.sig_terminated = Callback()
        self.sig_set_state = Callback(int)
    
    def run(self):
        writeLog(f'{self.name} Started', self)
        step = 0
        tm: float = 0.
        wait_for_transition: bool
        while self._keepAlive:
            if step == 0:
                wait_for_transition = True
                self.sig_set_state.emit(1)
                tm_wait_state = time.perf_counter()
                while wait_for_transition:
                    if self._dev.state == 1:
                        writeLog(f'{self._dev} state changed to {self._dev.state}', self)
                        wait_for_transition = False
                    if time.perf_counter() - tm_wait_state > 10:
                        writeLog('timeout! terminate timer on/off', self)
                        self._keepAlive = False
                        break
                    time.sleep(self._timer_interval)
                tm = time.perf_counter()
                step = 1
            elif step == 1:
                if time.perf_counter() - tm >= self._on_time * 60:
                    step = 2
            elif step == 2:
                wait_for_transition = True
                self.sig_set_state.emit(0)
                tm_wait_state = time.perf_counter()
                while wait_for_transition:
                    if self._dev.state == 0:
                        writeLog(f'{self._dev} state changed to {self._dev.state}', self)
                        wait_for_transition = False
                    if time.perf_counter() - tm_wait_state > 10:
                        writeLog('timeout! terminate timer on/off', self)
                        self._keepAlive = False
                        break
                    time.sleep(self._timer_interval)
                tm = time.perf_counter()
                step = 3
            elif step == 3:
                if time.perf_counter() - tm >= self._off_time * 60:
                    if self._repeat:
                        step = 0
                    else:
                        break
            time.sleep(self._timer_interval)
        writeLog(f'{self.name} Terminated', self)
        self.sig_terminated.emit()

    def stop(self):
        self._keepAlive = False

    def setParams(self, on_time: float, off_time: float, repeat: bool):
        self._on_time = on_time
        self._off_time = off_time
        self._repeat = repeat
