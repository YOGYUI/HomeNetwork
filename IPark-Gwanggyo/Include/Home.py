import os
import sys
import time
import json
import queue
from typing import List, Union
import paho.mqtt.client as mqtt
import xml.etree.ElementTree as ET
CURPATH = os.path.dirname(os.path.abspath(__file__))  # {$PROJECT}/Include
PROJPATH = os.path.dirname(CURPATH)  # {$PROJECT}
RS485PATH = os.path.join(PROJPATH, 'RS485')  # {$PROJECT}/RS485
sys.path.extend([CURPATH, PROJPATH, RS485PATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH, RS485PATH
from RS485 import *
from Include import *


class Home:
    name: str = 'Home'
    device_list: List[Device]

    rooms: List[Room]
    gas_valve: GasValve
    ventilator: Ventilator
    elevator: Elevator
    airquality: AirqualitySensor
    doorlock: Doorlock

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
    _enable_log_energy_31: bool = True
    _enable_log_energy_41: bool = True
    _enable_log_energy_42: bool = True
    _enable_log_energy_d1: bool = True
    _enable_log_energy_room_1: bool = True
    _enable_log_energy_room_2: bool = True
    _enable_log_energy_room_3: bool = True
    packets_control: List[bytearray]
    _enable_log_control_28: bool = True
    _enable_log_control_31: bool = True
    _enable_log_control_61: bool = True
    packets_smart_recv: List[bytearray]
    packets_smart_send: List[bytearray]

    rs485_list: List[RS485Comm]
    parser_list: List[PacketParser]

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
        self.rs485_list = list()
        self.parser_list = list()

        self.rs485_energy_config = RS485Config()
        self.rs485_energy = RS485Comm('Energy')
        self.rs485_list.append(self.rs485_energy)
        self.parser_energy = EnergyParser(self.rs485_energy)
        self.parser_energy.sig_parse_result.connect(self.handlePacketParseResult)
        self.parser_energy.sig_raw_packet.connect(self.onParserEnergyRawPacket)
        self.parser_list.append(self.parser_energy)

        self.rs485_control_config = RS485Config()
        self.rs485_control = RS485Comm('Control')
        self.rs485_list.append(self.rs485_control)
        self.parser_control = ControlParser(self.rs485_control)
        self.parser_control.sig_parse_result.connect(self.handlePacketParseResult)
        self.parser_control.sig_raw_packet.connect(self.onParserControlRawPacket)
        self.parser_list.append(self.parser_control)

        self.rs485_smart_recv_config = RS485Config()
        self.rs485_smart_recv = RS485Comm('Smart(Recv)')
        self.rs485_list.append(self.rs485_smart_recv)
        self.parser_smart_recv = SmartRecvParser(self.rs485_smart_recv)
        self.parser_smart_recv.sig_call_elevator.connect(self.callElevatorByParser)
        self.parser_smart_recv.sig_parse_result.connect(self.handlePacketParseResult)
        self.parser_smart_recv.sig_raw_packet.connect(self.onParserSmartRecvRawPacket)
        self.parser_list.append(self.parser_smart_recv)

        self.rs485_smart_send_config = RS485Config()
        self.rs485_smart_send = RS485Comm('Smart(Send)')
        self.rs485_list.append(self.rs485_smart_send)
        self.parser_smart_send = SmartSendParser(self.rs485_smart_send)
        self.parser_smart_send.sig_parse_result.connect(self.handlePacketParseResult)
        self.parser_smart_send.sig_raw_packet.connect(self.onParserSmartSendRawPacket)
        self.parser_list.append(self.parser_smart_send)

        self.initialize(init_service, False)

    def initialize(self, init_service: bool, connect_rs485: bool):
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
        
        if connect_rs485:
            self.initRS485Connection()

        writeLog(f'Initialized <{self.name}>', self)

    def release(self):
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        del self.mqtt_client

        self.stopThreadCommand()
        self.stopThreadMonitoring()

        for parser in self.parser_list:
            parser.release()
        for rs485 in self.rs485_list:
            rs485.release()
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

    def initRS485Connection(self):
        if self.rs485_energy_config.enable:
            self.rs485_energy.setType(self.rs485_energy_config.comm_type)
            if self.rs485_energy_config.comm_type == RS485HwType.Serial:
                port = self.rs485_energy_config.serial_port
                baud = self.rs485_energy_config.serial_baud
                self.rs485_energy.connect(port, baud)
            elif self.rs485_energy_config.comm_type == RS485HwType.Socket:
                ipaddr = self.rs485_energy_config.socket_ipaddr
                port = self.rs485_energy_config.socket_port
                self.rs485_energy.connect(ipaddr, port)

        if self.rs485_control_config.enable:
            self.rs485_control.setType(self.rs485_control_config.comm_type)
            if self.rs485_control_config.comm_type == RS485HwType.Serial:
                port = self.rs485_control_config.serial_port
                baud = self.rs485_control_config.serial_baud
                self.rs485_control.connect(port, baud)
            elif self.rs485_control_config.comm_type == RS485HwType.Socket:
                ipaddr = self.rs485_control_config.socket_ipaddr
                port = self.rs485_control_config.socket_port
                self.rs485_control.connect(ipaddr, port)

        if self.rs485_smart_recv_config.enable:
            self.rs485_smart_recv.setType(self.rs485_smart_recv_config.comm_type)
            if self.rs485_smart_recv_config.comm_type == RS485HwType.Serial:
                port = self.rs485_smart_recv_config.serial_port
                baud = self.rs485_smart_recv_config.serial_baud
                self.rs485_smart_recv.connect(port, baud)
            elif self.rs485_smart_recv_config.comm_type == RS485HwType.Socket:
                ipaddr = self.rs485_smart_recv_config.socket_ipaddr
                port = self.rs485_smart_recv_config.socket_port
                self.rs485_smart_recv.connect(ipaddr, port)

        if self.rs485_smart_send_config.enable:
            self.rs485_smart_send.setType(self.rs485_smart_send_config.comm_type)
            if self.rs485_smart_send_config.comm_type == RS485HwType.Serial:
                port = self.rs485_smart_send_config.serial_port
                baud = self.rs485_smart_send_config.serial_baud
                self.rs485_smart_send.connect(port, baud)
            elif self.rs485_smart_send_config.comm_type == RS485HwType.Socket:
                ipaddr = self.rs485_smart_send_config.socket_ipaddr
                port = self.rs485_smart_send_config.socket_port
                self.rs485_smart_send.connect(ipaddr, port)
        
        if self.thread_monitoring is not None:
            self.thread_monitoring.set_home_initialized()

    def loadConfig(self, filepath: str):
        if not os.path.isfile(filepath):
            return
        root = ET.parse(filepath).getroot()
        node = root.find('rs485')
        try:
            energy_node = node.find('energy')
            enable_node = energy_node.find('enable')
            self.rs485_energy_config.enable = bool(int(enable_node.text))
            type_node = energy_node.find('type')
            self.rs485_energy_config.comm_type = RS485HwType(int(type_node.text))
            usb2serial_node = energy_node.find('usb2serial')
            serial_port_node = usb2serial_node.find('port')
            self.rs485_energy_config.serial_port = serial_port_node.text
            serial_baud_node = usb2serial_node.find('baud')
            self.rs485_energy_config.serial_baud = int(serial_baud_node.text)
            ew11_node = energy_node.find('ew11')
            socket_addr_node = ew11_node.find('ipaddr')
            self.rs485_energy_config.socket_ipaddr = socket_addr_node.text
            socket_port_node = ew11_node.find('port')
            self.rs485_energy_config.socket_port = int(socket_port_node.text)
        except Exception as e:
            writeLog(f"Failed to load 'energy' rs485 config ({e})", self)
        try:
            control_node = node.find('control')
            enable_node = control_node.find('enable')
            self.rs485_control_config.enable = bool(int(enable_node.text))
            type_node = control_node.find('type')
            self.rs485_control_config.comm_type = RS485HwType(int(type_node.text))
            usb2serial_node = control_node.find('usb2serial')
            serial_port_node = usb2serial_node.find('port')
            self.rs485_control_config.serial_port = serial_port_node.text
            serial_baud_node = usb2serial_node.find('baud')
            self.rs485_control_config.serial_baud = int(serial_baud_node.text)
            ew11_node = control_node.find('ew11')
            socket_addr_node = ew11_node.find('ipaddr')
            self.rs485_control_config.socket_ipaddr = socket_addr_node.text
            socket_port_node = ew11_node.find('port')
            self.rs485_control_config.socket_port = int(socket_port_node.text)
        except Exception as e:
            writeLog(f"Failed to load 'control' rs485 config ({e})", self)
        try:
            smart1_node = node.find('smart1')
            enable_node = smart1_node.find('enable')
            self.rs485_smart_recv_config.enable = bool(int(enable_node.text))
            type_node = smart1_node.find('type')
            self.rs485_smart_recv_config.comm_type = RS485HwType(int(type_node.text))
            usb2serial_node = smart1_node.find('usb2serial')
            serial_port_node = usb2serial_node.find('port')
            self.rs485_smart_recv_config.serial_port = serial_port_node.text
            serial_baud_node = usb2serial_node.find('baud')
            self.rs485_smart_recv_config.serial_baud = int(serial_baud_node.text)
            ew11_node = smart1_node.find('ew11')
            socket_addr_node = ew11_node.find('ipaddr')
            self.rs485_smart_recv_config.socket_ipaddr = socket_addr_node.text
            socket_port_node = ew11_node.find('port')
            self.rs485_smart_recv_config.socket_port = int(socket_port_node.text)
        except Exception as e:
            writeLog(f"Failed to load 'smart1' rs485 config ({e})", self)
        try:
            smart2_node = node.find('smart2')
            enable_node = smart2_node.find('enable')
            self.rs485_smart_send_config.enable = bool(int(enable_node.text))
            type_node = smart2_node.find('type')
            self.rs485_smart_send_config.comm_type = RS485HwType(int(type_node.text))
            usb2serial_node = smart2_node.find('usb2serial')
            serial_port_node = usb2serial_node.find('port')
            self.rs485_smart_send_config.serial_port = serial_port_node.text
            serial_baud_node = usb2serial_node.find('baud')
            self.rs485_smart_send_config.serial_baud = int(serial_baud_node.text)
            ew11_node = smart2_node.find('ew11')
            socket_addr_node = ew11_node.find('ipaddr')
            self.rs485_smart_send_config.socket_ipaddr = socket_addr_node.text
            socket_port_node = ew11_node.find('port')
            self.rs485_smart_send_config.socket_port = int(socket_port_node.text)
        except Exception as e:
            writeLog(f"Failed to load 'smart2' rs485 config ({e})", self)

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
        try:
            self.elevator.my_floor = int(node.find('myfloor').text)
            self.parser_smart_send.setElevatorCallCount(int(node.find('callcount').text))
            self.parser_smart_send.setElevatorCallInterval(int(node.find('callinterval').text))
            self.elevator.notify_floor = bool(int(node.find('notifyfloor').text))
        except Exception as e:
            print(e)
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
            rs485_list = []
            if self.rs485_energy_config.enable:
                rs485_list.append(self.rs485_energy)
            if self.rs485_control_config.enable:
                rs485_list.append(self.rs485_control)
            if self.rs485_smart_recv_config.enable:
                rs485_list.append(self.rs485_smart_recv)
            if self.rs485_smart_send_config.enable:
                rs485_list.append(self.rs485_smart_send)

            self.thread_monitoring = ThreadMonitoring(rs485_list)
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

    def sendRS485EnergyPacket(self, packet: str):
        self.rs485_energy.sendData(bytearray([int(x, 16) for x in packet.split(' ')]))

    def sendRS485ControlPacket(self, packet: str):
        self.rs485_control.sendData(bytearray([int(x, 16) for x in packet.split(' ')]))

    def handlePacketParseResult(self, result: dict):
        try:
            dev_type = result.get('device')
            if dev_type == 'thermostat':
                room_idx = result.get('room_index')
                room = self.getRoomObjectByIndex(room_idx)
                if room is not None:
                    dev = room.thermostat
                    dev.state = result.get('state')
                    dev.temperature_setting = result.get('temperature_setting')
                    dev.temperature_current = result.get('temperature_current')
                    # notification
                    if not dev.init:
                        dev.publish_mqtt()
                        dev.init = True
                    if dev.state != dev.state_prev or dev.temperature_setting != dev.temperature_setting_prev:
                        dev.publish_mqtt()
                    dev.state_prev = dev.state
                    dev.temperature_setting_prev = dev.temperature_setting
                    dev.temperature_current_prev = dev.temperature_current
            elif dev_type == 'gasvalve':
                dev = self.gas_valve
                dev.state = result.get('state')
                # notification
                if not dev.init:
                    dev.publish_mqtt()
                    dev.init = True
                if dev.state != dev.state_prev:
                    dev.publish_mqtt()
                dev.state_prev = dev.state
            elif dev_type == 'ventilator':
                dev = self.ventilator
                dev.state = result.get('state')
                # dev.state_natural = result.get('state_natural')
                dev.rotation_speed = result.get('rotation_speed')
                # dev.timer_remain = result.get('timer_remain')
                # notification
                if not dev.init:
                    dev.publish_mqtt()
                    dev.init = True
                if dev.state != dev.state_prev or dev.rotation_speed != dev.rotation_speed_prev:
                    dev.publish_mqtt()
                dev.state_prev = dev.state
                dev.rotation_speed_prev = dev.rotation_speed
            elif dev_type == 'light':
                room_idx = result.get('room_index')
                room = self.getRoomObjectByIndex(room_idx)
                if room is not None:
                    index = result.get('index')
                    if index < room.light_count:
                        dev = room.lights[index]
                        dev.state = result.get('state')
                        # notification
                        if not dev.init:
                            dev.publish_mqtt()
                            dev.init = True
                        if dev.state != dev.state_prev:
                            dev.publish_mqtt()
                        dev.state_prev = dev.state
            elif dev_type == 'outlet':
                room_idx = result.get('room_index')
                room = self.getRoomObjectByIndex(room_idx)
                if room is not None:
                    index = result.get('index')
                    if index < room.outlet_count:
                        dev = room.outlets[index]
                        dev.state = result.get('state')
                        dev.measurement = result.get('consumption')
                        # notification
                        if not dev.init:
                            dev.publish_mqtt()
                            dev.init = True
                        if int(dev.measurement) != int(dev.measurement_prev):
                            dev.publish_mqtt()
                        dev.measurement_prev = dev.measurement
            elif dev_type == 'elevator':
                dev = self.elevator
                dev.state = result.get('state')
                dev.current_floor = result.get('current_floor')
                # notification
                if not dev.init:
                    dev.publish_mqtt()
                    dev.init = True
                if dev.state != dev.state_prev:
                    dev.publish_mqtt()
                if dev.current_floor != dev.current_floor_prev:
                    writeLog(f'Elevator Current Floor: {dev.current_floor}', self)
                    if dev.notify_floor:
                        dev.publish_mqtt_floor()
                dev.state_prev = dev.state
                dev.current_floor_prev = dev.current_floor
        except Exception as e:
            writeLog('handlePacketParseResult::Exception::{} ({})'.format(e, result), self)

    def onParserEnergyRawPacket(self, packet: bytearray):
        if len(self.packets_energy) > self.max_packet_log_cnt:
            self.packets_energy = self.packets_energy[1:]
        self.packets_energy.append(packet)

    def onParserControlRawPacket(self, packet: bytearray):
        if len(self.packets_control) > self.max_packet_log_cnt:
            self.packets_control = self.packets_control[1:]
        self.packets_control.append(packet)

    def onParserSmartRecvRawPacket(self, packet: bytearray):
        if len(self.packets_smart_recv) > self.max_packet_log_cnt:
            self.packets_smart_recv = self.packets_smart_recv[1:]
        self.packets_smart_recv.append(packet)

    def onParserSmartSendRawPacket(self, packet: bytearray):
        if len(self.packets_smart_send) > self.max_packet_log_cnt:
            self.packets_smart_send = self.packets_smart_send[1:]
        self.packets_smart_send.append(packet)

    def command(self, **kwargs):
        # writeLog('Command::{}'.format(kwargs), self)
        try:
            dev = kwargs['device']
            if isinstance(dev, Light) or isinstance(dev, Outlet):
                kwargs['parser'] = self.parser_energy
            elif isinstance(dev, Thermostat):
                kwargs['parser'] = self.parser_control
            elif isinstance(dev, Ventilator):
                kwargs['parser'] = self.parser_control
            elif isinstance(dev, GasValve):
                kwargs['parser'] = self.parser_control
            elif isinstance(dev, Elevator):
                kwargs['parser'] = self.parser_smart_recv
        except Exception as e:
            writeLog('command Exception::{}'.format(e), self)
        self.queue_command.put(kwargs)

    def callElevatorByParser(self, updown: int, timestamp: int):
        self.parser_smart_send.sendCallElevatorPacket(updown, timestamp)

    def callElevatorUp(self):
        self.parser_smart_recv.setFlagCallUp()

    def callElevatorDown(self):
        self.parser_smart_recv.setFlagCallDown()

    @property
    def enable_log_control_28(self) -> bool:
        return self._enable_log_control_28

    @enable_log_control_28.setter
    def enable_log_control_28(self, value: bool):
        self._enable_log_control_28 = value
        self.parser_control.enable_log_header_28 = value
    
    @property
    def enable_log_control_31(self) -> bool:
        return self._enable_log_control_31

    @enable_log_control_31.setter
    def enable_log_control_31(self, value: bool):
        self._enable_log_control_31 = value
        self.parser_control.enable_log_header_31 = value
    
    @property
    def enable_log_control_61(self) -> bool:
        return self._enable_log_control_61

    @enable_log_control_61.setter
    def enable_log_control_61(self, value: bool):
        self._enable_log_control_61 = value
        self.parser_control.enable_log_header_61 = value

    @property
    def enable_log_energy_31(self) -> bool:
        return self._enable_log_energy_31

    @enable_log_energy_31.setter
    def enable_log_energy_31(self, value: bool):
        self._enable_log_energy_31 = value
        self.parser_energy.enable_log_header_31 = value

    @property
    def enable_log_energy_41(self) -> bool:
        return self._enable_log_energy_41

    @enable_log_energy_41.setter
    def enable_log_energy_41(self, value: bool):
        self._enable_log_energy_41 = value
        self.parser_energy.enable_log_header_41 = value

    @property
    def enable_log_energy_42(self) -> bool:
        return self._enable_log_energy_42

    @enable_log_energy_42.setter
    def enable_log_energy_42(self, value: bool):
        self._enable_log_energy_42 = value
        self.parser_energy.enable_log_header_42 = value

    @property
    def enable_log_energy_d1(self) -> bool:
        return self._enable_log_energy_d1

    @enable_log_energy_d1.setter
    def enable_log_energy_d1(self, value: bool):
        self._enable_log_energy_d1 = value
        self.parser_energy.enable_log_header_d1 = value

    @property
    def enable_log_energy_room_1(self) -> bool:
        return self._enable_log_energy_room_1

    @enable_log_energy_room_1.setter
    def enable_log_energy_room_1(self, value: bool):
        self._enable_log_energy_room_1 = value
        self.parser_energy.enable_log_room_1 = value

    @property
    def enable_log_energy_room_2(self) -> bool:
        return self._enable_log_energy_room_2

    @enable_log_energy_room_2.setter
    def enable_log_energy_room_2(self, value: bool):
        self._enable_log_energy_room_2 = value
        self.parser_energy.enable_log_room_2 = value
    
    @property
    def enable_log_energy_room_3(self) -> bool:
        return self._enable_log_energy_room_3

    @enable_log_energy_room_3.setter
    def enable_log_energy_room_3(self, value: bool):
        self._enable_log_energy_room_3 = value
        self.parser_energy.enable_log_room_3 = value

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
 