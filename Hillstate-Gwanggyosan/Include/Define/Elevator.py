import json
from Device import *


class Elevator(Device):
    time_arrived: float = 0.
    time_threshold_arrived_change: float = 10.
    floor_list: List[str]
    moving_list: List[bool]

    def __init__(self, name: str = 'Elevator', count: int = 2, **kwargs):
        super().__init__(name, **kwargs)
        self.floor_list = ['??'] * count
        self.moving_list = [False] * count
    
    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += '>'
        return repr_txt
    
    def publish_mqtt(self):
        obj = {"state": self.state}
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)
    
    def updateState(self, state: int, **kwargs):
        self.state = state  # 0 = idle, 1 = arrived, 5 = moving(up), 6 = moving(down)
        if not self.init:
            self.publish_mqtt()
            self.init = True
        if self.state != self.state_prev:
            if self.state == 1:
                self.time_arrived = time.perf_counter()
                self.publish_mqtt()
                self.state_prev = self.state
            else:
                if self.state_prev == 1:
                    # 도착 후 상태가 다시 idle로 바뀔 때 시간차가 적으면 occupancy sensor가 즉시 off가 되어
                    # notification이 제대로 되지 않는 문제가 있어, 상태 변화 딜레이를 줘야한다
                    time_elapsed_last_arrived = time.perf_counter() - self.time_arrived
                    if time_elapsed_last_arrived > self.time_threshold_arrived_change:
                        self.publish_mqtt()
                        self.state_prev = self.state
                else:
                    self.publish_mqtt()
                    self.state_prev = self.state
        if 'floor' in kwargs.keys():
            floor = kwargs.get('floor')
            try:
                for i in range(len(self.floor_list)):
                    if floor[i] != '??':
                        self.floor_list[i] = floor[i]
            except Exception:
                pass
    
    def makePacketCallDownside(self) -> bytearray:
        # 하행 호출
        # F7 0B 01 34 02 41 10 06 00 XX EE
        packet = bytearray([0xF7, 0x0B, 0x01, 0x34])
        packet.append(0x02)
        packet.extend([0x41, 0x10, 0x06, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

    def makePacketCallUpside(self) -> bytearray:
        # 상행 호출
        # F7 0B 01 34 02 41 10 05 00 XX EE
        packet = bytearray([0xF7, 0x0B, 0x01, 0x34])
        packet.append(0x02)
        packet.extend([0x41, 0x10, 0x05, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet
