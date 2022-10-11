from asyncore import write
import json
from Device import *
from enum import IntEnum


class StateCalling(IntEnum):
    # 서브폰의 호출 상태
    IDLE = 0
    FRONT = 1  # 현관문 초인종
    COMMUNAL = 2  # 공동출입문


class StateDoorLock(IntEnum):
    Unsecured = 0
    Secured = 1
    Jammed = 2
    Unknown = 3


class HEMSDevType(IntEnum):
    Unknown = 0
    Electricity = 1  # 전기
    Water = 2  # 수도
    Gas = 3  # 가스
    HotWater = 4  # 온수
    Heating = 5  # 난방


class HEMSCategory(IntEnum):
    Unknown = 0
    History = 1  # 우리집 사용량 이력 (3달간, 단위: kWh/L)
    OtherAverage = 2  # 동일평수 평균 사용량 이력 (3달간, 단위: kWh/L)
    Fee = 3  # 요금 이력 (3달간, 단위: 천원/)
    CO2 = 4  # CO2 배출량 이력 (3달간, 단위: kg/)
    Target = 5  # 목표량
    Current = 7  # 현재 실시간 사용량 


class SubPhone(Device):
    state_streaming: int = 0
    state_calling: StateCalling = StateCalling.IDLE
    state_doorlock: StateDoorLock = StateDoorLock.Secured

    def __init__(self, name: str = 'SubPhone', **kwargs):
        super().__init__(name, **kwargs)
        self.sig_state_streaming = Callback(int)
        self.streaming_config = {
            'conf_file_path': '',
            'feed_path': '',
            'input_device': '/dev/video0',
            'frame_rate': 24,
            'width': 320,
            'height': 240,
        }
    
    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += '>'
        return repr_txt
    
    def publish_mqtt(self):
        topic = self.mqtt_publish_topic
        if self.mqtt_client is not None:
            obj = {"state": self.state_streaming}
            self.mqtt_client.publish(topic + '/streaming', json.dumps(obj), 1)

            if self.state_calling in [StateCalling.FRONT, StateCalling.COMMUNAL]:
                self.mqtt_client.publish(topic + '/doorbell', 'ON', 1)
            else:
                self.mqtt_client.publish(topic + '/doorbell', 'OFF', 1)

            obj = {"state": self.state_doorlock.name}  # 도어락은 상태 조회가 안되고 '열기' 기능만 존재한다
            self.mqtt_client.publish(topic + '/doorlock', json.dumps(obj), 1)

    def updateState(self, state: int, **kwargs):
        streaming = kwargs.get('streaming')
        if streaming is not None:
            self.state_streaming = streaming
            self.sig_state_streaming.emit(self.state_streaming)
            self.publish_mqtt()
        call_front = kwargs.get('call_front')
        if call_front is not None:
            if call_front:
                self.state_calling = StateCalling.FRONT
            else:
                self.state_calling = StateCalling.IDLE
            self.publish_mqtt()
        call_communal = kwargs.get('call_communal')
        if call_communal is not None:
            if call_communal:
                self.state_calling = StateCalling.COMMUNAL
            else:
                self.state_calling = StateCalling.IDLE
            self.publish_mqtt()
        doorlock = kwargs.get('doorlock')
        if doorlock is not None:
            self.state_doorlock = StateDoorLock(doorlock)
            self.publish_mqtt()
        writeLog(f"Streaming: {self.state_streaming}, Calling: {self.state_calling.name}, DoorLock: {self.state_doorlock.name}", self)

    def makePacketCommon(self, header: int) -> bytearray:
        return bytearray([0x7F, max(0, min(0xFF, header)), 0x00, 0x00, 0xEE])

    def makePacketSetVideoStreamingState(self, state: int) -> bytearray:
        if state:
            if self.state_calling == StateCalling.FRONT:
                # 현관 초인종 카메라 영상 서브폰 우회
                return self.makePacketCommon(0xB7)
            elif self.state_calling == StateCalling.COMMUNAL:
                # 공동현관문 영상 우회
                return self.makePacketCommon(0x5F)
            else:
                # 단순 문열기용 (주방 서브폰 활성화)
                return self.makePacketCommon(0xB9)
        else:
            if self.state_calling == StateCalling.FRONT:
                # 현관 초인종 카메라 영상 서브폰 우회 종료
                return self.makePacketCommon(0xB8)
            elif self.state_calling == StateCalling.COMMUNAL:
                # 공동현관문 영상 우회 종료
                return self.makePacketCommon(0x60)
            else:
                # 단순 문열기용 (주방 서브폰 활성화)
                return self.makePacketCommon(0xBA)

    def makePacketOpenFrontDoor(self) -> bytearray:
        # 현관 초인종 카메라 영상이 서브폰으로 우회된 상태에서 도어락 해제
        return self.makePacketCommon(0xB4)

    def makePacketOpenCommunalDoor(self) -> bytearray:
        # 공동현관문 호출 후 카메라 영상이 우회된 상태에서 열림 명령
        return self.makePacketCommon(0x61)

    def makePacketSetOuterDoorCamState(self, state: int) -> bytearray:
        if state:
            pass
        else:
            pass

    def makePacketQueryHEMS(self, devtype: HEMSDevType, category: HEMSCategory) -> bytearray:
        command = ((devtype.value & 0x0F) << 4) | (category.value & 0x0F)
        return bytearray([0x7F, 0xE0, command, 0x00, 0xEE])
