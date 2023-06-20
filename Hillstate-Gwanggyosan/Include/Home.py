import os
import time
import json
import queue
import psutil
import traceback
from functools import partial
from typing import List, Union
from collections import OrderedDict
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
    config_tree: Union[ET.ElementTree, None] = None
    thinq: ThinQ = None

    thread_cmd_queue: Union[ThreadCommandQueue, None] = None
    thread_parse_result_queue: Union[ThreadParseResultQueue, None] = None
    thread_timer: Union[ThreadTimer, None] = None
    thread_energy_monitor: Union[ThreadEnergyMonitor, None] = None
    thread_discovery: Union[ThreadDiscovery, None] = None
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

    mp_ffserver: Union[multiprocessing.Process, None] = None
    pid_ffserver_proc: int = 0
    mp_ffmpeg: Union[multiprocessing.Process, None] = None
    pid_ffmpeg_proc: int = 0

    discover_device: bool = False
    discover_timeout: int = 60  # unit: second
    discover_reload: bool = False
    discovered_dev_list: List[dict]

    verbose_unreg_dev_packet: bool = False

    def __init__(self, name: str = 'Home', init_service: bool = True):
        self.name = name
        self.device_list = list()
        self.discovered_dev_list = list()
        self.queue_command = queue.Queue()
        self.queue_parse_result = queue.Queue()
        self.rs485_info_list = list()
        self.parser_mapping = {
            DeviceType.LIGHT: 0,
            DeviceType.OUTLET: 0,
            DeviceType.GASVALVE: 0,
            DeviceType.THERMOSTAT: 0,
            DeviceType.VENTILATOR: 0,
            DeviceType.AIRCONDITIONER: 0,
            DeviceType.ELEVATOR: 0,
            DeviceType.SUBPHONE: 0,
            DeviceType.BATCHOFFSWITCH: 0,
            DeviceType.HEMS: 0,
        }
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
        if self.isSubphoneActivated():
            # 카메라 스트리밍
            self.startFFServer()
            self.startFFMpeg()
            if self.isHEMSActivated():
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
        if self.isSubphoneActivated():
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
            self.config_tree = None
            return
        self.config_tree = ET.parse(xml_path)
        root = self.config_tree.getroot()

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
                    parser = PacketParser(rs485, name, index, ParserType(packettype))
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
        dev_entry_cnt = 0
        node = root.find('device')
        try:
            parser_mapping_node = node.find('parser_mapping')
            if parser_mapping_node is not None:
                self.parser_mapping[DeviceType.LIGHT] = int(parser_mapping_node.find('light').text)
                self.parser_mapping[DeviceType.OUTLET] = int(parser_mapping_node.find('outlet').text)
                self.parser_mapping[DeviceType.GASVALVE] = int(parser_mapping_node.find('gasvalve').text)
                self.parser_mapping[DeviceType.THERMOSTAT] = int(parser_mapping_node.find('thermostat').text)
                self.parser_mapping[DeviceType.VENTILATOR] = int(parser_mapping_node.find('ventilator').text)
                self.parser_mapping[DeviceType.AIRCONDITIONER] = int(parser_mapping_node.find('airconditioner').text)
                self.parser_mapping[DeviceType.ELEVATOR] = int(parser_mapping_node.find('elevator').text)
                self.parser_mapping[DeviceType.SUBPHONE] = int(parser_mapping_node.find('subphone').text)
                self.parser_mapping[DeviceType.BATCHOFFSWITCH] = int(parser_mapping_node.find('batchoffsw').text)
                self.parser_mapping[DeviceType.HEMS] = int(parser_mapping_node.find('hems').text)

            verbose_unreg_dev_packet_node = node.find('verbose_unreg_dev_packet')
            if verbose_unreg_dev_packet_node is not None:
                self.verbose_unreg_dev_packet = bool(int(verbose_unreg_dev_packet_node.text))

            discovery_node = node.find('discovery')
            enable_discovery = False
            if discovery_node is not None:
                enable_node = discovery_node.find('enable')
                if enable_node is not None:
                    # self.discover_device = bool(int(enable_node.text))
                    enable_discovery = bool(int(enable_node.text))
                timeout_node = discovery_node.find('timeout')
                if timeout_node is not None:
                    self.discover_timeout = int(timeout_node.text)
                reload_node = discovery_node.find('reload')
                if reload_node is not None:
                    self.discover_reload = bool(int(reload_node.text))
            if enable_discovery:
                self.startDiscoverDevice()

            entry_node = node.find('entry')
            dev_entry_cnt = len(list(entry_node))
            
            for dev_node in list(entry_node):
                try:
                    tag_name = dev_node.tag.lower()
                    name_node = dev_node.find('name')
                    name = name_node.text if name_node is not None else 'Nonamed'
                    index_node = dev_node.find('index')
                    index = int(index_node.text) if index_node is not None else 0
                    room_node = dev_node.find('room')
                    room = int(room_node.text) if room_node is not None else 0
                    enable_node = dev_node.find('enable')
                    enable = bool(int(enable_node.text)) if enable_node is not None else False
                    
                    if not self.discover_device:
                        if not enable:
                            continue
                        device: Device = None
                        if tag_name == 'light':
                            device = Light(name, index, room)
                        elif tag_name == 'outlet':
                            device = Outlet(name, index, room)
                            enable_off_cmd_node = dev_node.find('enable_off_cmd')
                            if enable_off_cmd_node is not None:
                                enable_off_cmd = bool(int(enable_off_cmd_node.text))
                                device.setEnableOffCommand(enable_off_cmd)
                        elif tag_name == 'thermostat':
                            device = Thermostat(name, index, room)
                            range_min_node = dev_node.find('range_min')
                            range_min = int(range_min_node.text) if range_min_node is not None else 0
                            range_max_node = dev_node.find('range_max')
                            range_max = int(range_max_node.text) if range_max_node is not None else 100
                            device.setTemperatureRange(range_min, range_max)
                        elif tag_name == 'airconditioner':
                            device = AirConditioner(name, index, room)
                            range_min_node = dev_node.find('range_min')
                            range_min = int(range_min_node.text) if range_min_node is not None else 0
                            range_max_node = dev_node.find('range_max')
                            range_max = int(range_max_node.text) if range_max_node is not None else 100
                            device.setTemperatureRange(range_min, range_max)
                        elif tag_name == 'gasvalve':
                            device = GasValve(name, index, room)
                        elif tag_name == 'ventilator':
                            device = Ventilator(name, index, room)
                        elif tag_name == 'elevator':
                            device = Elevator(name, index, room)
                        elif tag_name == 'batchoffsw':
                            device = BatchOffSwitch(name, index, room)
                        elif tag_name == 'subphone':
                            device = SubPhone(name, index, room)
                            device.sig_state_streaming.connect(self.onSubphoneStateStreaming)
                            ffmpeg_node = dev_node.find('ffmpeg')
                            device.streaming_config['conf_file_path'] = ffmpeg_node.find('conf_file_path').text
                            device.streaming_config['feed_path'] = ffmpeg_node.find('feed_path').text
                            device.streaming_config['input_device'] = ffmpeg_node.find('input_device').text
                            device.streaming_config['frame_rate'] = int(ffmpeg_node.find('frame_rate').text)
                            device.streaming_config['width'] = int(ffmpeg_node.find('width').text)
                            device.streaming_config['height'] = int(ffmpeg_node.find('height').text)
                        elif tag_name == 'hems':
                            device = HEMS(name, index, room)
                        elif tag_name == 'airquality':
                            device = AirqualitySensor(name, index, room)
                            apikey = dev_node.find('apikey').text
                            obsname = dev_node.find('obsname').text
                            device.setApiParams(apikey, obsname)
                        
                        if device is not None:
                            if self.findDevice(device.getType(), device.getIndex(), device.getRoomIndex()) is None:
                                # prevent duplicated device list
                                mqtt_node = dev_node.find('mqtt')
                                if mqtt_node is not None:
                                    device.setMqttPublishTopic(mqtt_node.find('publish').text)
                                    device.setMqttSubscribeTopic(mqtt_node.find('subscribe').text)
                                self.device_list.append(device)
                            else:
                                writeLog(f"Already Exist! {str(device)}", self)
                    else:
                        # 이미 config에 등록된 기기는 탐색 시 제외해야 한다 (중복 등록 방지)
                        if tag_name == 'light':
                            self.discovered_dev_list.append({'type': DeviceType.LIGHT, 'index': index, 'room_index': room})
                        elif tag_name == 'outlet':
                            self.discovered_dev_list.append({'type': DeviceType.OUTLET, 'index': index, 'room_index': room})
                        elif tag_name == 'thermostat':
                            self.discovered_dev_list.append({'type': DeviceType.THERMOSTAT, 'index': index, 'room_index': room})
                        elif tag_name == 'airconditioner':
                            self.discovered_dev_list.append({'type': DeviceType.AIRCONDITIONER, 'index': index, 'room_index': room})
                        elif tag_name == 'gasvalve':
                            self.discovered_dev_list.append({'type': DeviceType.GASVALVE, 'index': index, 'room_index': room})
                        elif tag_name == 'ventilator':
                            self.discovered_dev_list.append({'type': DeviceType.VENTILATOR, 'index': index, 'room_index': room})
                        elif tag_name == 'elevator':
                            self.discovered_dev_list.append({'type': DeviceType.ELEVATOR, 'index': index, 'room_index': room})
                        elif tag_name == 'batchoffsw':
                            self.discovered_dev_list.append({'type': DeviceType.BATCHOFFSWITCH, 'index': index, 'room_index': room})
                        elif tag_name == 'subphone':
                            self.discovered_dev_list.append({'type': DeviceType.SUBPHONE, 'index': index, 'room_index': room})
                        elif tag_name == 'hems':
                            self.discovered_dev_list.append({'type': DeviceType.HEMS, 'index': index, 'room_index': room})
                except Exception as e:
                    writeLog(f"Failed to load device entry ({e})", self)
                    continue
        except Exception as e:
            writeLog(f"Failed to load device config ({e})", self)
        
        dev_cnt = len(self.device_list)
        if dev_cnt > 1:
            writeLog(f"Total {dev_cnt} Devices added (tag #: {dev_entry_cnt})", self)
        elif dev_cnt == 1:
            writeLog(f"Total {dev_cnt} Device added (tag #: {dev_entry_cnt})", self)

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
            device: HEMS = self.findDevice(DeviceType.HEMS, 0, 0)
            if device is not None:
                index = self.parser_mapping.get(DeviceType.HEMS)
                parser: PacketParser = self.rs485_info_list[index].parser
                self.thread_energy_monitor = ThreadEnergyMonitor(
                    hems=device, 
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
                dev.publishMQTT()
            except ValueError as e:
                writeLog(f'{e}: {dev}, {dev.mqtt_publish_topic}', self)

    def handlePacketParseResult(self, result: dict):
        if self.discover_device:
            self.updateDiscoverDeviceList(result)
        else:
            self.updateDeviceState(result)
    
    def findDevice(self, dev_type: DeviceType, index: int, room_index: int) -> Device:
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
            device = self.findDevice(dev_type, dev_idx, room_idx)
            if device is None:
                if self.verbose_unreg_dev_packet:
                    writeLog(f'updateDeviceState::Device is not registered ({dev_type.name}, idx={dev_idx}, room={room_idx})', self)
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
            elif dev_type is DeviceType.VENTILATOR:
                state = result.get('state')
                rotation_speed = result.get('rotation_speed')
                device.updateState(state, rotation_speed=rotation_speed)
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
                device.updateState(
                    0,
                    monitor_data=result
                )
            elif dev_type is DeviceType.DOORLOCK:
                pass
        except Exception as e:
            writeLog('updateDeviceState::Exception::{} ({})'.format(e, result), self)

    def isSubphoneActivated(self) -> bool:
        return self.findDevice(DeviceType.SUBPHONE, 0, 0) is not None
    
    def isHEMSActivated(self) -> bool:
        return self.findDevice(DeviceType.HEMS, 0, 0) is not None

    def command(self, **kwargs):
        try:
            dev: Device = kwargs['device']
            dev_type: DeviceType = dev.getType()
            index = self.parser_mapping.get(dev_type)
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
        device = self.findDevice(DeviceType.LIGHT, dev_idx, room_idx)
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
        device = self.findDevice(DeviceType.OUTLET, dev_idx, room_idx)
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
        device = self.findDevice(DeviceType.GASVALVE, dev_idx, room_idx)
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
        device = self.findDevice(DeviceType.THERMOSTAT, dev_idx, room_idx)
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
        device = self.findDevice(DeviceType.VENTILATOR, dev_idx, room_idx)
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
        device = self.findDevice(DeviceType.AIRCONDITIONER, dev_idx, room_idx)
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
        device = self.findDevice(DeviceType.ELEVATOR, dev_idx, room_idx)
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
        device = self.findDevice(DeviceType.SUBPHONE, dev_idx, room_idx)
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
        device = self.findDevice(DeviceType.BATCHOFFSWITCH, dev_idx, room_idx)
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
            subphone: SubPhone = self.findDevice(DeviceType.SUBPHONE, 0, 0)
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
            subphone: SubPhone = self.findDevice(DeviceType.SUBPHONE, 0, 0)
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
        
    def startDiscoverDevice(self):
        self.discover_device = True
        if self.thread_discovery is None:
            self.thread_discovery = ThreadDiscovery(self.discover_timeout)
            self.thread_discovery.sig_terminated.connect(self.onThreadDiscoveryTerminated)
            self.thread_discovery.setDaemon(True)
            self.thread_discovery.start()
    
    def stopDiscoverDevice(self):
        if self.thread_discovery is not None:
            self.thread_discovery.stop()

    def onThreadDiscoveryTerminated(self):
        del self.thread_discovery
        self.thread_discovery = None

        self.saveDiscoverdDevicesToConfigFile()
        if self.discover_reload:
            self.restart()
        else:
            self.discover_device = False

    def isDeviceDiscovered(self, dev_type: DeviceType, index: int, room_index: int) -> bool:
        find = list(filter(lambda x: 
            x.get('type') == dev_type and x.get('index') == index and x.get('room_index') == room_index, 
            self.discovered_dev_list))
        return len(find) > 0

    def updateDiscoverDeviceList(self, result: dict):
        try:
            dev_type: DeviceType = result.get('device')
            dev_idx: int = result.get('index')
            if dev_idx is None:
                dev_idx = 0
            room_index: int = result.get('room_index')
            if room_index is None:
                room_index = 0
            parser_index: int = result.get('parser_index')
            if parser_index is None:
                parser_index = 0
            
            if self.findDevice(dev_type, dev_idx, room_index):
                return
            if self.isDeviceDiscovered(dev_type, dev_idx, room_index):
                return
            if dev_type is DeviceType.UNKNOWN:
                return
            
            self.discovered_dev_list.append({
                'type': dev_type,
                'index': dev_idx,
                'room_index': room_index,
                'parser_index': parser_index
            })
            writeLog(f"discovered {dev_type.name} (index: {dev_idx}, room: {room_index}, parser index: {parser_index})", self)
        except Exception as e:
            writeLog('updateDiscoverDeviceList::Exception::{} ({})'.format(e, result), self)

    def saveDiscoverdDevicesToConfigFile(self):
        try:
            if self.config_tree is None:
                return
            root = self.config_tree.getroot()
            device_node = root.find('device')
            if device_node is None:
                device_node = ET.Element('device')
                root.append(device_node)
            
            discovery_node = device_node.find('discovery')
            if discovery_node is not None:
                enable_node = discovery_node.find('enable')
                if enable_node is not None:
                    enable_node.text = '0'

            entry_node = device_node.find('entry')
            if entry_node is None:
                entry_node = ET.Element('entry')
                device_node.append(entry_node)

            self.discovered_dev_list.sort(key=lambda x: (x.get('type').value, x.get('room_index'), x.get('index')))

            for elem in self.discovered_dev_list:
                dev_type: DeviceType = elem.get('type')
                dev_idx: int = elem.get('index')
                room_index: int = elem.get('room_index')
                parser_index: int = elem.get('parser_index')

                entry_info = OrderedDict()
                if room_index > 0:
                    entry_info['name'] = f'ROOM{room_index} ' + dev_type.name + f'{dev_idx}'
                else:
                    if dev_idx > 0:
                        entry_info['name'] = dev_type.name + f'{dev_idx}'
                    else:
                        entry_info['name'] = dev_type.name
                entry_info['index'] = dev_idx
                entry_info['room'] = room_index
                entry_info['enable'] = 1

                self.parser_mapping[dev_type] = parser_index
                
                if dev_type is DeviceType.LIGHT:
                    entry_info['type'] = 'light'
                elif dev_type is DeviceType.OUTLET:
                    entry_info['type'] = 'outlet'
                    entry_info['enable_off_cmd'] = 1
                elif dev_type is DeviceType.THERMOSTAT:
                    entry_info['type'] = 'thermostat'
                    entry_info['range_min'] = 18
                    entry_info['range_max'] = 35
                elif dev_type is DeviceType.AIRCONDITIONER:
                    entry_info['type'] = 'airconditioner'
                    entry_info['range_min'] = 18
                    entry_info['range_max'] = 35
                elif dev_type is DeviceType.GASVALVE:
                    entry_info['type'] = 'gasvalve'
                elif dev_type is DeviceType.VENTILATOR:
                    entry_info['type'] = 'ventilator'
                elif dev_type is DeviceType.ELEVATOR:
                    entry_info['type'] = 'elevator'
                elif dev_type is DeviceType.SUBPHONE:
                    entry_info['type'] = 'subphone'
                    entry_info['ffmpeg'] = {
                        'conf_file_path': '/etc/ffserver.conf',
                        'feed_path': 'http://0.0.0.0:8090/feed.ffm',
                        'input_device': '/dev/video0',
                        'frame_rate': 30,
                        'width': 640,
                        'height': 480
                    }
                elif dev_type is DeviceType.BATCHOFFSWITCH:
                    entry_info['type'] = 'batchoffsw'
                elif dev_type is DeviceType.HEMS:
                    entry_info['type'] = 'hems'

                entry_info['mqtt'] = dict()
                entry_info['mqtt']['publish'] = f"home/state/{entry_info['type']}/{room_index}/{dev_idx}"
                entry_info['mqtt']['subscribe'] = f"home/command/{entry_info['type']}/{room_index}/{dev_idx}"

                element_node = ET.Element(entry_info['type'])
                entry_info.pop('type')
                entry_node.append(element_node)
                for key in entry_info.keys():
                    value = entry_info.get(key)
                    child_node = ET.Element(key)
                    element_node.append(child_node)
                    if isinstance(value, dict):
                        for key2 in value.keys():
                            grand_child_node = ET.Element(key2)
                            child_node.append(grand_child_node)
                            grand_child_node.text = str(value.get(key2))
                    else:
                        child_node.text = str(value)
            
            # parser index mapping config
            parser_mapping_node = device_node.find('parser_mapping')
            if parser_mapping_node is None:
                parser_mapping_node = ET.Element('parser_mapping')
                device_node.append(parser_mapping_node)
            child_node = parser_mapping_node.find('light')
            if child_node is None:
                child_node = ET.Element('light')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping[DeviceType.LIGHT])
            child_node = parser_mapping_node.find('outlet')
            if child_node is None:
                child_node = ET.Element('outlet')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping[DeviceType.OUTLET])
            child_node = parser_mapping_node.find('gasvalve')
            if child_node is None:
                child_node = ET.Element('gasvalve')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping[DeviceType.GASVALVE])
            child_node = parser_mapping_node.find('thermostat')
            if child_node is None:
                child_node = ET.Element('thermostat')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping[DeviceType.THERMOSTAT])
            child_node = parser_mapping_node.find('ventilator')
            if child_node is None:
                child_node = ET.Element('ventilator')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping[DeviceType.VENTILATOR])
            child_node = parser_mapping_node.find('airconditioner')
            if child_node is None:
                child_node = ET.Element('airconditioner')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping[DeviceType.AIRCONDITIONER])
            child_node = parser_mapping_node.find('elevator')
            if child_node is None:
                child_node = ET.Element('elevator')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping[DeviceType.ELEVATOR])
            child_node = parser_mapping_node.find('subphone')
            if child_node is None:
                child_node = ET.Element('subphone')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping[DeviceType.SUBPHONE])
            child_node = parser_mapping_node.find('batchoffsw')
            if child_node is None:
                child_node = ET.Element('batchoffsw')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping[DeviceType.BATCHOFFSWITCH])
            child_node = parser_mapping_node.find('hems')
            if child_node is None:
                child_node = ET.Element('hems')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping[DeviceType.HEMS])

            writeXmlFile(root, os.path.join(PROJPATH, 'config.xml'))
        except Exception as e:
            writeLog('saveDiscoverdDevicesToConfigFile::Exception::{}'.format(e), self)



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
