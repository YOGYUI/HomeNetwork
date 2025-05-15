import os
import sys
import shutil
from typing import Union
from flask import Flask
import xml.etree.ElementTree as ET
CURPATH = os.path.dirname(os.path.abspath(__file__))  # {$PROJECT}/web
PROJPATH = os.path.dirname(CURPATH)  # {$PROJECT}
INCPATH = os.path.join(PROJPATH, 'Include')
sys.path.extend([CURPATH, PROJPATH, INCPATH])
sys.path = list(set(sys.path))
from Common import writeXmlFile


class Config:
    HOST: str = '0.0.0.0'
    PORT: int = 7929
    LOG: bool = False

    SECRET_KEY = 'My Secret Key'  # for CSRF

    def __init__(self, file_path: str = None):
        self._config_file_path = file_path
        if file_path is None:
            self._config_file_path = os.path.join(PROJPATH, 'config.xml')

    def init_app(self, app: Flask):
        if not os.path.isfile(self._config_file_path):
            xml_default_path = os.path.join(PROJPATH, 'config_default.xml')
            if os.path.isfile(xml_default_path):
                shutil.copy(xml_default_path, self._config_file_path)

        try:
            if os.path.isfile(self._config_file_path):
                root = ET.parse(self._config_file_path).getroot()
                node = root.find('webserver')
                node_host = node.find('host')
                self.HOST = node_host.text
                node_port = node.find('port')
                self.PORT = int(node_port.text)
                node_log = node.find('log')
                self.LOG = bool(int(node_log.text))
        except Exception as e:
            print(f'Config::init_app::Exception {e}')
    
    def set_config_mqtt_broker(self, cfg: dict):
        if not os.path.isfile(self._config_file_path):
            return
        try:
            root = ET.parse(self._config_file_path).getroot()
            node = root.find('mqtt')
            if node is None:
                node = ET.Element('mqtt')
                root.append(node)
            child = node.find('host')
            if child is None:
                child = ET.Element('host')
                node.append(child)
            child.text = cfg.get('host', 'core-mosquitto')
            child = node.find('port')
            if child is None:
                child = ET.Element('port')
                node.append(child)
            child.text = str(cfg.get('port', 1883))
            child = node.find('username')
            if child is None:
                child = ET.Element('username')
                node.append(child)
            child.text = cfg.get('username', 'username')
            child = node.find('password')
            if child is None:
                child = ET.Element('password')
                node.append(child)
            child.text = cfg.get('password', 'password')
            child = node.find('client_id')
            if child is None:
                child = ET.Element('client_id')
                node.append(child)
            child.text = cfg.get('client_id', 'yogyui_hyundai_ht')

            subnode = node.find('tls')
            if subnode is None:
                subnode = ET.Element('tls')
                node.append(subnode)
            child = subnode.find('enable')
            if child is None:
                child = ET.Element('enable')
                subnode.append(child)
            child.text = str(int(cfg.get('tls_enable', False)))
            child = subnode.find('ca_certs')
            if child is None:
                child = ET.Element('ca_certs')
                subnode.append(child)
            child.text = cfg.get('tls_ca_certs', '/config/ssl/cacert.pem')
            child = subnode.find('certfile')
            if child is None:
                child = ET.Element('certfile')
                subnode.append(child)
            child.text = cfg.get('tls_certfile', '/config/ssl/fullchain.pem')
            child = subnode.find('keyfile')
            if child is None:
                child = ET.Element('keyfile')
                subnode.append(child)
            child.text = cfg.get('tls_keyfile', '/config/ssl/privkey.pem')

            writeXmlFile(root, self._config_file_path)
        except Exception as e:
            print(f'Config::set_config_mqtt_broker::Exception {e}')

    def set_config_rs485(self, cfg: list):
        if not os.path.isfile(self._config_file_path):
            return
        try:
            root = ET.parse(self._config_file_path).getroot()
            node = root.find('rs485')
            if node is None:
                node = ET.Element('rs485')
                root.append(node)
                child = ET.Element('reconnect_limit')
                node.append(child)
                child.text = '30'
            port_nodes = list(filter(lambda x: x.tag == 'port', list(node)))
            for i, port_conf in enumerate(cfg):
                if len(port_nodes) > i:
                    child = port_nodes[i]
                else:
                    child = ET.Element('port')
                    node.append(child)
                elem = child.find('name')
                if elem is None:
                    elem = ET.Element('name')
                    child.append(elem)
                elem.text = port_conf.get('name', f'port{i + 1}')
                elem = child.find('index')
                if elem is None:
                    elem = ET.Element('index')
                    child.append(elem)
                elem.text = str(port_conf.get('index', 0))
                elem = child.find('enable')
                if elem is None:
                    elem = ET.Element('enable')
                    child.append(elem)
                elem.text = str(int(port_conf.get('enable', True)))
                elem = child.find('hwtype')
                if elem is None:
                    elem = ET.Element('hwtype')
                    child.append(elem)
                elem.text = str(int(port_conf.get('hwtype', 0)))
                elem = child.find('packettype')
                if elem is None:
                    elem = ET.Element('packettype')
                    child.append(elem)
                elem.text = str(port_conf.get('packettype', 0))
                elem = child.find('usb2serial')
                if elem is None:
                    elem = ET.Element('usb2serial')
                    child.append(elem)
                elem2 = elem.find('port')
                if elem2 is None:
                    elem2 = ET.Element('port')
                    elem.append(elem2)
                elem2.text = port_conf.get('serial', '/dev/ttyUSB0')
                elem2 = elem.find('baud')
                if elem2 is None:
                    elem2 = ET.Element('baud')
                    elem.append(elem2)
                elem2.text = str(port_conf.get('baudrate', 9600))
                elem2 = elem.find('databit')
                if elem2 is None:
                    elem2 = ET.Element('databit')
                    elem.append(elem2)
                elem2.text = str(port_conf.get('databit', 8))
                elem2 = elem.find('parity')
                if elem2 is None:
                    elem2 = ET.Element('parity')
                    elem.append(elem2)
                elem2.text = port_conf.get('parity', 'N')
                elem2 = elem.find('stopbits')
                if elem2 is None:
                    elem2 = ET.Element('stopbits')
                    elem.append(elem2)
                elem2.text = str(port_conf.get('stopbits', 1))
                elem = child.find('ew11')
                if elem is None:
                    elem = ET.Element('ew11')
                    child.append(elem)
                elem2 = elem.find('ipaddr')
                if elem2 is None:
                    elem2 = ET.Element('ipaddr')
                    elem.append(elem2)
                elem2.text = port_conf.get('socketaddr', '127.0.0.1')
                elem2 = elem.find('port')
                if elem2 is None:
                    elem2 = ET.Element('port')
                    elem.append(elem2)
                elem2.text = str(port_conf.get('socketport', 8899))
                elem = child.find('check')
                if elem is None:
                    elem = ET.Element('check')
                    child.append(elem)
                elem.text = str(int(port_conf.get('check_connection', True)))
                elem = child.find('buffsize')
                if elem is None:
                    elem = ET.Element('buffsize')
                    child.append(elem)
                elem.text = '64'
                elem = child.find('command')
                if elem is None:
                    elem = ET.Element('command')
                    child.append(elem)
                elem2 = elem.find('interval_ms')
                if elem2 is None:
                    elem2 = ET.Element('interval_ms')
                    elem.append(elem2)
                elem2.text = str(port_conf.get('cmd_interval_ms', 200))
                elem2 = elem.find('retry_count')
                if elem2 is None:
                    elem2 = ET.Element('retry_count')
                    elem.append(elem2)
                elem2.text = str(port_conf.get('cmd_retry_count', 10))
            writeXmlFile(root, self._config_file_path)
        except Exception as e:
            print(f'Config::set_config_rs485::Exception {e}')

    def set_config_discovery(self, cfg: dict):
        if not os.path.isfile(self._config_file_path):
            return
        try:
            root = ET.parse(self._config_file_path).getroot()
            node = root.find('mqtt')
            if node is None:
                node = ET.Element('mqtt')
                root.append(node)
            elem = node.find('homeassistant')
            if elem is None:
                elem = ET.Element('homeassistant')
                node.append(elem)
            elem2 = elem.find('discovery')
            if elem2 is None:
                elem2 = ET.Element('discovery')
                elem.append(elem2)
            elem3 = elem2.find('enable')
            if elem3 is None:
                elem3 = ET.Element('enable')
                elem2.append(elem3)
            elem3.text = '1'
            elem3 = elem2.find('prefix')
            if elem3 is None:
                elem3 = ET.Element('prefix')
                elem2.append(elem3)
            elem3.text = cfg.get('prefix', 'homeassistant')

            node = root.find('device')
            if node is None:
                node = ET.Element('device')
                root.append(node)
            elem = node.find('discovery')
            if elem is None:
                elem = ET.Element('discovery')
                node.append(elem)
            elem2 = elem.find('reload')
            if elem2 is None:
                elem2 = ET.Element('reload')
                elem.append(elem2)
            elem2.text = '1'
            elem2 = elem.find('enable')
            if elem2 is None:
                elem2 = ET.Element('enable')
                elem.append(elem2)
            elem2.text = str(int(cfg.get('activate', False)))
            elem2 = elem.find('timeout')
            if elem2 is None:
                elem2 = ET.Element('timeout')
                elem.append(elem2)
            elem2.text = str(cfg.get('timeout', 60))
            writeXmlFile(root, self._config_file_path)
        except Exception as e:
            print(f'Config::set_config_discovery::Exception {e}')

    def set_config_parser_mapping(self, cfg: dict):
        if not os.path.isfile(self._config_file_path):
            return
        try:
            root = ET.parse(self._config_file_path).getroot()
            node = root.find('device')
            if node is None:
                node = ET.Element('device')
                root.append(node)
            elem = node.find('parser_mapping')
            if elem is None:
                elem = ET.Element('parser_mapping')
                node.append(elem)

            names = [
                'light',
                'outlet',
                'gasvalve',
                'thermostat',
                'ventilator',
                'airconditioner',
                'elevator',
                'subphone',
                'batchoffsw',
                'hems',
                'emotionlight',
                'dimminglight',
            ]
            for n in names:
                elem2 = elem.find(n)
                if elem2 is None:
                    elem2 = ET.Element(n)
                    elem.append(elem2)
                if n in cfg.keys():
                    elem2.text = str(cfg.get(n))
                else:
                    elem2.text = '0'
            writeXmlFile(root, self._config_file_path)
        except Exception as e:
            print(f'Config::set_config_parser_mapping::Exception {e}')

    def set_config_periodic_query_state(self, cfg: dict):
        if not os.path.isfile(self._config_file_path):
            return
        try:
            root = ET.parse(self._config_file_path).getroot()
            node = root.find('device')
            if node is None:
                return
            elem = node.find('periodic_query_state')
            if elem is None:
                elem = ET.Element('periodic_query_state')
                node.append(elem)
            elem2 = elem.find('enable')
            if elem2 is None:
                elem2 = ET.Element('enable')
                elem.append(elem2)
            elem2.text = str(int(cfg.get('enable', False)))
            elem2 = elem.find('period')
            if elem2 is None:
                elem2 = ET.Element('period')
                elem.append(elem2)
            elem2.text = str(cfg.get('period', 1000))
            elem2 = elem.find('verbose')
            if elem2 is None:
                elem2 = ET.Element('verbose')
                elem.append(elem2)
            elem2.text = str(int(cfg.get('verbose', True)))

            writeXmlFile(root, self._config_file_path)
        except Exception as e:
            print(f'Config::set_config_periodic_query_state::Exception {e}')

    def set_config_subphone(self, cfg: dict):
        if not os.path.isfile(self._config_file_path):
            return
        try:
            root = ET.parse(self._config_file_path).getroot()
            node = root.find('device')
            if node is None:
                node = ET.Element('device')
                root.append(node)
            entry_node = node.find('entry')
            if entry_node is None:
                entry_node = ET.Element('entry')
                node.append(entry_node)
            subphone_nodes = list(filter(lambda x: x.tag == 'subphone', list(entry_node)))
            if len(subphone_nodes) == 0:
                subphone_node = ET.Element('subphone')
                entry_node.append(subphone_node)
            else:
                subphone_node = subphone_nodes[0]  # todo: 실수로 여러개 추가했을 경우의 예외처리?
            elem = subphone_node.find('name')
            if elem is None:
                elem = ET.Element('name')
                subphone_node.append(elem)
                elem.text = 'SUBPHONE'
            elem = subphone_node.find('index')
            if elem is None:
                elem = ET.Element('index')
                subphone_node.append(elem)
                elem.text = '0'
            elem = subphone_node.find('room')
            if elem is None:
                elem = ET.Element('room')
                subphone_node.append(elem)
                elem.text = '0'
            elem = subphone_node.find('enable')
            if elem is None:
                elem = ET.Element('enable')
                subphone_node.append(elem)
            elem.text = str(int(cfg.get('enable', False)))
            elem = subphone_node.find('enable_video_streaming')
            if elem is None:
                elem = ET.Element('enable_video_streaming')
                subphone_node.append(elem)
            elem.text = str(int(cfg.get('enable_video_streaming', False)))
            
            ffmpeg_node = subphone_node.find('ffmpeg')
            if ffmpeg_node is None:
                ffmpeg_node = ET.Element('ffmpeg')
                subphone_node.append(ffmpeg_node)
            elem = ffmpeg_node.find('conf_file_path')
            if elem is None:
                elem = ET.Element('conf_file_path')
                ffmpeg_node.append(elem)
            elem.text = cfg.get('conf_file_path', '/etc/ffserver.conf')
            elem = ffmpeg_node.find('feed_path')
            if elem is None:
                elem = ET.Element('feed_path')
                ffmpeg_node.append(elem)
            elem.text = cfg.get('feed_path', 'http://0.0.0.0:8090/feed.ffm')
            elem = ffmpeg_node.find('input_device')
            if elem is None:
                elem = ET.Element('input_device')
                ffmpeg_node.append(elem)
            elem.text = cfg.get('input_device', '/dev/video0')
            elem = ffmpeg_node.find('frame_rate')
            if elem is None:
                elem = ET.Element('frame_rate')
                ffmpeg_node.append(elem)
            elem.text = str(cfg.get('frame_rate', 30))
            elem = ffmpeg_node.find('width')
            if elem is None:
                elem = ET.Element('width')
                ffmpeg_node.append(elem)
            elem.text = str(cfg.get('width', 640))
            elem = ffmpeg_node.find('height')
            if elem is None:
                elem = ET.Element('height')
                ffmpeg_node.append(elem)
            elem.text = str(cfg.get('height', 480))

            auto_open_front_door_node = subphone_node.find('auto_open_front_door')
            if auto_open_front_door_node is None:
                auto_open_front_door_node = ET.Element('auto_open_front_door')
                subphone_node.append(auto_open_front_door_node)
            elem = auto_open_front_door_node.find('enable')
            if elem is None:
                elem = ET.Element('enable')
                auto_open_front_door_node.append(elem)
            elem.text = str(int(cfg.get('enable_auto_open_front_door', False)))
            elem = auto_open_front_door_node.find('interval')
            if elem is None:
                elem = ET.Element('interval')
                auto_open_front_door_node.append(elem)
            elem.text = str(cfg.get('auto_open_front_door_interval', 3.0))

            auto_open_communal_door_node = subphone_node.find('auto_open_communal_door')
            if auto_open_communal_door_node is None:
                auto_open_communal_door_node = ET.Element('auto_open_communal_door')
                subphone_node.append(auto_open_communal_door_node)
            elem = auto_open_communal_door_node.find('enable')
            if elem is None:
                elem = ET.Element('enable')
                auto_open_communal_door_node.append(elem)
            elem.text = str(int(cfg.get('enable_auto_open_communal_door', False)))
            elem = auto_open_communal_door_node.find('interval')
            if elem is None:
                elem = ET.Element('interval')
                auto_open_communal_door_node.append(elem)
            elem.text = str(cfg.get('auto_open_communal_door_interval', 3.0))

            writeXmlFile(root, self._config_file_path)
        except Exception as e:
            print(f'Config::set_config_subphone::Exception {e}')

    def set_config_etc(self, cfg: dict):
        if not os.path.isfile(self._config_file_path):
            return
        try:
            root = ET.parse(self._config_file_path).getroot()
            node = root.find('rs485')
            if node is None:
                node = ET.Element('rs485')
                root.append(elem)
            port_nodes = list(filter(lambda x: x.tag == 'port', list(node)))
            for pnode in port_nodes:
                elem = pnode.find('thermo_len_per_dev')
                if elem is None:
                    elem = ET.Element('thermo_len_per_dev')
                    pnode.append(elem)
                elem.text = str(cfg.get('thermo_len_per_dev', 3))
            
            node = root.find('device')
            if node is None:
                node = ET.Element('device')
                root.append(node)
            entry_node = node.find('entry')
            if entry_node is None:
                entry_node = ET.Element('entry')
                node.append(entry_node)
            
            elev_nodes = list(filter(lambda x: x.tag == 'elevator', list(entry_node)))
            for pnode in list(elev_nodes):
                elem = pnode.find('packet_call_type')
                if elem is None:
                    elem = ET.Element('packet_call_type')
                    pnode.append(elem)
                elem.text = str(cfg.get('elevator_packet_call_type', 0))
                elem = pnode.find('check_command_method')
                if elem is None:
                    elem = ET.Element('check_command_method')
                    pnode.append(elem)
                elem.text = str(cfg.get('elevator_check_command_method', 0))
                elem = pnode.find('packet_command_call_down_value')
                if elem is None:
                    elem = ET.Element('packet_command_call_down_value')
                    pnode.append(elem)
                elem.text = str(cfg.get('elevator_packet_command_call_down_value', 6))
                elem = pnode.find('verbose_packet')
                if elem is None:
                    elem = ET.Element('verbose_packet')
                    pnode.append(elem)
                elem.text = str(int(cfg.get('elevator_verbose_packet', False)))
            
            thermo_nodes = list(filter(lambda x: x.tag == 'thermostat', list(entry_node)))
            for pnode in list(thermo_nodes):
                elem = pnode.find('range_min')
                if elem is None:
                    elem = ET.Element('range_min')
                    pnode.append(elem)
                elem.text = str(cfg.get('thermostat_range_min', 0))
                elem = pnode.find('range_max')
                if elem is None:
                    elem = ET.Element('range_max')
                    pnode.append(elem)
                elem.text = str(cfg.get('thermostat_range_max', 100))
            
            aircon_nodes = list(filter(lambda x: x.tag == 'airconditioner', list(entry_node)))
            for pnode in list(aircon_nodes):
                elem = pnode.find('range_min')
                if elem is None:
                    elem = ET.Element('range_min')
                    pnode.append(elem)
                elem.text = str(cfg.get('airconditioner_range_min', 0))
                elem = pnode.find('range_max')
                if elem is None:
                    elem = ET.Element('range_max')
                    pnode.append(elem)
                elem.text = str(cfg.get('airconditioner_range_max', 100))
            
            dimming_light_nodes = list(filter(lambda x: x.tag == 'dimminglight', list(entry_node)))
            for pnode in list(dimming_light_nodes):
                elem = pnode.find('max_brightness_level')
                if elem is None:
                    elem = ET.Element('max_brightness_level')
                    pnode.append(elem)
                elem.text = str(cfg.get('dimminglight_max_brightness_level', 7))
                elem = pnode.find('convert_method')
                if elem is None:
                    elem = ET.Element('convert_method')
                    pnode.append(elem)
                elem.text = str(cfg.get('dimminglight_convert_method', 0))
            
            clear_node = node.find('clear')
            if clear_node is None:
                clear_node = ET.Element('clear')
                node.append(clear_node)
            clear_node.text = str(int(cfg.get('clear_all_devices', False)))

            change_state_node = node.find('change_state_after_command')
            if change_state_node is None:
                change_state_node = ET.Element('change_state_after_command')
                node.append(change_state_node)
            change_state_node.text = str(int(cfg.get('change_device_state_after_command', False)))

            writeXmlFile(root, self._config_file_path)
        except Exception as e:
            print(f'Config::set_config_etc::Exception {e}')


config_: Union[Config, None] = None


def get_app_config(config_file_path: str = None):
    global config_
    if config_ is None:
        config_ = Config(config_file_path)
    return config_
