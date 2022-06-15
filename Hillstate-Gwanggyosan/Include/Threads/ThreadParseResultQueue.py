import os
import sys
import time
import queue
import threading
from typing import Union
CURPATH = os.path.dirname(os.path.abspath(__file__))
INCPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, INCPATH])
sys.path = list(set(sys.path))
del CURPATH, INCPATH
from Define import *
from Common import Callback, writeLog


class ThreadParseResultQueue(threading.Thread):
    _keepAlive: bool = True

    def __init__(self, queue_: queue.Queue):
        threading.Thread.__init__(self, name='Parse Result Queue Thread')
        self._queue = queue_
        self.sig_get = Callback(dict)
        self.sig_terminated = Callback()
    
    def run(self):
        writeLog('Started', self)
        while self._keepAlive:
            if not self._queue.empty():
                result = self._queue.get()
                self.sig_get.emit(result)
            else:
                time.sleep(1e-3)
        writeLog('Terminated', self)
        self.sig_terminated.emit()
    
    def stop(self):
        self._keepAlive = False
