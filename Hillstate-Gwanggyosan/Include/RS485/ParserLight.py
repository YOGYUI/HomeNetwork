from SerialParser import *


class ParserLight(SerialParser):
    def handlePacket(self):
        idx = self.buffer.find(0xF7)
        if idx > 0:
            self.buffer = self.buffer[idx:]
        if len(self.buffer) >= 3:
            packet_length = self.buffer[1]
            if len(self.buffer) >= packet_length:
                if self.buffer[packet_length - 1] == 0xEE:
                    packet = self.buffer[:packet_length]
                    self.interpretPacket(packet)
                    self.buffer = self.buffer[packet_length:]
    
    def interpretPacket(self, packet: bytearray):
        try:
            if packet[2:4] == bytearray([0x01, 0x19]):  # 조명
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
                            self.sig_parse_result.emit({
                                'device': 'light', 
                                'index': idx,
                                'room_index': room_idx,
                                'state': state
                            })
                    else:  # 상태 변경 명령 직후 응답
                        state = 0 if packet[8] == 0x02 else 1
                        self.sig_parse_result.emit({
                            'device': 'light', 
                            'index': dev_idx - 1,
                            'room_index': room_idx,
                            'state': state
                        })
            elif packet[2:4] == bytearray([0x01, 0x1F]):  # 아울렛 (콘센트)
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
                            self.sig_parse_result.emit({
                                'device': 'outlet',
                                'index': idx,
                                'room_index': room_idx,
                                'state': state
                            })
                    else:  # 상태 변경 명령 직후 응답
                        state = 0 if packet[8] == 0x02 else 1
                        self.sig_parse_result.emit({
                            'device': 'outlet',
                            'index': dev_idx - 1,
                            'room_index': room_idx,
                            'state': state
                        })
        except Exception as e:
            writeLog('interpretPacket::Exception::{} ({})'.format(e, packet), self)
