import os
import sys
import queue
import serial
import datetime
from typing import Union
sys.path.extend([os.path.dirname(os.path.abspath(__file__))])
sys.path = list(set(sys.path))
from Define import writeLog, Callback
from SerialThreads import ThreadSend, ThreadReceive, ThreadCheck


class SerialComm:
    _name: str = 'SerialComm'
    _serial: serial.Serial
    _threadSend: Union[ThreadSend, None] = None
    _threadRecv: Union[ThreadReceive, None] = None
    _threadCheck: Union[ThreadCheck, None] = None

    def __init__(self, name: str = 'SerialComm'):
        self._name = name

        self.sig_connected = Callback()
        self.sig_disconnected = Callback()
        self.sig_send_data = Callback(bytes)
        self.sig_recv_data = Callback(bytes)
        self.sig_exception = Callback(str)

        self._serial = serial.Serial(timeout=0)
        self._serial.bytesize = 8
        self._serial.parity = 'N'
        self._serial.stopbits = 1

        self._last_recv_time = datetime.datetime.now()

        self._queue_send = queue.Queue()
        self._queue_recv = queue.Queue()

    def release(self):
        self.disconnect()

    def connect(self, port: str, baudrate: int) -> bool:
        try:
            if self._serial.isOpen():
                return False

            self._serial.port = port
            self._serial.baudrate = baudrate
            self._serial.open()
            if self._serial.isOpen():
                self.clearQueues()
                self.startThreads()
                self.sig_connected.emit()
                writeLog('Connected to <{}> (baud: {})'.format(port, baudrate), self)
                return True

            return False
        except Exception as e:
            writeLog('Exception::{}'.format(e), self)
            self.sig_exception.emit(str(e))

    def disconnect(self):
        try:
            if self._serial.isOpen():
                self.stopThreads()
                self._serial.close()
                self.sig_disconnected.emit()
                writeLog('Disconnected', self)
        except Exception as e:
            writeLog('Exception::{}'.format(e), self)
            self.sig_exception.emit(str(e))

    def isConnected(self) -> bool:
        try:
            return self._serial.isOpen()
        except Exception as e:
            writeLog('Exception::{}'.format(e), self)
            return False

    def startThreads(self):
        if self._threadSend is None:
            self._threadSend = ThreadSend(self._serial, self._queue_send)
            self._threadSend.sig_send_data.connect(self.onSendData)
            self._threadSend.sig_terminated.connect(self.onThreadSendTermanted)
            self._threadSend.sig_exception.connect(self.onException)
            self._threadSend.setDaemon(True)
            self._threadSend.start()

        if self._threadCheck is None:
            self._threadCheck = ThreadCheck(self._queue_recv)
            self._threadCheck.sig_get.connect(self.onRecvData)
            self._threadCheck.sig_terminated.connect(self.onThreadCheckTermanted)
            self._threadCheck.sig_exception.connect(self.onException)
            self._threadCheck.setDaemon(True)
            self._threadCheck.start()

        if self._threadRecv is None:
            self._threadRecv = ThreadReceive(self._serial, self._queue_recv)
            self._threadRecv.sig_recv_data.connect(self.onRecvSomething)
            self._threadRecv.sig_terminated.connect(self.onThreadRecvTermanted)
            self._threadRecv.sig_exception.connect(self.onException)
            self._threadRecv.setDaemon(True)
            self._threadRecv.start()

    def stopThreads(self):
        if self._threadSend is not None:
            self._threadSend.stop()
        if self._threadRecv is not None:
            self._threadRecv.stop()
        if self._threadCheck is not None:
            self._threadCheck.stop()

    def clearQueues(self):
        while not self._queue_send.empty():
            self._queue_send.get()
        while not self._queue_recv.empty():
            self._queue_recv.get()

    def sendData(self, data: Union[bytes, bytearray, str]):
        if not self.isConnected():
            return
        try:
            if isinstance(data, str):
                sData = bytearray()
                sData.extend(map(ord, data))
                sData = bytes(sData)
                self._queue_send.put(sData)
            elif isinstance(data, bytes) or isinstance(data, bytearray):
                sData = bytes(data)
                self._queue_send.put(sData)
        except Exception as e:
            writeLog('Exception::{}'.format(e), self)
            self.sig_exception.emit(str(e))

    def onSendData(self, data: bytes):
        # writeLog('onSendData::{}'.format(data), self)
        self.sig_send_data.emit(data)

    def onRecvSomething(self):
        self._last_recv_time = datetime.datetime.now()

    def onRecvData(self, data: bytes):
        self.sig_recv_data.emit(data)

    def onException(self, msg: str):
        self.sig_exception.emit(msg)

    def onThreadSendTermanted(self):
        del self._threadSend
        self._threadSend = None

    def onThreadRecvTermanted(self):
        del self._threadRecv
        self._threadRecv = None

    def onThreadCheckTermanted(self):
        del self._threadCheck
        self._threadCheck = None

    def reset_input_buffer(self):
        self._serial.reset_input_buffer()

    def time_after_last_recv(self) -> float:
        delta = datetime.datetime.now() - self._last_recv_time
        return delta.total_seconds()

    @property
    def name(self) -> str:
        return self._name

    @property
    def port(self) -> str:
        return self._serial.port

    @property
    def baudrate(self) -> int:
        return self._serial.baudrate


if __name__ == '__main__':
    import time

    def onRecv(data: bytes):
        print(data)

    obj = SerialComm()
    obj.sig_recv_data.connect(onRecv)
    obj.connect('/dev/ttyUSB1', 9600)
    time.sleep(5)
    obj.release()
