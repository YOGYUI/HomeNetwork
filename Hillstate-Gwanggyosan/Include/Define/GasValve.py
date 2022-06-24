import json
from Device import *


class GasValve(Device):
    def __init__(self, name: str = 'GasValve', **kwargs):
        super().__init__(name, **kwargs)
    
    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += '>'
        return repr_txt
    
    def publish_mqtt(self):
        obj = {"state": self.state}
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)
        
    def makePacketQueryState(self) -> bytearray:
        # F7 0B 01 1B 01 43 11 00 00 B5 EE
        return bytearray([0xF7, 0x0B, 0x01, 0x1B, 0x01, 0x43, 0x11, 0x00, 0x00, 0xB5, 0xEE])

    def makePacketSetState(self, state: bool) -> bytearray:
        # F7 0B 01 1B 02 43 11 XX 00 YY EE
        # XX: 03 = OFF, 04 = ON (지원되지 않음)
        # YY: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x1B, 0x02, 0x43, 0x11])
        if state:
            packet.extend([0x04, 0x00])
        else:
            packet.extend([0x03, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet
