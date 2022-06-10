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


class ThreadCommand(threading.Thread):
    _keepAlive: bool = True

    def __init__(self, queue_: queue.Queue):
        threading.Thread.__init__(self, name='Command Thread')
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
                    func = elem['func']
                    if target is None:
                        continue

                    if isinstance(dev, Light) or isinstance(dev, Outlet):
                        if category == 'state':
                            self.set_light_state(dev, target, func)
                    elif isinstance(dev, Thermostat):
                        if category == 'state':
                            self.set_state_common(dev, target, func)
                        elif category == 'temperature':
                            self.set_thermostat_temperature(dev, target, func)
                    elif isinstance(dev, GasValve):
                        if category == 'state':
                            self.set_gas_state(dev, target, func)
                    elif isinstance(dev, Ventilator):
                        if category == 'state':
                            self.set_state_common(dev, target, func)
                        elif category == 'rotation_speed':
                            self.set_ventilator_rotation_speed(dev, target, func)
                    elif isinstance(dev, Elevator):
                        if category == 'state':
                            if target == 1:
                                func()
                            dev.publish_mqtt()
                except Exception as e:
                    writeLog(str(e), self)
            else:
                time.sleep(1e-3)
        writeLog('Terminated', self)
        self.sig_terminated.emit()

    def stop(self):
        self._keepAlive = False

    def set_state_common(self, dev: Device, target: int, func):
        cnt = 0
        packet1 = dev.packet_set_state_on if target else dev.packet_set_state_off
        packet2 = dev.packet_get_state
        for _ in range(self._retry_cnt):
            if dev.state == target:
                break
            func(packet1)
            cnt += 1
            time.sleep(0.2)
            if dev.state == target:
                break
            func(packet2)
            time.sleep(0.2)
        writeLog('set_state_common::send # = {}'.format(cnt), self)
        time.sleep(self._delay_response)
        dev.publish_mqtt()

    def set_light_state(self, dev: Union[Light, Outlet], target: int, func):
        cnt = 0
        packet1 = dev.packet_set_state_on if target else dev.packet_set_state_off
        packet2 = dev.packet_get_state
        for _ in range(self._retry_cnt):
            if dev.state == target:
                break
            func(packet1)
            cnt += 1
            time.sleep(0.2)
            if dev.state == target:
                break
            func(packet2)
            time.sleep(0.2)
        writeLog('set_light_state::send # = {}'.format(cnt), self)
        time.sleep(self._delay_response)
        dev.publish_mqtt()

    def set_gas_state(self, dev: GasValve, target: int, func):
        cnt = 0
        packet1 = dev.packet_set_state_on if target else dev.packet_set_state_off
        packet2 = dev.packet_get_state
        # only closing is permitted, 2 = Opening/Closing (Valve is moving...)
        if target == 0:
            for _ in range(self._retry_cnt):
                if dev.state in [target, 2]:
                    break
                func(packet1)
                cnt += 1
                time.sleep(0.5)
                if dev.state in [target, 2]:
                    break
                func(packet2)
                time.sleep(0.5)
            writeLog('set_gas_state::send # = {}'.format(cnt), self)
        time.sleep(self._delay_response)
        dev.publish_mqtt()

    def set_thermostat_temperature(self, dev: Thermostat, target: float, func):
        cnt = 0
        idx = max(0, min(70, int((target - 5.0) / 0.5)))
        packet1 = dev.packet_set_temperature[idx]
        packet2 = dev.packet_get_state
        for _ in range(self._retry_cnt):
            if dev.temperature_setting == target:
                break
            func(packet1)
            cnt += 1
            time.sleep(0.2)
            if dev.temperature_setting == target:
                break
            func(packet2)
            time.sleep(0.2)
        writeLog('set_thermostat_temperature::send # = {}'.format(cnt), self)
        time.sleep(self._delay_response)
        dev.publish_mqtt()

    def set_ventilator_rotation_speed(self, dev: Ventilator, target: int, func):
        cnt = 0
        packet1 = dev.packet_set_rotation_speed[target - 1]
        packet2 = dev.packet_get_state
        for _ in range(self._retry_cnt):
            if dev.rotation_speed == target:
                break
            func(packet1)
            cnt += 1
            time.sleep(0.2)
            if dev.rotation_speed == target:
                break
            func(packet2)
            time.sleep(0.2)
        writeLog('set_ventilator_rotation_speed::send # = {}'.format(cnt), self)
        dev.publish_mqtt()
