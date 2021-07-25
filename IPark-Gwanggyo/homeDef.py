import os
import time
import json
import queue
import ctypes
import requests
import threading
from abc import ABCMeta, abstractmethod
from typing import List, Union
import paho.mqtt.client as mqtt
import xml.etree.ElementTree as ET
from common import Callback, writeLog
from Serial485.SerialComm import SerialComm
from Serial485.EnergyParser import EnergyParser
from Serial485.ControlParser import ControlParser
from Serial485.SmartParser import SmartParser


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

    def __init__(self, name: str = 'Device', **kwargs):
        self.name = name
        if 'room_index' in kwargs.keys():
            self.room_index = kwargs['room_index']
        self.mqtt_client = kwargs.get('mqtt_client')
        self.mqtt_subscribe_topics = list()
        writeLog('Device Initialized >> Name: {}, Room Index: {}'.format(self.name, self.room_index), self)
    
    @abstractmethod
    def publish_mqtt(self):
        pass


class Light(Device):
    def __init__(self, name: str = 'Device', index: int = 0, **kwargs):
        self.index = index
        super().__init__(name, **kwargs)

    def publish_mqtt(self):
        obj = {"state": self.state}
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)


class GasValve(Device):
    def publish_mqtt(self):
        # 0 = closed, 1 = opened, 2 = opening/closing
        obj = {"state": int(self.state == 1)}
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)


class Thermostat(Device):
    temperature_current: float = 0.
    temperature_current_prev: float = 0.
    temperature_setting: float = 0.
    temperature_setting_prev: float = 0.
    packet_set_temperature: List[str]

    def __init__(self, name: str = 'Device', **kwargs):
        super().__init__(name, **kwargs)
        self.packet_set_temperature = [''] * 71  # 5.0 ~ 40.0, step=0.5
        
    def publish_mqtt(self):
        obj = {
            "state": 'HEAT' if self.state == 1 else 'OFF',
            "currentTemperature": self.temperature_current,
            "targetTemperature": self.temperature_setting
            }
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)


class Ventilator(Device):
    state_natural: int = 0
    rotation_speed: int = 0
    rotation_speed_prev: int = 0
    timer_remain: int = 0
    packet_set_rotation_speed: List[str]

    def __init__(self, name: str = 'Ventilator', **kwargs):
        super().__init__(name, **kwargs)
        self.packet_set_rotation_speed = [''] * 3

    def publish_mqtt(self):
        obj = {
            "state": self.state,
            "rotationspeed": int(self.rotation_speed / 3 * 100)
            }
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)


class Elevator(Device):
    my_floor: int = -1
    current_floor: int = -1
    current_floor_prev: int = -1
    
    def __init__(self, name: str = 'Elevator', **kwargs):
        super().__init__(name, **kwargs)
        self.sig_call_up = Callback()
        self.sig_call_down = Callback()

    def call_up(self):
        self.sig_call_up.emit()

    def call_down(self):
        self.sig_call_down.emit()

    def publish_mqtt(self):
        obj = {
            "state": int(self.state == 4 and self.current_floor == self.my_floor)
        }
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)
        self.mqtt_client.publish("home/ipark/elevator/state/occupancy", json.dumps(obj), 1)


class Room:
    name: str = 'Room'
    # 각 방에는 조명 모듈 여러개와 난방 모듈 1개 존재
    index: int = 0
    lights: List[Light]
    thermostat: Thermostat = None

    def __init__(self, name: str = 'Room', index: int = 0, light_count: int = 0, has_thermostat: bool = True, **kwargs):
        self.name = name
        self.index = index
        self.lights = list()
        for i in range(light_count):
            self.lights.append(Light(
                name='Light {}'.format(i + 1),
                index=i,
                room_index=self.index,
                mqtt_client=kwargs.get('mqtt_client')
            ))
        if has_thermostat:
            self.thermostat = Thermostat(
                name='Thermostat',
                room_index=self.index,
                mqtt_client=kwargs.get('mqtt_client')
            )

    @property
    def light_count(self):
        return len(self.lights)


class ThreadMonitoring(threading.Thread):
    _keepAlive: bool = True

    def __init__(
            self, 
            serial_list: List[SerialComm], 
            device_list: List[Device], 
            publish_interval: int = 60, 
            interval_ms: int = 2000
    ):
        threading.Thread.__init__(self)
        self._serial_list = serial_list
        self._device_list = device_list
        self._publish_interval = publish_interval
        self._interval_ms = interval_ms
        self.sig_terminated = Callback()
    
    def run(self):
        writeLog('Started', self)
        tm = time.perf_counter()
        while self._keepAlive:
            for ser in self._serial_list:
                if ser.isConnected():
                    delta = ser.time_after_last_recv()
                    if delta > 10:
                        msg = 'Warning!! Serial <{}> is not receiving for {:.1f} seconds'.format(ser.name, delta)
                        writeLog(msg, self)
                else:
                    # writeLog('Warning!! Serial <{}> is not connected'.format(ser.name), self)
                    pass
            if time.perf_counter() - tm > self._publish_interval:
                writeLog('Regular Publishing Device State MQTT (interval: {} sec)'.format(self._publish_interval), self)
                for dev in self._device_list:
                    dev.publish_mqtt()
                tm = time.perf_counter()
            time.sleep(self._interval_ms / 1000)
        writeLog('Terminated', self)
        self.sig_terminated.emit()

    def stop(self):
        self._keepAlive = False


class ThreadCommand(threading.Thread):
    _keepAlive: bool = True

    def __init__(self, queue_: queue.Queue):
        threading.Thread.__init__(self)
        self._queue = queue_
        self._retry_cnt = 10
        self._delay_response = 0.4
        self.sig_send_energy = Callback(str)
        self.sig_send_control = Callback(str)
        self.sig_send_smart = Callback(str)
        self.sig_terminated = Callback()

    def run(self):
        writeLog('Started', self)
        while self._keepAlive:
            if not self._queue.empty():
                elem = self._queue.get()
                writeLog('Get Command Queue: {}'.format(elem), self)
                try:
                    dev = elem['device']
                    category = elem['category']
                    target = elem['target']
                    func = elem['func']
                    if target is None:
                        continue

                    if isinstance(dev, Light):
                        if category == 'state':
                            room_idx = elem['room_idx']
                            dev_idx = elem['dev_idx']
                            self.set_light_state(dev, target, room_idx, dev_idx, func)
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

    def set_light_state(self, dev: Light, target: int, room_idx: int, dev_idx: int, func):
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


