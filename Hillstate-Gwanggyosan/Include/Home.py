import os
import time
import json
import queue
import psutil
import traceback
from functools import partial
from typing import List, Union
import paho.mqtt.client as mqtt
import xml.etree.ElementTree as ET
import multiprocessing
from Define import *
from Threads import *
from RS485 import *
from Common import *
from Multiprocess import *
from ThinQ import ThinQ
CURPATH = os.path.dirname(os.path.abspath(__file__))  # {$PROJECT}/include/
PROJPATH = os.path.dirname(CURPATH)  # {$PROJECT}/


class RS485Info:
    rs485: RS485Comm = None
    config: RS485Config = None
    parser: PacketParser = None
    index: int = 0

    def __init__(self, rs485: RS485Comm, config: RS485Config, parser: PacketParser, index: int):
        self.rs485 = rs485
        self.config = config
        self.parser = parser
        self.index = index

    def __repr__(self) -> str:
        repr_txt = f'<{self.parser.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += f' Index: {self.index}'
        repr_txt += '>'
        return repr_txt

    def release(self):
        if self.rs485 is not None:
            self.rs485.release()
        if self.parser is not None:
            self.parser.release()


class Home:
    name: str = 'Home'
    device_list: List[Device]
    thinq: ThinQ = None

    thread_cmd_queue: Union[ThreadCommandQueue, None] = None
    thread_parse_result_queue: Union[ThreadParseResultQueue, None] = None
    thread_timer: Union[ThreadTimer, None] = None
    thread_energy_monitor: Union[ThreadEnergyMonitor, None] = None
    queue_command: queue.Queue
    queue_parse_result: queue.Queue

    mqtt_client: mqtt.Client
    mqtt_host: str = '127.0.0.1'
    mqtt_port: int = 1883
    mqtt_is_connected: bool = False
    enable_mqtt_console_log: bool = True
    verbose_mqtt_regular_publish: dict

    rs485_info_list: List[RS485Info]
    rs485_reconnect_limit: int = 60
    parser_mapping: dict

    enable_subphone: bool = True
    mp_ffserver: Union[multiprocessing.Process, None] = None
    pid_ffserver_proc: int = 0
    mp_ffmpeg: Union[multiprocessing.Process, None] = None
    pid_ffmpeg_proc: int = 0

    hems_info: dict
    enable_hems: bool = False
    topic_hems_publish: str = ''

    discover_device: bool = False
    discovered_dev_list: List[Device]

    def __init__(self, name: str = 'Home', init_service: bool = True):
        self.name = name
        self.device_list = list()
        self.discovered_dev_list = list()
        self.queue_command = queue.Queue()
        self.queue_parse_result = queue.Queue()
        self.rs485_info_list = list()
        self.parser_mapping = {
            Light: 0,
            Outlet: 0,
            GasValve: 0,
            Thermostat: 0,
            Ventilator: 0,
            AirConditioner: 0,
            Elevator: 0,
            SubPhone: 0,
            BatchOffSwitch: 0
        }
        self.hems_info = dict()
        self.initialize(init_service, False)
    
    def initialize(self, init_service: bool, connect_rs485: bool):
        self.initMQTT()
        self.loadConfig()
        self.initDevices()

        if init_service:
            self.startThreadCommandQueue()
            self.startThreadParseResultQueue()
            self.startThreadTimer()
            try:
                self.mqtt_client.connect(self.mqtt_host, self.mqtt_port)
            except Exception as e:
                writeLog('MQTT Connection Error: {}'.format(e), self)
            self.mqtt_client.loop_start()
            if self.thinq is not None:
                self.thinq.start()
        if self.enable_subphone:
            # 카메라 스트리밍
            self.startFFServer()
            self.startFFMpeg()
            if self.enable_hems:
                self.startThreadEnergyMonitor()
        if connect_rs485:
            self.initRS485Connection()
        writeLog(f'Initialized <{self.name}>', self)

    def initMQTT(self):
        self.mqtt_client = mqtt.Client(client_id="Yogyui_Hillstate_Gwanggyosan")
        self.mqtt_client.on_connect = self.onMqttClientConnect
        self.mqtt_client.on_disconnect = self.onMqttClientDisconnect
        self.mqtt_client.on_subscribe = self.onMqttClientSubscribe
        self.mqtt_client.on_unsubscribe = self.onMqttClientUnsubscribe
        self.mqtt_client.on_publish = self.onMqttClientPublish
        self.mqtt_client.on_message = self.onMqttClientMessage
        self.mqtt_client.on_log = self.onMqttClientLog

    def initDevices(self):
        for dev in self.device_list:
            dev.setMqttClient(self.mqtt_client)
            dev.sig_set_state.connect(partial(self.onDeviceSetState, dev))

    def release(self):
        if self.enable_subphone:
            self.stopThreadEnergyMonitor()
            self.stopFFMpeg()
            self.stopFFServer()
        
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        del self.mqtt_client

        if self.thinq is not None:
            self.thinq.release()
            del self.thinq

        self.stopThreadCommandQueue()
        self.stopThreadParseResultQueue()
        self.stopThreadTimer()

        for elem in self.rs485_info_list:
            elem.release()
        for dev in self.device_list:
            dev.release()
        
        self.hems_info.clear()
        writeLog(f'Released', self)
    
    def restart(self):
        self.release()
        print('... restarting ...')
        time.sleep(5)
        self.initialize(True, True)

    @staticmethod
    def splitTopicText(text: str) -> List[str]:
        topics = text.split('\n')
        topics = [x.replace(' ', '') for x in topics]
        topics = [x.replace('\t', '') for x in topics]
        topics = list(filter(lambda x: len(x) > 0, topics))
        return topics

    def loadConfig(self):
        xml_path = os.path.join(PROJPATH, 'config.xml')
        if not os.path.isfile(xml_path):
            return
        root = ET.parse(xml_path).getroot()

        node = root.find('rs485')
        try:
            self.rs485_reconnect_limit = int(node.find('reconnect_limit').text)
            self.rs485_info_list.clear()
            for cnode in list(node):
                if cnode.tag != 'port':
                    continue
                try:
                    name = cnode.find('name').text.upper()
                    index = int(cnode.find('index').text)
                    enable = bool(int(cnode.find('enable').text))
                    hwtype = int(cnode.find('hwtype').text)
                    packettype = int(cnode.find('packettype').text)
                    usb2serial_node = cnode.find('usb2serial')
                    ew11_node = cnode.find('ew11')
                    check = bool(int(cnode.find('check').text))
                    buffsize = int(cnode.find('buffsize').text)

                    cfg = RS485Config()
                    cfg.enable = enable
                    cfg.comm_type = RS485HwType(hwtype)
                    cfg.serial_port = usb2serial_node.find('port').text
                    cfg.serial_baud = int(usb2serial_node.find('baud').text)
                    cfg.serial_databit = int(usb2serial_node.find('databit').text)
                    cfg.serial_parity = usb2serial_node.find('parity').text
                    cfg.serial_stopbits = float(usb2serial_node.find('stopbits').text)
                    cfg.socket_ipaddr = ew11_node.find('ipaddr').text
                    cfg.socket_port = int(ew11_node.find('port').text)
                    cfg.check_connection = check
                    rs485 = RS485Comm(f'RS485-{name}')
                    if name.lower() == 'subphone':
                        rs485.sig_connected.connect(self.onRS485SubPhoneConnected)
                    parser = PacketParser(rs485, name, ParserType(packettype))
                    parser.setBufferSize(buffsize)
                    parser.sig_parse_result.connect(lambda x: self.queue_parse_result.put(x))
                    self.rs485_info_list.append(RS485Info(rs485, cfg, parser, index))
                    writeLog(f"Create RS485 Instance (name: {name})")
                except Exception as e:
                    writeLog(f"Failed to load rs485 config ({e})", self)
                    continue
            self.rs485_info_list.sort(key=lambda x: x.index)
        except Exception as e:
            writeLog(f"Failed to load rs485 config ({e})", self)

        node = root.find('mqtt')
        try:
            username = node.find('username').text
            password = node.find('password').text
            self.mqtt_host = node.find('host').text
            self.mqtt_port = int(node.find('port').text)
            self.mqtt_client.username_pw_set(username, password)
            self.enable_mqtt_console_log = bool(int(node.find('console_log').text))
            verbose_node = node.find('verbose_regular_publish')
            self.verbose_mqtt_regular_publish = dict()
            self.verbose_mqtt_regular_publish['enable'] = bool(int(verbose_node.find('enable').text))
            self.verbose_mqtt_regular_publish['interval'] = int(verbose_node.find('interval').text)
        except Exception as e:
            writeLog(f"Failed to load mqtt config ({e})", self)
        
        self.device_list.clear()
        node = root.find('device')
        try:
            parser_mapping_node = node.find('parser_mapping')
            self.parser_mapping[Light] = int(parser_mapping_node.find('light').text)
            self.parser_mapping[Outlet] = int(parser_mapping_node.find('outlet').text)
            self.parser_mapping[GasValve] = int(parser_mapping_node.find('gasvalve').text)
            self.parser_mapping[Thermostat] = int(parser_mapping_node.find('thermostat').text)
            self.parser_mapping[Ventilator] = int(parser_mapping_node.find('ventilator').text)
            self.parser_mapping[AirConditioner] = int(parser_mapping_node.find('airconditioner').text)
            self.parser_mapping[Elevator] = int(parser_mapping_node.find('elevator').text)
            self.parser_mapping[SubPhone] = int(parser_mapping_node.find('subphone').text)
            self.parser_mapping[BatchOffSwitch] = int(parser_mapping_node.find('batchoffsw').text)

            list_node = node.find('list')
            for dev_node in list(list_node):
                try:
                    name = dev_node.find('name').text
                    index = int(dev_node.find('index').text)
                    room = int(dev_node.find('room').text)
                    device: Device = None
                    if dev_node.tag.lower() == 'light':
                        device = Light(name, index, room)
                    elif dev_node.tag.lower() == 'airquality':
                        device = AirqualitySensor(name, index, room)
                        apikey = dev_node.find('apikey').text
                        obsname = dev_node.find('obsname').text
                        device.setApiParams(apikey, obsname)
                    if device is not None:
                        mqtt_node = dev_node.find('mqtt')
                        if mqtt_node is not None:
                            device.setMqttPublishTopic(mqtt_node.find('publish').text)
                            device.setMqttSubscribeTopic(mqtt_node.find('subscribe').text)
                        self.device_list.append(device)
                except Exception as e:
                    writeLog(f"Failed to load device entry ({e})", self)
                    continue
        except Exception as e:
            writeLog(f"Failed to load device config ({e})", self)

        node = root.find('hems')
        try:
            self.enable_hems = bool(int(node.find('enable').text))
            mqtt_node = node.find('mqtt')
            self.topic_hems_publish = mqtt_node.find('publish').text
        except Exception as e:
            writeLog(f"Failed to load HEMS config ({e})", self)  

        node = root.find('thinq')
        try:
            enable = bool(int(node.find('enable').text))
            robot_cleaner_node = node.find('robot_cleaner')
            robot_cleaner_dev_id = robot_cleaner_node.find('dev_id').text
            mqtt_node = node.find('mqtt')
            mqtt_topic = mqtt_node.find('publish').text
            log_mqtt_message = bool(int(mqtt_node.find('log_message').text))
            if enable:
                self.thinq = ThinQ(
                    country_code=node.find('country_code').text,
                    language_code=node.find('language_code').text,
                    api_key=node.find('api_key').text,
                    api_client_id=node.find('api_client_id').text,
                    refresh_token=node.find('refresh_token').text,
                    oauth_secret_key=node.find('oauth_secret_key').text,
                    app_client_id=node.find('app_client_id').text,
                    app_key=node.find('application_key').text,
                    robot_cleaner_dev_id=robot_cleaner_dev_id, 
                    mqtt_topic=mqtt_topic,
                    log_mqtt_message=log_mqtt_message
                )
                self.thinq.sig_publish_mqtt.connect(self.onThinqPublishMQTT)
        except Exception as e:
            writeLog(f"Failed to load thinq config ({e})", self)
            traceback.print_exc()

    def initRS485Connection(self):
        for elem in self.rs485_info_list:
            cfg = elem.config
            rs485 = elem.rs485
            name = elem.parser.name
            try:
                if cfg.enable:
                    rs485.setType(cfg.comm_type)
                    if cfg.comm_type == RS485HwType.Serial:
                        port, baud = cfg.serial_port, cfg.serial_baud
                        databit, parity, stopbits = cfg.serial_databit, cfg.serial_parity, cfg.serial_stopbits
                        rs485.connect(port, baud, bytesize=databit, parity=parity, stopbits=stopbits)
                    elif cfg.comm_type == RS485HwType.Socket:
                        ipaddr, port = cfg.socket_ipaddr, cfg.socket_port
                        rs485.connect(ipaddr, port)
                else:
                    writeLog(f"rs485 '{name}' is disabled", self)
            except Exception as e:
                writeLog(f"Failed to initialize '{name}' rs485 connection ({e})", self)
                continue
        
        if self.thread_timer is not None:
            self.thread_timer.set_home_initialized()

    def onRS485SubPhoneConnected(self):
        if self.thread_energy_monitor is not None:
            self.thread_energy_monitor.set_home_initialized()

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
            self.thread_parse_result_queue.sig_get.connect(self.handlePacketParseResult)
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
            rs485_obj_list = []
            for elem in self.rs485_info_list:
                rs485 = elem.rs485
                config = elem.config
                if config.enable and config.check_connection:
                    rs485_obj_list.append(rs485)
            self.thread_timer = ThreadTimer(
                rs485_obj_list,
                reconnect_limit_sec=self.rs485_reconnect_limit,
                verbose_regular_publish=self.verbose_mqtt_regular_publish
            )
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

    def startThreadEnergyMonitor(self):
        if self.thread_energy_monitor is None:
            device = self.getDevice(DeviceType.SUBPHONE, 0, 0)
            if device is not None:
                index = self.parser_mapping.get(SubPhone)
                parser = self.rs485_info_list[index].parser
                self.thread_energy_monitor = ThreadEnergyMonitor(
                    subphone=device, 
                    parser=parser,
                    interval_realtime_ms=5000,
                    interval_regular_ms=60*60*1000
                )
                self.thread_energy_monitor.sig_terminated.connect(self.onThreadEnergyMonitorTerminated)
                self.thread_energy_monitor.setDaemon(True)
                self.thread_energy_monitor.start()
    
    def stopThreadEnergyMonitor(self):
        if self.thread_energy_monitor is not None:
            self.thread_energy_monitor.stop()

    def onThreadEnergyMonitorTerminated(self):
        del self.thread_energy_monitor
        self.thread_energy_monitor = None

    def publish_all(self):
        for dev in self.device_list:
            try:
                dev.publish_mqtt()
            except ValueError as e:
                writeLog(f'{e}: {dev}, {dev.mqtt_publish_topic}', self)

    def handlePacketParseResult(self, result: dict):
        if self.discover_device:
            self.updateDiscoverDeviceList(result)
        else:
            self.updateDeviceState(result)
    
    def getDevice(self, dev_type: DeviceType, index: int, room_index: int) -> Device:
        find = list(filter(lambda x: 
            x.getType() == dev_type and x.getIndex() == index and x.getRoomIndex() == room_index, 
            self.device_list))
        if len(find) == 1:
            return find[0]
        return None

    def updateDeviceState(self, result: dict):
        try:
            dev_type: DeviceType = result.get('device')
            dev_idx: int = result.get('index')
            if dev_idx is None:
                dev_idx = 0
            room_idx: int = result.get('room_index')
            if room_idx is None:
                room_idx = 0
            device = self.getDevice(dev_type, dev_idx, room_idx)
            if device is None:
                # writeLog(f'handlePacketParseResult::Cannot find device ({dev_type}, {dev_idx}, {room_idx})', self)
                return
            
            if dev_type in [DeviceType.LIGHT, DeviceType.OUTLET, DeviceType.GASVALVE, DeviceType.BATCHOFFSWITCH]:
                state = result.get('state')
                device.updateState(state)
            elif dev_type is DeviceType.THERMOSTAT:
                state = result.get('state')
                temp_current = result.get('temp_current')
                temp_config = result.get('temp_config')
                device.updateState(
                    state, 
                    temp_current=temp_current, 
                    temp_config=temp_config
                )
            elif dev_type is DeviceType.VENTILATOR:
                state = result.get('state')
                rotation_speed = result.get('rotation_speed')
                device.updateState(state, rotation_speed=rotation_speed)
            elif dev_type is DeviceType.AIRCONDITIONER:
                state = result.get('state')
                temp_current = result.get('temp_current')
                temp_config = result.get('temp_config')
                mode = result.get('mode')
                rotation_speed = result.get('rotation_speed')
                device.updateState(
                    state,
                    temp_current=temp_current, 
                    temp_config=temp_config,
                    mode=mode,
                    rotation_speed=rotation_speed
                )
            elif dev_type is DeviceType.ELEVATOR:
                state = result.get('state')
                device.updateState(
                    state, 
                    data_type=result.get('data_type'),
                    ev_dev_idx=result.get('ev_dev_idx'),
                    direction=result.get('direction'),
                    floor=result.get('floor')
                )
            elif dev_type is DeviceType.SUBPHONE:
                device.updateState(
                    0, 
                    ringing_front=result.get('ringing_front'),
                    ringing_communal=result.get('ringing_communal'),
                    streaming=result.get('streaming'),
                    doorlock=result.get('doorlock')
                )
            elif dev_type is DeviceType.HEMS:
                result.pop('device')
                self.hems_info['last_recv_time'] = datetime.datetime.now()
                for key in list(result.keys()):
                    self.hems_info[key] = result.get(key)
                    if key in ['electricity_current']:
                        topic = self.topic_hems_publish + f'/{key}'
                        value = result.get(key)
                        """
                        if value == 0:
                            writeLog(f"zero power consumption? >> {prettifyPacket(result.get('packet'))}", self)
                        """
                        self.mqtt_client.publish(topic, json.dumps({"value": value}), 1)
            elif dev_type is DeviceType.DOORLOCK:
                pass
        except Exception as e:
            writeLog('handlePacketParseResult::Exception::{} ({})'.format(e, result), self)

    def command(self, **kwargs):
        try:
            dev = kwargs['device']
            index = self.parser_mapping.get(type(dev))
            info: RS485Info = self.rs485_info_list[index]
            kwargs['parser'] = info.parser
        except Exception as e:
            writeLog('command Exception::{}'.format(e), self)
        self.queue_command.put(kwargs)

    def onDeviceSetState(self, dev: Device, state: int):
        if isinstance(dev, AirConditioner):
            self.command(
                device=dev,
                category='active',
                target=state
            )
        elif isinstance(dev, Thermostat):
            self.command(
                device=dev,
                category='state',
                target='HEAT' if state else 'OFF'
            )

    def startMqttSubscribe(self):
        self.mqtt_client.subscribe('home/command/system')
        for dev in self.device_list:
            self.mqtt_client.subscribe(dev.mqtt_subscribe_topic)
        if self.thinq is not None:
            self.mqtt_client.subscribe('home/command/thinq')

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
        try:
            if self.enable_mqtt_console_log:
                writeLog('Mqtt Client Message: {}, {}'.format(userdata, message), self)
            topic = message.topic
            msg_dict = json.loads(message.payload.decode("utf-8"))
            writeLog(f'MQTT Message: {topic}: {msg_dict}', self)
            if 'command/system' in topic:
                self.onMqttCommandSystem(topic, msg_dict)
            if 'command/light' in topic:
                self.onMqttCommandLight(topic, msg_dict)
            if 'command/outlet' in topic:
                self.onMqttCommandOutlet(topic, msg_dict)
            if 'command/gasvalve' in topic:
                self.onMqttCommandGasvalve(topic, msg_dict)
            if 'command/thermostat' in topic:
                self.onMqttCommandThermostat(topic, msg_dict)
            if 'command/ventilator' in topic:
                self.onMqttCommandVentilator(topic, msg_dict)
            if 'command/airconditioner' in topic:
                self.onMqttCommandAirconditioner(topic, msg_dict)
            if 'command/elevator' in topic:
                self.onMqttCommandElevator(topic, msg_dict)
            if 'command/subphone' in topic:
                self.onMqttCommandSubPhone(topic, msg_dict)
            if 'command/thinq' in topic:
                self.onMqttCommandThinq(topic, msg_dict)
            if 'command/batchoffsw' in topic:
                self.onMqttCommandBatchOffSwitch(topic, msg_dict)
            """
            if 'command/doorlock' in topic:
                self.onMqttCommandDookLock(topic, msg_dict)
            """
        except Exception as e:
            writeLog(f"onMqttClientMessage Exception ({e}).. topic='{message.topic}', payload='{message.payload}'", self)

    def onMqttClientLog(self, _, userdata, level, buf):
        if self.enable_mqtt_console_log:
            writeLog('Mqtt Client Log: {}, {}, {}'.format(userdata, level, buf), self)

    def onMqttClientSubscribe(self, _, userdata, mid, granted_qos):
        if self.enable_mqtt_console_log:
            writeLog('Mqtt Client Subscribe: {}, {}, {}'.format(userdata, mid, granted_qos), self)

    def onMqttClientUnsubscribe(self, _, userdata, mid):
        if self.enable_mqtt_console_log:
            writeLog('Mqtt Client Unsubscribe: {}, {}'.format(userdata, mid), self)

    def onMqttCommandSystem(self, _: str, message: dict):
        if 'query_all' in message.keys():
            writeLog('Got query all command', self)
            self.publish_all()
        if 'restart' in message.keys():
            writeLog('Got restart command', self)
            self.restart()
        if 'reboot' in message.keys():
            os.system('sudo reboot')
        if 'publish_interval' in message.keys():
            try:
                interval = message['publish_interval']
                self.thread_timer.setMqttPublishInterval(interval)
            except Exception:
                pass
        if 'send_packet' in message.keys():
            try:
                idx = message.get('index')
                packet_str = message.get('packet')
                packet = bytearray([int(x, 16) for x in packet_str.split(' ')])
                self.rs485_info_list[idx].rs485.sendData(packet)
            except Exception:
                pass
        if 'clear_console' in message.keys():
            os.system('clear')

    def onMqttCommandLight(self, topic: str, message: dict):
        splt = topic.split('/')
        try:
            room_idx = int(splt[-2])
            dev_idx = int(splt[-1])
        except Exception as e:
            writeLog(f'onMqttCommandLight::topic template error ({e}, {topic})', self)
            room_idx, dev_idx = 0, 0
        device = self.getDevice(DeviceType.LIGHT, dev_idx, room_idx)
        if device is not None:
            if 'state' in message.keys():
                self.command(
                    device=device,
                    category='state',
                    target=message['state']
                )

    def onMqttCommandOutlet(self, topic: str, message: dict):
        splt = topic.split('/')
        try:
            room_idx = int(splt[-2])
            dev_idx = int(splt[-1])
        except Exception as e:
            writeLog(f'onMqttCommandOutlet::topic template error ({e}, {topic})', self)
            room_idx, dev_idx = 0, 0
        device = self.getDevice(DeviceType.OUTLET, dev_idx, room_idx)
        if device is not None:
            if 'state' in message.keys():
                self.command(
                    device=device,
                    category='state',
                    target=message['state']
                )

    def onMqttCommandGasvalve(self, topic: str, message: dict):
        splt = topic.split('/')
        try:
            room_idx = int(splt[-2])
            dev_idx = int(splt[-1])
        except Exception as e:
            writeLog(f'onMqttCommandGasvalve::topic template error ({e}, {topic})', self)
            room_idx, dev_idx = 0, 0
        device = self.getDevice(DeviceType.GASVALVE, dev_idx, room_idx)
        if device is not None:
            if 'state' in message.keys():
                self.command(
                    device=device,
                    category='state',
                    target=message['state']
                )

    def onMqttCommandThermostat(self, topic: str, message: dict):
        splt = topic.split('/')
        try:
            room_idx = int(splt[-2])
            dev_idx = int(splt[-1])
        except Exception as e:
            writeLog(f'onMqttCommandThermostat::topic template error ({e}, {topic})', self)
            room_idx, dev_idx = 0, 0
        device = self.getDevice(DeviceType.THERMOSTAT, dev_idx, room_idx)
        if device is not None:
            if 'state' in message.keys():
                self.command(
                    device=device,
                    category='state',
                    target=message['state']
                )
            if 'targetTemperature' in message.keys():
                self.command(
                    device=device,
                    category='temperature',
                    target=message['targetTemperature']
                )
            if 'timer' in message.keys():
                if message['timer']:
                    device.startTimerOnOff()
                else:
                    device.stopTimerOnOff()

    def onMqttCommandVentilator(self, topic: str, message: dict):
        splt = topic.split('/')
        try:
            room_idx = int(splt[-2])
            dev_idx = int(splt[-1])
        except Exception as e:
            writeLog(f'onMqttCommandVentilator::topic template error ({e}, {topic})', self)
            room_idx, dev_idx = 0, 0
        device = self.getDevice(DeviceType.VENTILATOR, dev_idx, room_idx)
        if device is not None:
            if 'state' in message.keys():
                self.command(
                    device=device,
                    category='state',
                    target=message['state']
                )
            if 'rotationspeed' in message.keys():
                if device.state == 1:
                    # 전원이 켜져있을 경우에만 풍량설정 가능하도록..
                    # 최초 전원 ON시 풍량 '약'으로 설정!
                    self.command(
                        device=device,
                        category='rotationspeed',
                        target=message['rotationspeed']
                    )

    def onMqttCommandAirconditioner(self, topic: str, message: dict):
        splt = topic.split('/')
        try:
            room_idx = int(splt[-2])
            dev_idx = int(splt[-1])
        except Exception as e:
            writeLog(f'onMqttCommandAirconditioner::topic template error ({e}, {topic})', self)
            room_idx, dev_idx = 0, 0
        device = self.getDevice(DeviceType.AIRCONDITIONER, dev_idx, room_idx)
        if device is not None:
            if 'active' in message.keys():
                self.command(
                    device=device,
                    category='active',
                    target=message['active']
                )
            if 'targetTemperature' in message.keys():
                self.command(
                    device=device,
                    category='temperature',
                    target=message['targetTemperature']
                )
            if 'rotationspeed' in message.keys():
                self.command(
                    device=device,
                    category='rotationspeed',
                    target=message['rotationspeed']
                )
            if 'rotationspeed_name' in message.keys():  # for HA
                speed_dict = {'Max': 100, 'Medium': 75, 'Min': 50, 'Auto': 25}
                target = speed_dict[message['rotationspeed_name']]
                self.command(
                    device=device,
                    category='rotationspeed',
                    target=target
                )
            if 'timer' in message.keys():
                if message['timer']:
                    device.startTimerOnOff()
                else:
                    device.stopTimerOnOff()

    def onMqttCommandElevator(self, topic: str, message: dict):
        splt = topic.split('/')
        try:
            room_idx = int(splt[-2])
            dev_idx = int(splt[-1])
        except Exception as e:
            writeLog(f'onMqttCommandElevator::topic template error ({e}, {topic})', self)
            room_idx, dev_idx = 0, 0
        device = self.getDevice(DeviceType.ELEVATOR, dev_idx, room_idx)
        if device is not None:
            if 'state' in message.keys():
                self.command(
                    device=device,
                    category='state',
                    target=message['state']
                )
    
    def onMqttCommandSubPhone(self, topic: str, message: dict):
        splt = topic.split('/')
        try:
            room_idx = int(splt[-2])
            dev_idx = int(splt[-1])
        except Exception as e:
            writeLog(f'onMqttCommandSubPhone::topic template error ({e}, {topic})', self)
            room_idx, dev_idx = 0, 0
        device = self.getDevice(DeviceType.SUBPHONE, dev_idx, room_idx)
        if device is not None:
            if 'streaming_state' in message.keys():
                self.command(
                    device=device,
                    category='streaming',
                    target=message['streaming_state']
                )
            if 'doorlock_state' in message.keys():
                self.command(
                    device=device,
                    category='doorlock',
                    target=message['doorlock_state']
                )

    def onMqttCommandThinq(self, _: str, message: dict):
        if self.thinq is None:
            return
        if 'restart' in message.keys():
            self.thinq.restart()
            return
        if 'log_mqtt_message' in message.keys():
            self.thinq.setEnableLogMqttMessage(bool(int(message.get('log_mqtt_message'))))

    def onMqttCommandBatchOffSwitch(self, topic: str, message: dict):
        splt = topic.split('/')
        try:
            room_idx = int(splt[-2])
            dev_idx = int(splt[-1])
        except Exception as e:
            writeLog(f'onMqttCommandBatchOffSwitch::topic template error ({e}, {topic})', self)
            room_idx, dev_idx = 0, 0
        device = self.getDevice(DeviceType.BATCHOFFSWITCH, dev_idx, room_idx)
        if device is not None:
            if 'state' in message.keys():
                self.command(
                    device=device,
                    category='state',
                    target=message['state']
                )

    def onSubphoneStateStreaming(self, state: int):
        # 카메라 응답없음이 해제가 안되므로, 초기화 시에 시작하도록 한다
        """
        if state:
            self.startFFMpeg()
        else:
            self.stopFFMpeg()
        """

    def startFFServer(self):
        try:
            subphone: SubPhone = self.getDevice(DeviceType.SUBPHONE, 0, 0)
            if subphone is None:
                return

            pipe1, pipe2 = multiprocessing.Pipe(duplex=True)
            args = [subphone.streaming_config, pipe1]
            self.mp_ffserver = multiprocessing.Process(target=procFFServer, name='FFServer', args=tuple(args))
            self.mp_ffserver.start()
            while True:
                if pipe2.poll():
                    recv = pipe2.recv_bytes().decode(encoding='utf-8', errors='ignore')
                    writeLog(f'Recv from FFServer process pipe: {recv}', self)
                    self.pid_ffserver_proc = int(recv)
                    break
        except Exception as e:
            writeLog(f'Failed to start FFServer Process ({e})', self)
    
    def stopFFServer(self):
        if self.mp_ffserver is not None:
            try:
                psutil.Process(self.pid_ffserver_proc).kill()
                self.mp_ffserver.terminate()
                writeLog(f'FFServer Process Terminated', self)
            except Exception:
                writeLog(f'Failed to kill FFServer Process', self)
                traceback.print_exc()
        self.mp_ffserver = None

    def startFFMpeg(self):
        try:
            subphone: SubPhone = self.getDevice(DeviceType.SUBPHONE, 0, 0)
            if subphone is None:
                return
            
            pipe1, pipe2 = multiprocessing.Pipe(duplex=True)
            args = [subphone.streaming_config, pipe1]
            self.mp_ffmpeg = multiprocessing.Process(target=procFFMpeg, name='FFMpeg', args=tuple(args))
            self.mp_ffmpeg.start()
            while True:
                if pipe2.poll():
                    recv = pipe2.recv_bytes().decode(encoding='utf-8', errors='ignore')
                    writeLog(f'Recv from FFMpeg process pipe: {recv}', self)
                    self.pid_ffmpeg_proc = int(recv)
                    break
            proc = psutil.Process(self.pid_ffmpeg_proc)
            proc.nice(0)
        except Exception as e:
            writeLog(f'Failed to start FFMpeg Process ({e})', self)
    
    def stopFFMpeg(self):
        if self.mp_ffmpeg is not None:
            try:
                psutil.Process(self.pid_ffmpeg_proc).kill()
                self.mp_ffmpeg.terminate()
                writeLog(f'FFMpeg Process Terminated', self)
            except Exception:
                writeLog(f'Failed to kill FFMpeg Process', self)
                traceback.print_exc()
        self.mp_ffmpeg = None

    """
    def onMqttCommandDookLock(self, topic: str, message: dict):
        if 'state' in message.keys():
            self.command(
                device=self.doorlock,
                category='state',
                target=message['state']
            )
    """

    def onThinqPublishMQTT(self, topic: str, message: dict):
        self.mqtt_client.publish(topic, json.dumps(message), 1)
    
    def startDiscoverDevice(self, clear_list: bool = False):
        if clear_list:
            self.clearDiscoveredDeviceList()
        self.discover_device = True
    
    def stopDiscoverDevice(self):
        # TODO: action after stop discovering
        self.discover_device = False

    def clearDiscoveredDeviceList(self):
        self.discovered_dev_list.clear()

    def isDeviceDiscovered(self, dev_type: DeviceType, index: int, room_index: int) -> bool:
        find = list(filter(lambda x: 
            x.getType() == dev_type and x.getIndex() == index and x.getRoomIndex() == room_index, 
            self.discovered_dev_list))
        return len(find) > 0

    def updateDiscoverDeviceList(self, result: dict):
        try:
            dev_type = result.get('device')
            dev_idx: int = result.get('index')
            if dev_idx is None:
                dev_idx = 0
            room_idx: int = result.get('room_index')
            if room_idx is None:
                room_idx = 0
            
            if self.isDeviceDiscovered(dev):
                return
            
            dev: Device = None
            if dev_type is DeviceType.LIGHT:
                dev = Light(f'Light {dev_idx + 1}', dev_idx, room_idx)
            elif dev_type is DeviceType.OUTLET:
                dev = Outlet(f'Outlet {dev_idx + 1}', dev_idx, room_idx)
            elif dev_type is DeviceType.THERMOSTAT:
                dev = Thermostat(f'Thermostat', dev_idx, room_idx)
            elif dev_type is DeviceType.AIRCONDITIONER:
                dev = AirConditioner(f'AirConditioner', dev_idx, room_idx)
            elif dev_type is DeviceType.GASVALVE:
                dev = GasValve('Gas Valve', dev_idx, room_idx)
            elif dev_type is DeviceType.VENTILATOR:
                dev = Ventilator('Ventilator', dev_idx, room_idx)
            elif dev_type is DeviceType.ELEVATOR:
                dev = Elevator('Elevator', dev_idx, room_idx)
            elif dev_type is DeviceType.SUBPHONE:
                dev = SubPhone("SubPhone", dev_idx, room_idx)
            elif dev_type is DeviceType.BATCHOFFSWITCH:
                dev = BatchOffSwitch("BatchOffSW", dev_idx, room_idx)
            elif dev_type is DeviceType.HEMS:
                pass
            if dev is not None:
                dev.setMqttClient(self.mqtt_client)
                self.discovered_dev_list.append(dev)
        except Exception as e:
            writeLog('updateDiscoverDeviceList::Exception::{} ({})'.format(e, result), self)


home_: Union[Home, None] = None


def get_home(name: str = '') -> Home:
    global home_
    if home_ is None:
        home_ = Home(name=name)
    return home_


if __name__ == "__main__":
    home_obj = get_home('hillstate')
    home_obj.initRS485Connection()
    
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
