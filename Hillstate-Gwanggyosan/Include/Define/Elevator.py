import json
from Device import *


class Elevator(Device):
    floor1: int = 0  # 엘리베이터1의 현재 층수
    floor2: int = 0  # 엘리베이터2의 현재 층수

    def __init__(self, name: str = 'Elevator', **kwargs):
        super().__init__(name, **kwargs)
    
    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += '>'
        return repr_txt
    
    def publish_mqtt(self):
        obj = {"state": self.state}
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)
    
    def makePacketCall(self):
        pass
