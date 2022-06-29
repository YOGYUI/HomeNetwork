from PacketParser import PacketParser
from Define import Callback
from RS485Comm import *


class SmartRecvParser(PacketParser):
    year: int = 0
    month: int = 0
    day: int = 0
    hour: int = 0
    minute: int = 0
    second: int = 0
    timestamp: int = 0

    flag_moving: bool = False
    flag_send_up_packet: bool = False
    flag_send_down_packet: bool = False

    def __init__(self, rs485: RS485Comm):
        super().__init__(rs485)
        self.sig_call_elevator = Callback(int, int)  # up(1)/down(0) flag, timestamp

    def handlePacket(self):
        try:
            idx = self.buffer.find(0x2)
            if idx > 0:
                self.buffer = self.buffer[idx:]

            if len(self.buffer) >= 3:
                packetLen = self.buffer[2]
                if len(self.buffer) >= 5:
                    self.timestamp = self.buffer[4]
                if len(self.buffer) >= 12:
                    self.flag_moving = bool(self.buffer[11])
                    if self.flag_moving:  # 0 = stopped, 1 = moving, 4 = arrived
                        self.flag_send_up_packet = False
                        self.flag_send_down_packet = False
                if len(self.buffer) >= packetLen:
                    chunk = self.buffer[:packetLen]
                    if chunk[3] == 0x11:
                        if self.flag_send_up_packet:
                            self.sig_call_elevator.emit(1, self.timestamp)
                        if self.flag_send_down_packet:
                            self.sig_call_elevator.emit(0, self.timestamp)

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

                    self.sig_parse.emit(chunk)
                    self.buffer = self.buffer[packetLen:]
        except Exception:
            pass

    def setFlagCallUp(self):
        self.flag_send_up_packet = True

    def setFlagCallDown(self):
        self.flag_send_down_packet = True
