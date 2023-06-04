import json
from Device import *


class BatchOffSwitch(Device):
    def __init__(self, name: str = 'BatchOffSW', **kwargs):
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
        # F7 0E 01 2A 01 40 10 00 19 00 1B 03 82 EE
        return bytearray([0xF7, 0x0E, 0x01, 0x2A, 0x01, 0x40, 0x10, 0x00, 0x19, 0x00, 0x1B, 0x03, 0x82, 0xEE])

    def makePacketSetState(self, state: bool) -> bytearray:
        # F7 0C 01 2A 02 40 11 XX 19 00 YY EE
        # XX: 02 = OFF 01 = ON
        # YY: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0C, 0x01, 0x2A, 0x02, 0x40, 0x11])
        if state:
            packet.extend([0x01, 0x19, 0x00])
        else:
            packet.extend([0x02, 0x19, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet
