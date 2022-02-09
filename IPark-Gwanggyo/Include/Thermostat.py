import json
from typing import List
from Device import Device


class Thermostat(Device):
    temperature_current: float = 0.
    temperature_current_prev: float = 0.
    temperature_setting: float = 0.
    temperature_setting_prev: float = 0.
    packet_set_temperature: List[str]

    def __init__(self, name: str = 'Device', **kwargs):
        super().__init__(name, **kwargs)
        self.packet_set_temperature = [''] * 71  # 5.0 ~ 40.0, step=0.5

    def publish_mqtt(self):
        obj = {
            "state": 'HEAT' if self.state == 1 else 'OFF',
            "currentTemperature": self.temperature_current,
            "targetTemperature": self.temperature_setting
        }
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)
