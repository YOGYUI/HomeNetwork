import json
import math
from Device import *


class DimmingLight(Device):
    brightness: int = 0  # 현재 밝기 레벨
    brightness_prev: int = 0  # 현재 밝기 레벨 버퍼
    max_brightness_level: int = 7
    conv_method: int = 0  # 0 = 반올림, 1 = 내림, 2 = 올림

    def __init__(self, name: str = 'DimmingLight', index: int = 0, room_index: int = 0):
        super().__init__(name, index, room_index)
        self.dev_type = DeviceType.DIMMINGLIGHT
        self.unique_id = f'dimminglight_{self.room_index}_{self.index}'
        self.mqtt_publish_topic = f'home/state/dimminglight/{self.room_index}/{self.index}'
        self.mqtt_subscribe_topic = f'home/command/dimminglight/{self.room_index}/{self.index}'

    def setDefaultName(self):
        self.name = 'DimmingLight'

    def publishMQTT(self):
        brightness_conv = self.convert_word_to_level(self.brightness)
        obj = {
            "state": self.state,
            "brightness": brightness_conv
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
            "command_on_template": '{'\
                '"state": 1'\
                '{%- if brightness is defined -%}'\
                ', "brightness": {{ brightness }}'\
                '{%- endif -%}'\
            '}',
            "command_off_template": '{"state": 0}',
            "state_template": "{% if value_json.state %} on {% else %} off {% endif %}",
            "brightness_template": '{{ value_json.brightness }}'
        }
        self.mqtt_client.publish(topic, json.dumps(obj), 1, retain)

    def setMaxBrightnessLevel(self, level: int):
        self.max_brightness_level = level
        writeLog(f"{str(self)} Set Max Brightness Level: {self.max_brightness_level}", self)

    def setConvertMethod(self, method: int):
        if method not in [0, 1, 2]:
            writeLog(f"{str(self)} warning:: invalid convert method (only 0, 1, 2 is available)", self)
            method = 0
        self.conv_method = method
        writeLog(f"{str(self)} Set Convert Method: {self.conv_method}", self)

    def convert_level_to_word(self, level: int) -> int:
        # HA 엔티티의 밝기 레벨 (범위 0 ~ 255)를 월패드상의 밝기 레벨로 변환
        if self.conv_method == 1:  # 내림
            return math.floor(level / 255 * self.max_brightness_level)
        elif self.conv_method == 2:  # 올림
            return math.ceil(level / 255 * self.max_brightness_level)
        # 반올림
        return round(level / 255 * self.max_brightness_level)

    def convert_word_to_level(self, word: int) -> int:
        # 월패드상의 밝기 레벨을 HA 엔티티의 밝기 레벨 (범위 0 ~ 255)로 변환
        if self.conv_method == 1:  # 내림
            return math.floor(255 * word / self.max_brightness_level)
        elif self.conv_method == 2:  # 올림
            return math.ceil(255 * word / self.max_brightness_level)
        # 반올림
        return round(255 * word / self.max_brightness_level)

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
