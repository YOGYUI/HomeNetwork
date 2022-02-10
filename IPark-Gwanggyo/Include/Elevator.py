import json
from Common import Callback
from Device import Device


class Elevator(Device):
    my_floor: int = -1
    current_floor: str = 'unknown'
    current_floor_prev: str = 'unknown'

    def __init__(self, name: str = 'Elevator', **kwargs):
        super().__init__(name, **kwargs)
        self.sig_call_up = Callback()
        self.sig_call_down = Callback()

    def call_up(self):
        self.sig_call_up.emit()

    def call_down(self):
        self.sig_call_down.emit()

    def publish_mqtt(self):
        """
        state value
        1: moving
        4: arrived
        """
        obj = {
            "state": int(self.state == 4)
        }
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)
        self.mqtt_client.publish("home/ipark/elevator/state/occupancy", json.dumps(obj), 1)
