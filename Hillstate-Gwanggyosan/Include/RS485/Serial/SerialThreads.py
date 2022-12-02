import os
import sys
import time
import queue
import serial
import threading
import traceback
CURPATH = os.path.dirname(os.path.abspath(__file__))  # {$PROJECT}/Include/RS485/Serial
INCPATH = os.path.dirname(os.path.dirname(CURPATH))  # {$PROJECT}/Include/
sys.path.extend([CURPATH, INCPATH])
sys.path = list(set(sys.path))
del CURPATH, INCPATH
from Common import writeLog, Callback


class ThreadSend(threading.Thread):
    _keepAlive: bool = True

    def __init__(self, serial_: serial.Serial, queue_: queue.Queue):
        threading.Thread.__init__(self, name='Serial Send Thread')
        self.sig_send_data = Callback(bytes)
        self.sig_terminated = Callback()
        self.sig_exception = Callback(str)
        self._serial = serial_
        self._queue = queue_

    def run(self):
        writeLog(f'Started ({self._serial.port})', self)
        while self._keepAlive:
            try:
                if not self._queue.empty():
                    data = self._queue.get()
                    sendLen = len(data)
                    # self._serial.setRTS(True)
                    while sendLen > 0:
                        nLen = self._serial.write(data[(len(data) - sendLen):])
                        sData = data[(len(data) - sendLen):(len(data) - sendLen + nLen)]
                        self.sig_send_data.emit(sData)
                        sendLen -= nLen
                    # self._serial.setRTS(False)
                else:
                    time.sleep(1e-3)
            except Exception as e:
                writeLog('Exception::{}'.format(e), self)
                traceback.print_exc()
                self.sig_exception.emit(str(e))
        writeLog(f'Terminated ({self._serial.port})', self)
        self.sig_terminated.emit()
    
    def stop(self):
        self._keepAlive = False


class ThreadReceive(threading.Thread):
    _keepAlive: bool = True

    def __init__(self, serial_: serial.Serial, queue_: queue.Queue):
        threading.Thread.__init__(self, name='Serial Recv Thread')
        self.sig_terminated = Callback()
        self.sig_recv_data = Callback()
        self.sig_exception = Callback(str)
        self._serial = serial_
        self._queue = queue_
    
    def run(self):
        writeLog(f'Started ({self._serial.port})', self)
        while self._keepAlive:
            try:
                if self._serial.isOpen():
                    if self._serial.in_waiting > 0:
                        rcv = self._serial.read(self._serial.in_waiting)
                        self.sig_recv_data.emit()
                        self._queue.put(rcv)
                    else:
                        time.sleep(1e-3)
                else:
                    time.sleep(1e-3)
            except Exception as e:
                writeLog(f'Exception::{self._serial.port}::{e}', self)
                traceback.print_exc()
                self.sig_exception.emit(str(e))
                # break
        writeLog(f'Terminated ({self._serial.port})', self)
        self.sig_terminated.emit()
    
    def stop(self):
        self._keepAlive = False


class ThreadCheckRecvQueue(threading.Thread):
    _keepAlive: bool = True

    def __init__(self, serial_: serial.Serial, queue_: queue.Queue):
        threading.Thread.__init__(self, name='Serial Check Thread')
        self.sig_get = Callback(bytes)
        self.sig_terminated = Callback()
        self.sig_exception = Callback(str)
        self._serial = serial_
        self._queue = queue_
    
    def run(self):
        writeLog(f'Started ({self._serial.port})', self)
        while self._keepAlive:
            try:
                if not self._queue.empty():
                    chunk = self._queue.get()
                    self.sig_get.emit(chunk)
                else:
                    time.sleep(1e-3)
            except Exception as e:
                writeLog('Exception::{}'.format(e), self)
                traceback.print_exc()
                self.sig_exception.emit(str(e))
        writeLog(f'Terminated ({self._serial.port})', self)
        self.sig_terminated.emit()
    
    def stop(self):
        self._keepAlive = False
