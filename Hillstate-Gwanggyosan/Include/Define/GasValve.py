import json
from Device import *


class GasValve(Device):
    def __init__(self, name: str = 'GasValve', index: int = 0, room_index: int = 0, topic_prefix: str = 'home'):
        super().__init__(name, index, room_index)
        self.dev_type = DeviceType.GASVALVE
        self.unique_id = f'gasvalve_{self.room_index}_{self.index}'
        self.mqtt_state_topic = f'{topic_prefix}/state/gasvalve/{self.room_index}/{self.index}'
        self.mqtt_command_topic = f'{topic_prefix}/command/gasvalve/{self.room_index}/{self.index}'

    def setDefaultName(self):
        self.name = 'GasValve'

    def publishMQTT(self):
        obj = {"state": self.state}
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_state_topic, json.dumps(obj), 1)
    
    def configMQTT(self, retain: bool = False):
        if self.mqtt_client is None:
            return

        topic = f'{self.ha_discovery_prefix}/switch/{self.unique_id}/config'
        obj = {
            "name": self.name,
            "object_id": self.unique_id,
            "unique_id": self.unique_id,
            "state_topic": self.mqtt_state_topic,
            "command_topic": self.mqtt_command_topic,
            "value_template": '{ "state": {{ value_json.state }} }',
            "payload_on": '{ "state": 1 }',
            "payload_off": '{ "state": 0 }',
            "icon": "mdi:pipe-valve"
        }
        self.mqtt_client.publish(topic, json.dumps(obj), 1, retain)

        # add homebridge accessory
        if not os.path.isfile(self.homebridge_config_path):
            return
        with open(self.homebridge_config_path, 'r') as fp:
            hb_config = json.load(fp)
        accessories = hb_config.get('accessories')
        find = list(filter(lambda x: x.get('name') == self.name, accessories))
        if len(find) > 0:
            return
        
        elem = {
            "name": self.name,
            "accessory": "mqttthing",
            "type": "valve",
            "valveType": "faucet",
            "url": f"{self.mqtt_host}:{self.mqtt_port}",
            "username": self.mqtt_username,
            "password": self.mqtt_password,
            "integerValue": True,
            "onValue": 1, 
            "offValue": 0,
            "history": True,
            "logMqtt": False,
            "topics": {
                "getActive": {
                    "topic": self.mqtt_state_topic,
                    "apply": "return JSON.parse(message).state;"
                },
                "getInUse": {
                    "topic": self.mqtt_state_topic,
                    "apply": "return JSON.parse(message).state;"
                },
                "setActive": {
                    "topic": self.mqtt_command_topic,
                    "apply": "return JSON.stringify({state: message});"
                }
            }
        }
        accessories.append(elem)
        self.homebridge_modifed = True

    def makePacketQueryState(self) -> bytearray:
        # F7 0B 01 1B 01 43 11 00 00 B5 EE
        packet = bytearray([0xF7, 0x0B, 0x01, 0x1B, 0x01, 0x43])
        packet.append(0x11)
        packet.extend([0x00, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

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
