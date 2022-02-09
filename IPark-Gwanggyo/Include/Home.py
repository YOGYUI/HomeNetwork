import os
import sys
import json
import queue
import ctypes
from typing import List, Union
import paho.mqtt.client as mqtt
import xml.etree.ElementTree as ET
from Common import writeLog
from Device import Device
from Room import Room
from Light import Light
from Outlet import Outlet
from Thermostat import Thermostat
from GasValve import GasValve
from Ventilator import Ventilator
from Elevator import Elevator
from AirqualitySensor import AirqualitySensor
from ThreadCommand import ThreadCommand
from ThreadMonitoring import ThreadMonitoring
CURPATH = os.path.dirname(os.path.abspath(__file__))  # Project/Include
PROJPATH = os.path.dirname(CURPATH)  # Proejct/
SERPATH = os.path.join(PROJPATH, 'Serial485')  # Project/Serial485
sys.path.extend([SERPATH])
sys.path = list(set(sys.path))
from SerialComm import SerialComm
from EnergyParser import EnergyParser
from ControlParser import ControlParser
from SmartParser import SmartParser


class Home:
    name: str = 'Home'
    device_list: List[Device]

    rooms: List[Room]
    gas_valve: GasValve
    ventilator: Ventilator
    elevator: Elevator
    airquality: AirqualitySensor

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

    max_packet_log_cnt: int = 100
    packets_energy: List[bytearray]
    enable_log_energy_31: bool = True
    enable_log_energy_41: bool = True
    enable_log_energy_42: bool = True
    enable_log_energy_d1: bool = True
    enable_log_energy_room_1: bool = True
    enable_log_energy_room_2: bool = True
    enable_log_energy_room_3: bool = True
    packets_control: List[bytearray]
    enable_log_control_28: bool = True
    enable_log_control_31: bool = True
    enable_log_control_61: bool = True
    packets_smart1: List[bytearray]
    packets_smart2: List[bytearray]

    def __init__(self, name: str = 'Home', init_service: bool = True):
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

        curpath = os.path.dirname(os.path.abspath(__file__))  # /project/include
        projpath = os.path.dirname(curpath)  # /project/
        xml_path = os.path.join(projpath, 'config.xml')

        self.rooms = list()
        self.initRoomsFromConfig(xml_path)
        self.gas_valve = GasValve(name='Gas Valve', mqtt_client=self.mqtt_client)
        self.ventilator = Ventilator(name='Ventilator', mqtt_client=self.mqtt_client)
        self.elevator = Elevator(name='Elevator', mqtt_client=self.mqtt_client)
        self.elevator.sig_call_up.connect(self.onElevatorCallUp)
        self.elevator.sig_call_down.connect(self.onElevatorCallDown)
        self.airquality = AirqualitySensor(mqtt_client=self.mqtt_client)

        # append device list
        for room in self.rooms:
            self.device_list.extend(room.getDevices())
        self.device_list.append(self.gas_valve)
        self.device_list.append(self.ventilator)
        self.device_list.append(self.elevator)
        self.device_list.append(self.airquality)

        self.loadConfig(xml_path)

        # for packet monitoring
        self.packets_energy = list()
        self.packets_control = list()
        self.packets_smart1 = list()
        self.packets_smart2 = list()

        self.serial_485_energy = SerialComm('Energy')
        self.parser_energy = EnergyParser(self.serial_485_energy)
        self.parser_energy.sig_parse.connect(self.onParserEnergyResult)
        self.serial_485_control = SerialComm('Control')
        self.parser_control = ControlParser(self.serial_485_control)
        self.parser_control.sig_parse.connect(self.onParserControlResult)
        self.serial_485_smart1 = SerialComm('Smart1')
        self.serial_485_smart2 = SerialComm('Smart2')
        self.parser_smart = SmartParser(self.serial_485_smart1, self.serial_485_smart2)
        self.parser_smart.sig_parse1.connect(self.onParserSmartResult1Result)
        self.parser_smart.sig_parse2.connect(self.onParserSmartResult2Result)

        self.queue_command = queue.Queue()
        if init_service:
            self.startThreadCommand()
            self.startThreadMonitoring()
            try:
                self.mqtt_client.connect(self.mqtt_host, self.mqtt_port)
            except Exception as e:
                writeLog('MQTT Connection Error: {}'.format(e), self)
            self.mqtt_client.loop_start()
        writeLog(f'Created <{self.name}> ', self)

    def release(self):
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.stopThreadCommand()
        self.stopThreadMonitoring()
        self.serial_485_energy.release()
        self.serial_485_control.release()
        self.serial_485_smart1.release()
        self.serial_485_smart2.release()

    def initRoomsFromConfig(self, filepath: str):
        if not os.path.isfile(filepath):
            return

        root = ET.parse(filepath).getroot()
        node = root.find('rooms')
        for child in list(node):
            writeLog(f'Initializing Room <{child.tag}>', self)
            try:
                child_tag_names = [x.tag for x in list(child)]
                name = child.find('name').text
                index = int(child.find('index').text)
                light_count = len(list(filter(lambda x: 'light' in x, child_tag_names)))
                has_thermostat = len(list(filter(lambda x: 'thermostat' == x, child_tag_names))) == 1
                outlet_count = len(list(filter(lambda x: 'outlet' in x, child_tag_names)))
                room = Room(
                    name=name,
                    index=index,
                    light_count=light_count,
                    has_thermostat=has_thermostat,
                    outlet_count=outlet_count,
                    mqtt_client=self.mqtt_client
                )
                self.rooms.append(room)
            except Exception:
                pass
        writeLog(f'Initializing Room Finished ({len(self.rooms)})', self)
        """
        for room in self.rooms:
            writeLog(str(room), self)
        """

    def initSerialConnection(self):
        self.serial_485_energy.connect(self.serial_485_energy_port, self.serial_baud)
        self.serial_485_control.connect(self.serial_485_control_port, self.serial_baud)
        self.serial_485_smart1.connect(self.serial_485_smart_port1, self.serial_baud)
        self.serial_485_smart2.connect(self.serial_485_smart_port2, self.serial_baud)

    def loadConfig(self, filepath: str):
        if not os.path.isfile(filepath):
            return

        root = ET.parse(filepath).getroot()

        node = root.find('serial')
        try:
            self.serial_485_energy_port = node.find('port_energy').text
            self.serial_485_control_port = node.find('port_control').text
            self.serial_485_smart_port1 = node.find('port_smart1').text
            self.serial_485_smart_port2 = node.find('port_smart2').text
        except Exception as e:
            writeLog(f"Failed to load serial port info ({e})", self)

        node = root.find('mqtt')
        username = node.find('username').text
        password = node.find('password').text
        try:
            self.mqtt_host = node.find('host').text
            self.mqtt_port = int(node.find('port').text)
            self.mqtt_client.username_pw_set(username, password)
        except Exception as e:
            writeLog(f"Failed to load mqtt config ({e})", self)

        node = root.find('thermo_temp_packet')
        try:
            thermo_setting_packets = node.text.split('\n')
            thermo_setting_packets = [x.replace('\t', '').strip() for x in thermo_setting_packets]
            thermo_setting_packets = list(filter(lambda x: len(x) > 0, thermo_setting_packets))
        except Exception as e:
            writeLog(f"Failed to load thermo packets ({e})", self)
            thermo_setting_packets = []

        node = root.find('rooms')
        for room in self.rooms:
            room_node = node.find('room{}'.format(room.index))
            if room_node is not None:
                for j in range(room.light_count):
                    light_node = room_node.find('light{}'.format(j))
                    if light_node is not None:
                        room.lights[j].packet_set_state_on = light_node.find('on').text
                        room.lights[j].packet_set_state_off = light_node.find('off').text
                        room.lights[j].packet_get_state = light_node.find('get').text
                        mqtt_node = light_node.find('mqtt')
                        room.lights[j].mqtt_publish_topic = mqtt_node.find('publish').text
                        room.lights[j].mqtt_subscribe_topics.append(mqtt_node.find('subscribe').text)

                thermo_node = room_node.find('thermostat')
                if thermo_node is not None:
                    room.thermostat.packet_set_state_on = thermo_node.find('on').text
                    room.thermostat.packet_set_state_off = thermo_node.find('off').text
                    room.thermostat.packet_get_state = thermo_node.find('get').text
                    mqtt_node = thermo_node.find('mqtt')
                    room.thermostat.mqtt_publish_topic = mqtt_node.find('publish').text
                    room.thermostat.mqtt_subscribe_topics.append(mqtt_node.find('subscribe').text)
                try:
                    for j in range(71):
                        room.thermostat.packet_set_temperature[j] = thermo_setting_packets[j + 71 * (room.index - 1)]
                except Exception:
                    pass

                for j in range(room.outlet_count):
                    outlet_node = room_node.find('outlet{}'.format(j))
                    if outlet_node is not None:
                        room.outlets[j].packet_set_state_on = outlet_node.find('on').text
                        room.outlets[j].packet_set_state_off = outlet_node.find('off').text
                        room.outlets[j].packet_get_state = outlet_node.find('get').text
                        mqtt_node = outlet_node.find('mqtt')
                        room.outlets[j].mqtt_publish_topic = mqtt_node.find('publish').text
                        room.outlets[j].mqtt_subscribe_topics.append(mqtt_node.find('subscribe').text)

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

        node = root.find('airquality')
        mqtt_node = node.find('mqtt')
        self.airquality.mqtt_publish_topic = mqtt_node.find('publish').text
        apikey = node.find('apikey').text
        obsname = node.find('obsname').text
        self.airquality.setApiParams(apikey, obsname)

    def getRoomObjectByIndex(self, index: int) -> Union[Room, None]:
        find = list(filter(lambda x: x.index == index, self.rooms))
        if len(find) == 1:
            return find[0]
        return None

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
            if len(chunk) < 8:
                return
            header = chunk[1]  # [0x31, 0x41, 0x42, 0xD1]
            command = chunk[3]
            room_idx = 0
            if header == 0x31:
                if command in [0x81, 0x91]:
                    # 방 조명 패킷
                    room_idx = chunk[5] & 0x0F
                    room = self.getRoomObjectByIndex(room_idx)
                    if room is not None:
                        for i in range(room.light_count):
                            dev = room.lights[i]
                            dev.state = (chunk[6] & (0x01 << i)) >> i
                            # notification
                            if not dev.init:
                                dev.publish_mqtt()
                                dev.init = True
                            if dev.state != dev.state_prev:
                                dev.publish_mqtt()
                            dev.state_prev = dev.state

                        # 콘센트 소비전력 패킷
                        for i in range(room.outlet_count):
                            dev = room.outlets[i]
                            dev.state = (chunk[7] & (0x01 << i)) >> i
                            if room_idx == 1 and i == 2:
                                dev.state = 1
                            if len(chunk) >= 14 + 2 * i + 2 + 1:
                                value = int.from_bytes(chunk[14 + 2 * i: 14 + 2 * i + 2], byteorder='big')
                                dev.measurement = value / 10.
                            else:
                                dev.measurement = 0
                            if not dev.init:
                                dev.publish_mqtt()
                                dev.init = True
                            if int(dev.measurement) != int(dev.measurement_prev):
                                dev.publish_mqtt()
                            dev.measurement_prev = dev.measurement
                elif command in [0x11]:
                    room_idx = chunk[5] & 0x0F

            # packet log
            append = True
            if header == 0x31:
                if not self.enable_log_energy_31:
                    append = False
                else:
                    if room_idx == 1 and not self.enable_log_energy_room_1:
                        append = False
                    if room_idx == 2 and not self.enable_log_energy_room_2:
                        append = False
                    if room_idx == 3 and not self.enable_log_energy_room_3:
                        append = False
            if header == 0x41 and not self.enable_log_energy_41:
                append = False
            if header == 0x42 and not self.enable_log_energy_42:
                append = False
            if header == 0xD1 and not self.enable_log_energy_d1:
                append = False

            if append:
                if len(self.packets_energy) > self.max_packet_log_cnt:
                    self.packets_energy = self.packets_energy[1:]
                self.packets_energy.append(chunk)
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
                # chunk[3] == 0x91: 쿼리 응답 / 0x92: 명령 응답
                room_idx = chunk[5] & 0x0F
                room = self.getRoomObjectByIndex(room_idx)
                if room is not None:
                    dev = room.thermostat
                    dev.state = chunk[6] & 0x01
                    dev.temperature_setting = (chunk[7] & 0x3F) + (chunk[7] & 0x40 > 0) * 0.5
                    dev.temperature_current = int.from_bytes(chunk[8:10], byteorder='big') / 10.0
                    # print('Room Idx: {}, Temperature Current: {}'.format(room_idx, dev.temperature_current))
                    # print('Raw Packet: {}'.format('|'.join(['%02X'%x for x in chunk])))
                    # notification
                    if not dev.init:
                        dev.publish_mqtt()
                        dev.init = True
                    if dev.state != dev.state_prev or dev.temperature_setting != dev.temperature_setting_prev:
                        dev.publish_mqtt()
                    """
                    if dev.temperature_current != dev.temperature_current_prev:
                        dev.publish_mqtt()
                        pass
                    """
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
                if not dev.init:
                    dev.publish_mqtt()
                    dev.init = True
                if dev.state != dev.state_prev:
                    dev.publish_mqtt()
                dev.state_prev = dev.state
            elif header == 0x61 and chunk[2] in [0x80, 0x81, 0x83, 0x84, 0x87]:
                # 환기 관련 패킷
                dev = self.ventilator
                dev.state = chunk[5] & 0x01
                dev.state_natural = (chunk[5] & 0x10) >> 4
                dev.rotation_speed = chunk[6]
                dev.timer_remain = chunk[7]
                # notification
                if not dev.init:
                    dev.publish_mqtt()
                    dev.init = True
                if dev.state != dev.state_prev or dev.rotation_speed != dev.rotation_speed_prev:
                    dev.publish_mqtt()
                dev.state_prev = dev.state
                dev.rotation_speed_prev = dev.rotation_speed
            else:
                pass

            # packet log
            append = True
            if header == 0x28 and not self.enable_log_control_28:
                append = False
            if header == 0x31 and not self.enable_log_control_31:
                append = False
            if header == 0x61 and not self.enable_log_control_61:
                append = False

            if append:
                if len(self.packets_control) > self.max_packet_log_cnt:
                    self.packets_control = self.packets_control[1:]
                self.packets_control.append(chunk)
        except Exception as e:
            writeLog('onParserControlResult Exception::{}'.format(e), self)

    def onParserSmartResult1Result(self, chunk: bytearray):
        try:
            if len(chunk) < 4:
                return
            header = chunk[1]  # [0xC1]
            packetLen = chunk[2]
            cmd = chunk[3]
            if header == 0xC1 and packetLen == 0x13 and cmd == 0x13:
                dev = self.elevator
                if len(chunk) >= 13:
                    dev.state = chunk[11]
                    dev.current_floor = ctypes.c_int8(chunk[12]).value
                    # notification
                    if not dev.init:
                        dev.publish_mqtt()
                        dev.init = True
                    if dev.state != dev.state_prev:
                        dev.publish_mqtt()
                    if dev.current_floor != dev.current_floor_prev:
                        writeLog(f'Elevator Current Floor: {dev.current_floor}', self)
                    dev.state_prev = dev.state
                    dev.current_floor_prev = dev.current_floor

            # packet log
            if len(self.packets_smart1) > self.max_packet_log_cnt:
                self.packets_smart1 = self.packets_smart1[1:]
            self.packets_smart1.append(chunk)
        except Exception as e:
            writeLog('onParserSmartResult1Result Exception::{}'.format(e), self)

    def onParserSmartResult2Result(self, chunk: bytearray):
        pass

    def command(self, **kwargs):
        writeLog('Command::{}'.format(kwargs), self)
        try:
            dev = kwargs['device']
            if isinstance(dev, Light) or isinstance(dev, Outlet):
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

    def onMqttClientConnect(self, _, userdata, flags, rc):
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

    def onMqttClientDisconnect(self, _, userdata, rc):
        self.mqtt_is_connected = False
        writeLog('Mqtt Client Disconnected: {}, {}'.format(userdata, rc), self)

    def onMqttClientPublish(self, _, userdata, mid):
        writeLog('Mqtt Client Publish: {}, {}'.format(userdata, mid), self)

    def onMqttClientMessage(self, _, userdata, message):
        writeLog('Mqtt Client Message: {}, {}'.format(userdata, message), self)
        topic = message.topic
        msg_dict = json.loads(message.payload.decode("utf-8"))
        if 'light/command' in topic:
            splt = topic.split('/')
            room_idx = int(splt[-2])
            dev_idx = int(splt[-1])
            room = self.getRoomObjectByIndex(room_idx)
            if room is not None:
                if 'state' in msg_dict.keys():
                    self.command(
                        device=room.lights[dev_idx],
                        category='state',
                        target=msg_dict['state'],
                        room_idx=room_idx,
                        dev_idx=dev_idx
                    )
        if 'thermostat/command' in topic:
            splt = topic.split('/')
            room_idx = int(splt[-1])
            room = self.getRoomObjectByIndex(room_idx)
            if room is not None:
                if 'state' in msg_dict.keys():
                    target = 1 if msg_dict['state'] == 'HEAT' else 0
                    self.command(
                        device=room.thermostat,
                        category='state',
                        target=target
                    )
                if 'targetTemperature' in msg_dict.keys():
                    self.command(
                        device=room.thermostat,
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
        if 'outlet/command' in topic:
            splt = topic.split('/')
            room_idx = int(splt[-2])
            dev_idx = int(splt[-1])
            room = self.getRoomObjectByIndex(room_idx)
            if room is not None:
                if 'state' in msg_dict.keys():
                    self.command(
                        device=room.outlets[dev_idx],
                        category='state',
                        target=msg_dict['state'],
                        room_idx=room_idx,
                        dev_idx=dev_idx
                    )

    def onMqttClientLog(self, _, userdata, level, buf):
        writeLog('Mqtt Client Log: {}, {}, {}'.format(userdata, level, buf), self)

    def onMqttClientSubscribe(self, _, userdata, mid, granted_qos):
        writeLog('Mqtt Client Subscribe: {}, {}, {}'.format(userdata, mid, granted_qos), self)

    def onMqttClientUnsubscribe(self, _, userdata, mid):
        writeLog('Mqtt Client Unsubscribe: {}, {}'.format(userdata, mid), self)


home_: Union[Home, None] = None


def get_home(name: str = '') -> Home:
    global home_
    if home_ is None:
        home_ = Home(name=name)
    return home_
