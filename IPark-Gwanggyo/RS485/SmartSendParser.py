# import os
# import pickle
# from typing import List
import time
from PacketParser import *
from RS485Comm import *
from functools import reduce


class SmartSendParser(PacketParser):
    """
    elevator_up_packets: List[str]
    elevator_down_packets: List[str]
    """
    elevator_call_count: int = 1
    elevator_call_interval: int = 0  # 엘리베이터 호출 반복 호출 사이 딜레이 (단위: ms)
    is_calling_elevator: bool = False

    def __init__(self, rs485: RS485Comm, elevator_call_count: int = 1):
        super().__init__(rs485)
        # packets in here
        """
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
        """
        self.elevator_call_count = max(1, elevator_call_count)

    def handlePacket(self):
        try:
            idx = self.buffer.find(0x2)
            if idx > 0:
                self.buffer = self.buffer[idx:]

            if len(self.buffer) >= 3:
                packetLen = self.buffer[2]
                if len(self.buffer) >= 5:
                    self.timestamp = self.buffer[4]
                if len(self.buffer) >= packetLen:
                    chunk = self.buffer[:packetLen]

                    if self.enable_console_log:
                        msg = ' '.join(['%02X' % x for x in chunk])
                        print('[SER 2] ' + msg)

                    self.interpretPacket(chunk)
                    self.buffer = self.buffer[packetLen:]
                    # TODO: bypass here
        except Exception as e:
            writeLog('handlePacket Exception::{}'.format(e), self)

    def setElevatorCallCount(self, count: int):
        self.elevator_call_count = max(1, count)

    def setElevatorCallInterval(self, interval: int):
        self.elevator_call_interval = interval

    def sendCallElevatorPacket(self, updown: int, timestamp: int):
        # updown 0 = down, 1 = up
        if self.is_calling_elevator:
            return
        self.is_calling_elevator = True
        for i in range(self.elevator_call_count):
            """
            temp = (timestamp + i) % 256
            if updown:
                packet = self.elevator_up_packets[temp]
            else:
                packet = self.elevator_down_packets[temp]
            self.sendPacketString(packet)
            """
            if updown:
                packet = self.make_packet_call_up((timestamp + i) % 256)
            else:
                packet = self.make_packet_call_down((timestamp + i) % 256)
            self.sendPacket(packet)
            if self.elevator_call_interval > 0:
                time.sleep(self.elevator_call_interval / 1000)

        self.is_calling_elevator = False

    def interpretPacket(self, packet: bytearray):
        # packet log
        # self.sig_raw_packet.emit(packet)
        pass

    def make_packet_call_down(self, timestamp: int) -> bytearray:
        packet = bytearray([0x02, 0xC1, 0x0C, 0x91, timestamp, 0x10, 0x01, 0x00, 0x02, 0x01, 0x02])
        packet.append(self.calculate_bestin_checksum(packet))
        return packet

    def make_packet_call_up(self, timestamp: int) -> bytearray:
        packet = bytearray([0x02, 0xC1, 0x0C, 0x91, timestamp, 0x20, 0x01, 0x00, 0x02, 0x01, 0x02])
        packet.append(self.calculate_bestin_checksum(packet))
        return packet

    @staticmethod
    def calculate_bestin_checksum(packet: bytearray) -> int:
        try:
            return reduce(lambda x, y: ((x ^ y) + 1) & 0xFF, packet, 3)
        except Exception as e:
            writeLog(f'Calc Bestin Checksum Error ({e})')
            return 0