import time
import queue
import serial
import threading
import traceback
from Define import Callback, writeLog


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
        writeLog('Started', self)
        while self._keepAlive:
            try:
                if not self._queue.empty():
                    data = self._queue.get()
                    sendLen = len(data)
                    while sendLen > 0:
                        nLen = self._serial.write(data[(len(data) - sendLen):])
                        sData = data[(len(data) - sendLen):(len(data) - sendLen + nLen)]
                        self.sig_send_data.emit(sData)
                        sendLen -= nLen
                else:
                    time.sleep(1e-3)
            except Exception as e:
                writeLog('Exception::{}'.format(e), self)
                traceback.print_exc()
                self.sig_exception.emit(str(e))
        writeLog('Terminated', self)
        self.sig_terminated.emit()
    
    def stop(self):
        self._keepAlive = False


class ThreadReceive(threading.Thread):
    _keepAlive: bool = True

    def __init__(self, serial_: serial.Serial, queue_: queue.Queue):
        threading.Thread.__init__(self, name='Serial Recv Thread')
        self.sig_terminated = Callback()
        # self.sig_recv_data = Callback(bytes)
        self.sig_recv_data = Callback()
        self.sig_exception = Callback(str)
        self._serial = serial_
        self._queue = queue_
    
    def run(self):
        writeLog('Started', self)
        while self._keepAlive:
            try:
                if self._serial.isOpen():
                    if self._serial.in_waiting > 0:
                        rcv = self._serial.read(self._serial.in_waiting)
                        # self.sig_recv_data.emit(rcv)
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
        writeLog('Terminated', self)
        self.sig_terminated.emit()
    
    def stop(self):
        self._keepAlive = False


class ThreadCheck(threading.Thread):
    _keepAlive: bool = True

    def __init__(self, queue_: queue.Queue):
        threading.Thread.__init__(self, name='Serial Check Thread')
        self.sig_get = Callback(bytes)
        self.sig_terminated = Callback()
        self.sig_exception = Callback(str)
        self._queue = queue_
    
    def run(self):
        writeLog('Started', self)
        while self._keepAlive:
            try:
                if not self._queue.empty():
                    self.sig_get.emit(self._queue.get())
                else:
                    time.sleep(1e-3)
            except Exception as e:
                writeLog('Exception::{}'.format(e), self)
                traceback.print_exc()
                self.sig_exception.emit(str(e))
        writeLog('Terminated', self)
        self.sig_terminated.emit()
    
    def stop(self):
        self._keepAlive = False
