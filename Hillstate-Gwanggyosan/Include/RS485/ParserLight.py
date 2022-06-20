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
                    # self.sig_parse.emit(packet)
                    self.buffer = self.buffer[packet_length:]
    
    def interpretPacket(self, packet: bytearray):
        try:
            if packet[2:4] == bytearray([0x01, 0x19]):
                room_idx = packet[6] >> 4
                if packet[4] == 0x01:  # 조명 상태 쿼리
                    pass
                elif packet[4] == 0x02:  # 조명 상태 변경 명령
                    pass
                elif packet[4] == 0x04:  # 각 방별 조명 On/Off 상태
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
            elif packet[2:4] == bytearray([0x01, 0x1F]):
                room_idx = packet[6] >> 4
                if packet[4] == 0x01:
                    pass
                elif packet[4] == 0x02:
                    pass
                elif packet[4] == 0x04:
                    pass
        except Exception as e:
            writeLog('interpretPacket::Exception::{} ({})'.format(e, packet), self)
