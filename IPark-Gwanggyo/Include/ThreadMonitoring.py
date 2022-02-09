import os
import sys
import time
import threading
from typing import List
from Device import Device
from Common import Callback, writeLog
CURPATH = os.path.dirname(os.path.abspath(__file__))  # Project/Include
PROJPATH = os.path.dirname(CURPATH)  # Proejct/
SERPATH = os.path.join(PROJPATH, 'Serial485')  # Project/Serial485
sys.path.extend([SERPATH])
sys.path = list(set(sys.path))
from SerialComm import SerialComm


class ThreadMonitoring(threading.Thread):
    _keepAlive: bool = True

    def __init__(
            self,
            serial_list: List[SerialComm],
            device_list: List[Device],
            publish_interval: int = 60,
            interval_ms: int = 2000
    ):
        threading.Thread.__init__(self)
        self._serial_list = serial_list
        self._device_list = device_list
        self._publish_interval = publish_interval
        self._interval_ms = interval_ms
        self.sig_terminated = Callback()

    def run(self):
        writeLog('Started', self)
        tm = time.perf_counter()
        while self._keepAlive:
            for ser in self._serial_list:
                if ser.isConnected():
                    delta = ser.time_after_last_recv()
                    if delta > 10:
                        msg = 'Warning!! Serial <{}> is not receiving for {:.1f} seconds'.format(ser.name, delta)
                        writeLog(msg, self)
                else:
                    # writeLog('Warning!! Serial <{}> is not connected'.format(ser.name), self)
                    pass
            if time.perf_counter() - tm > self._publish_interval:
                writeLog('Regular Publishing Device State MQTT (interval: {} sec)'.format(self._publish_interval), self)
                for dev in self._device_list:
                    try:
                        dev.publish_mqtt()
                    except ValueError as e:
                        writeLog(f'{e}: {dev}, {dev.mqtt_publish_topic}', self)
                tm = time.perf_counter()
            time.sleep(self._interval_ms / 1000)
        writeLog('Terminated', self)
        self.sig_terminated.emit()

    def stop(self):
        self._keepAlive = False
