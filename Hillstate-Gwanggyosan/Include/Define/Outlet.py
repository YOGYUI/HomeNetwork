import json
from Device import *


class Outlet(Device):
    enable_off_command: bool = False
    handle_power_consumption: bool = False
    power_consumption: int = 0
    power_consumption_prev: int = 0
    handle_standby_cutoff_mode: bool = False
    standby_cutoff_mode: int = 0  # 대기전력 차단 모드, 0 = 수동, 1 = 자동
    standby_cutoff_mode_prev: int = 0

    def __init__(self, name: str = 'Outlet', index: int = 0, room_index: int = 0, topic_prefix: str = 'home'):
        super().__init__(name, index, room_index, topic_prefix)
        self.dev_type = DeviceType.OUTLET
        self.unique_id = f'outlet_{self.room_index}_{self.index}'
        self.mqtt_state_topic = f'{topic_prefix}/state/outlet/{self.room_index}/{self.index}'
        self.mqtt_command_topic = f'{topic_prefix}/command/outlet/{self.room_index}/{self.index}'

    def setDefaultName(self):
        self.name = 'Outlet'

    def __repr__(self):
        # repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))}) '
        repr_txt = f'<{self.__class__.__name__}, {self.name}, '
        repr_txt += f'Dev Idx: {self.index}, '
        repr_txt += f'Room Idx: {self.room_index}, '
        repr_txt += f'Enable Off Cmd: {self.enable_off_command}'
        repr_txt += '>'
        return repr_txt
    
    def setEnableOffCommand(self, value: bool):
        self.enable_off_command = value

    def setEnableHandlePowerConsumption(self, value: bool):
        self.handle_power_consumption = value
    
    def setEnableHandleStandbyCutoffMode(self, value: bool):
        self.handle_standby_cutoff_mode = value

    def publishMQTT(self):
        obj = {
            "state": self.state,
            "power_consumption": self.power_consumption,
            "standby_cutoff_mode": self.standby_cutoff_mode
        }
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_state_topic, json.dumps(obj), 1)

    def configMQTT(self, retain: bool = False):
        if self.mqtt_client is None:
            return
        
        # On/Off switch
        topic = f'{self.ha_discovery_prefix}/switch/{self.unique_id}/config'
        obj = {
            "name": self.name,
            "unique_id": self.unique_id,
            "state_topic": self.mqtt_state_topic,
            "command_topic": self.mqtt_command_topic,
            "value_template": '{ "state": {{ value_json.state }} }',
            "payload_on": '{ "state": 1 }',
            "payload_off": '{ "state": 0 }',
            "icon": "mdi:power-socket-de"
        }
        if self.check_ha_core_version("2025.10.1"):
            obj["default_entity_id"] = self.unique_id
        else:
            obj["object_id"] = self.unique_id
        self.mqtt_client.publish(topic, json.dumps(obj), 1, retain)

        # Power consumption sensor
        topic = f'{self.ha_discovery_prefix}/sensor/{self.unique_id}/config'
        if self.handle_power_consumption:
            obj = {
                "name": self.name + "_power_consumption",
                "unique_id": self.unique_id + "_power_consumption",
                "state_topic": self.mqtt_state_topic,
                "unit_of_measurement": "W",
                "value_template": '{{ value_json.power_consumption }}',
                "device_class": "power",
                "state_class": "measurement"
            }
            if self.check_ha_core_version("2025.10.1"):
                obj["default_entity_id"] = self.unique_id + "_power_consumption"
            else:
                obj["object_id"] = self.unique_id + "_power_consumption"
        else:
            obj = {}
        self.mqtt_client.publish(topic, json.dumps(obj), 1, retain)

        # Stanby cut-off mode switch
        topic = f'{self.ha_discovery_prefix}/switch/{self.unique_id}_standby/config'
        if self.handle_standby_cutoff_mode:
            obj = {
                "name": self.name + "_stanby_cutoff",
                "unique_id": self.unique_id + "_stanby_cutoff",
                "state_topic": self.mqtt_state_topic,
                "command_topic": self.mqtt_command_topic,
                "value_template": '{ "standby_cutoff_mode": {{ value_json.standby_cutoff_mode }} }',
                "payload_on": '{ "standby_cutoff_mode": 1 }',
                "payload_off": '{ "standby_cutoff_mode": 0 }',
                "icon": "mdi:power-socket-de"
            }
            if self.check_ha_core_version("2025.10.1"):
                obj["default_entity_id"] = self.unique_id + "_stanby_cutoff"
            else:
                obj["object_id"] = self.unique_id + "_stanby_cutoff"
        else:
            obj = {}
        self.mqtt_client.publish(topic, json.dumps(obj), 1, retain)

        # add homebridge accessory
        hb_config = self.read_homebridge_config_template()
        accessories = hb_config.get('accessories')
        find = list(filter(lambda x: x.get('name') == self.name, accessories))
        if len(find) > 0:
            return
        
        elem = {
            "name": self.name,
            "accessory": "mqttthing",
            "type": "outlet",
            "url": f"{self.mqtt_host}:{self.mqtt_port}",
            "username": self.mqtt_username,
            "password": self.mqtt_password,
            "integerValue": False,
            "onValue": 1, 
            "offValue": 0,
            "history": True,
            "logMqtt": False,
            "topics": {
                "getOn": {
                    "topic": self.mqtt_state_topic,
                    "apply": "return JSON.parse(message).state;"
                },
                "setOn": {
                    "topic": self.mqtt_command_topic,
                    "apply": "return JSON.stringify({state: message});"
                }
            }
        }
        accessories.append(elem)
        
        self.write_homebridge_config_template(hb_config)

    def updateState(self, state: int, **kwargs):
        self.state = state
        if not self.init:
            self.publishMQTT()
            self.init = True
        if self.state != self.state_prev:
            self.publishMQTT()
        self.state_prev = self.state
        # 소비전력
        if self.handle_power_consumption:
            power_consumption = kwargs.get('power_consumption')
            if power_consumption is not None:
                self.power_consumption = power_consumption
                if self.power_consumption != self.power_consumption_prev:
                    self.publishMQTT()
                self.power_consumption_prev = self.power_consumption
        # 대기전력 차단 모드
        if self.handle_standby_cutoff_mode:
            standby_cutoff_mode = kwargs.get('standby_cutoff_mode')
            if standby_cutoff_mode is not None:
                self.standby_cutoff_mode = standby_cutoff_mode
                if self.standby_cutoff_mode != self.standby_cutoff_mode_prev:
                    self.publishMQTT()
                self.standby_cutoff_mode_prev = self.standby_cutoff_mode

    def makePacketQueryState(self) -> bytearray:
        # F7 0B 01 1F 01 40 XX 00 00 YY EE
        # XX: 상위 4비트 = Room Index, 하위 4비트 = 0
        # YY: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x1F, 0x01, 0x40])
        # packet.append(self.room_index << 4)
        packet.append((self.room_index << 4) + (self.index + 1))
        packet.extend([0x00, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

    def makePacketSetState(self, state: bool) -> bytearray:
        # F7 0B 01 1F 02 40 XX YY 00 ZZ EE
        # XX: 상위 4비트 = Room Index, 하위 4비트 = Device Index (1-based)
        # YY: 02 = OFF, 01 = ON
        # ZZ: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x1F, 0x02, 0x40])
        packet.append((self.room_index << 4) + (self.index + 1))
        if state:
            packet.extend([0x01, 0x00])
        else:
            packet.extend([0x02, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

    def makePacketSetStandbyCutoffMode(self, mode: bool) -> bytearray:
        # F7 0B 01 1F 02 ?? XX YY 00 ZZ EE
        pass
