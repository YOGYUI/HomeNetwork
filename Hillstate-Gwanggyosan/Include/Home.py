import time
import json
import queue
from typing import List, Union
import paho.mqtt.client as mqtt
import xml.etree.ElementTree as ET
from Define import *
from Room import *
from Threads import *
from RS485 import *


class Home:
    name: str = 'Home'
    device_list: List[Device]
    rooms: List[Room]
    gasvalve: GasValve
    ventilator: Ventilator
    elevator: Elevator

    serial_baud: int = 9600

    thread_cmd_queue: Union[ThreadCommandQueue, None] = None
    thread_parse_result_queue: Union[ThreadParseResultQueue, None] = None
    thread_timer: Union[ThreadTimer, None] = None
    queue_command: queue.Queue
    queue_parse_result: queue.Queue

    mqtt_client: mqtt.Client
    mqtt_host: str = '127.0.0.1'
    mqtt_port: int = 1883
    mqtt_is_connected: bool = False
    enable_mqtt_console_log: bool = True

    serial_list: List[SerialComm]
    parser_list: List[SerialParser]

    def __init__(self, name: str = 'Home', init_service: bool = True):
        self.name = name
        self.device_list = list()
        self.rooms = list()
        self.queue_command = queue.Queue()
        self.queue_parse_result = queue.Queue()
        self.serial_list = list()
        self.parser_list = list()

        self.serial_port_light: str = ''
        self.serial_light = SerialComm('Light')
        self.serial_list.append(self.serial_light)
        self.parser_light = ParserLight(self.serial_light)
        self.parser_light.sig_parse_result.connect(self.onParsePacketResult)
        self.parser_list.append(self.parser_light)

        self.serial_port_various: str = ''
        self.serial_various = SerialComm('Various')
        self.serial_list.append(self.serial_various)
        self.parser_various = ParserVarious(self.serial_various)
        self.parser_various.sig_parse_result.connect(self.onParsePacketResult)
        self.parser_list.append(self.parser_various)

        self.initialize(init_service, False)
    
    def initialize(self, init_service: bool, connect_serial: bool):
        self.device_list.clear()
        self.rooms.clear()

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.onMqttClientConnect
        self.mqtt_client.on_disconnect = self.onMqttClientDisconnect
        self.mqtt_client.on_subscribe = self.onMqttClientSubscribe
        self.mqtt_client.on_unsubscribe = self.onMqttClientUnsubscribe
        self.mqtt_client.on_publish = self.onMqttClientPublish
        self.mqtt_client.on_message = self.onMqttClientMessage
        self.mqtt_client.on_log = self.onMqttClientLog

        curpath = os.path.dirname(os.path.abspath(__file__))  # {$PROJECT}/include/
        projpath = os.path.dirname(curpath)  # {$PROJECT}/
        xml_path = os.path.join(projpath, 'config.xml')

        self.initRoomsFromConfig(xml_path)
        self.gasvalve = GasValve(name='Gas Valve', mqtt_client=self.mqtt_client)
        self.ventilator = Ventilator(name='Ventilator', mqtt_client=self.mqtt_client)
        self.elevator = Elevator(name='Elevator', mqtt_client=self.mqtt_client)

        # append device list
        for room in self.rooms:
            self.device_list.extend(room.getDevices())
        self.device_list.append(self.gasvalve)
        self.device_list.append(self.ventilator)
        self.device_list.append(self.elevator)
        
        self.loadConfig(xml_path)

        if init_service:
            self.startThreadCommandQueue()
            self.startThreadParseResultQueue()
            self.startThreadTimer()
            try:
                self.mqtt_client.connect(self.mqtt_host, self.mqtt_port)
            except Exception as e:
                writeLog('MQTT Connection Error: {}'.format(e), self)
            self.mqtt_client.loop_start()
        
        if connect_serial:
            self.initSerialConnection()

        writeLog(f'Initialized <{self.name}>', self)

    def release(self):
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        del self.mqtt_client

        self.stopThreadCommandQueue()
        self.stopThreadParseResultQueue()
        self.stopThreadTimer()

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
                name = child.find('name').text
                index = int(child.find('index').text)
                tag_lights = child.find('lights')
                light_count = len(list(tag_lights))
                tag_outlets = child.find('outlets')
                outlet_count = len(list(tag_outlets))
                tag_thermostat = child.find('thermostat')
                tag_has_thermostat = tag_thermostat.find('exist')
                has_thermostat = bool(int(tag_has_thermostat.text))
                tag_airconditioner = child.find('airconditioner')
                tag_has_airconditioner = tag_airconditioner.find('exist')
                has_airconditioner = bool(int(tag_has_airconditioner.text))
                room = Room(
                    name=name,
                    index=index,
                    light_count=light_count,
                    outlet_count=outlet_count,
                    has_thermostat=has_thermostat,
                    has_airconditioner=has_airconditioner,
                    mqtt_client=self.mqtt_client
                )
                self.rooms.append(room)
            except Exception as e:
                writeLog(f"Failed to initializing room <{child.tag}> ({e})", self)
        writeLog(f'Initializing Room Finished ({len(self.rooms)})', self)

    def initSerialConnection(self):
        self.serial_light.connect(self.serial_port_light, self.serial_baud)
        self.serial_various.connect(self.serial_port_various, self.serial_baud)

    def loadConfig(self, filepath: str):
        if not os.path.isfile(filepath):
            return
        root = ET.parse(filepath).getroot()

        node = root.find('serial')
        try:
            self.serial_port_light = node.find('port_light').text
            self.serial_port_various = node.find('port_various').text
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
        
        node = root.find('rooms')
        try:
            for room in self.rooms:
                room_node = node.find('room{}'.format(room.index))
                if room_node is not None:
                    lights_node = room_node.find('lights')
                    if lights_node is not None:
                        for j in range(room.light_count):
                            light_node = lights_node.find(f'light{j + 1}')
                            if light_node is not None:
                                room.lights[j].name = light_node.find('name').text
                                mqtt_node = light_node.find('mqtt')
                                room.lights[j].mqtt_publish_topic = mqtt_node.find('publish').text
                                room.lights[j].mqtt_subscribe_topics.append(mqtt_node.find('subscribe').text)
                    outlets_node = room_node.find('outlets')
                    if outlets_node is not None:
                        for j in range(room.outlet_count):
                            outlet_node = outlets_node.find(f'outlet{j + 1}')
                            if outlet_node is not None:
                                room.outlets[j].name = outlet_node.find('name').text
                                mqtt_node = outlet_node.find('mqtt')
                                room.outlets[j].mqtt_publish_topic = mqtt_node.find('publish').text
                                room.outlets[j].mqtt_subscribe_topics.append(mqtt_node.find('subscribe').text)
                    thermostat_node = room_node.find('thermostat')
                    if thermostat_node is not None:
                        range_min_node = thermostat_node.find('range_min')
                        range_min = int(range_min_node.text)
                        range_max_node = thermostat_node.find('range_max')
                        range_max = int(range_max_node.text)
                        mqtt_node = thermostat_node.find('mqtt')
                        if room.has_thermostat:
                            room.thermostat.setTemperatureRange(range_min, range_max)
                            room.thermostat.mqtt_publish_topic = mqtt_node.find('publish').text
                            room.thermostat.mqtt_subscribe_topics.append(mqtt_node.find('subscribe').text)
                    airconditioner_node = room_node.find('airconditioner')
                    if airconditioner_node is not None:
                        range_min_node = airconditioner_node.find('range_min')
                        range_min = int(range_min_node.text)
                        range_max_node = airconditioner_node.find('range_max')
                        range_max = int(range_max_node.text)
                        mqtt_node = airconditioner_node.find('mqtt')
                        if room.has_airconditioner:
                            room.airconditioner.setTemperatureRange(range_min, range_max)
                            room.airconditioner.mqtt_publish_topic = mqtt_node.find('publish').text
                            room.airconditioner.mqtt_subscribe_topics.append(mqtt_node.find('subscribe').text)
                else:
                    writeLog(f"Failed to find room{room.index} node", self)        
        except Exception as e:
            writeLog(f"Failed to load room config ({e})", self)
        
        node = root.find('gasvalve')
        try:
            mqtt_node = node.find('mqtt')
            self.gasvalve.mqtt_publish_topic = mqtt_node.find('publish').text
            self.gasvalve.mqtt_subscribe_topics.append(mqtt_node.find('subscribe').text)
        except Exception as e:
            writeLog(f"Failed to load gas valve config ({e})", self)
        
        node = root.find('ventilator')
        try:
            mqtt_node = node.find('mqtt')
            self.ventilator.mqtt_publish_topic = mqtt_node.find('publish').text
            self.ventilator.mqtt_subscribe_topics.append(mqtt_node.find('subscribe').text)
        except Exception as e:
            writeLog(f"Failed to load ventilator config ({e})", self)      

        node = root.find('elevator')
        try:
            mqtt_node = node.find('mqtt')
            self.elevator.mqtt_publish_topic = mqtt_node.find('publish').text
            self.elevator.mqtt_subscribe_topics.append(mqtt_node.find('subscribe').text)
        except Exception as e:
            writeLog(f"Failed to load elevator config ({e})", self)  

    def getRoomObjectByIndex(self, index: int) -> Union[Room, None]:
        find = list(filter(lambda x: x.index == index, self.rooms))
        if len(find) == 1:
            return find[0]
        return None

    def startThreadCommandQueue(self):
        if self.thread_cmd_queue is None:
            self.thread_cmd_queue = ThreadCommandQueue(self.queue_command)
            self.thread_cmd_queue.sig_terminated.connect(self.onThreadCommandQueueTerminated)
            self.thread_cmd_queue.setDaemon(True)
            self.thread_cmd_queue.start()

    def stopThreadCommandQueue(self):
        if self.thread_cmd_queue is not None:
            self.thread_cmd_queue.stop()

    def onThreadCommandQueueTerminated(self):
        del self.thread_cmd_queue
        self.thread_cmd_queue = None
    
    def startThreadParseResultQueue(self):
        if self.thread_parse_result_queue is None:
            self.thread_parse_result_queue = ThreadParseResultQueue(self.queue_parse_result)
            self.thread_parse_result_queue.sig_get.connect(self.handleSerialParseResult)
            self.thread_parse_result_queue.sig_terminated.connect(self.onThreadParseResultQueueTerminated)
            self.thread_parse_result_queue.setDaemon(True)
            self.thread_parse_result_queue.start()
    
    def stopThreadParseResultQueue(self):
        if self.thread_parse_result_queue is not None:
            self.thread_parse_result_queue.stop()

    def onThreadParseResultQueueTerminated(self):
        del self.thread_parse_result_queue
        self.thread_parse_result_queue = None

    def startThreadTimer(self):
        if self.thread_timer is None:
            self.thread_timer = ThreadTimer(self.serial_list)
            self.thread_timer.sig_terminated.connect(self.onThreadTimerTerminated)
            self.thread_timer.sig_publish_regular.connect(self.publish_all)
            self.thread_timer.setDaemon(True)
            self.thread_timer.start()

    def stopThreadTimer(self):
        if self.thread_timer is not None:
            self.thread_timer.stop()
    
    def onThreadTimerTerminated(self):
        del self.thread_timer
        self.thread_timer = None

    def publish_all(self):
        for dev in self.device_list:
            try:
                dev.publish_mqtt()
            except ValueError as e:
                writeLog(f'{e}: {dev}, {dev.mqtt_publish_topic}', self)

    def onParsePacketResult(self, result: dict):
        self.queue_parse_result.put(result)

    def handleSerialParseResult(self, result: dict):
        try:
            dev_type = result.get('device')
            if dev_type in ['light', 'outlet']:
                room_idx = result.get('room_index')
                dev_idx = result.get('index')
                state = result.get('state')
                room_obj = self.getRoomObjectByIndex(room_idx)
                if dev_type == 'light':
                    room_obj.lights[dev_idx].setState(state)
                elif dev_type == 'outlet':
                    room_obj.outlets[dev_idx].setState(state)
            elif dev_type == 'gasvalve':
                state = result.get('state')
                self.gasvalve.setState(state)
            elif dev_type == 'thermostat':
                room_idx = result.get('room_index')
                room_obj = self.getRoomObjectByIndex(room_idx)
                if room_obj.has_thermostat:
                    state = result.get('state')
                    temp_current = result.get('temp_current')
                    temp_config = result.get('temp_config')
                    room_obj.thermostat.setState(
                        state, 
                        temp_current=temp_current, 
                        temp_config=temp_config
                    )
            elif dev_type == 'ventilator':
                state = result.get('state')
                rotation_speed = result.get('rotation_speed')
                self.ventilator.setState(state, rotation_speed=rotation_speed)
            elif dev_type == 'airconditioner':
                room_idx = result.get('room_index')
                room_obj = self.getRoomObjectByIndex(room_idx)
                if room_obj.has_airconditioner:
                    state = result.get('state')
                    temp_current = result.get('temp_current')
                    temp_config = result.get('temp_config')
                    mode = result.get('mode')
                    rotation_speed = result.get('rotation_speed')
                    room_obj.airconditioner.setState(
                        state,
                        temp_current=temp_current, 
                        temp_config=temp_config,
                        mode=mode,
                        rotation_speed=rotation_speed
                    )
            elif dev_type == 'elevator':
                state = result.get('state')
                arrived = result.get('arrived')
                current_floor = result.get('current_floor')
                self.elevator.setState(
                    state, 
                    arrived=arrived,
                    current_floor=current_floor
                )
        except Exception as e:
            writeLog('handleSerialParseResult::Exception::{} ({})'.format(e, result), self)

    def command(self, **kwargs):
        try:
            dev = kwargs['device']
            if isinstance(dev, Light):
                kwargs['parser'] = self.parser_light
            elif isinstance(dev, Outlet):
                kwargs['parser'] = self.parser_light
            elif isinstance(dev, GasValve):
                kwargs['parser'] = self.parser_various
            elif isinstance(dev, Thermostat):
                kwargs['parser'] = self.parser_various
            elif isinstance(dev, Ventilator):
                kwargs['parser'] = self.parser_various
            elif isinstance(dev, AirConditioner):
                kwargs['parser'] = self.parser_various
            elif isinstance(dev, Elevator):
                kwargs['parser'] = self.parser_various
        except Exception as e:
            writeLog('command Exception::{}'.format(e), self)
        self.queue_command.put(kwargs)

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
        사용자에 의한 명령 MQTT 토픽 핸들링
        """
        if self.enable_mqtt_console_log:
            writeLog('Mqtt Client Message: {}, {}'.format(userdata, message), self)
        topic = message.topic
        msg_dict = json.loads(message.payload.decode("utf-8"))
        if 'system/command' == topic:
            self.onMqttCommandSystem(topic, msg_dict)
        if 'light/command' in topic:
            self.onMqttCommandLight(topic, msg_dict)
        if 'outlet/command' in topic:
            self.onMqttCommandOutlet(topic, msg_dict)
        if 'gasvalve/command' in topic:
            self.onMqttCommandGasvalve(topic, msg_dict)
        if 'thermostat/command' in topic:
            self.onMqttCommandThermostat(topic, msg_dict)
        if 'ventilator/command' in topic:
            self.onMqttCommandVentilator(topic, msg_dict)
        if 'airconditioner/command' in topic:
            self.onMqttCommandAirconditioner(topic, msg_dict)
        if 'elevator/command' in topic:
            self.onMqttCommandElevator(topic, msg_dict)

    def onMqttClientLog(self, _, userdata, level, buf):
        if self.enable_mqtt_console_log:
            writeLog('Mqtt Client Log: {}, {}, {}'.format(userdata, level, buf), self)

    def onMqttClientSubscribe(self, _, userdata, mid, granted_qos):
        if self.enable_mqtt_console_log:
            writeLog('Mqtt Client Subscribe: {}, {}, {}'.format(userdata, mid, granted_qos), self)

    def onMqttClientUnsubscribe(self, _, userdata, mid):
        if self.enable_mqtt_console_log:
            writeLog('Mqtt Client Unsubscribe: {}, {}'.format(userdata, mid), self)

    def onMqttCommandSystem(self, topic: str, message: dict):
        if 'query_all' in message.keys():
            writeLog('Got query all command', self)
            self.publish_all()
        if 'restart' in message.keys():
            writeLog('Got restart command', self)
            self.restart()
        if 'reboot' in message.keys():
            import os
            os.system('sudo reboot')
        if 'publish_interval' in message.keys():
            try:
                interval = message['publish_interval']
                self.thread_timer.setMqttPublishInterval(interval)
            except Exception:
                pass
        if 'send_packet' in message.keys():
            try:
                ser_idx = message.get('index')
                packet_str = message.get('packet')
                packet = bytearray([int(x, 16) for x in packet_str.split(' ')])
                self.serial_list[ser_idx].sendData(packet)
            except Exception:
                pass

    def onMqttCommandLight(self, topic: str, message: dict):
        splt = topic.split('/')
        room_idx = int(splt[-2])
        dev_idx = int(splt[-1]) - 1
        room = self.getRoomObjectByIndex(room_idx)
        if room is not None:
            if 'state' in message.keys():
                self.command(
                    device=room.lights[dev_idx],
                    category='state',
                    target=message['state']
                )

    def onMqttCommandOutlet(self, topic: str, message: dict):
        splt = topic.split('/')
        room_idx = int(splt[-2])
        dev_idx = int(splt[-1]) - 1
        room = self.getRoomObjectByIndex(room_idx)
        if room is not None:
            if 'state' in message.keys():
                self.command(
                    device=room.outlets[dev_idx],
                    category='state',
                    target=message['state']
                )

    def onMqttCommandGasvalve(self, topic: str, message: dict):
        if 'state' in message.keys():
            self.command(
                device=self.gasvalve,
                category='state',
                target=message['state']
            )

    def onMqttCommandThermostat(self, topic: str, message: dict):
        splt = topic.split('/')
        room_idx = int(splt[-1])
        room = self.getRoomObjectByIndex(room_idx)
        if room is not None and room.has_thermostat:
            if 'state' in message.keys():
                self.command(
                    device=room.thermostat,
                    category='state',
                    target=message['state']
                )
            if 'targetTemperature' in message.keys():
                self.command(
                    device=room.thermostat,
                    category='temperature',
                    target=message['targetTemperature']
                )

    def onMqttCommandVentilator(self, topic: str, message: dict):
        if 'state' in message.keys():
            self.command(
                device=self.ventilator,
                category='state',
                target=message['state']
            )
        if 'rotationspeed' in message.keys():
            if self.ventilator.state == 1:
                # 전원이 켜져있을 경우에만 풍량설정 가능하도록..
                # 최초 전원 ON시 풍량 '약'으로 설정!
                self.command(
                    device=self.ventilator,
                    category='rotationspeed',
                    target=message['rotationspeed']
                )

    def onMqttCommandAirconditioner(self, topic: str, message: dict):
        splt = topic.split('/')
        room_idx = int(splt[-1])
        room = self.getRoomObjectByIndex(room_idx)
        if room is not None and room.has_airconditioner:
            if 'active' in message.keys():
                self.command(
                    device=room.airconditioner,
                    category='active',
                    target=message['active']
                )
            if 'targetTemperature' in message.keys():
                self.command(
                    device=room.airconditioner,
                    category='temperature',
                    target=message['targetTemperature']
                )
            if 'rotationspeed' in message.keys():
                self.command(
                    device=room.airconditioner,
                    category='rotationspeed',
                    target=message['rotationspeed']
                )
            if 'rotationspeed_name' in message.keys():  # for HA
                speed_dict = {'Max': 100, 'Medium': 75, 'Min': 50, 'Auto': 25}
                target = speed_dict[message['rotationspeed_name']]
                self.command(
                    device=room.airconditioner,
                    category='rotationspeed',
                    target=target
                )

    def onMqttCommandElevator(self, topic: str, message: dict):
        if 'state' in message.keys():
            self.command(
                device=self.elevator,
                category='state',
                target=message['state']
            )


home_: Union[Home, None] = None


def get_home(name: str = '') -> Home:
    global home_
    if home_ is None:
        home_ = Home(name=name)
    return home_


if __name__ == "__main__":
    home_obj = get_home('hillstate')
    home_obj.initSerialConnection()
    
    def loop():
        sysin = sys.stdin.readline()
        try:
            head = int(sysin.split('\n')[0])
        except Exception:
            loop()
            return
        
        if head == 0:
            pass
        else:
            os.system('clear')
            loop()
    loop()
    home_obj.release()
