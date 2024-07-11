import json
from Device import *


class DimmingLight(Device):
    brightness: int = 0  # 현재 밝기 레벨
    brightness_prev: int = 0  # 현재 밝기 레벨 버퍼
    max_brightness_level: int = 10

    def __init__(self, name: str = 'DimmingLight', index: int = 0, room_index: int = 0):
        super().__init__(name, index, room_index)
        self.dev_type = DeviceType.DIMMINGLIGHT
        self.unique_id = f'dimminglight_{self.room_index}_{self.index}'
        self.mqtt_publish_topic = f'home/state/dimminglight/{self.room_index}/{self.index}'
        self.mqtt_subscribe_topic = f'home/command/dimminglight/{self.room_index}/{self.index}'

    def setDefaultName(self):
        self.name = 'DimmingLight'

    def publishMQTT(self):
        obj = {
            "state": self.state,
            "brightness": self.brightness
        }
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)

    def configMQTT(self, retain: bool = False):
        if self.mqtt_client is None:
            return

        topic = f'{self.ha_discovery_prefix}/light/{self.unique_id}/config'
        obj = {
            "name": self.name,
            "object_id": self.unique_id,
            "unique_id": self.unique_id,
            "state_topic": self.mqtt_publish_topic,
            "command_topic": self.mqtt_subscribe_topic,
            "schema": "template",
            "state_template": "{% if value_json.state %} on {% else %} off {% endif %}",
            "command_on_template": '{"state": 1}',
            "command_off_template": '{"state": 0 }',
            "brightness_state_topic ": self.mqtt_publish_topic,
            "brightness_command_topic ": self.mqtt_subscribe_topic,
            "brightness_value_template": "{{ value_json.brightness }}",
            "brightness_command_template": '{ "brightness": {{ value }} }',
            "brightness": True,
            "brightness_scale": self.max_brightness_level,
            "supported_color_modes": ["brightness"]
        }
        self.mqtt_client.publish(topic, json.dumps(obj), 1, retain)

    def setMaxBrightnessLevel(self, level: int):
        self.max_brightness_level = level
        writeLog(f"{str(self)} Set Max Brightness Level: {self.max_brightness_level}", self)

    def updateState(self, state: int, **kwargs):
        self.state = state
        if not self.init:
            self.publishMQTT()
            self.init = True
        if self.state != self.state_prev:
            self.publishMQTT()
        self.state_prev = self.state
        # 밝기 레벨
        brightness = kwargs.get('brightness')
        if brightness is not None:
            self.brightness = brightness
            if self.brightness != self.brightness_prev:
                self.publishMQTT()
            self.brightness_prev = self.brightness

    def makePacketQueryState(self) -> bytearray:
        # F7 0B 01 1A 01 40 XX 00 00 YY EE
        # XX: 상위 4비트 = Room Index, 하위 4비트 = Device Index (1-based)
        # YY: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x1A, 0x01, 0x40])
        packet.append((self.room_index << 4) + (self.index + 1))
        packet.extend([0x00, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

    def makePacketQueryBrightness(self) -> bytearray:
        # F7 0B 01 1A 01 42 XX 00 00 YY EE
        # XX: 상위 4비트 = Room Index, 하위 4비트 = Device Index (1-based)
        # YY: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x1A, 0x01, 0x42])
        packet.append((self.room_index << 4) + (self.index + 1))
        packet.extend([0x00, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

    def makePacketSetState(self, state: bool) -> bytearray:
        # F7 0B 01 1A 02 40 XX YY 00 ZZ EE
        # XX: 상위 4비트 = Room Index, 하위 4비트 = Device Index (1-based)
        # YY: 02 = OFF, 01 = ON
        # ZZ: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x1A, 0x02, 0x40])
        packet.append((self.room_index << 4) + (self.index + 1))
        if state:
            packet.extend([0x01, 0x00])
        else:
            packet.extend([0x02, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

    def makePacketSetBrightness(self, brightness: int) -> bytearray:
        # F7 0B 01 1A 02 42 XX YY 00 ZZ EE
        # XX: 상위 4비트 = Room Index, 하위 4비트 = Device Index (1-based)
        # YY: Dimming 레벨
        # ZZ: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x1A, 0x02, 0x42])
        packet.append((self.room_index << 4) + (self.index + 1))
        packet.extend([max(0, min(brightness, self.max_brightness_level)), 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet
