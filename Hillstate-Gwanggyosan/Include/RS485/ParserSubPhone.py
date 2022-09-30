from PacketParser import *


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

    def interpretPacket(self, packet: bytearray):
        try:
            store: bool = self.enable_store_packets
            packet_info = {'packet': packet, 'timestamp': datetime.datetime.now()}
            result = {'device': 'subphone'}
            if packet[1] == 0xB5:
                # 현관 도어폰 초인종 호출 (월패드 -> 서브폰)
                result['call_front'] = 1
                writeLog(f'{self.prettifyPacket(packet)} >> Front door call started', self)
            elif packet[1] == 0xB6:
                # 현관 도어폰 초인종 호출 종료 (월패드 -> 서브폰)
                result['call_front'] = 0
                writeLog(f'{self.prettifyPacket(packet)} >> Front door call terminated', self)
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
            elif packet[1] in [0xBA, 0xBB]:
                # 현관 도어폰 통화 종료?
                result['call_front'] = 0
                result['call_communal'] = 0
                result['streaming'] = 0
                result['doorlock'] = 1  # Secured
                writeLog(f'{self.prettifyPacket(packet)} >> Streaming finished', self)
            elif packet[1] == 0x5A:
                # 공동현관문 호출 (월패드 -> 서브폰)
                result['call_communal'] = 1
                writeLog(f'{self.prettifyPacket(packet)} >> Communal door call started', self)
            elif packet[1] == 0x5C:
                # 공동현관문 호출 종료 (월패드 -> 서브폰)
                result['call_communal'] = 0
                writeLog(f'{self.prettifyPacket(packet)} >> Communal door call terminated', self)
            else:
                writeLog(f'{self.prettifyPacket(packet)} >> ???', self)
            self.sig_parse_result.emit(result)

            if store:
                if len(self.packet_storage) > self.max_packet_store_cnt:
                    self.packet_storage.pop(0)
                self.packet_storage.append(packet_info)
        except Exception as e:
            writeLog('interpretPacket::Exception::{} ({})'.format(e, packet), self)
