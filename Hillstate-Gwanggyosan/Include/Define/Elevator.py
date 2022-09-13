import json
from Device import *
from enum import IntEnum


class Direction(IntEnum):
    UNKNOWN = 0
    UP = 5
    DOWN = 6


class State(IntEnum):
    IDLE = 0
    ARRIVED = 1
    MOVINGUP = 5
    MOVINGDOWN = 6


class DevInfo:
    index: int  # n호기
    state: State
    direction: Direction
    floor: str

    def __init__(self, index: int):
        self.index = index
        self.state = State.IDLE
        self.direction = Direction.UNKNOWN
        self.floor = ''

    def __repr__(self) -> str:
        return f'<Elevator({self.index}) - STAT:{self.state.name}, DIR:{self.direction.name}, FLOOR:{self.floor}>'


class Elevator(Device):
    time_arrived: float = 0.
    time_threshold_arrived_change: float = 10.
    dev_info_list: List[DevInfo]
    ready_to_clear: bool = True

    def __init__(self, name: str = 'Elevator', **kwargs):
        super().__init__(name, **kwargs)
        self.dev_info_list = list()
    
    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += '>'
        return repr_txt
    
    def publish_mqtt(self):
        obj = {
            "state": self.state, 
            "index": [x.index for x in self.dev_info_list],
            "direction": [x.direction.value for x in self.dev_info_list],
            "floor": [x.floor for x in self.dev_info_list]
        }
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)
    
    def updateState(self, state: int, **kwargs):
        dev_idx = kwargs.get('dev_idx')
        if dev_idx is not None:
            # 월패드 -> 복도 미니패드 상태 쿼리 패킷 (packet[4] == 0x01)
            direction = kwargs.get('direction')
            floor = kwargs.get('floor')
            if dev_idx == 0:  # idle 상태
                if self.ready_to_clear:
                    self.dev_info_list.clear()
                if self.state_prev in [5, 6]:  # '도착' 정보가 담긴 패킷을 놓치는 경우에 대한 처리
                    writeLog(f"Arrived (Missing Packet) ({self.state}, {self.state_prev})", self)
                    self.state = 1
                    self.state_prev = 0
                else:
                    self.state = 0
            else:
                find = list(filter(lambda x: x.index == dev_idx, self.dev_info_list))
                if len(find) == 0:
                    dev_info = DevInfo(dev_idx)
                    self.dev_info_list.append(dev_info)
                    self.dev_info_list.sort(key=lambda x: x.index)
                else:
                    dev_info = find[0]
                dev_info.state = State(state)
                dev_info.direction = Direction(direction)
                dev_info.floor = floor
            
            for e in self.dev_info_list:
                # 여러대의 엘리베이터 중 한대라도 '도착'이면 state를 1로 전환
                if e.state == State.ARRIVED:
                    if self.state_prev != 1:
                        writeLog(f"Arrived (#{e.index})", self)
                    self.state = 1
                    break
        else:
            # 복도 미니패드 -> 월패드 상태 응답 패킷 (packet[4] == 0x04)
            # state값은 0(idle) 혹은 6(하행 호출)만 전달됨
            self.state = state
        
        if not self.init:
            self.publish_mqtt()
            self.init = True

        if self.state != self.state_prev:
            if self.state == 1:  # Arrived
                self.ready_to_clear = False
                self.time_arrived = time.perf_counter()
                self.publish_mqtt()
                self.state_prev = self.state
            else:
                if self.state_prev == 1:
                    # 도착 후 상태가 다시 idle로 바뀔 때 시간차가 적으면 occupancy sensor가 즉시 off가 되어
                    # notification이 제대로 되지 않는 문제가 있어, 상태 변화 딜레이를 줘야한다
                    time_elapsed_last_arrived = time.perf_counter() - self.time_arrived
                    if time_elapsed_last_arrived > self.time_threshold_arrived_change:
                        writeLog(f"Ready to rollback state (idle) ({self.state}, {self.state_prev})", self)
                        self.ready_to_clear = True
                        self.publish_mqtt()
                        self.state_prev = self.state
                else:
                    self.publish_mqtt()
                    self.state_prev = self.state
    
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
