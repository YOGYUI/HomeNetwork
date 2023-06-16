import json
from Device import *


class GasValve(Device):
    def __init__(self, name: str = 'GasValve', index: int = 0, room_index: int = 0):
        super().__init__(name, index, room_index)
        self.dev_type = DeviceType.GASVALVE
        self.mqtt_publish_topic = f'home/state/gasvalve/{self.room_index}/{self.index}'
        self.mqtt_subscribe_topic = f'home/command/gasvalve/{self.room_index}/{self.index}'

    def setDefaultName(self):
        self.name = 'GasValve'

    def publishMQTT(self):
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
