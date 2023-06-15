import os
import sys
import time
from enum import IntEnum
from typing import Union
from Serial import *
from Socket import *
CURPATH = os.path.dirname(os.path.abspath(__file__))  # {$PROJECT}/Include/RS485
INCPATH = os.path.dirname(CURPATH)  # {$PROJECT}/Include/
sys.path.extend([CURPATH, INCPATH])
sys.path = list(set(sys.path))
del CURPATH, INCPATH
from Common import writeLog, Callback


class RS485HwType(IntEnum):
    Serial = 0
    Socket = 1
    Unknown = 2


class RS485Config:
    enable: bool = True
    comm_type: RS485HwType
    serial_port: str = '/dev/ttyUSB0'
    serial_baud: int = 9600
    serial_databit: int = 8
    serial_parity: str = 'N'
    serial_stopbits: float = 1.
    socket_ipaddr: str = '127.0.0.1'
    socket_port: int = 80
    check_connection: bool = True


class RS485Comm:
    _comm_obj: Union[SerialComm, TCPClient, None] = None
    _hw_type: RS485HwType = RS485HwType.Unknown
    _last_conn_addr: str = ''
    _last_conn_port: int = 0
    
    def __init__(self, name: str = 'RS485Comm'):
        self._name = name
        self.sig_connected = Callback()
        self.sig_disconnected = Callback()
        self.sig_send_data = Callback(bytes)
        self.sig_recv_data = Callback(bytes)
        self.sig_exception = Callback(str)

    def setType(self, comm_type: RS485HwType):
        if self._comm_obj is not None:
            self.release()
        if comm_type == RS485HwType.Serial:
            self._comm_obj = SerialComm(self._name)
        elif comm_type == RS485HwType.Socket:
            self._comm_obj = TCPClient(self._name)
        self._hw_type = comm_type
        if self._comm_obj is not None:
            self._comm_obj.sig_connected.connect(self.onConnect)
            self._comm_obj.sig_disconnected.connect(self.onDisconnect)
            self._comm_obj.sig_send_data.connect(self.onSendData)
            self._comm_obj.sig_recv_data.connect(self.onRecvData)
            self._comm_obj.sig_exception.connect(self.onException)
            writeLog(f"Set HW Type as '{comm_type.name}'", self)

    def getType(self) -> RS485HwType:
        return self._hw_type

    def release(self):
        if self._comm_obj is not None:
            self._comm_obj.release()
            del self._comm_obj
        self._comm_obj = None

    def connect(self, addr: str, port: int, **kwargs) -> bool:
        # serial - (devport, baud)
        # socket - (ipaddr, port)
        self._last_conn_addr = addr
        self._last_conn_port = port
        return self._comm_obj.connect(addr, port, **kwargs)

    def disconnect(self):
        self._comm_obj.disconnect()

    def reconnect(self, count: int = 1):
        self.disconnect()
        for _ in range(count):
            if self.isConnected():
                break
            writeLog(f'Debug Issue >> {self._last_conn_addr}, {self._last_conn_port}', self)
            self.connect(self._last_conn_addr, self._last_conn_port)
            time.sleep(1)

    def isConnected(self) -> bool:
        if self._comm_obj is None:
            return False
        return self._comm_obj.isConnected()
    
    def sendData(self, data: Union[bytes, bytearray, str]):
        if self._comm_obj is not None:
            if len(data) > 0:
                self._comm_obj.sendData(data)

    def time_after_last_recv(self) -> float:
        if self._comm_obj is None:
            return 0.
        return self._comm_obj.time_after_last_recv()

    # Callbacks
    def onConnect(self, success: bool):
        if success:
            self.sig_connected.emit()
        else:
            self.sig_disconnected.emit()

    def onDisconnect(self):
        self.sig_disconnected.emit()

    def onSendData(self, data: bytes):
        self.sig_send_data.emit(data)

    def onRecvData(self, data: bytes):
        self.sig_recv_data.emit(data)

    def onException(self, msg: str):
        self.sig_exception.emit(msg)

    @property
    def name(self) -> str:
        return self._name
