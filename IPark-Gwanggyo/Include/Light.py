import json
from Device import Device


class Light(Device):
    def __init__(self, name: str = 'Light', index: int = 0, **kwargs):
        self.index = index
        super().__init__(name, **kwargs)

    def publish_mqtt(self):
        obj = {"state": self.state}
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)

    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += f' Room Idx: {self.room_index}, Dev Indx: {self.index}'
        repr_txt += '>'
        return repr_txt
