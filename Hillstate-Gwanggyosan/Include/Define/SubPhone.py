import json
from Device import *


class SubPhone(Device):
    state_door_cam: int = 0
    state_door_bell: int = 0
    state_outer_door_call: int = 0

    def __init__(self, name: str = 'SubPhone', **kwargs):
        super().__init__(name, **kwargs)
    
    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += '>'
        return repr_txt
    
    def publish_mqtt(self):
        topic = self.mqtt_publish_topic
        if self.mqtt_client is not None:
            obj = {"state": self.state_door_cam}
            topic_doorcam = topic + '/doorcam'
            self.mqtt_client.publish(topic_doorcam, json.dumps(obj), 1)

            topic_doorbell = topic + '/doorbell'
            if self.state_door_bell or self.state_outer_door_call:
                self.mqtt_client.publish(topic_doorbell, 'ON', 1)
                # self.state_door_bell = 0
            else:
                self.mqtt_client.publish(topic_doorbell, 'OFF', 1)

            topic_doorlock = topic + '/doorlock'
            obj = {"state": 0}
            self.mqtt_client.publish(topic_doorlock, json.dumps(obj), 1)

    def updateState(self, state: int, **kwargs):
        state_door_cam = kwargs.get('doorcam')
        if state_door_cam is not None:
            self.state_door_cam = state_door_cam
            self.publish_mqtt()
        state_door_bell = kwargs.get('doorbell')
        if state_door_bell is not None:
            self.state_door_bell = state_door_bell
            self.publish_mqtt()
        state_outer_door_call = kwargs.get('outer_door_call')
        if state_outer_door_call is not None:
            self.state_outer_door_call = state_outer_door_call
            self.publish_mqtt()

    def makePacketCommon(self, header: int) -> bytearray:
        return bytearray([0x7F, max(0, min(0xFF, header)), 0x00, 0x00, 0xEE])

    def makePacketSetDoorCamState(self, state: int) -> bytearray:
        # 현관 초인종 카메라 영상을 서브폰으로 우회
        if state:
            self.state_door_cam = 1
            self.publish_mqtt()
            # TODO: doorbell 활성화 상태에서는?
            if self.state_door_bell:
                return self.makePacketCommon(0xB7)
            elif self.state_outer_door_call:
                # 공동현관문 영상 우회?
                return self.makePacketCommon(0x5F)
            else:    
                return self.makePacketCommon(0xB9)
        else:
            if self.state_door_bell:
                return self.makePacketCommon(0xB8)
            elif self.state_outer_door_call:
                # 공동현관문 영상 우회 종료?
                return self.makePacketCommon(0x60)
            else:
                return self.makePacketCommon(0xBA)

    def makePacketOpenDoorLock(self) -> bytearray:
        # 현관 초인종 카메라 영상이 서브폰으로 우회된 상태에서 도어락 해제
        return self.makePacketCommon(0xB4)

    def makePacketOpenOuterDoor(self) -> bytearray:
        return self.makePacketCommon(0x61)

    def makePacketSetOuterDoorCamState(self, state: int) -> bytearray:
        if state:
            pass
        else:
            pass

    def makePacketOpenOuterDoor(self) -> bytearray:
        # 공동현관문 호출 후 카메라 영상이 우회된 상태에서 열림 명령
        return self.makePacketCommon(0x61)
