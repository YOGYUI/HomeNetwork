import json
from Device import *
from enum import IntEnum


class StateRinging(IntEnum):
    # 서브폰의 호출 상태
    IDLE = 0
    FRONT = 1  # 현관문 초인종
    COMMUNAL = 2  # 공동출입문


class StateDoorLock(IntEnum):
    Unsecured = 0
    Secured = 1
    Jammed = 2
    Unknown = 3


class SubPhone(Device):
    state_streaming: int = 0
    state_ringing: StateRinging = StateRinging.IDLE
    state_ringing_prev: StateRinging = StateRinging.IDLE
    state_doorlock: StateDoorLock = StateDoorLock.Secured

    def __init__(self, name: str = 'SubPhone', index: int = 0, room_index: int = 0):
        super().__init__(name, index, room_index)
        self.dev_type = DeviceType.SUBPHONE
        self.unique_id = f'subphone_{self.room_index}_{self.index}'
        self.mqtt_publish_topic = f'home/state/subphone/{self.room_index}/{self.index}'
        self.mqtt_subscribe_topic = f'home/command/subphone/{self.room_index}/{self.index}'
        self.setHomeAssistantConfigTopic()
        self.sig_state_streaming = Callback(int)
        self.enable_streaming = True
        self.streaming_config = {
            'conf_file_path': '',
            'feed_path': '',
            'input_device': '/dev/video0',
            'frame_rate': 24,
            'width': 320,
            'height': 240,
        }
    
    def setDefaultName(self):
        self.name = 'SubPhone'

    def publishMQTT(self):
        if self.mqtt_client is not None:
            obj = {
                "streaming_state": self.state_streaming,
                "doorlock_state": self.state_doorlock.name,  # 도어락은 상태 조회가 안되고 '열기' 기능만 존재한다
            }
            self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)

            if self.state_ringing != self.state_ringing_prev:  # 초인종 호출 상태 알림이 반복적으로 뜨는 것 방지 
                writeLog(f"Ringing Publish: Prev={bool(self.state_ringing.name)}, Current={self.state_ringing_prev.name}", self)
                if self.state_ringing in [StateRinging.FRONT, StateRinging.COMMUNAL]:
                    # obj = {"doorbell_state": 'ON'}
                    self.mqtt_client.publish(self.mqtt_publish_topic + '/doorbell', 'ON', 1)
                else:
                    # obj = {"doorbell_state": 'OFF'}
                    self.mqtt_client.publish(self.mqtt_publish_topic + '/doorbell', 'OFF', 1)

    def setHomeAssistantConfigTopic(self):
        self.mqtt_config_topic = f'{self.ha_discovery_prefix}/lock/{self.unique_id}/config'

    def configMQTT(self):
        obj = {
            "name": self.name + "_doorlock",
            "object_id": self.unique_id + "_doorlock",
            "unique_id": self.unique_id + "_doorlock",
            "state_topic": self.mqtt_publish_topic,
            "command_topic": self.mqtt_subscribe_topic,
            "value_template": '{{ value_json.doorlock_state }}',
            "payload_lock": '{ "doorlock_state": "Secured" }',
            "payload_unlock": '{ "doorlock_state": "Unsecured" }',
            "state_locked": "Secured",
            "state_unlocked": "Unsecured",
            "icon": "mdi:door-closed-lock"
        }
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_config_topic, json.dumps(obj), 1, True)

    def updateState(self, _: int, **kwargs):
        streaming = kwargs.get('streaming')
        if streaming is not None:
            self.state_streaming = streaming
            self.sig_state_streaming.emit(self.state_streaming)
            self.publishMQTT()
        ringing_front = kwargs.get('ringing_front')
        if ringing_front is not None:
            if ringing_front:
                self.state_ringing = StateRinging.FRONT
            else:
                self.state_ringing = StateRinging.IDLE
            self.publishMQTT()
            self.state_ringing_prev = self.state_ringing
        ringing_communal = kwargs.get('ringing_communal')
        if ringing_communal is not None:
            if ringing_communal:
                self.state_ringing = StateRinging.COMMUNAL
            else:
                self.state_ringing = StateRinging.IDLE
            self.publishMQTT()
            self.state_ringing_prev = self.state_ringing
        doorlock = kwargs.get('doorlock')
        if doorlock is not None:
            self.state_doorlock = StateDoorLock(doorlock)
            self.publishMQTT()
        writeLog(f"Streaming: {bool(self.state_streaming)}, Ringing: {self.state_ringing.name}, DoorLock: {self.state_doorlock.name}", self)

    def makePacketCommon(self, header: int) -> bytearray:
        return bytearray([0x7F, max(0, min(0xFF, header)), 0x00, 0x00, 0xEE])

    def makePacketSetVideoStreamingState(self, state: int) -> bytearray:
        if state:
            if self.state_ringing == StateRinging.FRONT:
                # 현관 초인종 카메라 영상 서브폰 우회
                return self.makePacketCommon(0xB7)
            elif self.state_ringing == StateRinging.COMMUNAL:
                # 공동현관문 영상 우회
                return self.makePacketCommon(0x5F)
            else:
                # 단순 문열기용 (주방 서브폰 활성화)
                return self.makePacketCommon(0xB9)
        else:
            if self.state_ringing == StateRinging.FRONT:
                # 현관 초인종 카메라 영상 서브폰 우회 종료
                return self.makePacketCommon(0xB8)
            elif self.state_ringing == StateRinging.COMMUNAL:
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
