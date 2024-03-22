import json
from Device import *


class Ventilator(Device):
    def __init__(self, name: str = 'Ventilator', index: int = 0, room_index: int = 0):
        super().__init__(name, index, room_index)
        self.dev_type = DeviceType.VENTILATOR
        self.unique_id = f'ventilator_{self.room_index}_{self.index}'
        self.mqtt_publish_topic = f'home/state/ventilator/{self.room_index}/{self.index}'
        self.mqtt_subscribe_topic = f'home/command/ventilator/{self.room_index}/{self.index}'
        self.rotation_speed: int = -1
        self.rotation_speed_prev: int = -1
    
    def setDefaultName(self):
        self.name = 'Ventilator'

    def publishMQTT(self):
        obj = {
            "state": self.state, 
            "rotationspeed": 0
        }
        if self.state:
            if self.rotation_speed == 0x01:
                obj['rotationspeed'] = 30
            elif self.rotation_speed == 0x03:
                obj['rotationspeed'] = 60
            elif self.rotation_speed == 0x07:
                obj['rotationspeed'] = 100
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)

    def configMQTT(self, retain: bool = False):
        if self.mqtt_client is None:
            return
        
        topic = f'{self.ha_discovery_prefix}/fan/{self.unique_id}/config'
        obj = {
            "name": self.name,
            "object_id": self.unique_id,
            "unique_id": self.unique_id,
            "state_topic": self.mqtt_publish_topic,
            "state_value_template": "{% if value_json.state %} ON {% else %} OFF {% endif %}",
            "command_topic": self.mqtt_subscribe_topic,
            "command_template": "{% set values = {'OFF': 0, 'ON': 1} %} \
                                 { \"state\": {{ values[value] if value in values.keys() else 0 }} }",
            "percentage_state_topic": self.mqtt_publish_topic,
            "percentage_value_template": "{{ value_json.rotationspeed }}",
            "percentage_command_topic": self.mqtt_subscribe_topic,
            "percentage_command_template": '{ "rotationspeed": {{ value }} }',
            "speed_range_min": 1,
            "speed_range_max": 100
        }
        self.mqtt_client.publish(topic, json.dumps(obj), 1, retain)

    def updateState(self, state: int, **kwargs):
        self.state = state
        if not self.init:
            self.publishMQTT()
            self.init = True
        if self.state != self.state_prev:
            self.publishMQTT()
        self.state_prev = self.state
        # 풍량 인자
        rotation_speed = kwargs.get('rotation_speed')
        if rotation_speed is not None:
            self.rotation_speed = rotation_speed
            if self.rotation_speed != self.rotation_speed_prev:
                self.publishMQTT()
            self.rotation_speed_prev = self.rotation_speed
    
    def makePacketQueryState(self) -> bytearray:
        # F7 0B 01 2B 01 40 11 00 00 XX EE
        # XX: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x2B, 0x01, 0x40])
        packet.append(0x11)
        packet.extend([0x00, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

    def makePacketSetState(self, state: bool) -> bytearray:
        # F7 0B 01 2B 02 40 11 XX 00 YY EE
        # XX: 0x01=On, 0x02=Off
        # YY: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x2B, 0x02, 0x40])
        # packet.append(0x10 + (self.room_index & 0x0F))
        packet.append(0x11)  # 환기는 거실(공간인덱스 1)에 설치된걸로 설정되어 있다
        if state:
            packet.extend([0x01, 0x00])
        else:
            packet.extend([0x02, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

    def makePacketSetRotationSpeed(self, rotation_speed: int) -> bytearray:
        # F7 0B 01 2B 02 42 11 XX 00 YY EE
        # XX: 풍량 (0x01=약, 0x03=중, 0x07=강)
        # YY: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x2B, 0x02, 0x42])
        # packet.append(0x10 + (self.room_index & 0x0F))
        packet.append(0x11)  # 환기는 거실(공간인덱스 1)에 설치된걸로 설정되어 있다
        packet.extend([rotation_speed & 0xFF, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet
