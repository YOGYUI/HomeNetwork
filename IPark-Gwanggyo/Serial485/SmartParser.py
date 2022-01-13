import os
import pickle
from typing import List
from SerialComm import SerialComm
from Define import Callback, writeLog


class SmartParser:
    buffer1: bytearray
    buffer2: bytearray
    timestamp1: int = 0
    timestamp2: int = 0
    enable_console_log: bool = False
    max_buffer_size: int = 200

    flag_moving: bool = False
    elevator_up_packets: List[str]
    flag_send_up_packet: bool = False
    elevator_down_packets: List[str]
    flag_send_down_packet: bool = False

    year: int = 0
    month: int = 0
    day: int = 0
    hour: int = 0
    minute: int = 0
    second: int = 0

    def __init__(self, ser1: SerialComm, ser2: SerialComm):
        super().__init__()
        self.buffer1 = bytearray()
        self.buffer2 = bytearray()
        self.sig_parse1 = Callback(bytearray)
        self.sig_parse2 = Callback(bytearray)
        ser1.sig_send_data.connect(self.onSendData1)
        ser1.sig_recv_data.connect(self.onRecvData1)
        ser2.sig_send_data.connect(self.onSendData2)
        ser2.sig_recv_data.connect(self.onRecvData2)
        self.serial2 = ser2

        # packets in here
        curpath = os.path.dirname(os.path.abspath(__file__))
        picklepath = os.path.join(curpath, 'smart_elevator_up_packets.pkl')
        if os.path.isfile(picklepath):
            with open(picklepath, 'rb') as fp:
                temp = pickle.load(fp)
                temp.sort(key=lambda x: x[4])
                self.elevator_up_packets = [' '.join(['%02X' % x for x in e]) for e in temp]
        else:
            self.elevator_up_packets = [''] * 256
        picklepath = os.path.join(curpath, 'smart_elevator_down_packets.pkl')
        if os.path.isfile(picklepath):
            with open(picklepath, 'rb') as fp:
                temp = pickle.load(fp)
                temp.sort(key=lambda x: x[4])
                self.elevator_down_packets = [' '.join(['%02X' % x for x in e]) for e in temp]
        else:
            self.elevator_down_packets = [''] * 256

    def release(self):
        self.buffer1.clear()
        self.buffer2.clear()

    def onSendData1(self, data: bytes):
        msg = ' '.join(['%02X' % x for x in data])
        writeLog("Send(1) >> {}".format(msg), self)

    def onRecvData1(self, data: bytes):
        if len(self.buffer1) > self.max_buffer_size:
            self.buffer1.clear()
        self.buffer1.extend(data)
        self.handlePacket1()

    def onSendData2(self, data: bytes):
        msg = ' '.join(['%02X' % x for x in data])
        writeLog("Send(2) >> {}".format(msg), self)

    def onRecvData2(self, data: bytes):
        if len(self.buffer2) > self.max_buffer_size:
            self.buffer2.clear()
        self.buffer2.extend(data)
        self.handlePacket2()

    def handlePacket1(self):
        try:
            idx = self.buffer1.find(0x2)
            if idx > 0:
                self.buffer1 = self.buffer1[idx:]

            if len(self.buffer1) >= 3:
                packetLen = self.buffer1[2]
                if len(self.buffer1) >= 5:
                    self.timestamp1 = self.buffer1[4]
                if len(self.buffer1) >= 12:
                    self.flag_moving = bool(self.buffer1[11])
                    if self.flag_moving:  # 0 = stopped, 1 = moving, 4 = arrived
                        self.flag_send_up_packet = False
                        self.flag_send_down_packet = False
                if len(self.buffer1) >= packetLen:
                    chunk = self.buffer1[:packetLen]
                    if chunk[3] == 0x11:
                        if self.flag_send_up_packet:
                            packet = self.elevator_up_packets[self.timestamp1]
                            self.serial2.sendData(bytearray([int(x, 16) for x in packet.split(' ')]))
                        if self.flag_send_down_packet:
                            packet = self.elevator_down_packets[self.timestamp1]
                            self.serial2.sendData(bytearray([int(x, 16) for x in packet.split(' ')]))
                    if chunk[1] == 0xC1 and chunk[3] == 0x13:
                        self.year = chunk[5]
                        self.month = chunk[6]
                        self.day = chunk[7]
                        self.hour = chunk[8]
                        self.minute = chunk[9]
                        self.second = chunk[10]
                    if self.enable_console_log:
                        msg = ' '.join(['%02X' % x for x in chunk])
                        print('[SER 1] ' + msg)
                    self.sig_parse1.emit(chunk)
                    self.buffer1 = self.buffer1[packetLen:]
        except Exception:
            pass
    
    def handlePacket2(self):
        try:
            idx = self.buffer2.find(0x2)
            if idx > 0:
                self.buffer2 = self.buffer2[idx:]

            if len(self.buffer2) >= 3:
                packetLen = self.buffer2[2]
                if len(self.buffer2) >= 5:
                    self.timestamp2 = self.buffer2[4]
                if len(self.buffer2) >= packetLen:
                    chunk = self.buffer2[:packetLen]
                    if self.enable_console_log:
                        msg = ' '.join(['%02X' % x for x in chunk])
                        print('[SER 2] ' + msg)
                    self.sig_parse2.emit(chunk)
                    self.buffer2 = self.buffer2[packetLen:]
                    # TODO: bypass here
        except Exception:
            pass


if __name__ == '__main__':
    ser1_ = SerialComm()
    ser2_ = SerialComm()
    par = SmartParser(ser1_, ser2_)
    par.enable_console_log = True

    ser1_.connect('/dev/rs485_smart1', 9600)
    ser2_.connect('/dev/rs485_smart2', 9600)

    while True:
        pass
