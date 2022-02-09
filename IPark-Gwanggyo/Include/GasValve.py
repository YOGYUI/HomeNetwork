import json
from Device import Device


class GasValve(Device):
    def publish_mqtt(self):
        # 0 = closed, 1 = opened, 2 = opening/closing
        obj = {"state": int(self.state == 1)}
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)
