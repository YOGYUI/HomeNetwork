import json
from Device import *
import RPi.GPIO as GPIO

class DoorPhone(Device):
    gpio_cam_relay: int = 0

    def __init__(self, name: str = 'DoorPhone', **kwargs):
        super().__init__(name, **kwargs)
        self.state_cam_relay = 0
        self.setParams(18)
    
    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += '>'
        return repr_txt
    
    def publish_mqtt(self):
        obj = {"cam_power": self.state_cam_relay}
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)

    def setParams(self, gpio_cam_relay: int):
        self.gpio_cam_relay = gpio_cam_relay
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.gpio_cam_relay, GPIO.OUT)
    
    def updateState(self, state: int, **kwargs):
        if not self.init:
            self.publish_mqtt()
            self.init = True

    def turn_on_camera(self):
        self.state_cam_relay = 1
        GPIO.output(self.gpio_cam_relay, GPIO.HIGH)
        self.publish_mqtt()
    
    def turn_off_camera(self):
        self.state_cam_relay = 0
        GPIO.output(self.gpio_cam_relay, GPIO.LOW)
        self.publish_mqtt()
