import os
import sys
import time
import threading
from typing import List
from Common import Callback, writeLog
CURPATH = os.path.dirname(os.path.abspath(__file__))  # Project/Include
PROJPATH = os.path.dirname(CURPATH)  # Proejct/
SERPATH = os.path.join(PROJPATH, 'Serial485')  # Project/Serial485
sys.path.extend([SERPATH])
sys.path = list(set(sys.path))
from RS485 import SerialComm


class ThreadTimer(threading.Thread):
    _keepAlive: bool = True

    def __init__(
            self,
            serial_list: List[SerialComm],
            publish_interval: int = 60,
            interval_ms: int = 2000
    ):
        threading.Thread.__init__(self, name='Timer Thread')
        self._serial_list = serial_list
        self._publish_interval = publish_interval
        self._interval_ms = interval_ms
        self.sig_terminated = Callback()
        self.sig_publish_regular = Callback()

    def run(self):
        first_publish: bool = False
        writeLog('Started', self)
        tm = time.perf_counter()
        while self._keepAlive:
            ser_all_connected: bool = sum([x.isConnected() for x in self._serial_list]) == len(self._serial_list)
            if ser_all_connected and not first_publish:
                first_publish = True
                writeLog('Serial ports are all opened >> Publish', self)
                self.sig_publish_regular.emit()

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
                self.sig_publish_regular.emit()
                tm = time.perf_counter()
            time.sleep(self._interval_ms / 1000)
        writeLog('Terminated', self)
        self.sig_terminated.emit()

    def stop(self):
        self._keepAlive = False
