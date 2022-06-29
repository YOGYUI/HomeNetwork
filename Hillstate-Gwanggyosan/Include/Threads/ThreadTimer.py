import os
import sys
import time
import threading
from typing import List
from Common import Callback, writeLog
CURPATH = os.path.dirname(os.path.abspath(__file__))  # Project/Include/Threads
PROJPATH = os.path.dirname(os.path.dirname(CURPATH))  # Proejct/
RS485PATH = os.path.join(PROJPATH, 'RS485')  # Project/RS485
sys.path.extend([RS485PATH])
sys.path = list(set(sys.path))
from RS485 import RS485Comm


class ThreadTimer(threading.Thread):
    _keepAlive: bool = True
    _publish_count: int = 0

    def __init__(
        self,
        rs485_list: List[RS485Comm],
        publish_interval: int = 60,
        interval_ms: int = 2000
    ):
        threading.Thread.__init__(self, name='Timer Thread')
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
            try:
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

                if time.perf_counter() - tm > self._publish_interval:
                    self.sig_publish_regular.emit()
                    self._publish_count += 1
                    writeLog(f'Regular Publishing Device State MQTT (#: {self._publish_count}, interval: {self._publish_interval} sec)', self)
                    tm = time.perf_counter()
                time.sleep(self._interval_ms / 1000)
            except Exception as e:
                writeLog(f'Exception::{e}', self)
        writeLog('Terminated', self)
        self.sig_terminated.emit()

    def stop(self):
        self._keepAlive = False
    
    def setMqttPublishInterval(self, interval: int):
        self._publish_interval = interval
        writeLog(f'Set Regular MQTT Publish Interval as {self._publish_interval} sec', self)
