import time
import json
import threading
from typing import Union
from Device import Device
import RPi.GPIO as GPIO
from Common import Callback, writeLog


class ThreadOpen(threading.Thread):
    def __init__(self, gpio_port: int, repeat: int, interval_ms: int):
        threading.Thread.__init__(self)
        self.gpio_port = gpio_port
        self.repeat = repeat
        self.interval_ms = interval_ms
        self.sig_terminated = Callback()
    
    def run(self):
        writeLog('Started', self)
        for i in range(self.repeat):
            GPIO.output(self.gpio_port, GPIO.HIGH)
            time.sleep(self.interval_ms / 1000)
            GPIO.output(self.gpio_port, GPIO.LOW)
            time.sleep(self.interval_ms / 1000)
        writeLog('Terminated', self)
        self.sig_terminated.emit()


class Doorlock(Device):
    gpio_port: int
    repeat: int
    interval_ms: int
    thread_open: Union[ThreadOpen, None] = None

    def __init__(self, name: str = 'Doorlock', **kwargs):
        super().__init__(name, **kwargs)

    def setParams(self, gpio_port: int = 23, repeat: int = 2, interval_ms: int = 200):
        self.gpio_port = gpio_port
        self.repeat = repeat
        self.interval_ms = interval_ms

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.gpio_port, GPIO.IN, GPIO.PUD_DOWN)  # GPIO IN, Pull Down 설정

    def startThreadOpen(self):
        if self.thread_open is None:
            GPIO.setup(self.gpio_port, GPIO.OUT)
            GPIO.output(self.gpio_port, GPIO.LOW)
            self.thread_open = ThreadOpen(self.gpio_port, self.repeat, self.interval_ms)
            self.thread_open.sig_terminated.connect(self.onThreadOpenTerminated)
            self.thread_open.start()
        else:
            writeLog('Thread is still working', self)

    def onThreadOpenTerminated(self):
        del self.thread_open
        self.thread_open = None
        self.publish_mqtt()
        GPIO.setup(self.gpio_port, GPIO.IN, GPIO.PUD_DOWN)  # GPIO IN, Pull Down 설정

    def open(self):
        self.startThreadOpen()

    def publish_mqtt(self):
        obj = {"state": int(self.state == 1)}
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)

    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})'
        repr_txt += '>'
        return repr_txt
