import os
import sys
import time
import queue
import threading
from typing import Union
from Device import Device
from Common import Callback, writeLog
from Light import Light
from Outlet import Outlet
from Thermostat import Thermostat
from Ventilator import Ventilator
from GasValve import GasValve
from Elevator import Elevator
CURPATH = os.path.dirname(os.path.abspath(__file__))  # Project/Include
PROJPATH = os.path.dirname(CURPATH)  # Proejct/
RS485PATH = os.path.join(PROJPATH, 'RS485')  # Project/RS485
sys.path.extend([CURPATH, PROJPATH, RS485PATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH, RS485PATH
from RS485 import PacketParser, RS485HwType


class ThreadCommand(threading.Thread):
    _keepAlive: bool = True

    def __init__(self, queue_: queue.Queue):
        threading.Thread.__init__(self, name='Command Thread')
        self._queue = queue_
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

                    if isinstance(dev, Light) or isinstance(dev, Outlet):
                        if category == 'state':
                            self.set_light_outlet_state(dev, target, parser)
                    elif isinstance(dev, Thermostat):
                        if category == 'state':
                            self.set_state_common(dev, target, parser)
                        elif category == 'temperature':
                            self.set_thermostat_temperature(dev, target, parser)
                    elif isinstance(dev, GasValve):
                        if category == 'state':
                            self.set_gas_state(dev, target, parser)
                    elif isinstance(dev, Ventilator):
                        if category == 'state':
                            self.set_state_common(dev, target, parser)
                        elif category == 'rotation_speed':
                            self.set_ventilator_rotation_speed(dev, target, parser)
                    elif isinstance(dev, Elevator):
                        if category == 'state':
                            if target == 1:
                                if elem['direction'] == 'up':
                                    parser.setFlagCallUp()
                                else:
                                    parser.setFlagCallDown()
                            dev.publish_mqtt()
                except Exception as e:
                    writeLog(str(e), self)
            else:
                time.sleep(1e-3)
        writeLog('Terminated', self)
        self.sig_terminated.emit()

    def stop(self):
        self._keepAlive = False

    @staticmethod
    def getSendParams(parser: PacketParser) -> tuple:
        interval = 0.2
        retry_cnt = 10
        if parser.getRS485HwType() == RS485HwType.Socket:
            # ew11은 무선 송수신 레이턴시때문에 RS485 IDLE 시간을 명확하게 알 수 없으므로
            # 짧은 간격으로 패킷을 많이 쏴보도록 한다
            interval = 0.1
            retry_cnt = 50
        return interval, retry_cnt

    def set_state_common(self, dev: Device, target: int, parser: PacketParser):
        cnt = 0
        """
        packet1 = dev.packet_set_state_on if target else dev.packet_set_state_off
        packet2 = dev.packet_get_state
        """
        interval, retry_cnt = self.getSendParams(parser)
        while cnt < retry_cnt:
            if parser.isRS485LineBusy():
                time.sleep(1e-3)  # prevent cpu occupation
                continue
            if dev.state == target:
                break
            packet = dev.make_packet_set_state(target, parser.get_packet_timestamp() + 1)
            # parser.sendPacketString(packet)
            parser.sendPacket(packet)
            cnt += 1
            time.sleep(interval)
            if dev.state == target:
                break
            packet = dev.make_packet_query_state(parser.get_packet_timestamp() + 1)
            # parser.sendPacketString(packet)
            parser.sendPacket(packet)
            time.sleep(interval)
        if cnt > 0:
            writeLog('set_state_common::send # = {}'.format(cnt), self)
            time.sleep(self._delay_response)
        dev.publish_mqtt()

    def set_light_outlet_state(self, dev: Union[Light, Outlet], target: int, parser: PacketParser):
        cnt = 0
        """
        packet1 = dev.packet_set_state_on if target else dev.packet_set_state_off
        packet2 = dev.packet_get_state
        """
        interval, retry_cnt = self.getSendParams(parser)
        while cnt < retry_cnt:
            if parser.isRS485LineBusy():
                time.sleep(1e-3)  # prevent cpu occupation
                continue
            if dev.state == target:
                break
            packet = dev.make_packet_set_state(target, parser.get_packet_timestamp() + 1)
            # parser.sendPacketString(packet)
            parser.sendPacket(packet)
            cnt += 1
            time.sleep(interval)
            if dev.state == target:
                break
            packet = dev.make_packet_query_state(parser.get_packet_timestamp() + 1)
            # parser.sendPacketString(packet)
            parser.sendPacket(packet)
            time.sleep(interval)
        if cnt > 0:
            writeLog('set_light_outlet_state::send # = {}'.format(cnt), self)
            time.sleep(self._delay_response)
        dev.publish_mqtt()

    def set_gas_state(self, dev: GasValve, target: int, parser: PacketParser):
        cnt = 0
        """
        packet1 = dev.packet_set_state_on if target else dev.packet_set_state_off
        packet2 = dev.packet_get_state
        """
        interval, retry_cnt = self.getSendParams(parser)
        # only closing is permitted, 2 = Opening/Closing (Valve is moving...)
        if target == 0:
            while cnt < retry_cnt:
                if parser.isRS485LineBusy():
                    time.sleep(1e-3)  # prevent cpu occupation
                    continue
                if dev.state in [target, 2]:
                    break
                packet = dev.make_packet_set_state(parser.get_packet_timestamp() + 1)
                # parser.sendPacketString(packet)
                parser.sendPacket(packet)
                cnt += 1
                time.sleep(interval)
                if dev.state in [target, 2]:
                    break
                packet = dev.make_packet_query_state(parser.get_packet_timestamp() + 1)
                # parser.sendPacketString(packet)
                parser.sendPacket(packet)
                time.sleep(interval)
            if cnt > 0:
                writeLog('set_gas_state::send # = {}'.format(cnt), self)
                time.sleep(self._delay_response)
        dev.publish_mqtt()

    def set_thermostat_temperature(self, dev: Thermostat, target: float, parser: PacketParser):
        cnt = 0
        """
        idx = max(0, min(70, int((target - 5.0) / 0.5)))
        packet1 = dev.packet_set_temperature[idx]
        packet2 = dev.packet_get_state
        """
        interval, retry_cnt = self.getSendParams(parser)
        while cnt < retry_cnt:
            if parser.isRS485LineBusy():
                time.sleep(1e-3)  # prevent cpu occupation
                continue
            if dev.temperature_setting == target:
                break
            packet = dev.make_packet_set_temperature(target, parser.get_packet_timestamp() + 1)
            # parser.sendPacketString(packet)
            parser.sendPacket(packet)
            cnt += 1
            time.sleep(interval)
            if dev.temperature_setting == target:
                break
            packet = dev.make_packet_query_state(parser.get_packet_timestamp() + 1)
            # parser.sendPacketString(packet)
            parser.sendPacket(packet)
            time.sleep(interval)
        if cnt > 0:
            writeLog('set_thermostat_temperature::send # = {}'.format(cnt), self)
            time.sleep(self._delay_response)
        dev.publish_mqtt()

    def set_ventilator_rotation_speed(self, dev: Ventilator, target: int, parser: PacketParser):
        cnt = 0
        """
        packet1 = dev.packet_set_rotation_speed[target - 1]
        packet2 = dev.packet_get_state
        """
        interval, retry_cnt = self.getSendParams(parser)
        while cnt < retry_cnt:
            if parser.isRS485LineBusy():
                time.sleep(1e-3)  # prevent cpu occupation
                continue
            if dev.rotation_speed == target:
                break
            # parser.sendPacketString(packet1)
            packet = dev.make_packet_set_rotation_speed(target, parser.get_packet_timestamp() + 1)
            parser.sendPacket(packet)
            cnt += 1
            time.sleep(interval)
            if dev.rotation_speed == target:
                break
            # parser.sendPacketString(packet2)
            packet = dev.make_packet_query_state(parser.get_packet_timestamp() + 1)
            parser.sendPacket(packet)
            time.sleep(interval)
        if cnt > 0:
            writeLog('set_ventilator_rotation_speed::send # = {}'.format(cnt), self)
            dev.publish_mqtt()
