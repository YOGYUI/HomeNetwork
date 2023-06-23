import json
from Device import *


class GasValve(Device):
    def __init__(self, name: str = 'GasValve', index: int = 0, room_index: int = 0):
        super().__init__(name, index, room_index)
        self.dev_type = DeviceType.GASVALVE
        self.unique_id = f'gasvalve_{self.room_index}_{self.index}'
        self.mqtt_publish_topic = f'home/state/gasvalve/{self.room_index}/{self.index}'
        self.mqtt_subscribe_topic = f'home/command/gasvalve/{self.room_index}/{self.index}'
        self.setHomeAssistantConfigTopic()

    def setDefaultName(self):
        self.name = 'GasValve'

    def publishMQTT(self):
        obj = {"state": self.state}
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)
    
    def setHomeAssistantConfigTopic(self):
        self.mqtt_config_topic = f'{self.ha_discovery_prefix}/switch/{self.unique_id}/config'

    def configMQTT(self):
        obj = {
            "name": self.name,
            "object_id": self.unique_id,
            "unique_id": self.unique_id,
            "state_topic": self.mqtt_publish_topic,
            "command_topic": self.mqtt_subscribe_topic,
            "value_template": '{ "state": {{ value_json.state }} }',
            "payload_on": '{ "state": 1 }',
            "payload_off": '{ "state": 0 }',
            "icon": "mdi:pipe-valve"
        }
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_config_topic, json.dumps(obj), 1, True)

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
