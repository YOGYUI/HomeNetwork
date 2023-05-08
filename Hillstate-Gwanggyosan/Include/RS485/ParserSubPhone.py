import os
import sys
from PacketParser import *
import datetime
CURPATH = os.path.dirname(os.path.abspath(__file__))  # Project/Include/RS485
INCPATH = os.path.dirname(CURPATH)  # Project/Include/
sys.path.extend([CURPATH, INCPATH])
sys.path = list(set(sys.path))
del CURPATH, INCPATH
from Define import *


class ParserSubPhone(PacketParser):
    enable_store_packets: bool = False

    def handlePacket(self):
        # 3840 baudrate
        # packet format: 7F XX XX XX EE
        idx = self.buffer.find(0x7F)
        if idx > 0:
            self.buffer = self.buffer[idx:]
        if len(self.buffer) >= 2:
            idx2 = self.buffer.find(0xEE)
            if idx2 > 0:
                self.line_busy = False
                packet = self.buffer[:idx2 + 1]
                self.interpretPacket(packet)
                self.buffer = self.buffer[idx2 + 1:]
        elif len(self.buffer) == 1 and self.buffer[0] == 0xEE:
            self.line_busy = False
            self.buffer.clear()

    def interpretPacket(self, packet: bytearray):
        try:
            store: bool = self.enable_store_packets
            packet_info = {'packet': packet, 'timestamp': datetime.datetime.now()}
            if (packet[1] & 0xF0) == 0xB0:  # 현관 도어폰 호출
                self.handleFrontDoor(packet)
            elif (packet[1] & 0xF0) == 0x50:  # 공동 현관문 호출
                self.handleCommunalDoor(packet)
            elif (packet[1] & 0xF0) == 0xE0:
                self.handleHEMS(packet)
            else:
                writeLog(f'{self.prettifyPacket(packet)} >> ???', self)
            
            if store:
                if len(self.packet_storage) > self.max_packet_store_cnt:
                    self.packet_storage.pop(0)
                self.packet_storage.append(packet_info)
        except Exception as e:
            writeLog('interpretPacket::Exception::{} ({})'.format(e, packet), self)

    def handleFrontDoor(self, packet: bytearray):
        result = {'device': DeviceType.SUBPHONE}
        notify: bool = True
        if packet[1] == 0xB5:
            # 현관 도어폰 초인종 호출 (월패드 -> 서브폰)
            result['ringing_front'] = 1
            writeLog(f'{self.prettifyPacket(packet)} >> Front door ringing started', self)
        elif packet[1] == 0xB6:
            # 현관 도어폰 초인종 호출 종료 (월패드 -> 서브폰)
            result['ringing_front'] = 0
            writeLog(f'{self.prettifyPacket(packet)} >> Front door ringing terminated', self)
        elif packet[1] == 0xB9:
            # 서브폰에서 현관 통화 시작 (서브폰 -> 월패드)
            result['streaming'] = 1
            writeLog(f'{self.prettifyPacket(packet)} >> Streaming (front door) started from Subphone', self)
        elif packet[1] == 0xBA:
            # 서브폰에서 현관 통화 종료 (서브폰 -> 월패드)
            result['streaming'] = 0
            writeLog(f'{self.prettifyPacket(packet)} >> Streaming (front door) terminated from Subphone', self)
        elif packet[1] == 0xB4:
            # 서브폰에서 현관문 열림 명령 (서브폰 -> 월패드)
            result['doorlock'] = 0  # Unsecured
            writeLog(f'{self.prettifyPacket(packet)} >> Open front door from Subphone', self)
        elif packet[1] in [0xBB, 0xB8]:
            # 현관 도어폰 통화 종료
            result['ringing_front'] = 0
            result['streaming'] = 0
            result['doorlock'] = 1  # Secured
            writeLog(f'{self.prettifyPacket(packet)} >> Streaming finished', self)
        else:
            notify = False
            writeLog(f'{self.prettifyPacket(packet)} >> ???', self)
        if notify:
            self.sig_parse_result.emit(result)

    def handleCommunalDoor(self, packet: bytearray):
        result = {'device': DeviceType.SUBPHONE}
        notify: bool = True
        if packet[1] == 0x5A:
            # 공동현관문 호출 (월패드 -> 서브폰)
            result['ringing_communal'] = 1
            writeLog(f'{self.prettifyPacket(packet)} >> Communal door ringing started', self)
        elif packet[1] == 0x5C:
            # 공동현관문 호출 종료 (월패드 -> 서브폰)
            result['ringing_communal'] = 0
            writeLog(f'{self.prettifyPacket(packet)} >> Communal door ringing terminated', self)
        elif packet[1] == 0x5E:
            # 공동현관문 통화 종료
            result['ringing_communal'] = 0
            result['streaming'] = 0
            result['doorlock'] = 1  # Secured
            writeLog(f'{self.prettifyPacket(packet)} >> Streaming finished', self)
        else:
            notify = False
            writeLog(f'{self.prettifyPacket(packet)} >> ???', self)
        if notify:
            self.sig_parse_result.emit(result)

    def handleHEMS(self, packet: bytearray):
        packet_type = packet[1] & 0x0F
        if packet_type == 0x00:
            # 쿼리 패킷 (서브폰 -> 월패드)
            pass
        elif packet_type == 0x01:
            result = {'device': DeviceType.HEMS, 'packet': packet}
            notify: bool = True
            # 응답 패킷 (월패드 -> 서브폰)
            devtype = HEMSDevType((packet[2] & 0xF0) >> 4)
            category = HEMSCategory(packet[2] & 0x0F)
            if category.value in [1, 2, 3, 4]:
                # 7F E1 XY 09 P1 P2 P3 Q1 Q2 Q3 R1 R2 R3 ZZ EE
                # X: 디바이스 타입
                # Y: 쿼리 타입
                # P1 P2 P3 : 당월 이력 값
                # Q1 Q2 Q3 : 전월 이력 값
                # R1 R2 R3 : 전전월 이력 값
                # ZZ : XOR Checksum
                v1 = int.from_bytes(packet[4:7], byteorder='big', signed=False)
                v2 = int.from_bytes(packet[7:10], byteorder='big', signed=False)
                v3 = int.from_bytes(packet[10:13], byteorder='big', signed=False)
                result[f'{devtype.name.lower()}_{category.name.lower()}_cur_month'] = v1
                result[f'{devtype.name.lower()}_{category.name.lower()}_1m_ago'] = v2
                result[f'{devtype.name.lower()}_{category.name.lower()}_2m_ago'] = v3
            elif category.value in [5, 7]:
                # 7F E1 XY 03 P1 P2 P3 ZZ EE
                # X: 디바이스 타입
                # Y: 쿼리 타입
                # P1~P3: 값
                # ZZ : XOR Checksum
                v = int.from_bytes(packet[4:7], byteorder='big', signed=False)
                result[f'{devtype.name.lower()}_{category.name.lower()}'] = v
            else:
                notify = False
                writeLog(f'{self.prettifyPacket(packet)} >> ???', self)
            if notify:
                self.sig_parse_result.emit(result)
        else:
            writeLog(f'{self.prettifyPacket(packet)} >> ???', self)
