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

    time_call_started: float = 0.
    time_threshold_check_duration: float = 10.

    state_calling: int = 0
    packet_call_type: int = 0

    mqtt_config_topic2: str = ''

    def __init__(self, name: str = 'Elevator', index: int = 0, room_index: int = 0):
        super().__init__(name, index, room_index)
        self.dev_type = DeviceType.ELEVATOR
        self.unique_id = f'elevator_{self.room_index}_{self.index}'
        self.mqtt_publish_topic = f'home/state/elevator/{self.room_index}/{self.index}'
        self.mqtt_subscribe_topic = f'home/command/elevator/{self.room_index}/{self.index}'
        self.setHomeAssistantConfigTopic()
        self.dev_info_list = list()
    
    def setDefaultName(self):
        self.name = 'Elevator'

    def setPacketCallType(self, value: int):
        self.packet_call_type = value
    
    def getPacketCallType(self) -> int:
        return self.packet_call_type

    def publishMQTT(self):
        obj = {
            "state": self.state, 
            "index": [x.index for x in self.dev_info_list],
            "direction": [x.direction.value for x in self.dev_info_list],
            "floor": [x.floor for x in self.dev_info_list]
        }
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)
    
    def setHomeAssistantConfigTopic(self):
        self.mqtt_config_topic = f'{self.ha_discovery_prefix}/switch/{self.unique_id}_calldown/config'
        # TODO: 상행 호출 버튼도 만들어줘야하나?
        self.mqtt_config_topic2 = f'{self.ha_discovery_prefix}/sensor/{self.unique_id}_arrived/config'

    def configMQTT(self):
        # 호출 스위치 및 도착 알림용 센서를 위해 디바이스 정보를 각각 발행해야 한다
        obj1 = {
            "name": self.name + "_CALLDOWN",
            "object_id": self.unique_id + "_calldown",
            "unique_id": self.unique_id + "_calldown",
            "state_topic": self.mqtt_publish_topic,
            "command_topic": self.mqtt_subscribe_topic,
            "value_template": '{ "state": {{ value_json.state }} }',
            "payload_on": '{ "state": 6 }',
            "payload_off": '{ "state": 0 }',
            "icon": "mdi:elevator"
        }
        obj2 = {
            "name": self.name + "_SENSOR",
            "object_id": self.unique_id + "_arrived",
            "unique_id": self.unique_id + "_arrived",
            "state_topic": self.mqtt_publish_topic,
            "value_template": "{% if value_json.state == 0 %} \
                               IDLE \
                               {% elif value_json.state == 1 %} \
                               ARRIVED \
                               {% else %} \
                               MOVING \
                               {% endif %}",
            "icon": "mdi:elevator-passenger"
        }
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_config_topic, json.dumps(obj1), 1, True)
            self.mqtt_client.publish(self.mqtt_config_topic2, json.dumps(obj2), 1, True)
        

    def updateState(self, state: int, **kwargs):
        # TODO: 월패드 오류로 인해 미니패드가 계속 눌린 상태일 때는 어떻게하나?
        data_type = kwargs.get('data_type')
        if data_type == 'query':
            # 월패드 -> 복도 미니패드 상태 쿼리 패킷 (packet[4] == 0x01)
            ev_dev_idx = kwargs.get('ev_dev_idx')
            direction = kwargs.get('direction')
            floor = kwargs.get('floor')
            if ev_dev_idx == 0:  # idle 상태
                if self.ready_to_clear and len(self.dev_info_list) > 0:
                    self.dev_info_list.clear()
                """
                if self.state_prev in [5, 6]:  # '도착' 정보가 담긴 패킷을 놓치는 경우에 대한 처리
                    if time.perf_counter() - self.time_call_started > self.time_threshold_check_duration:
                        writeLog(f"Arrived (Missing Packet) ({self.state}, {self.state_prev})", self)
                        self.state = 1
                        self.state_prev = 0
                else:
                    self.state = 0
                """
                if self.state_calling != 0:
                    if self.state_prev in [5, 6]:
                        writeLog(f"Arrived (Missing Packet) ({self.state}, {self.state_prev})", self)
                        self.state = 1
                        self.state_prev = self.state_calling
                else:
                    self.state = 0
            else:
                find = list(filter(lambda x: x.index == ev_dev_idx, self.dev_info_list))
                if len(find) == 0:
                    dev_info = DevInfo(ev_dev_idx)
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
                        # elapsed = time.perf_counter() - self.time_call_started
                        writeLog(f"Arrived (#{e.index})", self)
                    self.state = 1
                    break
        elif data_type == 'response':
            # 복도 미니패드 -> 월패드 상태 응답 패킷 (packet[4] == 0x04)
            # state값은 0(idle) 혹은 6(하행 호출)만 전달됨
            self.state = state
            self.state_calling = state
            if self.state != 0:  # 0이 아니면 미니패드가 엘리베이터를 '호출한 상태'
                self.time_call_started = time.perf_counter()
                if self.state_prev == 0:
                    writeLog("Called", self)
        
        if not self.init:
            self.publishMQTT()
            self.init = True

        if self.state != self.state_prev:
            if self.state == 1:  # Arrived
                self.ready_to_clear = False
                self.time_arrived = time.perf_counter()
                writeLog("State changed as <arrived>, elapsed: {:g} sec".format(self.time_arrived - self.time_call_started), self)
                self.publishMQTT()
                self.state_prev = self.state
            else:
                if self.state_prev == 1:
                    # 도착 후 상태가 다시 idle로 바뀔 때 시간차가 적으면 occupancy sensor가 즉시 off가 되어
                    # notification이 제대로 되지 않는 문제가 있어, 상태 변화 딜레이를 줘야한다
                    time_elapsed_last_arrived = time.perf_counter() - self.time_arrived
                    if time_elapsed_last_arrived > self.time_threshold_arrived_change:
                        writeLog(f"Ready to rollback state (idle) ({self.state}, {self.state_prev})", self)
                        self.ready_to_clear = True
                        self.publishMQTT()
                        self.state_prev = self.state
                else:
                    self.publishMQTT()
                    self.state_prev = self.state
    
    def makePacketCallDownside(self) -> bytearray:
        # 하행 호출
        # F7 0B 01 34 02 41 10 06 00 XX EE
        packet = bytearray([0xF7, 0x0B, 0x01, 0x34])
        if self.packet_call_type == 1:
            # 일부 환경에서는 F7 0B 01 34 04 41 10 00 06 XX EE로 호출해야 된다? (차이 파악 필요)
            packet.extend([0x04, 0x41, 0x10, 0x00, 0x06])
        else:
            packet.extend([0x02, 0x41, 0x10, 0x06, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

    def makePacketCallUpside(self) -> bytearray:
        # 상행 호출
        # F7 0B 01 34 02 41 10 05 00 XX EE
        packet = bytearray([0xF7, 0x0B, 0x01, 0x34])
        if self.packet_call_type == 1:
            # 일부 환경에서는 F7 0B 01 34 04 41 10 00 05 XX EE로 호출해야 된다? (차이 파악 필요)
            packet.extend([0x04, 0x41, 0x10, 0x00, 0x05])
        else:
            packet.extend([0x02, 0x41, 0x10, 0x05, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet
