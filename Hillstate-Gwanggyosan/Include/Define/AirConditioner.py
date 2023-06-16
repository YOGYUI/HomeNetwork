import json
from Device import *
import datetime


class AirConditioner(Device):
    temp_current: int = 0  # 현재 온도
    temp_current_prev: int = 0  # 현재 온도 버퍼
    temp_config: int = 0  # 냉방 설정 온도
    temp_config_prev: int = 0  # 냉방 설정 온도 버퍼
    temp_range: List[int]  # 설정 가능한 온도값의 범위
    mode: int = -1  # 운전모드
    mode_prev: int = -1  # 운전모드 버퍼
    rotation_speed: int = -1  # 풍량
    rotation_speed_prev: int = -1  # 풍량 버퍼

    def __init__(self, name: str = 'AirConditioner', index: int = 0, room_index: int = 0):
        super().__init__(name, index, room_index)
        self.dev_type = DeviceType.AIRCONDITIONER
        self.mqtt_publish_topic = f'home/state/airconditioner/{self.room_index}/{self.index}'
        self.mqtt_subscribe_topic = f'home/command/airconditioner/{self.room_index}/{self.index}'
        self.temp_range = [0, 100]
        
    def publish_mqtt(self):
        # https://ddhometech.wordpress.com/2021/01/03/ha-mqtt-hvac-integration-using-tasmota-ir-bridge/
        if self.state:
            state = 'COOLING'
        else:
            state = 'INACTIVE'
        obj = {
            "active": self.state,
            "state": state,
            "currentTemperature": self.temp_current,
            "targetTemperature": self.temp_config,
            "timer": int(self.isTimerOnOffRunning())
        }
        if self.rotation_speed == 0x02:  # 미풍
            obj['rotationspeed'] = 50
            obj['rotationspeed_name'] = 'Min'
        elif self.rotation_speed == 0x03:  # 약풍
            obj['rotationspeed'] = 75
            obj['rotationspeed_name'] = 'Medium'
        elif self.rotation_speed == 0x04:  # 강풍
            obj['rotationspeed'] = 100
            obj['rotationspeed_name'] = 'Max'
        else:
            obj['rotationspeed'] = 25
            obj['rotationspeed_name'] = 'Auto'
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)

    def setTemperatureRange(self, range_min: int, range_max: int):
        self.temp_range[0] = range_min
        self.temp_range[1] = range_max
        self.temp_current = max(range_min, min(range_max, self.temp_current))
        self.temp_config = max(range_min, min(range_max, self.temp_config))
        writeLog(f"Set Temperature Range ({self.temp_range[0]}~{self.temp_range[1]}), {self.temp_current}, {self.temp_config}", self)
    
    def updateState(self, state: int, **kwargs):
        self.state = state
        if not self.init:
            self.publish_mqtt()
            self.init = True
        if self.state != self.state_prev:
            self.publish_mqtt()
        self.state_prev = self.state
        # 현재온도
        temp_current = kwargs.get('temp_current')
        if temp_current is not None:
            # self.temp_current = temp_current
            self.temp_current = max(self.temp_range[0], min(self.temp_range[1], temp_current))
            if self.temp_current != self.temp_current_prev:
                self.publish_mqtt()
            self.temp_current_prev = self.temp_current
        # 희망온도
        temp_config = kwargs.get('temp_config')
        if temp_config is not None:
            # self.temp_config = temp_config
            self.temp_config = max(self.temp_range[0], min(self.temp_range[1], temp_config))
            if self.temp_config != self.temp_config_prev:
                self.publish_mqtt()
            self.temp_config_prev = self.temp_config
        # 모드
        # 0=자동, 1=냉방, 2=제습, 3=공기청정
        mode = kwargs.get('mode')
        if mode is not None:
            self.mode = mode
            if self.mode != self.mode_prev:
                self.publish_mqtt()
            self.mode_prev = self.mode
        # 풍량
        # 1=자동, 2=미풍, 3=약풍, 4=강풍
        rotation_speed = kwargs.get('rotation_speed')
        if rotation_speed is not None:
            self.rotation_speed = rotation_speed
            if self.rotation_speed != self.rotation_speed_prev:
                self.publish_mqtt()
            self.rotation_speed_prev = self.rotation_speed

    def makePacketQueryState(self) -> bytearray:
        # F7 0B 01 1C 01 40 XX 00 00 YY EE
        # XX: 상위 4비트=공간 인덱스, 하위 4비트=1
        # YY: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x1C, 0x01, 0x40])
        packet.append((self.room_index << 4) + 0x01)
        packet.extend([0x00, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

    def makePacketSetState(self, state: bool) -> bytearray:
        # F7 0B 01 1C 02 40 XX YY 00 ZZ EE
        # XX: 상위 4비트=공간 인덱스, 하위 4비트=1
        # YY: 0x01=On, 0x02=Off
        # ZZ: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x1C, 0x02, 0x40])
        packet.append((self.room_index << 4) + 0x01)
        if state:
            packet.extend([0x01, 0x00])
        else:
            packet.extend([0x02, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

    def makePacketSetTemperature(self, temperature: int) -> bytearray:
        # F7 0B 01 1C 02 45 XX YY 00 ZZ EE
        # XX: 상위 4비트=공간 인덱스, 하위 4비트=1
        # YY: 온도 설정값
        # ZZ: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x1C, 0x02, 0x45])
        packet.append((self.room_index << 4) + 0x01)
        packet.extend([temperature & 0xFF, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

    def makePacketSetRotationSpeed(self, rotation_speed: int) -> bytearray:
        # F7 0B 01 1C 02 5D XX YY 00 ZZ EE
        # XX: 상위 4비트=공간 인덱스, 하위 4비트=1
        # YY: 0x01=자동, 0x02=미풍, 0x03=약풍, 0x04=강풍
        # ZZ: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x1C, 0x02, 0x5D])
        packet.append((self.room_index << 4) + 0x01)
        packet.extend([rotation_speed & 0xFF, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

    def makePacketSetMode(self, mode: int) -> bytearray:
        # F7 0B 01 1C 02 5C XX YY 00 ZZ EE
        # XX: 상위 4비트=공간 인덱스, 하위 4비트=1
        # YY: 0x0=자동, 0x01=냉방, 0x03=제습, 0x04=공기청정
        # ZZ: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x1C, 0x02, 0x5C])
        packet.append((self.room_index << 4) + 0x01)
        packet.extend([mode & 0xFF, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet
