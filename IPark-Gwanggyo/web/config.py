import os
from flask import Flask
import xml.etree.ElementTree as ET


class Config:
    HOST: str = '0.0.0.0'
    PORT: int = 9999

    SECRET_KEY = 'Yogyui Secret Key'  # for CSRF

    def init_app(self, app: Flask):
        curpath = os.path.dirname(os.path.abspath(__file__))  # /project/web
        projpath = os.path.dirname(curpath)  # /project
        xml_path = os.path.join(projpath, 'config.xml')

        try:
            if os.path.isfile(xml_path):
                root = ET.parse(xml_path).getroot()
                node = root.find('webserver')
                node_host = node.find('host')
                self.HOST = node_host.text
                node_port = node.find('port')
                self.PORT = int(node_port.text)
        except Exception as e:
            print(f'Config - Exception {e}')


config = Config()
