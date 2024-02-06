import json
from Device import *
import threading
import RPi.GPIO as GPIO
from Common import Callback, writeLog


class ThreadDoorLockOpen(threading.Thread):
    def __init__(self, gpio_port: int):
        threading.Thread.__init__(self)
        self.gpio_port = gpio_port
        self.sig_terminated = Callback()
    
    def run(self):
        writeLog('Started', self)
        GPIO.output(self.gpio_port, GPIO.LOW)
        for _ in range(2):
            writeLog(f"Set GPIO PIN{self.gpio_port} as LOW", self)
            time.sleep(0.1)
            GPIO.output(self.gpio_port, GPIO.HIGH)
            writeLog(f"Set GPIO PIN{self.gpio_port} as HIGH", self)
            time.sleep(0.1)
        time.sleep(5)  # 5초간 Unsecured state를 유지해준다
        writeLog('Terminated', self)
        self.sig_terminated.emit()


class DoorLock(Device):
    enable: bool = False
    gpio_port: int = 0
    thread_open: Union[ThreadDoorLockOpen, None] = None

    def __init__(self, name: str = 'Doorlock', index: int = 0, room_index: int = 0):
        super().__init__(name, index, room_index)
        self.dev_type = DeviceType.DOORLOCK
        self.unique_id = f'doorlock_{self.room_index}_{self.index}'
        self.mqtt_publish_topic = f'home/state/doorlock/{self.room_index}/{self.index}'
        self.mqtt_subscribe_topic = f'home/command/doorlock/{self.room_index}/{self.index}'
        self.state = 1
        self.setParams(True, 23)
    
    def setDefaultName(self):
        self.name = 'Doorlock'

    def publishMQTT(self):
        # 'Unsecured', 'Secured', 'Jammed', 'Unknown'
        state_str = 'Unknown'
        if self.state == 0:
            state_str = 'Unsecured'
        elif self.state == 1:
            state_str = 'Secured'
        obj = {"state": state_str}
        if self.mqtt_client is not None:
            self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)

    def configMQTT(self, retain: bool = False):
        pass

    def setParams(self, enable: bool, gpio_port: int):
        self.enable = enable
        self.gpio_port = gpio_port
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.gpio_port, GPIO.IN, GPIO.PUD_UP)  # GPIO IN, Pull Down 설정

    def updateState(self, state: int, **kwargs):
        self.state = state
        if not self.init:
            self.publishMQTT()
            self.init = True
        if self.state != self.state_prev:
            self.publishMQTT()
        self.state_prev = self.state

    def startThreadOpen(self):
        if self.thread_open is None:
            self.updateState(0)
            GPIO.setup(self.gpio_port, GPIO.OUT)
            GPIO.output(self.gpio_port, GPIO.HIGH)
            self.thread_open = ThreadDoorLockOpen(self.gpio_port)
            self.thread_open.sig_terminated.connect(self.onThreadOpenTerminated)
            self.thread_open.start()
        else:
            writeLog('Thread is still working', self)

    def onThreadOpenTerminated(self):
        del self.thread_open
        self.thread_open = None
        self.updateState(1)
        GPIO.setup(self.gpio_port, GPIO.IN, GPIO.PUD_UP)  # GPIO IN, Pull Down 설정

    def open(self):
        if self.enable:
            self.startThreadOpen()
        else:
            writeLog('Disabled!', self)

    def makePacketOpen(self) -> bytearray:
        # F7 0E 01 1E 02 43 11 04 00 04 FF FF B6 EE
        return bytearray([0xF7, 0x0E, 0x01, 0x1E, 0x02, 0x43, 0x11, 0x04, 0x00, 0x04, 0xFF, 0xFF, 0xB6, 0xEE])
