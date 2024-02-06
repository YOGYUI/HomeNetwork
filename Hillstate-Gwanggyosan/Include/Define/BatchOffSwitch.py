import json
from Device import *


class BatchOffSwitch(Device):
    def __init__(self, name: str = 'BatchOffSW', index: int = 0, room_index: int = 0):
        super().__init__(name, index, room_index)
        self.dev_type = DeviceType.BATCHOFFSWITCH
        self.unique_id = f'batchoffswitch_{self.room_index}_{self.index}'
        self.mqtt_publish_topic = f'home/state/batchoffsw/{self.room_index}/{self.index}'
        self.mqtt_subscribe_topic = f'home/command/batchoffsw/{self.room_index}/{self.index}'
    
    def setDefaultName(self):
        self.name = 'BatchOffSW'

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
            "icon": "mdi:home-lightbulb-outline"
        }
        self.mqtt_client.publish(topic, json.dumps(obj), 1, retain)

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
