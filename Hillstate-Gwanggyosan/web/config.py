import os
import sys
import shutil
from typing import Union
from flask import Flask
import xml.etree.ElementTree as ET
CURPATH = os.path.dirname(os.path.abspath(__file__))  # {$PROJECT}/web
PROJPATH = os.path.dirname(CURPATH)  # {$PROJECT}
INCPATH = os.path.join(PROJPATH, 'Include')
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
            child.text = cfg.get('host')
            child = node.find('port')
            if child is None:
                child = ET.Element('port')
                node.append(child)
            child.text = str(cfg.get('port'))
            child = node.find('username')
            if child is None:
                child = ET.Element('username')
                node.append(child)
            child.text = cfg.get('username')
            child = node.find('password')
            if child is None:
                child = ET.Element('password')
                node.append(child)
            child.text = cfg.get('password')
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
                elem.text = port_conf.get('name')
                elem = child.find('index')
                if elem is None:
                    elem = ET.Element('index')
                    child.append(elem)
                elem.text = str(port_conf.get('index'))
                elem = child.find('enable')
                if elem is None:
                    elem = ET.Element('enable')
                    child.append(elem)
                elem.text = str(int(port_conf.get('enable')))
                elem = child.find('hwtype')
                if elem is None:
                    elem = ET.Element('hwtype')
                    child.append(elem)
                elem.text = str(int(port_conf.get('hwtype')))
                elem = child.find('packettype')
                if elem is None:
                    elem = ET.Element('packettype')
                    child.append(elem)
                elem.text = str(port_conf.get('packettype'))
                elem = child.find('usb2serial')
                if elem is None:
                    elem = ET.Element('usb2serial')
                    child.append(elem)
                elem2 = elem.find('port')
                if elem2 is None:
                    elem2 = ET.Element('port')
                    elem.append(elem2)
                elem2.text = port_conf.get('serial')
                elem2 = elem.find('baud')
                if elem2 is None:
                    elem2 = ET.Element('baud')
                    elem.append(elem2)
                elem2.text = str(port_conf.get('baudrate'))
                elem2 = elem.find('databit')
                if elem2 is None:
                    elem2 = ET.Element('databit')
                    elem.append(elem2)
                elem2.text = str(port_conf.get('databit'))
                elem2 = elem.find('parity')
                if elem2 is None:
                    elem2 = ET.Element('parity')
                    elem.append(elem2)
                elem2.text = port_conf.get('parity')
                elem2 = elem.find('stopbits')
                if elem2 is None:
                    elem2 = ET.Element('stopbits')
                    elem.append(elem2)
                elem2.text = str(port_conf.get('stopbits'))
                elem = child.find('ew11')
                if elem is None:
                    elem = ET.Element('ew11')
                    child.append(elem)
                elem2 = elem.find('ipaddr')
                if elem2 is None:
                    elem2 = ET.Element('ipaddr')
                    elem.append(elem2)
                elem2.text = port_conf.get('socketaddr')
                elem2 = elem.find('port')
                if elem2 is None:
                    elem2 = ET.Element('port')
                    elem.append(elem2)
                elem2.text = str(port_conf.get('socketport'))
                elem = child.find('check')
                if elem is None:
                    elem = ET.Element('check')
                    child.append(elem)
                elem.text = '1'
                elem = child.find('buffsize')
                if elem is None:
                    elem = ET.Element('buffsize')
                    child.append(elem)
                elem.text = '64'
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
            elem3.text = cfg.get('prefix')

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
            elem2.text = str(int(cfg.get('activate')))
            elem2 = elem.find('timeout')
            if elem2 is None:
                elem2 = ET.Element('timeout')
                elem.append(elem2)
            elem2.text = str(cfg.get('timeout'))
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
                'hems'
            ]
            for n in names:
                elem2 = elem.find(n)
                if elem2 is None:
                    elem2 = ET.Element(n)
                    elem.append(elem2)
                elem2.text = str(cfg.get(n))
            writeXmlFile(root, self._config_file_path)
        except Exception as e:
            print(f'Config::set_config_parser_mapping::Exception {e}')

    def set_config_etc(self, cfg: dict):
        if not os.path.isfile(self._config_file_path):
            return
        try:
            root = ET.parse(self._config_file_path).getroot()
            node = root.find('rs485')
            if node is None:
                return
            port_nodes = list(filter(lambda x: x.tag == 'port', list(node)))
            for pnode in port_nodes:
                elem = pnode.find('thermo_len_per_dev')
                if elem is None:
                    elem = ET.Element('thermo_len_per_dev')
                    pnode.append(elem)
                elem.text = str(cfg.get('thermo_len_per_dev'))
            
            node = root.find('device')
            if node is None:
                return
            entry_node = node.find('entry')
            if entry_node is None:
                return
            
            elev_nodes = list(filter(lambda x: x.tag == 'elevator', list(entry_node)))
            for pnode in list(elev_nodes):
                elem = pnode.find('packet_call_type')
                if elem is None:
                    elem = ET.Element('packet_call_type')
                    pnode.append(elem)
                elem.text = str(cfg.get('elevator_packet_call_type'))
                elem = pnode.find('check_command_method')
                if elem is None:
                    elem = ET.Element('check_command_method')
                    pnode.append(elem)
                elem.text = str(cfg.get('elevator_check_command_method'))
            
            thermo_nodes = list(filter(lambda x: x.tag == 'thermostat', list(entry_node)))
            for pnode in list(thermo_nodes):
                elem = pnode.find('range_min')
                if elem is None:
                    elem = ET.Element('range_min')
                    pnode.append(elem)
                elem.text = str(cfg.get('thermostat_range_min'))
                elem = pnode.find('range_max')
                if elem is None:
                    elem = ET.Element('range_max')
                    pnode.append(elem)
                elem.text = str(cfg.get('thermostat_range_max'))
            
            aircon_nodes = list(filter(lambda x: x.tag == 'airconditioner', list(entry_node)))
            for pnode in list(aircon_nodes):
                elem = pnode.find('range_min')
                if elem is None:
                    elem = ET.Element('range_min')
                    pnode.append(elem)
                elem.text = str(cfg.get('airconditioner_range_min'))
                elem = pnode.find('range_max')
                if elem is None:
                    elem = ET.Element('range_max')
                    pnode.append(elem)
                elem.text = str(cfg.get('airconditioner_range_max'))

            writeXmlFile(root, self._config_file_path)
        except Exception as e:
            print(f'Config::set_config_etc::Exception {e}')


config_: Union[Config, None] = None


def get_app_config(config_file_path: str = None):
    global config_
    if config_ is None:
        config_ = Config(config_file_path)
    return config_
