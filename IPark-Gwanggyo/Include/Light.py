import json
from Device import Device


class Light(Device):
    def __init__(self, name: str = 'Device', index: int = 0, **kwargs):
        self.index = index
        super().__init__(name, **kwargs)

    def publish_mqtt(self):
        obj = {"state": self.state}
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)
