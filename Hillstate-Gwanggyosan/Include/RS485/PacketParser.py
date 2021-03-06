from abc import abstractmethod, ABCMeta
from typing import Union, List
from functools import reduce
from RS485Comm import *


class PacketParser:
    __metaclass__ = ABCMeta

    rs485: RS485Comm
    buffer: bytearray
    enable_console_log: bool = False
    chunk_cnt: int = 0
    max_chunk_cnt: int = 1e6
    max_buffer_size: int = 200
    line_busy: bool = False

    def __init__(self, rs485: RS485Comm):
        self.buffer = bytearray()
        self.sig_parse_result = Callback(dict)
        rs485.sig_send_data.connect(self.onSendData)
        rs485.sig_recv_data.connect(self.onRecvData)
        self.rs485 = rs485

    def release(self):
        self.buffer.clear()

    def sendPacket(self, packet: Union[bytes, bytearray]):
        self.rs485.sendData(packet)

    def sendString(self, packet_str: str):
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

    def handlePacket(self):
        idx = self.buffer.find(0xF7)
        if idx > 0:
            self.buffer = self.buffer[idx:]
        if len(self.buffer) >= 3:
            packet_length = self.buffer[1]
            if len(self.buffer) >= packet_length:
                if self.buffer[0] == 0xF7 and self.buffer[packet_length - 1] == 0xEE:
                    self.line_busy = False
                    packet = self.buffer[:packet_length]
                    try:
                        checksum_calc = self.calcXORChecksum(packet[:-2])
                        checksum_recv = packet[-2]
                        if checksum_calc == checksum_recv:
                            self.interpretPacket(packet)
                        else:
                            writeLog('Checksum Error (calc={}, recv={}) ({})'.format(
                                checksum_calc, checksum_recv, self.prettifyPacket(packet)), self)
                        self.buffer = self.buffer[packet_length:]
                    except IndexError:
                        writeLog('Index Error (buffer={}, packet_len={}, packet={})'.format(
                            self.prettifyPacket(self.buffer), packet_length, self.prettifyPacket(packet)), self)
    
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

    def isRS485LineBusy(self) -> bool:
        if self.rs485.getType() == RS485HwType.Socket:
            return False  # ?????? ?????? ????????????????????? ?????? ????????? IDLE?????? ????????? ????????? ??? ??????
        return self.line_busy

    def getRS485HwType(self) -> RS485HwType:
        return self.rs485.getType()

    @staticmethod
    def prettifyPacket(packet: bytearray) -> str:
        return ' '.join(['%02X' % x for x in packet])
    
    @staticmethod
    def calcXORChecksum(data: Union[bytearray, bytes, List[int]]) -> int:
        return reduce(lambda x, y: x ^ y, data, 0)