class Home:
    name: str = 'Home'
    device_list: List[Device]

    rooms: List[Room]
    gas_valve: GasValve
    ventilator: Ventilator
    elevator: Elevator

    serial_baud: int = 9600
    serial_485_energy_port: str = ''
    serial_485_control_port: str = ''
    serial_485_smart_port1: str = ''
    serial_485_smart_port2: str = ''

    thread_command: Union[ThreadCommand, None] = None
    thread_monitoring: Union[ThreadMonitoring, None] = None
    queue_command: queue.Queue

    mqtt_client: mqtt.Client
    # mqtt_host: str = 'localhost'
    mqtt_host: str = '127.0.0.1'
    mqtt_port: int = 1883
    mqtt_is_connected: bool = False

    def __init__(self, room_info: List, name: str = 'Home'):
        self.name = name
        self.device_list = list()

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.onMqttClientConnect
        self.mqtt_client.on_disconnect = self.onMqttClientDisconnect
        self.mqtt_client.on_subscribe = self.onMqttClientSubscribe
        self.mqtt_client.on_unsubscribe = self.onMqttClientUnsubscribe
        self.mqtt_client.on_publish = self.onMqttClientPublish
        self.mqtt_client.on_message = self.onMqttClientMessage
        self.mqtt_client.on_log = self.onMqttClientLog
        
        self.rooms = list()
        for i, info in enumerate(room_info):
            name = info['name']
            light_count = info['light_count']
            has_thermostat = info['has_thermostat']
            self.rooms.append(Room(
                name=name,
                index=i,
                light_count=light_count,
                has_thermostat=has_thermostat,
                mqtt_client=self.mqtt_client)
            )
        self.gas_valve = GasValve(name='Gas Valve', mqtt_client=self.mqtt_client)
        self.ventilator = Ventilator(name='Ventilator', mqtt_client=self.mqtt_client)
        self.elevator = Elevator(name='Elevator', mqtt_client=self.mqtt_client)
        self.elevator.sig_call_up.connect(self.onElevatorCallUp)
        self.elevator.sig_call_down.connect(self.onElevatorCallDown)

        # device list
        for room in self.rooms:
            self.device_list.extend(room.lights)
            if room.thermostat is not None:
                self.device_list.append(room.thermostat)
        self.device_list.append(self.gas_valve)
        self.device_list.append(self.ventilator)
        self.device_list.append(self.elevator)

        curpath = os.path.dirname(os.path.abspath(__file__))
        xml_path = os.path.join(curpath, 'config.xml')
        self.load_config(xml_path)

        try:
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port)
        except Exception as e:
            print('MQTT Connection Error: {}'.format(e))
        self.mqtt_client.loop_start()

        self.queue_command = queue.Queue()
        self.startThreadCommand()

        self.serial_485_energy = SerialComm('Energy')
        self.parser_energy = EnergyParser(self.serial_485_energy)
        self.parser_energy.sig_parse.connect(self.onParserEnergyResult)
        self.serial_485_control = SerialComm('Control')
        self.parser_control = ControlParser(self.serial_485_control)
        self.parser_control.sig_parse.connect(self.onParserControlResult)
        self.serial_485_smart1 = SerialComm('Smart1')
        self.serial_485_smart2 = SerialComm('Smart2')
        self.parser_smart = SmartParser(self.serial_485_smart1, self.serial_485_smart2)
        self.parser_smart.sig_parse1.connect(self.onParserSmartResult1)
        self.parser_smart.sig_parse2.connect(self.onParserSmartResult2)

        self.startThreadMonitoring()

    def release(self):
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.stopThreadCommand()
        self.stopThreadMonitoring()
        self.serial_485_energy.release()
        self.serial_485_control.release()
        self.serial_485_smart1.release()
        self.serial_485_smart2.release()

    def initDevices(self):
        self.serial_485_energy.connect(self.serial_485_energy_port, self.serial_baud)
        self.serial_485_control.connect(self.serial_485_control_port, self.serial_baud)
        self.serial_485_smart1.connect(self.serial_485_smart_port1, self.serial_baud)
        self.serial_485_smart2.connect(self.serial_485_smart_port2, self.serial_baud)

    def load_config(self, filepath: str):
        root = ET.parse(filepath).getroot()

        node = root.find('serial')
        self.serial_485_energy_port = node.find('port_energy').text
        self.serial_485_control_port = node.find('port_control').text
        self.serial_485_smart_port1 = node.find('port_smart1').text
        self.serial_485_smart_port2 = node.find('port_smart2').text

        node = root.find('mqtt')
        username = node.find('username').text
        password = node.find('password').text
        self.mqtt_host = node.find('host').text
        self.mqtt_port = int(node.find('port').text)
        self.mqtt_client.username_pw_set(username, password)

        node = root.find('thermo_temp_packet')
        thermo_setting_packets = node.text.split('\n')
        thermo_setting_packets = [x.replace('\t', '').strip() for x in thermo_setting_packets]
        thermo_setting_packets = list(filter(lambda x: len(x) > 0, thermo_setting_packets))

        node = root.find('rooms')
        for i, room in enumerate(self.rooms):
            room_node = node.find('room{}'.format(i))
            if room_node is None:
                continue
            for j in range(room.light_count):
                light_node = room_node.find('light{}'.format(j))
                if light_node is None:
                    continue
                room.lights[j].packet_set_state_on = light_node.find('on').text
                room.lights[j].packet_set_state_off = light_node.find('off').text
                room.lights[j].packet_get_state = light_node.find('get').text
                mqtt_node = light_node.find('mqtt')
                room.lights[j].mqtt_publish_topic = mqtt_node.find('publish').text
                room.lights[j].mqtt_subscribe_topics.append(mqtt_node.find('subscribe').text)
            thermo_node = room_node.find('thermostat')
            if thermo_node is None:
                continue
            room.thermostat.packet_set_state_on = thermo_node.find('on').text
            room.thermostat.packet_set_state_off = thermo_node.find('off').text
            room.thermostat.packet_get_state = thermo_node.find('get').text
            mqtt_node = thermo_node.find('mqtt')
            room.thermostat.mqtt_publish_topic = mqtt_node.find('publish').text
            room.thermostat.mqtt_subscribe_topics.append(mqtt_node.find('subscribe').text)
            for j in range(71):
                room.thermostat.packet_set_temperature[j] = thermo_setting_packets[j + 71 * (i - 1)]

        node = root.find('gasvalve')
        self.gas_valve.packet_set_state_off = node.find('off').text
        self.gas_valve.packet_get_state = node.find('get').text
        mqtt_node = node.find('mqtt')
        self.gas_valve.mqtt_publish_topic = mqtt_node.find('publish').text
        self.gas_valve.mqtt_subscribe_topics.append(mqtt_node.find('subscribe').text)

        node = root.find('ventilator')
        self.ventilator.packet_set_state_on = node.find('on').text
        self.ventilator.packet_set_state_off = node.find('off').text
        self.ventilator.packet_get_state = node.find('get').text
        speed_setting_packets = node.find('speed').text.split('\n')
        speed_setting_packets = [x.replace('\t', '').strip() for x in speed_setting_packets]
        speed_setting_packets = list(filter(lambda x: len(x) > 0, speed_setting_packets))
        self.ventilator.packet_set_rotation_speed = speed_setting_packets
        mqtt_node = node.find('mqtt')
        self.ventilator.mqtt_publish_topic = mqtt_node.find('publish').text
        self.ventilator.mqtt_subscribe_topics.append(mqtt_node.find('subscribe').text)

        node = root.find('elevator')
        self.elevator.my_floor = int(node.find('myfloor').text)
        mqtt_node = node.find('mqtt')
        self.elevator.mqtt_publish_topic = mqtt_node.find('publish').text
        topic_text = mqtt_node.find('subscribe').text
        topics = list(filter(lambda y: len(y) > 0, [x.strip() for x in topic_text.split('\n')]))
        self.elevator.mqtt_subscribe_topics.extend(topics)

    def startThreadCommand(self):
        if self.thread_command is None:
            self.thread_command = ThreadCommand(self.queue_command)
            self.thread_command.sig_send_energy.connect(self.sendSerialEnergyPacket)
            self.thread_command.sig_send_control.connect(self.sendSerialControlPacket)
            self.thread_command.sig_send_smart.connect(self.sendSerialSmartPacket)
            self.thread_command.sig_terminated.connect(self.onThreadCommandTerminated)
            self.thread_command.setDaemon(True)
            self.thread_command.start()

    def stopThreadCommand(self):
        if self.thread_command is not None:
            self.thread_command.stop()

    def onThreadCommandTerminated(self):
        del self.thread_command
        self.thread_command = None

    def startThreadMonitoring(self):
        if self.thread_monitoring is None:
            self.thread_monitoring = ThreadMonitoring([
                self.serial_485_energy,
                self.serial_485_control,
                self.serial_485_smart1
                # self.serial_485_smart2
            ], self.device_list)
            self.thread_monitoring.sig_terminated.connect(self.onThreadMonitoringTerminated)
            self.thread_monitoring.setDaemon(True)
            self.thread_monitoring.start()

    def stopThreadMonitoring(self):
        if self.thread_monitoring is not None:
            self.thread_monitoring.stop()

    def onThreadMonitoringTerminated(self):
        del self.thread_monitoring
        self.thread_monitoring = None

    def sendSerialEnergyPacket(self, packet: str):
        if self.serial_485_energy.isConnected():
            self.serial_485_energy.sendData(bytearray([int(x, 16) for x in packet.split(' ')]))

    def sendSerialControlPacket(self, packet: str):
        if self.serial_485_control.isConnected():
            self.serial_485_control.sendData(bytearray([int(x, 16) for x in packet.split(' ')]))

    def sendSerialSmartPacket(self, packet: str):
        if self.serial_485_smart2.isConnected():
            self.serial_485_smart2.sendData(bytearray([int(x, 16) for x in packet.split(' ')]))

    def onParserEnergyResult(self, chunk: bytearray):
        try:
            if len(chunk) < 7:
                return
            header = chunk[1]  # [0x31, 0x41, 0x42, 0xD1]
            command = chunk[3]
            if header == 0x31 and command in [0x81, 0x91]:
                # 방 조명 패킷
                room_idx = chunk[5] & 0x0F
                room = self.rooms[room_idx]
                for i in range(room.light_count):
                    dev = room.lights[i]
                    dev.state = (chunk[6] & (0x01 << i)) >> i
                    # notification
                    if dev.state != dev.state_prev or not dev.init:
                        dev.publish_mqtt()
                        dev.init = True
                    dev.state_prev = dev.state
        except Exception as e:
            writeLog('onParserEnergyResult::Exception::{}'.format(e), self)

    def onParserControlResult(self, chunk: bytearray):
        try:
            if len(chunk) < 10:
                return
            header = chunk[1]  # [0x28, 0x31, 0x61]
            command = chunk[3]
            if header == 0x28 and command in [0x91, 0x92]:
                # 난방 관련 패킷 (방 인덱스)
                # chunk[3] == 0x91: 쿼리 응답
                # chunk[3] == 0x92: 명령 응답
                room_idx = chunk[5] & 0x0F
                room = self.rooms[room_idx]
                dev = room.thermostat
                dev.state = chunk[6] & 0x01
                dev.temperature_setting = (chunk[7] & 0x3F) + (chunk[7] & 0x40 > 0) * 0.5
                # dev.temperature_current = chunk[9] / 10.0
                dev.temperature_current = int.from_bytes(chunk[8:10], byteorder='big') / 10.0
                # print('Room Idx: {}, Temperature Current: {}'.format(room_idx, dev.temperature_current))
                # print('Raw Packet: {}'.format('|'.join(['%02X'%x for x in chunk])))
                # notification
                if dev.state != dev.state_prev \
                        or dev.temperature_setting != dev.temperature_setting_prev \
                        or not dev.init:
                    dev.publish_mqtt()
                    dev.init = True
                if dev.temperature_current != dev.temperature_current_prev:
                    # dev.publish_mqtt()
                    pass
                dev.state_prev = dev.state
                dev.temperature_setting_prev = dev.temperature_setting
                dev.temperature_current_prev = dev.temperature_current
            elif header == 0x31 and chunk[2] in [0x80, 0x82]:
                # 가스 관련 패킷 (길이 정보 없음, 무조건 10 고정)
                # chunk[2] == 0x80: 쿼리 응답
                # chunk[2] == 0x82: 명령 응답
                dev = self.gas_valve
                dev.state = chunk[5]
                # notification
                if dev.state != dev.state_prev or not dev.init:
                    dev.publish_mqtt()
                    dev.init = True
                dev.state_prev = dev.state
            elif header == 0x61 and chunk[2] in [0x80, 0x81, 0x83, 0x84, 0x87]:
                # 환기 관련 패킷
                dev = self.ventilator
                dev.state = chunk[5] & 0x01
                dev.state_natural = (chunk[5] & 0x10) >> 4
                dev.rotation_speed = chunk[6]
                dev.timer_remain = chunk[7]
                # notification
                if dev.state != dev.state_prev or dev.rotation_speed != dev.rotation_speed_prev or not dev.init:
                    dev.publish_mqtt()
                    dev.init = True
                dev.state_prev = dev.state
                dev.rotation_speed_prev = dev.rotation_speed
            else:
                pass
        except Exception as e:
            writeLog('onParserControlResult Exception::{}'.format(e), self)

    def onParserSmartResult1(self, chunk: bytearray):
        try:
            if len(chunk) >= 4:
                header = chunk[1]  # [0xC1]
                packetLen = chunk[2]
                cmd = chunk[3]
                if header == 0xC1 and packetLen == 0x13 and cmd == 0x13:
                    dev = self.elevator
                    if len(chunk) >= 13:
                        dev.state = chunk[11]
                        dev.current_floor = ctypes.c_int8(chunk[12]).value
                        # notification
                        if dev.state != dev.state_prev or not dev.init:
                            dev.publish_mqtt()
                            dev.init = True
                        if dev.current_floor != dev.current_floor_prev:
                            writeLog(f'Elevator Current Floor: {dev.current_floor}', self)
                        dev.state_prev = dev.state
                        dev.current_floor_prev = dev.current_floor
        except Exception as e:
            writeLog('onParserSmartResult1 Exception::{}'.format(e), self)

    def onParserSmartResult2(self, chunk: bytearray):
        try:
            pass
        except Exception as e:
            writeLog('onParserSmartResult2 Exception::{}'.format(e), self)

    def command(self, **kwargs):
        writeLog('Command::{}'.format(kwargs), self)
        try:
            dev = kwargs['device']
            if isinstance(dev, Light):
                kwargs['func'] = self.sendSerialEnergyPacket
            elif isinstance(dev, Thermostat):
                kwargs['func'] = self.sendSerialControlPacket
            elif isinstance(dev, Ventilator):
                kwargs['func'] = self.sendSerialControlPacket
            elif isinstance(dev, GasValve):
                kwargs['func'] = self.sendSerialControlPacket
            elif isinstance(dev, Elevator):
                if kwargs['direction'] == 'up':
                    kwargs['func'] = self.onElevatorCallUp
                else:
                    kwargs['func'] = self.onElevatorCallDown
        except Exception as e:
            writeLog('command Exception::{}'.format(e), self)
        self.queue_command.put(kwargs)

    def onElevatorCallUp(self):
        self.parser_smart.flag_send_up_packet = True

    def onElevatorCallDown(self):
        self.parser_smart.flag_send_down_packet = True

    def startMqttSubscribe(self):
        for dev in self.device_list:
            for topic in dev.mqtt_subscribe_topics:
                self.mqtt_client.subscribe(topic)

    def onMqttClientConnect(self, client, userdata, flags, rc):
        writeLog('Mqtt Client Connected: {}, {}, {}'.format(userdata, flags, rc), self)
        """
        0: Connection successful
        1: Connection refused - incorrect protocol version
        2: Connection refused - invalid client identifier
        3: Connection refused - server unavailable
        4: Connection refused - bad username or password
        5: Connection refused - not authorised
        """
        if rc == 0:
            self.mqtt_is_connected = True
            self.startMqttSubscribe()
        else:
            self.mqtt_is_connected = False

    def onMqttClientDisconnect(self, client, userdata, rc):
        self.mqtt_is_connected = False
        writeLog('Mqtt Client Disconnected: {}, {}'.format(userdata, rc), self)

    def onMqttClientPublish(self, client, userdata, mid):
        writeLog('Mqtt Client Publish: {}, {}'.format(userdata, mid), self)

    def onMqttClientMessage(self, client, userdata, message):
        writeLog('Mqtt Client Message: {}, {}'.format(userdata, message), self)
        topic = message.topic
        msg_dict = json.loads(message.payload.decode("utf-8"))
        if 'light/command' in topic:
            splt = topic.split('/')
            room_idx = int(splt[-2])
            dev_idx = int(splt[-1])
            if 'state' in msg_dict.keys():
                self.command(
                    device=self.rooms[room_idx].lights[dev_idx],
                    category='state',
                    target=msg_dict['state'],
                    room_idx=room_idx,
                    dev_idx=dev_idx
                )
        if 'thermostat/command' in topic:
            splt = topic.split('/')
            room_idx = int(splt[-1])
            if 'state' in msg_dict.keys():
                target = 1 if msg_dict['state'] == 'HEAT' else 0
                self.command(
                    device=self.rooms[room_idx].thermostat,
                    category='state',
                    target=target
                )
            if 'targetTemperature' in msg_dict.keys():
                self.command(
                    device=self.rooms[room_idx].thermostat,
                    category='temperature',
                    target=msg_dict['targetTemperature']
                )
        if 'ventilator/command' in topic:
            if 'state' in msg_dict.keys():
                self.command(
                    device=self.ventilator,
                    category='state',
                    target=msg_dict['state']
                )
            if 'rotationspeed' in msg_dict.keys():
                conv = min(3, max(0, int(msg_dict['rotationspeed'] / 100 * 3) + 1))
                self.command(
                    device=self.ventilator,
                    category='rotation_speed',
                    target=conv
                )
        if 'gasvalve/command' in topic:
            if 'state' in msg_dict.keys():
                self.command(
                    device=self.gas_valve,
                    category='state',
                    target=msg_dict['state']
                )
        if 'elevator/command' in topic:
            if 'state' in msg_dict.keys():
                last_word = topic.split('/')[-1]
                self.command(
                    device=self.elevator,
                    category='state',
                    target=msg_dict['state'],
                    direction=last_word
                )
    
    def onMqttClientLog(self, client, userdata, level, buf):
        writeLog('Mqtt Client Log: {}, {}, {}'.format(userdata, level, buf), self)

    def onMqttClientSubscribe(self, client, userdata, mid, granted_qos):
        writeLog('Mqtt Client Subscribe: {}, {}, {}'.format(userdata, mid, granted_qos), self)

    def onMqttClientUnsubscribe(self, client, userdata, mid):
        writeLog('Mqtt Client Unsubscribe: {}, {}'.format(userdata, mid), self)
