import os
import pickle
from Parser import Parser
from SerialComm import SerialComm
from typing import List


class SmartSendParser(Parser):
    timestamp: int = 0
    elevator_up_packets: List[str]
    elevator_down_packets: List[str]

    def __init__(self, ser: SerialComm):
        super().__init__(ser)
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

                    self.sig_parse.emit(chunk)
                    self.buffer = self.buffer[packetLen:]
                    # TODO: bypass here
        except Exception:
            pass

    def sendCallElevatorPacket(self, updown: int, timestamp: int):
        # updown 0 = down, 1 = up
        if updown:
            packet = self.elevator_up_packets[timestamp]
        else:
            packet = self.elevator_down_packets[timestamp]
        self.sendPacketString(packet)
