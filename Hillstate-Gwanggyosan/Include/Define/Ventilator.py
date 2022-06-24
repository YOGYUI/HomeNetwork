import json
from Device import *


class Ventilator(Device):
    rotation_speed: int = -1
    rotation_speed_prev: int = -1

    def __init__(self, name: str = 'Ventilator', **kwargs):
        super().__init__(name, **kwargs)
    
    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += '>'
        return repr_txt
    
    def publish_mqtt(self):
        obj = {"state": self.state}
        if self.state:
            if self.rotation_speed == 0x01:
                obj['rotationspeed'] = 30
            elif self.rotation_speed == 0x03:
                obj['rotationspeed'] = 60
            elif self.rotation_speed == 0x07:
                obj['rotationspeed'] = 100
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)
    
    def updateState(self, state: int, **kwargs):
        self.state = state
        if not self.init:
            self.publish_mqtt()
            self.init = True
        if self.state != self.state_prev:
            self.publish_mqtt()
        self.state_prev = self.state
        # 풍량 인자
        rotation_speed = kwargs.get('rotation_speed')
        if rotation_speed is not None:
            self.rotation_speed = rotation_speed
            if self.rotation_speed != self.rotation_speed_prev:
                self.publish_mqtt()
            self.rotation_speed_prev = self.rotation_speed
    
    def makePacketQueryState(self) -> bytearray:
        # F7 0B 01 2B 01 40 11 00 00 XX EE
        # XX: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x2B, 0x01, 0x40])
        packet.extend([0x11, 0x00, 0x00])
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
