import os
import sys
import time
import math
import queue
import threading
CURPATH = os.path.dirname(os.path.abspath(__file__))
INCPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, INCPATH])
sys.path = list(set(sys.path))
del CURPATH, INCPATH
from Define import *
from Common import Callback, writeLog
from RS485 import SerialParser


class ThreadCommandQueue(threading.Thread):
    _keepAlive: bool = True

    def __init__(self, queue_: queue.Queue):
        threading.Thread.__init__(self, name='Command Queue Thread')
        self._queue = queue_
        self._retry_cnt = 10
        self._delay_response = 0.4
        self.sig_terminated = Callback()

    def run(self):
        writeLog('Started', self)
        while self._keepAlive:
            if not self._queue.empty():
                elem = self._queue.get()
                elem_txt = '\n'
                for k, v in elem.items():
                    elem_txt += f'  {k}: {v}\n'
                writeLog(f'Get Command Queue: \n{{{elem_txt}}}', self)
                try:
                    dev = elem['device']
                    category = elem['category']
                    target = elem['target']
                    parser = elem['parser']
                    if target is None:
                        continue

                    if isinstance(dev, Light):
                        if category == 'state':
                            self.set_state_common(dev, target, parser)
                    elif isinstance(dev, Outlet):
                        if category == 'state':
                            self.set_state_common(dev, target, parser)
                    elif isinstance(dev, GasValve):
                        if category == 'state':
                            if target == 0:  
                                self.set_state_common(dev, target, parser)
                            else:  # 밸브 여는것은 지원되지 않음!
                                packet_query = dev.makePacketQueryState()
                                parser.sendPacket(packet_query)
                    elif isinstance(dev, Thermostat):
                        if category == 'state':
                            if target == 'OFF':
                                self.set_state_common(dev, 0, parser)
                            elif target == 'HEAT':
                                self.set_state_common(dev, 1, parser)
                        elif category == 'temperature':
                            self.set_temperature(dev, target, parser)
                    elif isinstance(dev, Ventilator):
                        if category == 'state':
                            self.set_state_common(dev, target, parser)
                        elif category == 'rotationspeed':
                            self.set_rotation_speed(dev, target, parser)
                except Exception as e:
                    writeLog(str(e), self)
            else:
                time.sleep(1e-3)
        writeLog('Terminated', self)
        self.sig_terminated.emit()

    def stop(self):
        self._keepAlive = False

    def set_state_common(self, dev: Device, target: int, parser: SerialParser):
        cnt = 0
        packet_command = dev.makePacketSetState(bool(target))
        packet_query = dev.makePacketQueryState()
        for _ in range(self._retry_cnt):
            if dev.state == target:
                break
            parser.sendPacket(packet_command)
            cnt += 1
            time.sleep(0.2)
            if dev.state == target:
                break
            parser.sendPacket(packet_query)
            time.sleep(0.2)
        if cnt > 0:
            writeLog('set_state_common::send # = {}'.format(cnt), self)
            time.sleep(self._delay_response)
        dev.publish_mqtt()

    def set_temperature(self, dev: Thermostat, target: float, parser: SerialParser):
        # 힐스테이트는 온도값 범위가 정수형이므로 올림처리해준다
        target_temp = math.ceil(target)
        cnt = 0
        packet_command = dev.makePacketSetTemperature(target_temp)
        packet_query = dev.makePacketQueryState()
        for _ in range(self._retry_cnt):
            if dev.temp_config == target_temp:
                break
            parser.sendPacket(packet_command)
            cnt += 1
            time.sleep(0.2)
            if dev.temp_config == target_temp:
                break
            parser.sendPacket(packet_query)
            time.sleep(0.2)
        if cnt > 0:
            writeLog('set_temperature::send # = {}'.format(cnt), self)
            time.sleep(self._delay_response)
        dev.publish_mqtt()

    def set_rotation_speed(self, dev: Ventilator, target: int, parser: SerialParser):
        # Speed 값 변환 (100단계의 풍량을 세단계로 나누어 1, 3, 7 중 하나로)
        if target <= 30:
            conv = 0x01
        elif target <= 60:
            conv = 0x03
        else:
            conv = 0x07
        cnt = 0
        packet_command = dev.makePacketSetRotationSpeed(conv)
        packet_query = dev.makePacketQueryState()
        for _ in range(self._retry_cnt):
            if dev.rotation_speed == conv:
                break
            parser.sendPacket(packet_command)
            cnt += 1
            time.sleep(0.2)
            if dev.rotation_speed == conv:
                break
            parser.sendPacket(packet_query)
            time.sleep(0.2)
        if cnt > 0:
            writeLog('set_rotation_speed::send # = {}'.format(cnt), self)
            time.sleep(self._delay_response)
        dev.publish_mqtt()
