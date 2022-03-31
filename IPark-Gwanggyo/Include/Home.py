import time
import json
import queue
import ctypes
from typing import List, Union
import paho.mqtt.client as mqtt
import xml.etree.ElementTree as ET
from Include import *
from Serial485 import *


class Home:
    name: str = 'Home'
    device_list: List[Device]

    rooms: List[Room]
    gas_valve: GasValve
    ventilator: Ventilator
    elevator: Elevator
    airquality: AirqualitySensor
    doorlock: Doorlock

    serial_baud: int = 9600
    serial_485_energy_port: str = ''
    serial_485_control_port: str = ''
    serial_485_smart_port_recv: str = ''
    serial_485_smart_port_send: str = ''

    thread_command: Union[ThreadCommand, None] = None
    thread_monitoring: Union[ThreadMonitoring, None] = None
    queue_command: queue.Queue

    mqtt_client: mqtt.Client
    # mqtt_host: str = 'localhost'
    mqtt_host: str = '127.0.0.1'
    mqtt_port: int = 1883
    mqtt_is_connected: bool = False
    enable_mqtt_console_log: bool = True

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
    packets_smart_recv: List[bytearray]
    packets_smart_send: List[bytearray]

    serial_list: List[SerialComm]
    parser_list: List[Parser]

    def __init__(self, name: str = 'Home', init_service: bool = True):
        self.name = name
        self.device_list = list()
        self.rooms = list()
        self.queue_command = queue.Queue()
        # for packet monitoring
        self.packets_energy = list()
        self.packets_control = list()
        self.packets_smart_recv = list()
        self.packets_smart_send = list()
        self.serial_list = list()
        self.parser_list = list()

        self.serial_485_energy = SerialComm('Energy')
        self.serial_list.append(self.serial_485_energy)
        self.parser_energy = EnergyParser(self.serial_485_energy)
        self.parser_energy.sig_parse.connect(self.onParserEnergyResult)
        self.parser_list.append(self.parser_energy)

        self.serial_485_control = SerialComm('Control')
        self.serial_list.append(self.serial_485_control)
        self.parser_control = ControlParser(self.serial_485_control)
        self.parser_control.sig_parse.connect(self.onParserControlResult)
        self.parser_list.append(self.parser_control)

        self.serial_485_smart_recv = SerialComm('Smart(Recv)')
        self.serial_list.append(self.serial_485_smart_recv)
        self.parser_smart_recv = SmartRecvParser(self.serial_485_smart_recv)
        self.parser_smart_recv.sig_parse.connect(self.onParserSmartRecvResult)
        self.parser_smart_recv.sig_call_elevator.connect(self.callElevatorByParser)
        self.parser_list.append(self.parser_smart_recv)

        self.serial_485_smart_send = SerialComm('Smart(Send)')
        self.serial_list.append(self.serial_485_smart_send)
        self.parser_smart_send = SmartSendParser(self.serial_485_smart_send)
        self.parser_smart_send.sig_parse.connect(self.onParserSmartSendResult)
        self.parser_list.append(self.parser_smart_send)

        self.initialize(init_service, False)

    def initialize(self, init_service: bool, serial_conn: bool):
        self.device_list.clear()
        self.rooms.clear()

        self.packets_energy.clear()
        self.packets_control.clear()
        self.packets_smart_recv.clear()
        self.packets_smart_send.clear()

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

        self.initRoomsFromConfig(xml_path)
        self.gas_valve = GasValve(name='Gas Valve', mqtt_client=self.mqtt_client)
        self.ventilator = Ventilator(name='Ventilator', mqtt_client=self.mqtt_client)
        self.elevator = Elevator(name='Elevator', mqtt_client=self.mqtt_client)
        self.elevator.sig_call_up.connect(self.callElevatorUp)
        self.elevator.sig_call_down.connect(self.callElevatorDown)
        self.airquality = AirqualitySensor(mqtt_client=self.mqtt_client)
        self.doorlock = Doorlock(name='Doorlock', mqtt_client=self.mqtt_client)

        # append device list
        for room in self.rooms:
            self.device_list.extend(room.getDevices())
        self.device_list.append(self.gas_valve)
        self.device_list.append(self.ventilator)
        self.device_list.append(self.elevator)
        self.device_list.append(self.airquality)
        self.device_list.append(self.doorlock)

        self.loadConfig(xml_path)

        if init_service:
            self.startThreadCommand()
            self.startThreadMonitoring()
            try:
                self.mqtt_client.connect(self.mqtt_host, self.mqtt_port)
            except Exception as e:
                writeLog('MQTT Connection Error: {}'.format(e), self)
            self.mqtt_client.loop_start()
        
        if serial_conn:
            self.initSerialConnection();

        writeLog(f'Initialized <{self.name}>', self)

    def release(self):
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        del self.mqtt_client

        self.stopThreadCommand()
        self.stopThreadMonitoring()

        for parser in self.parser_list:
            parser.release()
        for serial in self.serial_list:
            serial.release()
        writeLog(f'Released', self)

    def restart(self):
        self.release()
        time.sleep(1)
        self.initialize(True, True)

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
        self.serial_485_smart_recv.connect(self.serial_485_smart_port_recv, self.serial_baud)
        self.serial_485_smart_send.connect(self.serial_485_smart_port_send, self.serial_baud)

    def loadConfig(self, filepath: str):
        if not os.path.isfile(filepath):
            return

        root = ET.parse(filepath).getroot()

        node = root.find('serial')
        try:
            self.serial_485_energy_port = node.find('port_energy').text
            self.serial_485_control_port = node.find('port_control').text
            self.serial_485_smart_port_recv = node.find('port_smart1').text
            self.serial_485_smart_port_send = node.find('port_smart2').text
        except Exception as e:
            writeLog(f"Failed to load serial port info ({e})", self)

        node = root.find('mqtt')
        try:
            username = node.find('username').text
            password = node.find('password').text
            self.mqtt_host = node.find('host').text
            self.mqtt_port = int(node.find('port').text)
            self.mqtt_client.username_pw_set(username, password)
            self.enable_mqtt_console_log = bool(int(node.find('console_log').text))
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

        node = root.find('doorlock')
        mqtt_node = node.find('mqtt')
        self.doorlock.mqtt_publish_topic = mqtt_node.find('publish').text
        self.doorlock.mqtt_subscribe_topics.append(mqtt_node.find('subscribe').text)
        enable = bool(int(node.find('enable').text))
        gpio_port = int(node.find('port').text)
        repeat = int(node.find('repeat').text)
        interval_ms = int(node.find('interval').text)
        self.doorlock.setParams(enable, gpio_port, repeat, interval_ms)

    def getRoomObjectByIndex(self, index: int) -> Union[Room, None]:
        find = list(filter(lambda x: x.index == index, self.rooms))
        if len(find) == 1:
            return find[0]
        return None

    def startThreadCommand(self):
        if self.thread_command is None:
            self.thread_command = ThreadCommand(self.queue_command)
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
                self.serial_485_smart_recv,
                # self.serial_485_smart_send
            ])
            self.thread_monitoring.sig_terminated.connect(self.onThreadMonitoringTerminated)
            self.thread_monitoring.sig_publish_regular.connect(self.publish_all)
            self.thread_monitoring.setDaemon(True)
            self.thread_monitoring.start()

    def stopThreadMonitoring(self):
        if self.thread_monitoring is not None:
            self.thread_monitoring.stop()

    def onThreadMonitoringTerminated(self):
        del self.thread_monitoring
        self.thread_monitoring = None

    def publish_all(self):
        for dev in self.device_list:
            try:
                dev.publish_mqtt()
            except ValueError as e:
                writeLog(f'{e}: {dev}, {dev.mqtt_publish_topic}', self)

    def sendSerialEnergyPacket(self, packet: str):
        self.serial_485_energy.sendData(bytearray([int(x, 16) for x in packet.split(' ')]))

    def sendSerialControlPacket(self, packet: str):
        self.serial_485_control.sendData(bytearray([int(x, 16) for x in packet.split(' ')]))

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
                    """
                    print('Room Idx: {}, Temperature Current: {}, Temperature Setting: {}'.format(
                        room_idx, dev.temperature_current, dev.temperature_setting))
                    print('Raw Packet: {}'.format('|'.join(['%02X'%x for x in chunk])))
                    """
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

    def onParserSmartRecvResult(self, chunk: bytearray):
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
                    # 0xFF : unknown, 최상위 비트가 1이면 지하
                    if chunk[12] == 0xFF:
                        dev.current_floor = 'unknown'
                    elif chunk[12] & 0x80:
                        dev.current_floor = f'B{chunk[12] & 0x7F}'
                    else:
                        dev.current_floor = f'{chunk[12] & 0xFF}'
                    # dev.current_floor = ctypes.c_int8(chunk[12]).value
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
            if len(self.packets_smart_recv) > self.max_packet_log_cnt:
                self.packets_smart_recv = self.packets_smart_recv[1:]
            self.packets_smart_recv.append(chunk)
        except Exception as e:
            writeLog('onParserSmartRecvResult Exception::{}'.format(e), self)

    def onParserSmartSendResult(self, chunk: bytearray):
        pass

    def command(self, **kwargs):
        # writeLog('Command::{}'.format(kwargs), self)
        try:
            dev = kwargs['device']
            if isinstance(dev, Light) or isinstance(dev, Outlet):
                kwargs['func'] = self.parser_energy.sendPacketString
            elif isinstance(dev, Thermostat):
                kwargs['func'] = self.parser_control.sendPacketString
            elif isinstance(dev, Ventilator):
                kwargs['func'] = self.parser_control.sendPacketString
            elif isinstance(dev, GasValve):
                kwargs['func'] = self.parser_control.sendPacketString
            elif isinstance(dev, Elevator):
                if kwargs['direction'] == 'up':
                    kwargs['func'] = self.parser_smart_recv.setFlagCallUp
                else:
                    kwargs['func'] = self.parser_smart_recv.setFlagCallDown
        except Exception as e:
            writeLog('command Exception::{}'.format(e), self)
        self.queue_command.put(kwargs)

    def callElevatorByParser(self, updown: int, timestamp: int):
        self.parser_smart_send.sendCallElevatorPacket(updown, timestamp)

    def callElevatorUp(self):
        self.parser_smart_recv.setFlagCallUp()

    def callElevatorDown(self):
        self.parser_smart_recv.setFlagCallDown()

    def startMqttSubscribe(self):
        self.mqtt_client.subscribe('system/command')
        for dev in self.device_list:
            for topic in dev.mqtt_subscribe_topics:
                self.mqtt_client.subscribe(topic)

    def onMqttClientConnect(self, _, userdata, flags, rc):
        if self.enable_mqtt_console_log:
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
        if self.enable_mqtt_console_log:
            writeLog('Mqtt Client Disconnected: {}, {}'.format(userdata, rc), self)

    def onMqttClientPublish(self, _, userdata, mid):
        if self.enable_mqtt_console_log:
            writeLog('Mqtt Client Publish: {}, {}'.format(userdata, mid), self)

    def onMqttClientMessage(self, _, userdata, message):
        """
        Homebridge Publish, App Subscribe
        사용자에 의한 명령 토픽 핸들링
        """
        if self.enable_mqtt_console_log:
            writeLog('Mqtt Client Message: {}, {}'.format(userdata, message), self)
        topic = message.topic
        msg_dict = json.loads(message.payload.decode("utf-8"))
        if 'system/command' == topic:
            if 'query_all' in msg_dict.keys():
                writeLog('Got query all command', self)
                self.publish_all()
            if 'restart' in msg_dict.keys():
                writeLog('Got restart command', self)
                self.restart()
            if 'reboot' in msg_dict.keys():
                import os
                os.system('sudo reboot')
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
                        target=msg_dict['state']
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
                        target=msg_dict['state']
                    )
        if 'doorlock/command' in topic:
            # do not use command queue becase door module handles only gpio
            if msg_dict['state'] == 1:
                self.doorlock.open()

    def onMqttClientLog(self, _, userdata, level, buf):
        if self.enable_mqtt_console_log:
            writeLog('Mqtt Client Log: {}, {}, {}'.format(userdata, level, buf), self)

    def onMqttClientSubscribe(self, _, userdata, mid, granted_qos):
        if self.enable_mqtt_console_log:
            writeLog('Mqtt Client Subscribe: {}, {}, {}'.format(userdata, mid, granted_qos), self)

    def onMqttClientUnsubscribe(self, _, userdata, mid):
        if self.enable_mqtt_console_log:
            writeLog('Mqtt Client Unsubscribe: {}, {}'.format(userdata, mid), self)


home_: Union[Home, None] = None


def get_home(name: str = '') -> Home:
    global home_
    if home_ is None:
        home_ = Home(name=name)
    return home_
