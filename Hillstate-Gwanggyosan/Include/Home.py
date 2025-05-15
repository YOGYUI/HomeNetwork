import os
import ssl
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
import subprocess
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
    config_file_path: str = None

    thread_cmd_queue: Union[ThreadCommandQueue, None] = None
    thread_parse_result_queue: Union[ThreadParseResultQueue, None] = None
    thread_timer: Union[ThreadTimer, None] = None
    thread_energy_monitor: Union[ThreadEnergyMonitor, None] = None
    thread_discovery: Union[ThreadDiscovery, None] = None
    thread_query_state: Union[ThreadQueryState, None] = None
    queue_command: queue.Queue
    queue_parse_result: queue.Queue

    mqtt_client: mqtt.Client
    mqtt_username: str = ''
    mqtt_password: str = ''
    mqtt_host: str = '127.0.0.1'
    mqtt_port: int = 1883
    mqtt_client_id: str = 'yogyui_hyundai_ht'
    mqtt_tls_enable: bool = False
    mqtt_tls_ca_certs: str = ''
    mqtt_tls_certfile: str = ''
    mqtt_tls_keyfile: str = ''
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

    ha_mqtt_discover_enable: bool = False
    ha_mqtt_discover_prefix: str = 'homeassistant'
    ha_mqtt_topic_status: str = 'homeassistant/status'

    verbose_unreg_dev_packet: bool = False

    enable_periodic_query_state: bool = False
    query_state_period: int = 1000
    verbose_periodic_query_state: bool = False
    change_device_state_after_command: bool = False

    clear_all_devices: bool = False

    def __init__(self, name: str = 'Home', init_service: bool = True, config_file_path: str = None):
        self.name = name
        self.device_list = list()
        self.discovered_dev_list = list()
        self.queue_command = queue.Queue()
        self.queue_parse_result = queue.Queue()
        self.rs485_info_list = list()
        self.parser_mapping = {
            DeviceType.LIGHT: 0,
            DeviceType.EMOTIONLIGHT: 0,
            DeviceType.DIMMINGLIGHT: 0,
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
        self.config_file_path = config_file_path
        if self.config_file_path is None:
            self.config_file_path = os.path.join(PROJPATH, 'config.xml')
        self.initialize(init_service, False)
    
    def initialize(self, init_service: bool, connect_rs485: bool):
        self.loadAppInfo()
        self.loadConfig()
        self.initMQTT()
        self.initDevices()

        if self.clear_all_devices:
            self.clearAllDevices()
            self.restart()
            return

        if init_service:
            self.startThreadCommandQueue()
            self.startThreadParseResultQueue()
            self.startThreadTimer()
            if self.enable_periodic_query_state:
                self.startThreadQueryState()
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
        self.mqtt_client = mqtt.Client(
            client_id=self.mqtt_client_id,
            protocol=mqtt.MQTTv311,
            transport='tcp'
        )
        self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
        
        # tls setting
        if self.mqtt_tls_enable:
            ca_certs = self.mqtt_tls_ca_certs if os.path.isfile(self.mqtt_tls_ca_certs) else None
            certfile = self.mqtt_tls_certfile if os.path.isfile(self.mqtt_tls_certfile) else None
            keyfile = self.mqtt_tls_keyfile if os.path.isfile(self.mqtt_tls_keyfile) else None
            
            self.mqtt_client.tls_set(
                ca_certs=ca_certs,
                certfile=certfile,
                keyfile=keyfile,
                tls_version=ssl.PROTOCOL_TLSv1_2,
                cert_reqs=ssl.CERT_REQUIRED
            )
        
        # set callback functions
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
            dev.setHomeAssistantDiscoveryPrefix(self.ha_mqtt_discover_prefix)
            dev.configMQTT()

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
        self.stopThreadQueryState()

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

    def loadAppInfo(self):
        app_version = 'unknown'
        app_info_json_path = os.path.join(PROJPATH, 'app_info.json')
        if os.path.isfile(app_info_json_path):
            with open(app_info_json_path, 'r') as fp:
                app_info = json.load(fp)
                if 'version' in app_info.keys():
                    app_version = app_info.get('version')
        writeLog(f'Version: {app_version}', self)

    def loadConfig(self):
        if not os.path.isfile(self.config_file_path):
            self.config_tree = None
            return
        self.config_tree = ET.parse(self.config_file_path)
        root = self.config_tree.getroot()

        try:
            node = root.find('rs485')
            self.loadRS485Config(node)
        except Exception:
            writeLog(f"Failed to read <rs485> node", self)
            traceback.print_exc()

        try:
            node = root.find('mqtt')
            self.loadMQTTConfig(node)
        except Exception:
            writeLog(f"Failed to read <mqtt> node", self)
            traceback.print_exc()
        
        try:
            node = root.find('device')
            self.loadDeviceConfig(node)
        except Exception:
            writeLog(f"Failed to read <device> node", self)
            traceback.print_exc()

        try:
            node = root.find('thinq')
            if node is not None:
                self.loadThinqConfig(node)
        except Exception:
            writeLog(f"Failed to read <thinq> node", self)
            traceback.print_exc()
        
    def loadRS485Config(self, node: ET.Element):
        writeLog("Loading RS485 configurations", self)
        try:
            self.rs485_reconnect_limit = int(node.find('reconnect_limit').text)
        except Exception as e:
            writeLog(f"Failed to read <reconnect_limit> node ({e})", self)
            self.rs485_reconnect_limit = 60

        self.rs485_info_list.clear()
        for cnode in list(node):
            if cnode.tag != 'port':
                continue
            cfg = RS485Config()
            try:
                name = cnode.find('name').text.upper()
            except Exception as e:
                writeLog(f"Failed to read <name> node ({e})", self)
                name = 'nonamed'
            try:
                index = int(cnode.find('index').text)
            except Exception as e:
                writeLog(f"Failed to read <index> node ({e})", self)
                index = 0
            try:
                enable = bool(int(cnode.find('enable').text))
            except Exception as e:
                writeLog(f"Failed to read <enable> node ({e})", self)
                enable = False
            try:
                hwtype = int(cnode.find('hwtype').text)
            except Exception as e:
                writeLog(f"Failed to read <hwtype> node ({e})", self)
                hwtype = 0
            try:
                packettype = int(cnode.find('packettype').text)
            except Exception as e:
                writeLog(f"Failed to read <packettype> node ({e})", self)
                packettype = 0
            try:
                check = bool(int(cnode.find('check').text))
            except Exception as e:
                writeLog(f"Failed to read <check> node ({e})", self)
                check = False
            try:
                buffsize = int(cnode.find('buffsize').text)
            except Exception as e:
                writeLog(f"Failed to read <buffsize> node ({e})", self)
                buffsize = 64

            usb2serial_node = cnode.find('usb2serial')
            if usb2serial_node is not None:
                try:
                    cfg.serial_port = usb2serial_node.find('port').text
                except Exception as e:
                    writeLog(f"Failed to read <usb2serial>-<port> node ({e})", self)
                    cfg.serial_port = '/dev/ttyUSB0'
                try:
                    cfg.serial_baud = int(usb2serial_node.find('baud').text)
                except Exception as e:
                    writeLog(f"Failed to read <usb2serial>-<baud> node ({e})", self)
                    cfg.serial_baud = 9600
                try:
                    cfg.serial_databit = int(usb2serial_node.find('databit').text)
                except Exception as e:
                    writeLog(f"Failed to read <usb2serial>-<databit> node ({e})", self)
                    cfg.serial_databit = 8
                try:
                    cfg.serial_parity = usb2serial_node.find('parity').text
                except Exception as e:
                    writeLog(f"Failed to read <usb2serial>-<parity> node ({e})", self)
                    cfg.serial_parity = 'N'
                try:
                    cfg.serial_stopbits = float(usb2serial_node.find('stopbits').text)
                except Exception as e:
                    writeLog(f"Failed to read <usb2serial>-<stopbits> node ({e})", self)
                    cfg.serial_stopbits = 1.0
            
            ew11_node = cnode.find('ew11')
            if ew11_node is not None:
                try:
                    cfg.socket_ipaddr = ew11_node.find('ipaddr').text
                except Exception as e:
                    writeLog(f"Failed to read <ew11>-<ipaddr> node ({e})", self)
                    cfg.socket_ipaddr = "127.0.0.1"
                try:
                    cfg.socket_port = int(ew11_node.find('port').text)
                except Exception as e:
                    writeLog(f"Failed to read <ew11>-<port> node ({e})", self)
                    cfg.socket_port = 8899

            try:
                thermo_len_per_dev = int(cnode.find('thermo_len_per_dev').text)
            except Exception as e:
                writeLog(f"Failed to read <thermo_len_per_dev> node ({e})", self)
                thermo_len_per_dev = 3
            
            cmd_interval_ms = 100
            cmd_retry_count = 50
            command_node = cnode.find('command')
            if command_node is not None:
                try:
                    cmd_interval_ms = int(command_node.find('interval_ms').text)
                except Exception as e:
                    writeLog(f"Failed to read <command_node>-<interval_ms> node ({e})", self)
                try:
                    cmd_retry_count = int(command_node.find('retry_count').text)
                except Exception as e:
                    writeLog(f"Failed to read <command_node>-<retry_count> node ({e})", self)
            
            cfg.enable = enable
            cfg.comm_type = RS485HwType(hwtype)
            cfg.check_connection = check
            rs485 = RS485Comm(f'RS485-{name}')
            if packettype == 1:  # subphone
                rs485.sig_connected.connect(self.onRS485SubPhoneConnected)
            parser = PacketParser(rs485, name, index, cmd_interval_ms, cmd_retry_count, ParserType(packettype))
            parser.setBufferSize(buffsize)
            parser.thermo_len_per_dev = thermo_len_per_dev
            parser.sig_parse_result.connect(lambda x: self.queue_parse_result.put(x))
            self.rs485_info_list.append(RS485Info(rs485, cfg, parser, index))
            writeLog(f"Created RS485 Instance (name: {name})", self)
        self.rs485_info_list.sort(key=lambda x: x.index)

    def loadMQTTConfig(self, node: ET.Element):
        try:
            self.mqtt_username = node.find('username').text
        except Exception as e:
            writeLog(f"Failed to read <username> node ({e})", self)
            self.mqtt_username = ''
        
        try:
            self.mqtt_password = node.find('password').text
        except Exception as e:
            writeLog(f"Failed to read <password> node ({e})", self)
            self.mqtt_password = ''
        
        try:
            self.mqtt_host = node.find('host').text
        except Exception as e:
            writeLog(f"Failed to read <host> node ({e})", self)
            self.mqtt_host = '127.0.0.1'
        
        try:
            self.mqtt_port = int(node.find('port').text)
        except Exception as e:
            writeLog(f"Failed to read <port> node ({e})", self)
            self.mqtt_port = 1883
        
        try:
            self.enable_mqtt_console_log = bool(int(node.find('console_log').text))
        except Exception as e:
            writeLog(f"Failed to read <console_log> node ({e})", self)
            self.enable_mqtt_console_log = False
        
        try:
            self.mqtt_client_id = node.find('client_id').text
        except Exception as e:
            writeLog(f"Failed to read <client_id> node ({e})", self)
            self.mqtt_client_id = 'yogyui_hyundai_ht'
        
        tls_node = node.find('tls')
        if tls_node is not None:
            try:
                self.mqtt_tls_enable = bool(int(tls_node.find('enable').text))
            except Exception as e:
                writeLog(f"Failed to read <enable> node ({e})", self)
                self.mqtt_tls_enable = False
            
            try:
                self.mqtt_tls_ca_certs = tls_node.find('ca_certs').text
                if self.mqtt_tls_ca_certs is None:
                    self.mqtt_tls_ca_certs = ''
            except Exception as e:
                writeLog(f"Failed to read <ca_certs> node ({e})", self)
                self.mqtt_tls_ca_certs = ''
            
            try:
                self.mqtt_tls_certfile = tls_node.find('certfile').text
                if self.mqtt_tls_certfile is None:
                    self.mqtt_tls_certfile = ''
            except Exception as e:
                writeLog(f"Failed to read <certfile> node ({e})", self)
                self.mqtt_tls_certfile = ''
            
            try:
                self.mqtt_tls_keyfile = tls_node.find('keyfile').text
                if self.mqtt_tls_keyfile is None:
                    self.mqtt_tls_keyfile = ''
            except Exception as e:
                writeLog(f"Failed to read <keyfile> node ({e})", self)
                self.mqtt_tls_keyfile = ''
        
        self.verbose_mqtt_regular_publish = {
            'enable': True,
            'interval': 100
        }
        verbose_node = node.find('verbose_regular_publish')
        if verbose_node is not None:
            try:
                self.verbose_mqtt_regular_publish['enable'] = bool(int(verbose_node.find('enable').text))
            except Exception as e:
                writeLog(f"Failed to read <verbose_regular_publish> - <enable> node ({e})", self)
            
            try:
                self.verbose_mqtt_regular_publish['interval'] = int(verbose_node.find('interval').text)
            except Exception as e:
                writeLog(f"Failed to read <verbose_regular_publish> - <interval> node ({e})", self)

        ha_node = node.find('homeassistant')
        if ha_node is not None:
            ha_discovery_node = ha_node.find('discovery')
            if ha_discovery_node is not None:
                ha_discovery_enable_node = ha_discovery_node.find('enable')
                if ha_discovery_enable_node is not None:
                    self.ha_mqtt_discover_enable = bool(int(ha_discovery_enable_node.text))
                ha_discovery_prefix_node = ha_discovery_node.find('prefix')
                if ha_discovery_prefix_node is not None:
                    self.ha_mqtt_discover_prefix = ha_discovery_prefix_node.text
        writeLog(f"HA MQTT Discovery Enable: {self.ha_mqtt_discover_enable}", self)
        writeLog(f"HA MQTT Discovery Prefix: {self.ha_mqtt_discover_prefix}", self)

    def loadDeviceConfig(self, node: ET.Element):
        self.device_list.clear()
        dev_entry_cnt = 0
        try:
            parser_mapping_node = node.find('parser_mapping')
            if parser_mapping_node is not None:
                try:
                    self.parser_mapping[DeviceType.LIGHT] = int(parser_mapping_node.find('light').text)
                except Exception as e:
                    writeLog(f"Failed to read <parser_mapping> - <light> node ({e})", self)
                try:
                    self.parser_mapping[DeviceType.EMOTIONLIGHT] = int(parser_mapping_node.find('emotionlight').text)
                except Exception as e:
                    writeLog(f"Failed to read <parser_mapping> - <emotionlight> node ({e})", self)
                try:
                    self.parser_mapping[DeviceType.DIMMINGLIGHT] = int(parser_mapping_node.find('dimminglight').text)
                except Exception as e:
                    writeLog(f"Failed to read <parser_mapping> - <dimminglight> node ({e})", self)
                try:
                    self.parser_mapping[DeviceType.OUTLET] = int(parser_mapping_node.find('outlet').text)
                except Exception as e:
                    writeLog(f"Failed to read <parser_mapping> - <outlet> node ({e})", self)
                try:
                    self.parser_mapping[DeviceType.GASVALVE] = int(parser_mapping_node.find('gasvalve').text)
                except Exception as e:
                    writeLog(f"Failed to read <parser_mapping> - <gasvalve> node ({e})", self)
                try:
                    self.parser_mapping[DeviceType.THERMOSTAT] = int(parser_mapping_node.find('thermostat').text)
                except Exception as e:
                    writeLog(f"Failed to read <parser_mapping> - <thermostat> node ({e})", self)
                try:
                    self.parser_mapping[DeviceType.VENTILATOR] = int(parser_mapping_node.find('ventilator').text)
                except Exception as e:
                    writeLog(f"Failed to read <parser_mapping> - <ventilator> node ({e})", self)
                try:
                    self.parser_mapping[DeviceType.AIRCONDITIONER] = int(parser_mapping_node.find('airconditioner').text)
                except Exception as e:
                    writeLog(f"Failed to read <parser_mapping> - <airconditioner> node ({e})", self)
                try:
                    self.parser_mapping[DeviceType.ELEVATOR] = int(parser_mapping_node.find('elevator').text)
                except Exception as e:
                    writeLog(f"Failed to read <parser_mapping> - <elevator> node ({e})", self)
                try:
                    self.parser_mapping[DeviceType.SUBPHONE] = int(parser_mapping_node.find('subphone').text)
                except Exception as e:
                    writeLog(f"Failed to read <parser_mapping> - <subphone> node ({e})", self)
                try:
                    self.parser_mapping[DeviceType.BATCHOFFSWITCH] = int(parser_mapping_node.find('batchoffsw').text)
                except Exception as e:
                    writeLog(f"Failed to read <parser_mapping> - <batchoffsw> node ({e})", self)
                try:
                    self.parser_mapping[DeviceType.HEMS] = int(parser_mapping_node.find('hems').text)
                except Exception as e:
                    writeLog(f"Failed to read <parser_mapping> - <hems> node ({e})", self)

            verbose_unreg_dev_packet_node = node.find('verbose_unreg_dev_packet')
            if verbose_unreg_dev_packet_node is not None:
                self.verbose_unreg_dev_packet = bool(int(verbose_unreg_dev_packet_node.text))

            self.discover_device = False
            enable_discovery = False
            discovery_node = node.find('discovery')
            if discovery_node is not None:
                try:
                    enable_node = discovery_node.find('enable')
                    enable_discovery = bool(int(enable_node.text))
                except Exception as e:
                    writeLog(f"Failed to read <discovery> - <enable> node ({e})", self)
                try:
                    timeout_node = discovery_node.find('timeout')
                    self.discover_timeout = int(timeout_node.text)
                except Exception as e:
                    writeLog(f"Failed to read <discovery> - <timeout> node ({e})", self)
                try:
                    reload_node = discovery_node.find('reload')
                    self.discover_reload = bool(int(reload_node.text))
                except Exception as e:
                    writeLog(f"Failed to read <discovery> - <reload> node ({e})", self)
            if enable_discovery:
                self.startDiscoverDevice()

            periodic_query_state_node = node.find('periodic_query_state')
            if periodic_query_state_node is not None:
                try:
                    enable_node = periodic_query_state_node.find('enable')
                    self.enable_periodic_query_state = bool(int(enable_node.text))
                except Exception as e:
                    writeLog(f"Failed to read <periodic_query_state> - <enable> node ({e})", self)
                try:
                    period_node = periodic_query_state_node.find('period')
                    self.query_state_period = int(period_node.text)
                except Exception as e:
                    writeLog(f"Failed to read <periodic_query_state> - <period> node ({e})", self)
                try:
                    verbose_node = periodic_query_state_node.find('verbose')
                    self.verbose_periodic_query_state = bool(int(verbose_node.text))
                except Exception as e:
                    writeLog(f"Failed to read <periodic_query_state> - <verbose> node ({e})", self)

            self.clear_all_devices = False
            clear_node = node.find('clear')
            if clear_node is not None:
                try:
                    self.clear_all_devices = bool(int(clear_node.text))
                except Exception as e:
                    writeLog(f"Failed to read <clear> node ({e})", self)
            
            self.change_device_state_after_command = False
            change_state_node = node.find('change_state_after_command')
            if change_state_node is not None:
                try:
                    self.change_device_state_after_command = bool(int(change_state_node.text))
                except Exception as e:
                    writeLog(f"Failed to read <change_state_after_command> node ({e})", self)

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
                    rs485_port_index_node = dev_node.find('rs485_port_index')
                    rs485_port_index = int(rs485_port_index_node.text) if rs485_port_index_node is not None else -1
                    
                    if not self.discover_device:
                        if not enable:
                            continue
                        device: Device = None
                        if tag_name == 'light':
                            device = Light(name, index, room)
                        elif tag_name == 'emotionlight':
                            device = EmotionLight(name, index, room)
                        elif tag_name == 'dimminglight':
                            device = DimmingLight(name, index, room)
                            max_brightness_level_node = dev_node.find('max_brightness_level')
                            if max_brightness_level_node is not None:
                                max_brightness_level = int(max_brightness_level_node.text)
                                device.setMaxBrightnessLevel(max_brightness_level)
                            convert_method_node = dev_node.find('convert_method')
                            if convert_method_node is not None:
                                convert_method = int(convert_method_node.text)
                                device.setConvertMethod(convert_method)
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
                            packet_call_type_node = dev_node.find('packet_call_type')
                            packet_call_type = int(packet_call_type_node.text) if packet_call_type_node is not None else 0
                            device.setPacketCallType(packet_call_type)
                            check_command_method_node = dev_node.find('check_command_method')
                            check_command_method = int(check_command_method_node.text) if check_command_method_node is not None else 0
                            device.setCheckCommandMethod(check_command_method)
                            packet_command_call_down_value_node = dev_node.find('packet_command_call_down_value')
                            packet_command_call_down_value = int(packet_command_call_down_value_node.text) if packet_command_call_down_value_node is not None else 6
                            device.setPacketCommandCallDownValue(packet_command_call_down_value)
                            verbose_packet_node = dev_node.find('verbose_packet')
                            verbose_packet = bool(int(verbose_packet_node.text)) if verbose_packet_node is not None else False
                            device.setVerbosePacket(verbose_packet)
                        elif tag_name == 'batchoffsw':
                            device = BatchOffSwitch(name, index, room)
                        elif tag_name == 'subphone':
                            device = SubPhone(name, index, room)
                            device.sig_state_streaming.connect(self.onSubphoneStateStreaming)
                            device.sig_open_front_door.connect(self.onSubphoneCommandOpenFrontDoor)
                            device.sig_open_communal_door.connect(self.onSubphoneCommandOpenCommunalDoor)
                            enable_streaming_node = dev_node.find('enable_video_streaming')
                            try:
                                device.enable_streaming = bool(int(enable_streaming_node.text))
                            except Exception as e:
                                writeLog(f"Failed to read subphone <enable_video_streaming> node ({e})", self)
                                device.enable_streaming = False
                            ffmpeg_node = dev_node.find('ffmpeg')
                            if ffmpeg_node is not None:
                                device.streaming_config['conf_file_path'] = ffmpeg_node.find('conf_file_path').text
                                device.streaming_config['feed_path'] = ffmpeg_node.find('feed_path').text
                                device.streaming_config['input_device'] = ffmpeg_node.find('input_device').text
                                device.streaming_config['frame_rate'] = int(ffmpeg_node.find('frame_rate').text)
                                device.streaming_config['width'] = int(ffmpeg_node.find('width').text)
                                device.streaming_config['height'] = int(ffmpeg_node.find('height').text)
                            auto_open_front_door_node = dev_node.find('auto_open_front_door')
                            if auto_open_front_door_node is not None:
                                enable_node = auto_open_front_door_node.find('enable')
                                if enable_node is not None:
                                    try:
                                        device.setEnableAutoOpenFrontDoor(bool(int(enable_node.text)))
                                    except Exception as e:
                                        writeLog(f"Failed to read subphone <auto_open_front_door><enable> node ({e})", self)
                                        device.setEnableAutoOpenFrontDoor(False)
                                interval_node = auto_open_front_door_node.find('interval')
                                if interval_node is not None:
                                    try:
                                        device.setAutoOpenFrontDoorInterval(float(interval_node.text))
                                    except Exception as e:
                                        writeLog(f"Failed to read subphone <auto_open_front_door><interval> node ({e})", self)
                                        device.setAutoOpenFrontDoorInterval(3.)
                            auto_open_communal_door_node = dev_node.find('auto_open_communal_door')
                            if auto_open_communal_door_node is not None:
                                enable_node = auto_open_communal_door_node.find('enable')
                                if enable_node is not None:
                                    try:
                                        device.setEnableAutoOpenCommunalDoor(bool(int(enable_node.text)))
                                    except Exception as e:
                                        writeLog(f"Failed to read subphone <auto_open_communal_door><enable> node ({e})", self)
                                        device.setEnableAutoOpenCommunalDoor(False)
                                interval_node = auto_open_communal_door_node.find('interval')
                                if interval_node is not None:
                                    try:
                                        device.setAutoOpenCommunalDoorInterval(float(interval_node.text))
                                    except Exception as e:
                                        writeLog(f"Failed to read subphone <auto_open_communal_door><interval> node ({e})", self)
                                        device.setAutoOpenCommunalDoorInterval(3.)
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
                                if rs485_port_index >= 0:
                                    device.setRS485PortIndex(rs485_port_index)
                                self.device_list.append(device)
                            else:
                                writeLog(f"Already Exist! {str(device)}", self)
                    else:
                        # 이미 config에 등록된 기기는 탐색 시 제외해야 한다 (중복 등록 방지)
                        if tag_name == 'light':
                            devtype = DeviceType.LIGHT
                        elif tag_name == 'emotionlight':
                            devtype = DeviceType.EMOTIONLIGHT
                        elif tag_name == 'dimminglight':
                            devtype = DeviceType.DIMMINGLIGHT
                        elif tag_name == 'outlet':
                            devtype = DeviceType.OUTLET
                        elif tag_name == 'thermostat':
                            devtype = DeviceType.THERMOSTAT
                        elif tag_name == 'airconditioner':
                            devtype = DeviceType.AIRCONDITIONER
                        elif tag_name == 'gasvalve':
                            devtype = DeviceType.GASVALVE
                        elif tag_name == 'ventilator':
                            devtype = DeviceType.VENTILATOR
                        elif tag_name == 'elevator':
                            devtype = DeviceType.ELEVATOR
                        elif tag_name == 'batchoffsw':
                            devtype = DeviceType.BATCHOFFSWITCH
                        elif tag_name == 'subphone':
                            devtype = DeviceType.SUBPHONE
                        elif tag_name == 'hems':
                            devtype = DeviceType.HEMS
                        else:
                            continue
                        self.discovered_dev_list.append({'type': devtype, 'index': index, 'room_index': room, 'parser_index': self.parser_mapping[devtype]})
                except Exception as e:
                    writeLog(f"Failed to load device entry ({e})", self)
                    traceback.print_exc()
                    continue
        except Exception as e:
            writeLog(f"Failed to load device config ({e})", self)
        
        if not self.discover_device:
            dev_cnt = len(self.device_list)
            writeLog(f"Total {dev_cnt} Device(s) added (tag #: {dev_entry_cnt})", self)
        else:
            writeLog("Start device discovery!", self)

    def loadThinqConfig(self, node: ET.Element):
        try:
            enable = bool(int(node.find('enable').text))
        except Exception as e:
            writeLog(f"Failed to load <thinq> - <enable> node ({e})", self)
            enable = False
        
        if enable:
            robot_cleaner_node = node.find('robot_cleaner')
            robot_cleaner_dev_id = robot_cleaner_node.find('dev_id').text
            mqtt_node = node.find('mqtt')
            mqtt_topic = mqtt_node.find('publish').text
            log_mqtt_message = bool(int(mqtt_node.find('log_message').text))
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
            self.thread_cmd_queue.sig_start_seq.connect(self.onThreadCommandQueueStartSequence)
            self.thread_cmd_queue.sig_finish_seq.connect(self.onThreadCommandQueueFinishSequence)
            self.thread_cmd_queue.sig_terminated.connect(self.onThreadCommandQueueTerminated)
            self.thread_cmd_queue.setDaemon(True)
            self.thread_cmd_queue.start()

    def stopThreadCommandQueue(self):
        if self.thread_cmd_queue is not None:
            self.thread_cmd_queue.stop()

    def onThreadCommandQueueTerminated(self):
        del self.thread_cmd_queue
        self.thread_cmd_queue = None
    
    def onThreadCommandQueueStartSequence(self):
        if self.thread_query_state is not None:
            self.thread_query_state.setAvailable(False)

    def onThreadCommandQueueFinishSequence(self):
        if self.thread_query_state is not None:
            self.thread_query_state.setAvailable(True)

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

    def startThreadQueryState(self):
        if self.thread_query_state is None:
            self.thread_query_state = ThreadQueryState(
                self.device_list,
                self.parser_mapping,
                self.rs485_info_list,
                self.query_state_period,
                self.verbose_periodic_query_state
            )
            self.thread_query_state.sig_terminated.connect(self.onThreadQueryStateTerminated)
            self.thread_query_state.setDaemon(True)
            self.thread_query_state.start()

    def stopThreadQueryState(self):
        if self.thread_query_state is not None:
            self.thread_query_state.stop()

    def onThreadQueryStateTerminated(self):
        del self.thread_query_state
        self.thread_query_state = None

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
    
    def findDevices(self, dev_type: DeviceType) -> List[Device]:
        return list(filter(lambda x: x.getType() == dev_type, self.device_list))

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
            
            if dev_type in [
                    DeviceType.LIGHT,
                    DeviceType.EMOTIONLIGHT,
                    DeviceType.OUTLET,
                    DeviceType.GASVALVE,
                    DeviceType.BATCHOFFSWITCH]:
                state = result.get('state')
                device.updateState(state)
            elif dev_type is DeviceType.DIMMINGLIGHT:
                state = result.get('state')
                if state is None:
                    state = device.state
                brightness = result.get('brightness')
                if brightness is None:
                    brightness = device.brightness
                device.updateState(
                    state, 
                    brightness=brightness
                )
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
                device.updateState(
                    0, 
                    data_type=result.get('data_type'),
                    command_state=result.get('command_state'),
                    moving_state=result.get('moving_state'),
                    call_state=result.get('call_state'),
                    ev_dev_idx=result.get('ev_dev_idx'),
                    floor=result.get('floor'),
                    packet=result.get('packet'),
                )
            elif dev_type is DeviceType.SUBPHONE:
                device.updateState(
                    0, 
                    ringing_front=result.get('ringing_front'),
                    ringing_communal=result.get('ringing_communal'),
                    streaming=result.get('streaming'),
                    doorlock=result.get('doorlock'),
                    lock_front=result.get('lock_front'),
                    lock_communal=result.get('lock_communal')
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

    def send_command(self, **kwargs):
        try:
            dev: Device = kwargs['device']
            dev_type: DeviceType = dev.getType()
            index: int = self.parser_mapping.get(dev_type)
            if dev.rs485_port_index >= 0:
                if len(self.rs485_info_list) > dev.rs485_port_index:
                    index = dev.rs485_port_index
                else:
                    writeLog(f'manual set rs485 port index for {dev} is {dev.rs485_port_index} but failed to find valid port instance!', self)
            info: RS485Info = self.rs485_info_list[index]
            kwargs['parser'] = info.parser
            kwargs['change_state_after_command'] = self.change_device_state_after_command
        except Exception as e:
            writeLog('send_command Exception::{}'.format(e), self)
        self.queue_command.put(kwargs)

    def onDeviceSetState(self, dev: Device, state: int):
        if isinstance(dev, AirConditioner):
            self.send_command(
                device=dev,
                category='active',
                target=state
            )
        elif isinstance(dev, Thermostat):
            self.send_command(
                device=dev,
                category='state',
                target='HEAT' if state else 'OFF'
            )

    def startMqttSubscribe(self):
        self.mqtt_client.subscribe('home/command/system')
        self.mqtt_client.subscribe(self.ha_mqtt_topic_status)
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
            writeLog('Conneted to MQTT Broker', self)
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
            payload = message.payload.decode("utf-8")
            try:
                msg_dict = json.loads(payload)
                writeLog(f'MQTT Message: {topic}: {msg_dict}', self)
            except Exception:
                msg_dict = dict()
            if 'command/system' in topic:
                self.onMqttCommandSystem(topic, msg_dict)
            if 'command/light' in topic:
                self.onMqttCommandLight(topic, msg_dict)
            if 'command/emotionlight' in topic:
                self.onMqttCommandEmotionLight(topic, msg_dict)
            if 'command/dimminglight' in topic:
                self.onMqttCommandDimmingLight(topic, msg_dict)
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
            if self.ha_mqtt_topic_status in topic:
                if payload == 'online':
                    writeLog(f'Homeassistant has been started', self)
                    for dev in self.device_list:
                        dev.configMQTT()
                    self.publish_all()
                elif payload == 'offline':
                    writeLog(f'Homeassistant has been terminated', self)
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
                self.send_command(
                    device=device,
                    category='state',
                    target=message['state']
                )

    def onMqttCommandEmotionLight(self, topic: str, message: dict):
        splt = topic.split('/')
        try:
            room_idx = int(splt[-2])
            dev_idx = int(splt[-1])
        except Exception as e:
            writeLog(f'onMqttCommandEmotionLight::topic template error ({e}, {topic})', self)
            room_idx, dev_idx = 0, 0
        device = self.findDevice(DeviceType.EMOTIONLIGHT, dev_idx, room_idx)
        if device is not None:
            if 'state' in message.keys():
                self.send_command(
                    device=device,
                    category='state',
                    target=message['state']
                )
    
    def onMqttCommandDimmingLight(self, topic: str, message: dict):
        splt = topic.split('/')
        try:
            room_idx = int(splt[-2])
            dev_idx = int(splt[-1])
        except Exception as e:
            writeLog(f'onMqttCommandDimmingLight::topic template error ({e}, {topic})', self)
            room_idx, dev_idx = 0, 0
        device = self.findDevice(DeviceType.DIMMINGLIGHT, dev_idx, room_idx)
        if device is not None:
            if 'state' in message.keys():
                self.send_command(
                    device=device,
                    category='state',
                    target=message['state']
                )
            if 'brightness' in message.keys():
                self.send_command(
                    device=device,
                    category='brightness',
                    target=message['brightness']
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
                self.send_command(
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
                self.send_command(
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
                self.send_command(
                    device=device,
                    category='state',
                    target=message['state']
                )
            if 'targetTemperature' in message.keys():
                self.send_command(
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
                self.send_command(
                    device=device,
                    category='state',
                    target=message['state']
                )
            if 'rotationspeed' in message.keys():
                if device.state == 1:
                    # 전원이 켜져있을 경우에만 풍량설정 가능하도록..
                    # 최초 전원 ON시 풍량 '약'으로 설정!
                    self.send_command(
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
                self.send_command(
                    device=device,
                    category='active',
                    target=message['active']
                )
            if 'mode' in message.keys():
                self.send_command(
                    device=device,
                    category='mode',
                    target=message['mode']
                )
            if 'targetTemperature' in message.keys():
                self.send_command(
                    device=device,
                    category='temperature',
                    target=message['targetTemperature']
                )
            if 'rotationspeed' in message.keys():
                self.send_command(
                    device=device,
                    category='rotationspeed',
                    target=message['rotationspeed']
                )
            if 'rotationspeed_name' in message.keys():  # for HA
                speed_dict = {'Max': 100, 'Medium': 75, 'Min': 50, 'Auto': 25}
                target = speed_dict[message['rotationspeed_name']]
                self.send_command(
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
                self.send_command(
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
        device: SubPhone = self.findDevice(DeviceType.SUBPHONE, dev_idx, room_idx)
        if device is not None:
            if 'streaming_state' in message.keys():
                self.send_command(
                    device=device,
                    category='streaming',
                    target=message['streaming_state']
                )
            if 'doorlock_state' in message.keys():
                self.send_command(
                    device=device,
                    category='doorlock',
                    target=message['doorlock_state']
                )
            # 세대현관문, 공동현관문 분리
            if 'lock_front_state' in message.keys():
                self.send_command(
                    device=device,
                    category='lock_front',
                    target=message['lock_front_state']
                )
            if 'lock_communal_state' in message.keys():
                self.send_command(
                    device=device,
                    category='lock_communal',
                    target=message['lock_communal_state']
                )
            # 세대/공동현관문 자동 열림 기능
            if 'enable_auto_open_front' in message.keys():
                device.setEnableAutoOpenFrontDoor(bool(message['enable_auto_open_front']))
            if 'auto_open_front_interval' in message.keys():
                device.setAutoOpenFrontDoorInterval(message['auto_open_front_interval'])
            if 'enable_auto_open_communal' in message.keys():
                device.setEnableAutoOpenCommunalDoor(bool(message['enable_auto_open_communal']))
            if 'auto_open_communal_interval' in message.keys():
                device.setAutoOpenCommunalDoorInterval(message['auto_open_communal_interval'])

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
                self.send_command(
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

    def onSubphoneCommandOpenFrontDoor(self, index: int, room_index: int):
        device = self.findDevice(DeviceType.SUBPHONE, index, room_index)
        if device:
            self.send_command(
                device=device,
                category='lock_front',
                target="Unsecured"
            )

    def onSubphoneCommandOpenCommunalDoor(self, index: int, room_index: int):
        device = self.findDevice(DeviceType.SUBPHONE, index, room_index)
        if device:
            self.send_command(
                device=device,
                category='lock_communal',
                target="Unsecured"
            )

    def startFFServer(self):
        try:
            subphone: SubPhone = self.findDevice(DeviceType.SUBPHONE, 0, 0)
            if subphone is None:
                return
            if not subphone.enable_streaming:
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
        try:
            psutil.Process(self.pid_ffserver_proc).kill()
        except Exception as e:
            writeLog(f'Failed to kill FFServer Process ({self.pid_ffserver_proc})::{e}', self)
            traceback.print_exc()

        if self.mp_ffserver is not None:
            try:
                self.mp_ffserver.terminate()
                writeLog(f'FFServer Process Terminated', self)
            except Exception as e:
                writeLog(f'Failed to terminate FFServer MultiProc::{e}', self)
                traceback.print_exc()
        self.mp_ffserver = None

    def startFFMpeg(self):
        try:
            subphone: SubPhone = self.findDevice(DeviceType.SUBPHONE, 0, 0)
            if subphone is None:
                return
            if not subphone.enable_streaming:
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
        try:
            psutil.Process(self.pid_ffmpeg_proc).kill()
        except Exception as e:
            writeLog(f'Failed to kill FFMpeg Process ({self.pid_ffmpeg_proc})::{e}', self)
            traceback.print_exc()

        if self.mp_ffmpeg is not None:
            try:
                self.mp_ffmpeg.terminate()
                writeLog(f'FFMpeg Process Terminated', self)
            except Exception as e:
                writeLog(f'Failed to terminate FFMpeg MultiProc::{e}', self)
                traceback.print_exc()
        self.mp_ffmpeg = None

    """
    def onMqttCommandDookLock(self, topic: str, message: dict):
        if 'state' in message.keys():
            self.send_command(
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
        self.deactivateHaAddonDiscoveryOption()
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
            dev_idx: int = result.get('index', 0)
            room_index: int = result.get('room_index', 0)
            parser_index: int = result.get('parser_index', 0)
            
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

    def getRegisteredDeviceList(self, entry_node: ET.Element) -> List[dict]:
        registered = list()
        for elem in list(entry_node):
            entry = dict()
            if elem.tag == 'light':
                entry['type'] = DeviceType.LIGHT
            elif elem.tag == 'emotionlight':
                entry['type'] = DeviceType.EMOTIONLIGHT
            elif elem.tag == 'dimminglight':
                entry['type'] = DeviceType.DIMMINGLIGHT
            elif elem.tag == 'outlet':
                entry['type'] = DeviceType.OUTLET
            elif elem.tag == 'thermostat':
                entry['type'] = DeviceType.THERMOSTAT
            elif elem.tag == 'airconditioner':
                entry['type'] = DeviceType.AIRCONDITIONER
            elif elem.tag == 'gasvalve':
                entry['type'] = DeviceType.GASVALVE
            elif elem.tag == 'ventilator':
                entry['type'] = DeviceType.VENTILATOR
            elif elem.tag == 'elevator':
                entry['type'] = DeviceType.ELEVATOR
            elif elem.tag == 'subphone':
                entry['type'] = DeviceType.SUBPHONE
            elif elem.tag == 'batchoffsw':
                entry['type'] = DeviceType.BATCHOFFSWITCH
            elif elem.tag == 'hems':
                entry['type'] = DeviceType.HEMS
            else:
                continue
            try:
                child = elem.find('index')
                entry['index'] = int(child.text)
            except Exception:
                entry['index'] = None
            try:
                child = elem.find('room')
                entry['room_index'] = int(child.text)
            except Exception:
                entry['room_index'] = None
            registered.append(entry)
        return registered

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
            registered = self.getRegisteredDeviceList(entry_node)

            for elem in self.discovered_dev_list:
                dev_type: DeviceType = elem.get('type')
                dev_idx: int = elem.get('index')
                room_index: int = elem.get('room_index')
                parser_index: int = elem.get('parser_index')

                find = list(filter(lambda x: x.get('type') == dev_type and x.get('index') == dev_idx and x.get('room_index') == room_index, registered))
                if len(find) > 0:
                    # writeLog(f"{dev_type.name} (index: {dev_idx}, room: {room_index}) is already registered", self)
                    continue

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
                entry_info['rs485_port_index'] = parser_index

                self.parser_mapping[dev_type] = parser_index
                
                if dev_type is DeviceType.LIGHT:
                    entry_info['type'] = 'light'
                elif dev_type is DeviceType.EMOTIONLIGHT:
                    entry_info['type'] = 'emotionlight'
                elif dev_type is DeviceType.DIMMINGLIGHT:
                    entry_info['type'] = 'dimminglight'
                    entry_info['max_brightness_level'] = 7
                    entry_info['convert_method'] = 0
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
                    entry_info['packet_call_type'] = 0
                    entry_info['check_command_method'] = 0
                    entry_info['packet_command_call_down_value'] = 6
                elif dev_type is DeviceType.SUBPHONE:
                    entry_info['type'] = 'subphone'
                    entry_info['enable_video_streaming'] = 0
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
            child_node.text = str(self.parser_mapping.get(DeviceType.LIGHT, 0))

            child_node = parser_mapping_node.find('emotionlight')
            if child_node is None:
                child_node = ET.Element('emotionlight')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping.get(DeviceType.EMOTIONLIGHT, 0))

            child_node = parser_mapping_node.find('dimminglight')
            if child_node is None:
                child_node = ET.Element('dimminglight')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping.get(DeviceType.DIMMINGLIGHT, 0))

            child_node = parser_mapping_node.find('outlet')
            if child_node is None:
                child_node = ET.Element('outlet')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping.get(DeviceType.OUTLET, 0))

            child_node = parser_mapping_node.find('gasvalve')
            if child_node is None:
                child_node = ET.Element('gasvalve')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping.get(DeviceType.GASVALVE, 0))

            child_node = parser_mapping_node.find('thermostat')
            if child_node is None:
                child_node = ET.Element('thermostat')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping.get(DeviceType.THERMOSTAT, 0))

            child_node = parser_mapping_node.find('ventilator')
            if child_node is None:
                child_node = ET.Element('ventilator')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping.get(DeviceType.VENTILATOR, 0))

            child_node = parser_mapping_node.find('airconditioner')
            if child_node is None:
                child_node = ET.Element('airconditioner')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping.get(DeviceType.AIRCONDITIONER, 0))

            child_node = parser_mapping_node.find('elevator')
            if child_node is None:
                child_node = ET.Element('elevator')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping.get(DeviceType.ELEVATOR, 0))

            child_node = parser_mapping_node.find('subphone')
            if child_node is None:
                child_node = ET.Element('subphone')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping.get(DeviceType.SUBPHONE, 0))

            child_node = parser_mapping_node.find('batchoffsw')
            if child_node is None:
                child_node = ET.Element('batchoffsw')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping.get(DeviceType.BATCHOFFSWITCH, 0))

            child_node = parser_mapping_node.find('hems')
            if child_node is None:
                child_node = ET.Element('hems')
                parser_mapping_node.append(child_node)
            child_node.text = str(self.parser_mapping.get(DeviceType.HEMS, 0))

            writeXmlFile(root, self.config_file_path)
        except Exception as e:
            writeLog('saveDiscoverdDevicesToConfigFile::Exception::{}'.format(e), self)

    def clearAllDevices(self):
        try:
            if self.config_tree is None:
                return
            root = self.config_tree.getroot()
            device_node = root.find('device')
            if device_node is None:
                device_node = ET.Element('device')
                root.append(device_node)

            # delete all <entry> nodes
            entry_node = device_node.find('entry')
            if entry_node is None:
                entry_node = ET.Element('entry')
                device_node.append(entry_node)
            for child in list(entry_node):
                entry_node.remove(child)
            
            # set <device> - <clear> node value as 0
            clear_node = device_node.find('clear')
            if clear_node is None:
                clear_node = ET.Element('clear')
                device_node.append(clear_node)
            clear_node.text = '0'

            writeXmlFile(root, self.config_file_path)

            self.disableHaAddonClearDeviceOption()
            writeLog('Finished clearing all devices, app will be restarted...', self)
        except Exception as e:
            writeLog('clearAllDevices::Exception::{}'.format(e), self)

    def callBashIO(self, script: str):
        try:
            if not os.path.isfile('/usr/bin/bashio'):
                writeLog('cannot locate bashio', self)
                return False

            # create shell script file
            tmp_path = os.path.join(CURPATH, 'temp.sh')
            with open(tmp_path, 'w') as fp:
                fp.write("\n".join(["#!/usr/bin/env bashio", script]))

            if not os.path.isfile(tmp_path):
                writeLog('Failed to create temp shell script', self)
                return
            
            # call shell script using bashio
            cmd = f"/usr/bin/bashio {tmp_path}"
            with subprocess.Popen(cmd,
                shell=True, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT
            ) as subproc:
                buff = subproc.stdout.read()
                msg = f"deactivateHaAddonDiscoveryOption::bashio call result:{buff.decode(encoding='UTF-8', errors='ignore')}"
                writeLog(msg, self)
            
            # remove shell script file
            os.remove(tmp_path)
        except Exception as e:
            writeLog('deactivateHaAddonDiscoveryOption::Exception::{}'.format(e), self)

    def deactivateHaAddonDiscoveryOption(self):
        self.callBashIO("$(bashio::addon.option 'discovery.activate' ^false)")

    def disableHaAddonClearDeviceOption(self):
        self.callBashIO("$(bashio::addon.option 'etc.clear_all_devices' ^false)")


home_: Union[Home, None] = None


def get_home(name: str = '', config_file_path: str = None) -> Home:
    global home_
    if home_ is None:
        home_ = Home(name=name, config_file_path=config_file_path)
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
