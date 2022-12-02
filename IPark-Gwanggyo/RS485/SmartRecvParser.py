from PacketParser import *
from Define import Callback
from RS485Comm import *


class SmartRecvParser(PacketParser):
    year: int = 0
    month: int = 0
    day: int = 0
    hour: int = 0
    minute: int = 0
    second: int = 0

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
                    if len(chunk) >= 11:
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

                        self.interpretPacket(chunk)
                        self.buffer = self.buffer[packetLen:]
        except Exception as e:
            writeLog('handlePacket Exception::{}'.format(e), self)

    def setFlagCallUp(self):
        self.flag_send_up_packet = True

    def setFlagCallDown(self):
        self.flag_send_down_packet = True

    def interpretPacket(self, packet: bytearray):
        try:
            if len(packet) < 4:
                return
            header = packet[1]  # [0xC1]
            packetLen = packet[2]
            cmd = packet[3]
            if header == 0xC1 and packetLen == 0x13 and cmd == 0x13:
                if len(packet) >= 13:
                    state = packet[11]
                    # 0xFF : unknown, 최상위 비트가 1이면 지하
                    if packet[12] == 0xFF:
                        current_floor = 'unknown'
                    elif packet[12] & 0x80:
                        current_floor = f'B{packet[12] & 0x7F}'
                    else:
                        current_floor = f'{packet[12] & 0xFF}'
                    result = {
                        'device': 'elevator',
                        'state': state,
                        'current_floor': current_floor
                    }
                    self.sig_parse_result.emit(result)
            
            # packet log
            self.sig_raw_packet.emit(packet)
        except Exception as e:
            writeLog('interpretPacket Exception::{}'.format(e), self)