import json
from Device import *


class Thermostat(Device):
    temp_current: int = 0  # 현재 온도
    temp_current_prev: int = 0  # 현재 온도 버퍼
    temp_config: int = 0  # 난방 설정 온도
    temp_config_prev: int = 0  # 난방 설정 온도 버퍼
    temp_range: List[int]  # 설정 가능한 온도값의 범위

    def __init__(self, name: str = 'Thermostat', index: int = 0, room_index: int = 0, topic_prefix: str = 'home'):
        super().__init__(name, index, room_index, topic_prefix)
        self.dev_type = DeviceType.THERMOSTAT
        self.unique_id = f'thermostat_{self.room_index}_{self.index}'
        self.mqtt_state_topic = f'{topic_prefix}/state/thermostat/{self.room_index}/{self.index}'
        self.mqtt_command_topic = f'{topic_prefix}/command/thermostat/{self.room_index}/{self.index}'
        self.temp_range = [0, 100]

    def setDefaultName(self):
        self.name = 'Thermostat'

    def publishMQTT(self):
        obj = {
            "state": 'HEAT' if self.state == 1 else 'OFF',
            "currentTemperature": self.temp_current, 
            "targetTemperature": self.temp_config,
            "timer": int(self.isTimerOnOffRunning())
        }
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_state_topic, json.dumps(obj), 1)

    def configMQTT(self, retain: bool = False):
        if self.mqtt_client is None:
            return
        
        topic = f'{self.ha_discovery_prefix}/climate/{self.unique_id}/config'
        obj = {
            "name": self.name,
            "object_id": self.unique_id,
            "unique_id": self.unique_id,
            "modes": ["off", "heat"],
            "mode_state_topic": self.mqtt_state_topic,
            "mode_state_template": "{{ value_json.state.lower() }}",
            "mode_command_topic": self.mqtt_command_topic,
            "mode_command_template": "{% set values = {'off': '\"OFF\"', 'heat': '\"HEAT\"'} %} \
                                      { \"state\": {{ values[value] if value in values.keys() else \"OFF\" }} }",
            "temperature_state_topic": self.mqtt_state_topic,
            "temperature_state_template": "{{ value_json.targetTemperature }}",
            "temperature_command_topic": self.mqtt_command_topic,
            "temperature_command_template": '{ "targetTemperature": {{ value }} }',
            "current_temperature_topic": self.mqtt_state_topic,
            "current_temperature_template": "{{ value_json.currentTemperature }}",
            "min_temp": self.temp_range[0],
            "max_temp": self.temp_range[1],
            "precision": 1,
        }
        self.mqtt_client.publish(topic, json.dumps(obj), 1, retain)

        # add homebridge accessory
        if not os.path.isfile(self.homebridge_config_path):
            return
        with open(self.homebridge_config_path, 'r') as fp:
            hb_config = json.load(fp)
        accessories = hb_config.get('accessories')
        find = list(filter(lambda x: x.get('name') == self.name, accessories))
        if len(find) > 0:
            return
        
        elem = {
            "name": self.name,
            "accessory": "mqttthing",
            "type": "thermostat",
            "url": f"{self.mqtt_host}:{self.mqtt_port}",
            "username": self.mqtt_username,
            "password": self.mqtt_password,
            "minTemperature": self.temp_range[0],
            "maxTemperature": self.temp_range[1],
            "restrictHeatingCoolingState": [0, 1],
            "history": True,
            "logMqtt": False,
            "topics": {
                "getCurrentHeatingCoolingState": {
                    "topic": self.mqtt_state_topic,
                    "apply": "return JSON.parse(message).state;"
                },
                "setTargetHeatingCoolingState": {
                    "topic": self.mqtt_command_topic,
                    "apply": "return JSON.stringify({state: message});"
                },
                "getTargetHeatingCoolingState": {
                    "topic": self.mqtt_state_topic,
                    "apply": "return JSON.parse(message).state;"
                },
                "getCurrentTemperature": {
                    "topic": self.mqtt_state_topic,
                    "apply": "return JSON.parse(message).currentTemperature;"
                },
                "setTargetTemperature": {
                    "topic": self.mqtt_command_topic,
                    "apply": "return JSON.stringify({targetTemperature: message});"
                },
                "getTargetTemperature": {
                    "topic": self.mqtt_state_topic,
                    "apply": "return JSON.parse(message).targetTemperature;"
                }
            }
        }
        accessories.append(elem)

        elem = {
            "name": self.name + "_timer",
            "accessory": "mqttthing",
            "type": "switch",
            "url": f"{self.mqtt_host}:{self.mqtt_port}",
            "username": self.mqtt_username,
            "password": self.mqtt_password,
            "integerValue": True,
            "onValue": 1,
            "offValue": 0,
            "history": True,
            "logMqtt": False,
            "topics": {
                "getOn": {
                    "topic": self.mqtt_state_topic,
                    "apply": "return (JSON.parse(message).timer == 1);"
                },
                "setOn": {
                    "topic": self.mqtt_command_topic,
                    "apply": "return JSON.stringify({timer: message});"
                }
            }
        }
        accessories.append(elem)
        self.homebridge_modifed = True

    def setTemperatureRange(self, range_min: int, range_max: int):
        self.temp_range[0] = range_min
        self.temp_range[1] = range_max
        self.temp_current = max(range_min, min(range_max, self.temp_current))
        self.temp_config = max(range_min, min(range_max, self.temp_config))
        writeLog(f"{str(self)} Set Temperature Range: {self.temp_range[0]} ~ {self.temp_range[1]}", self)

    def updateState(self, state: int, **kwargs):
        self.state = state
        if not self.init:
            self.publishMQTT()
            self.init = True
        if self.state != self.state_prev:
            self.publishMQTT()
        self.state_prev = self.state
        # 현재온도
        temp_current = kwargs.get('temp_current')
        if temp_current is not None:
            # self.temp_current = temp_current
            self.temp_current = max(self.temp_range[0], min(self.temp_range[1], temp_current))
            if self.temp_current != self.temp_current_prev:
                self.publishMQTT()
            self.temp_current_prev = self.temp_current
        # 희망온도
        temp_config = kwargs.get('temp_config')
        if temp_config is not None:
            # self.temp_config = temp_config
            self.temp_config = max(self.temp_range[0], min(self.temp_range[1], temp_config))
            if self.temp_config != self.temp_config_prev:
                self.publishMQTT()
            self.temp_config_prev = self.temp_config
    
    def makePacketQueryState(self) -> bytearray:
        # F7 0B 01 18 01 46 10 00 00 XX EE
        # XX: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x18, 0x01, 0x46])
        packet.append(0x10 + self.room_index)
        packet.extend([0x00, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet

    def makePacketSetState(self, state: bool) -> bytearray:
        # F7 0B 01 18 02 46 XX YY 00 ZZ EE
        # XX: 상위 4비트 = 1, 하위 4비트 = Room Index
        # YY: 0x01=On, 0x04=Off
        # ZZ: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x18, 0x02, 0x46])
        packet.append(0x10 + (self.room_index & 0x0F))
        if state:
            packet.extend([0x01, 0x00])
        else:
            packet.extend([0x04, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet
        
    def makePacketSetTemperature(self, temperature: int) -> bytearray:
        # F7 0B 01 18 02 45 XX YY 00 ZZ EE
        # XX: 상위 4비트 = 1, 하위 4비트 = Room Index
        # YY: 온도 설정값
        # ZZ: Checksum (XOR SUM)
        packet = bytearray([0xF7, 0x0B, 0x01, 0x18, 0x02, 0x45])
        packet.append(0x10 + (self.room_index & 0x0F))
        packet.extend([temperature & 0xFF, 0x00])
        packet.append(self.calcXORChecksum(packet))
        packet.append(0xEE)
        return packet
