import json
from Device import *


class EmotionLight(Device):
    def __init__(self, name: str = 'EmotionLight', index: int = 0, room_index: int = 0, topic_prefix: str = 'home'):
        super().__init__(name, index, room_index, topic_prefix)
        self.dev_type = DeviceType.EMOTIONLIGHT
        self.unique_id = f'emotionlight_{self.room_index}_{self.index}'
        self.mqtt_state_topic = f'{topic_prefix}/state/emotionlight/{self.room_index}/{self.index}'
        self.mqtt_command_topic = f'{topic_prefix}/command/emotionlight/{self.room_index}/{self.index}'

    def setDefaultName(self):
        self.name = 'EmotionLight'

    def publishMQTT(self):
        obj = {"state": self.state}
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_state_topic, json.dumps(obj), 1)

    def configMQTT(self, retain: bool = False):
        if self.mqtt_client is None:
            return

        topic = f'{self.ha_discovery_prefix}/light/{self.unique_id}/config'
        obj = {
            "name": self.name,
            "object_id": self.unique_id,
            "unique_id": self.unique_id,
            "state_topic": self.mqtt_state_topic,
            "command_topic": self.mqtt_command_topic,
            "schema": "template",
            "state_template": "{% if value_json.state %} on {% else %} off {% endif %}",
            "command_on_template": '{"state": 1}',
            "command_off_template": '{"state": 0 }'
        }
        self.mqtt_client.publish(topic, json.dumps(obj), 1, retain)

        # add homebridge accessory
        hb_config = self.read_homebridge_config_template()
        accessories = hb_config.get('accessories')
        find = list(filter(lambda x: x.get('name') == self.name, accessories))
        if len(find) > 0:
            return
        # todo:

        self.write_homebridge_config_template(hb_config)

    def makePacketQueryState(self) -> bytearray:
        # F7 0B 01 15 01 40 XX 00 00 YY EE
        # XX: 상위 4비트 = Room Index, 하위 4비트 = Device Index
        # YY: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x15, 0x01, 0x40])
        packet.append((self.room_index << 4) + (self.index + 1))
        packet.extend([0x00, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

    def makePacketSetState(self, state: bool) -> bytearray:
        # F7 0B 01 15 02 40 XX YY 00 ZZ EE
        # XX: 상위 4비트 = Room Index, 하위 4비트 = Device Index (1-based)
        # YY: 02 = OFF, 01 = ON
        # ZZ: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x15, 0x02, 0x40])
        packet.append((self.room_index << 4) + (self.index + 1))
        if state:
            packet.extend([0x01, 0x00])
        else:
            packet.extend([0x02, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet
