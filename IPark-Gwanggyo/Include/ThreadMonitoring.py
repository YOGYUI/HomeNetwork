import os
import sys
import time
import threading
from typing import List
from Common import Callback, writeLog
CURPATH = os.path.dirname(os.path.abspath(__file__))  # Project/Include
PROJPATH = os.path.dirname(CURPATH)  # Proejct/
RS485PATH = os.path.join(PROJPATH, 'RS485')  # Project/RS485
sys.path.extend([CURPATH, PROJPATH, RS485PATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH, RS485PATH
from RS485 import RS485Comm


class ThreadMonitoring(threading.Thread):
    _keepAlive: bool = True
    _home_initialized: bool = False

    def __init__(
        self,
        rs485_list: List[RS485Comm],
        publish_interval: int = 60,
        interval_ms: int = 2000
    ):
        threading.Thread.__init__(self, name='Monitoring Thread')
        self._rs485_list = rs485_list
        self._publish_interval = publish_interval
        self._interval_ms = interval_ms
        self.sig_terminated = Callback()
        self.sig_publish_regular = Callback()

    def run(self):
        first_publish: bool = False
        writeLog('Started', self)
        tm = time.perf_counter()
        while self._keepAlive:
            if not self._home_initialized:
                writeLog('Home is not initialized!', self)
                time.sleep(0.1)
                continue
            rs485_all_connected: bool = sum([x.isConnected() for x in self._rs485_list]) == len(self._rs485_list)
            if rs485_all_connected and not first_publish:
                first_publish = True
                writeLog('RS485 are all opened >> Publish', self)
                self.sig_publish_regular.emit()

            for obj in self._rs485_list:
                if obj.isConnected():
                    delta = obj.time_after_last_recv()
                    if delta > 10:
                        msg = 'Warning!! RS485 <{}> is not receiving for {:.1f} seconds'.format(obj.name, delta)
                        writeLog(msg, self)
                    if delta > 120:
                        # 2분이상이면 재접속 시도
                        obj.reconnect()
                else:
                    writeLog('Warning!! RS485 <{}> is not connected'.format(obj.name), self)
                    delta = obj.time_after_last_recv()
                    if delta > 120:
                        # 2분이상이면 재접속 시도
                        writeLog('Try to reconnect RS485 <{}>'.format(obj.name), self)
                        obj.reconnect()

            if time.perf_counter() - tm > self._publish_interval:
                writeLog('Regular Publishing Device State MQTT (interval: {} sec)'.format(self._publish_interval), self)
                self.sig_publish_regular.emit()
                tm = time.perf_counter()
            time.sleep(self._interval_ms / 1000)
        writeLog('Terminated', self)
        self.sig_terminated.emit()

    def stop(self):
        self._keepAlive = False

    def set_home_initialized(self):
        self._home_initialized = True
