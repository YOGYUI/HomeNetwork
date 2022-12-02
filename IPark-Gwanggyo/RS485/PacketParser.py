from abc import abstractmethod, ABCMeta
from Define import Callback, writeLog
from RS485Comm import *


class PacketParser:
    __metaclass__ = ABCMeta

    buffer: bytearray
    enable_console_log: bool = False
    chunk_cnt: int = 0
    max_chunk_cnt: int = 1e6
    max_buffer_size: int = 200
    line_busy: bool = False
    timestamp: int = 0

    def __init__(self, rs485: RS485Comm):
        self.buffer = bytearray()
        self.sig_parse_result = Callback(dict)
        self.sig_raw_packet = Callback(bytearray)
        rs485.sig_send_data.connect(self.onSendData)
        rs485.sig_recv_data.connect(self.onRecvData)
        self.rs485 = rs485

    def release(self):
        self.buffer.clear()

    def sendPacket(self, packet: bytearray):
        self.rs485.sendData(packet)

    def sendPacketString(self, packet_str: str):
        self.rs485.sendData(bytearray([int(x, 16) for x in packet_str.split(' ')]))

    def onSendData(self, data: bytes):
        msg = ' '.join(['%02X' % x for x in data])
        writeLog("Send >> {}".format(msg), self)

    def onRecvData(self, data: bytes):
        self.line_busy = True
        if len(self.buffer) > self.max_buffer_size:
            self.buffer.clear()
        self.buffer.extend(data)
        self.handlePacket()
        self.line_busy = False

    @abstractmethod
    def handlePacket(self):
        pass
    
    @abstractmethod
    def interpretPacket(self, packet: bytearray):
        pass

    def startRecv(self, count: int = 64):
        self.buffer.clear()
        self.chunk_cnt = 0
        self.enable_console_log = True
        while self.chunk_cnt < count:
            pass
        self.enable_console_log = False
    
    def getRS485HwType(self) -> RS485HwType:
        return self.rs485.getType()

    def isRS485LineBusy(self) -> bool:
        if self.rs485.getType() == RS485HwType.Socket:
            return False  # 무선 송신 레이턴시때문에 언제 라인이 IDLE인지 정확히 파악할 수 없다
        return self.line_busy

    def get_packet_timestamp(self) -> int:
        return self.timestamp

    @staticmethod
    def prettifyPacket(packet: bytearray) -> str:
        return ' '.join(['%02X' % x for x in packet])
