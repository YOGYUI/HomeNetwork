import json
from Device import *


class Outlet(Device):
    enable_off_command: bool = False

    def __init__(self, name: str = 'Outlet', index: int = 0, room_index: int = 0):
        super().__init__(name, index, room_index)
        self.dev_type = DeviceType.OUTLET
        self.unique_id = f'outlet_{self.room_index}_{self.index}'
        self.mqtt_publish_topic = f'home/state/outlet/{self.room_index}/{self.index}'
        self.mqtt_subscribe_topic = f'home/command/outlet/{self.room_index}/{self.index}'

    def setDefaultName(self):
        self.name = 'Outlet'

    def __repr__(self):
        # repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))}) '
        repr_txt = f'<{self.__class__.__name__}, {self.name}, '
        repr_txt += f'Dev Idx: {self.index}, '
        repr_txt += f'Room Idx: {self.room_index}, '
        repr_txt += f'Enable Off Cmd: {self.enable_off_command}'
        repr_txt += '>'
        return repr_txt
    
    def setEnableOffCommand(self, value: bool):
        self.enable_off_command = value

    def publishMQTT(self):
        obj = {"state": self.state}
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)

    def configMQTT(self, retain: bool = False):
        if self.mqtt_client is None:
            return
        
        topic = f'{self.ha_discovery_prefix}/switch/{self.unique_id}/config'
        obj = {
            "name": self.name,
            "object_id": self.unique_id,
            "unique_id": self.unique_id,
            "state_topic": self.mqtt_publish_topic,
            "command_topic": self.mqtt_subscribe_topic,
            "value_template": '{ "state": {{ value_json.state }} }',
            "payload_on": '{ "state": 1 }',
            "payload_off": '{ "state": 0 }',
            "icon": "mdi:power-socket-de"
        }
        self.mqtt_client.publish(topic, json.dumps(obj), 1, retain)

    def makePacketQueryState(self) -> bytearray:
        # F7 0B 01 1F 01 40 XX 00 00 YY EE
        # XX: 상위 4비트 = Room Index, 하위 4비트 = 0
        # YY: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x1F, 0x01, 0x40])
        # packet.append(self.room_index << 4)
        packet.append((self.room_index << 4) + (self.index + 1))
        packet.extend([0x00, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

    def makePacketSetState(self, state: bool) -> bytearray:
        # F7 0B 01 1F 02 40 XX YY 00 ZZ EE
        # XX: 상위 4비트 = Room Index, 하위 4비트 = Device Index (1-based)
        # YY: 02 = OFF, 01 = ON
        # ZZ: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x1F, 0x02, 0x40])
        packet.append((self.room_index << 4) + (self.index + 1))
        if state:
            packet.extend([0x01, 0x00])
        else:
            packet.extend([0x02, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet
