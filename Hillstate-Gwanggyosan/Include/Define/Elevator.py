import json
from Device import *


class Elevator(Device):
    arrived: int = 0
    arrived_prev: int = 0
    enable_publish_arrived: bool = True
    time_last_arrived: float = 0.
    current_floor: str = '??'

    def __init__(self, name: str = 'Elevator', **kwargs):
        super().__init__(name, **kwargs)
    
    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += '>'
        return repr_txt
    
    def publish_mqtt(self):
        obj = {"state": self.state}
        if self.enable_publish_arrived:
            obj["arrived"] = self.arrived
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)
    
    def setState(self, state: int, **kwargs):
        self.state = state  # 0 = idle, 1 = moving
        if not self.init:
            self.publish_mqtt()
            self.init = True
        if self.state != self.state_prev:
            self.publish_mqtt()
        self.state_prev = self.state
        # 도착여부 플래그
        arrived = kwargs.get('arrived')
        if arrived is not None:
            self.arrived = arrived
            if self.arrived != self.arrived_prev:
                if self.arrived == 1:  # 도착 시 즉시 publish (trigger occupancy sensor)
                    self.enable_publish_arrived = True
                    self.time_last_arrived = time.perf_counter()
                    self.publish_mqtt()
            if not self.arrived:
                # arrived=0이더라도, occupancy sensor의 on 상태가 10초가량 유지되도록
                # (regular publish 할 때 무작정 off시키지 않도록)
                time_elapsed_last_arrived = time.perf_counter() - self.time_last_arrived
                self.enable_publish_arrived = True if time_elapsed_last_arrived > 10 else False
            self.arrived_prev = self.arrived
        # 현재 층수
        current_floor = kwargs.get('current_floor')
        if current_floor is not None:
            self.current_floor = current_floor
    
    def makePacketSetState(self, state: bool) -> bytearray:
        # F7 0B 01 34 02 41 10 06 00 9C EE
        packet = bytearray([0xF7, 0x0B, 0x01, 0x34])
        packet.append(0x02)
        packet.extend([0x41, 0x10, 0x06, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet
