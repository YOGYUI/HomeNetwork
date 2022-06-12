from abc import abstractmethod, ABCMeta
from typing import Union
from SerialComm import SerialComm
from Define import Callback, writeLog


class SerialParser:
    __metaclass__ = ABCMeta

    buffer: bytearray
    enable_console_log: bool = False
    chunk_cnt: int = 0
    max_chunk_cnt: int = 1e6
    max_buffer_size: int = 200

    def __init__(self, ser: SerialComm):
        self.buffer = bytearray()
        self.sig_parse = Callback(bytearray)
        ser.sig_send_data.connect(self.onSendData)
        ser.sig_recv_data.connect(self.onRecvData)
        self.serial = ser

    def release(self):
        self.buffer.clear()

    def sendPacket(self, packet: Union[bytes, bytearray]):
        self.serial.sendData(packet)

    def sendString(self, packet_str: str):
        self.serial.sendData(bytearray([int(x, 16) for x in packet_str.split(' ')]))

    def onSendData(self, data: bytes):
        msg = ' '.join(['%02X' % x for x in data])
        writeLog("Send >> {}".format(msg), self)

    def onRecvData(self, data: bytes):
        if len(self.buffer) > self.max_buffer_size:
            self.buffer.clear()
        self.buffer.extend(data)
        self.handlePacket()

    @abstractmethod
    def handlePacket(self):
        pass
    
    def startRecv(self, count: int = 64):
        self.buffer.clear()
        self.chunk_cnt = 0
        self.enable_console_log = True
        while self.chunk_cnt < count:
            pass
        self.enable_console_log = False
