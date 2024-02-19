import os
import shutil
from flask import Flask
import xml.etree.ElementTree as ET


class Config:
    HOST: str = '0.0.0.0'
    PORT: int = 9999
    LOG: bool = False

    SECRET_KEY = 'My Secret Key'  # for CSRF

    def init_app(self, app: Flask):
        curpath = os.path.dirname(os.path.abspath(__file__))  # {$PROJECT}/web
        projpath = os.path.dirname(curpath)  # {$PROJECT}
        xml_path = os.path.join(projpath, 'config.xml')
    
        if not os.path.isfile(xml_path):
            xml_default_path = os.path.join(projpath, 'config_default.xml')
            if os.path.isfile(xml_default_path):
                shutil.copy(xml_default_path, xml_path)

        try:
            if os.path.isfile(xml_path):
                root = ET.parse(xml_path).getroot()
                node = root.find('webserver')
                node_host = node.find('host')
                self.HOST = node_host.text
                node_port = node.find('port')
                self.PORT = int(node_port.text)
                node_log = node.find('log')
                self.LOG = bool(int(node_log.text))
        except Exception as e:
            print(f'Config - Exception {e}')


config = Config()
