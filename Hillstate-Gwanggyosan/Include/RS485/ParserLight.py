from PacketParser import *


class ParserLight(PacketParser):
    def interpretPacket(self, packet: bytearray):
        try:
            if packet[3] == 0x19:  # 조명
                self.handleLight(packet)
            elif packet[3] == 0x1F:  # 아울렛 (콘센트)
                self.handleOutlet(packet)
            else:
                writeLog(f'Unknown packet: {self.prettifyPacket(packet)}', self)
            """
            elif packet[3] == 0x1E:  # 현관 도어락 (?)
                writeLog(f'Doorlock Packet: {self.prettifyPacket(packet)}', self)
            """
        except Exception as e:
            writeLog('interpretPacket::Exception::{} ({})'.format(e, packet), self)

    def handleLight(self, packet: bytearray):
        room_idx = packet[6] >> 4
        if packet[4] == 0x01:  # 상태 쿼리
            pass
        elif packet[4] == 0x02:  # 상태 변경 명령
            pass
        elif packet[4] == 0x04:  # 각 방별 On/Off
            dev_idx = packet[6] & 0x0F
            if dev_idx == 0:  # 일반 쿼리 (존재하는 모든 디바이스)
                light_count = len(packet) - 10
                for idx in range(light_count):
                    state = 0 if packet[8 + idx] == 0x02 else 1
                    result = {
                        'device': 'light', 
                        'index': idx,
                        'room_index': room_idx,
                        'state': state
                    }
                    self.sig_parse_result.emit(result)
            else:  # 상태 변경 명령 직후 응답
                state = 0 if packet[8] == 0x02 else 1
                result = {
                    'device': 'light', 
                    'index': dev_idx - 1,
                    'room_index': room_idx,
                    'state': state
                }
                self.sig_parse_result.emit(result)

    def handleOutlet(self, packet: bytearray):
        room_idx = packet[6] >> 4
        if packet[4] == 0x01:  # 상태 쿼리
            pass
        elif packet[4] == 0x02:  # 상태 변경 명령
            pass
        elif packet[4] == 0x04:  # 각 방별 상태 (On/Off)
            dev_idx = packet[6] & 0x0F
            if dev_idx == 0:  # 일반 쿼리 (모든 디바이스)
                outlet_count = (len(packet) - 10) // 9
                for idx in range(outlet_count):
                    # XX YY -- -- -- -- -- -- ZZ
                    # XX: 상위 4비트 = 공간 인덱스, 하위 4비트는 디바이스 인덱스
                    # YY: 02 = OFF, 01 = ON
                    # ZZ: 02 = 대기전력 차단 수동, 01 = 대기전력 차단 자동
                    # 중간에 있는 패킷들은 전력량계 데이터같은데, 파싱 위한 레퍼런스가 없음
                    dev_packet = packet[8 + idx * 9: 8 + (idx + 1) * 9]
                    state = 0 if dev_packet[1] == 0x02 else 1
                    result = {
                        'device': 'outlet',
                        'index': idx,
                        'room_index': room_idx,
                        'state': state
                    }
                    self.sig_parse_result.emit(result)
            else:  # 상태 변경 명령 직후 응답
                state = 0 if packet[8] == 0x02 else 1
                result = {
                    'device': 'outlet',
                    'index': dev_idx - 1,
                    'room_index': room_idx,
                    'state': state
                }
                self.sig_parse_result.emit(result)
