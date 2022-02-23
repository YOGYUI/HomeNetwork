import json
from Device import Device


class GasValve(Device):
    def __init__(self, name: str = 'GasValve', **kwargs):
        super().__init__(name, **kwargs)

    def publish_mqtt(self):
        # 0 = closed, 1 = opened, 2 = opening/closing
        obj = {"state": int(self.state == 1)}
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)

    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += '>'
        return repr_txt
